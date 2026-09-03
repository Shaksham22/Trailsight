"""Read-only DuckDB repository for deterministic Trailsight V2 investigations."""

from __future__ import annotations

import base64
import binascii
import math
import json
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import RLock
from typing import Any

import duckdb

from trailsight_v2.data.constants import FORBIDDEN_RUNTIME_COLUMN_NAMES
from trailsight_v2.domain.errors import (
    DataIntegrityError,
    InvalidInputError,
    NotFoundError,
    ResultTooLargeError,
)
from trailsight_v2.domain.models import Direction


REQUIRED_SCHEMA: dict[str, tuple[str, ...]] = {
    "source_manifest": (
        "source_dataset", "external_file_path", "raw_transaction_sha256", "row_count",
        "min_timestamp", "max_timestamp", "preparation_timestamp", "data_contract_version",
    ),
    "banks": (
        "bank_id", "mapping_version", "country_name", "iso_alpha2",
        "centroid_latitude", "centroid_longitude",
    ),
    "accounts": (
        "account_ref", "source_dataset", "bank_id", "account_id", "bank_country_code",
    ),
    "transactions": (
        "transaction_ref", "source_dataset", "source_row_ordinal", "transaction_timestamp",
        "from_bank_id", "from_account_id", "from_account_ref", "to_bank_id", "to_account_id",
        "to_account_ref", "amount_received", "receiving_currency", "amount_paid",
        "payment_currency", "payment_format", "cross_currency",
    ),
    "detector_edge_day_deltas": ("edge_day", "account_ref_a", "account_ref_b"),
    "detector_snapshots": (
        "snapshot_id", "source_dataset", "cutoff_timestamp", "algorithm_name", "algorithm_variant",
        "algorithm_version", "upstream_code_provenance", "identity_rule_version",
        "eligibility_rule_version", "community_algorithm", "community_resolution", "community_seed",
        "config_hash", "status", "started_at", "completed_at", "account_count",
        "eligible_account_count", "scored_account_count", "failure_message_safe",
    ),
    "account_detector_states": (
        "snapshot_id", "account_ref", "scoring_eligible", "network_pattern_score", "rank",
        "percentile", "network_review_band", "unscored_reason",
    ),
    "account_detector_support": (
        "snapshot_id", "account_ref", "first_order_neighbor_count", "second_order_neighbor_count",
        "community_id_or_stable_snapshot_local_index", "block_measure_1", "block_measure_2",
        "block_measure_3", "network_pattern_score",
    ),
    "transaction_review_states": (
        "transaction_ref", "snapshot_id", "detector_cutoff", "sender_band", "receiver_band",
        "aml_review_priority", "derivation_code", "derivation_text", "alert_involvement",
        "sender_related_alert_ref", "receiver_related_alert_ref",
    ),
    "network_alerts": (
        "alert_ref", "account_ref", "entry_snapshot_id", "entry_cutoff", "entry_score",
        "entry_rank", "entry_percentile", "reason_code", "created_state",
    ),
}

_FORBIDDEN_NORMALIZED = set(FORBIDDEN_RUNTIME_COLUMN_NAMES) | {
    "patterns", "laundering", "laundering_label", "ground_truth", "ground_truth_label"
}


def _normalize_column_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


class DuckDBInvestigationRepositoryV2:
    """Safe, read-only query boundary over the merged WP01+WP02 runtime database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        if not self.database_path.is_file():
            raise NotFoundError("Trailsight runtime database was not found")
        try:
            self._connection = duckdb.connect(str(self.database_path), read_only=True)
        except duckdb.Error as exc:
            raise DataIntegrityError("Trailsight runtime database could not be opened read-only") from exc
        self._lock = RLock()
        try:
            self.validate_schema()
        except Exception:
            self._connection.close()
            raise

    def __enter__(self) -> "DuckDBInvestigationRepositoryV2":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def validate_schema(self) -> None:
        try:
            rows = self._fetchall(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'main'
                ORDER BY table_name, ordinal_position
                """
            )
        except duckdb.Error as exc:
            raise DataIntegrityError() from exc
        actual: dict[str, set[str]] = {}
        for table_name, column_name in rows:
            table_name = str(table_name)
            column_name = str(column_name)
            actual.setdefault(table_name, set()).add(column_name)
            if _normalize_column_name(table_name) in _FORBIDDEN_NORMALIZED:
                raise DataIntegrityError("Ground-truth firewall violation in runtime schema")
            normalized = _normalize_column_name(column_name)
            if normalized in _FORBIDDEN_NORMALIZED:
                raise DataIntegrityError("Ground-truth firewall violation in runtime schema")
        missing_tables = sorted(set(REQUIRED_SCHEMA) - set(actual))
        if missing_tables:
            raise DataIntegrityError("Runtime schema is incomplete; required tables are missing")
        for table_name, required_columns in REQUIRED_SCHEMA.items():
            if not set(required_columns).issubset(actual[table_name]):
                raise DataIntegrityError(
                    f"Runtime schema is incomplete for required table {table_name}"
                )

    def execute_readonly_probe(self, statement: str) -> None:
        """Used only by tests to prove the underlying connection rejects writes."""
        with self._lock:
            self._connection.execute(statement)

    def get_account_row(self, account_ref: str) -> tuple[Any, ...]:
        row = self._fetchone(
            """
            SELECT a.account_ref, a.source_dataset, a.bank_id, a.account_id,
                   b.mapping_version, b.country_name, b.iso_alpha2,
                   b.centroid_latitude, b.centroid_longitude
            FROM accounts a JOIN banks b USING (bank_id)
            WHERE a.account_ref = ?
            """,
            [account_ref],
        )
        if row is None:
            raise NotFoundError("Account was not found")
        return row

    def get_transaction_row(self, transaction_ref: str) -> tuple[Any, ...]:
        row = self._fetchone(
            """
            SELECT t.transaction_ref, t.transaction_timestamp,
                   t.from_account_ref, t.from_bank_id, fa.account_id,
                   fb.mapping_version, fb.country_name, fb.iso_alpha2,
                   fb.centroid_latitude, fb.centroid_longitude,
                   t.to_account_ref, t.to_bank_id, ta.account_id,
                   tb.mapping_version, tb.country_name, tb.iso_alpha2,
                   tb.centroid_latitude, tb.centroid_longitude,
                   t.amount_paid, t.payment_currency, t.amount_received,
                   t.receiving_currency, t.payment_format, t.cross_currency,
                   t.source_dataset
            FROM transactions t
            JOIN accounts fa ON fa.account_ref = t.from_account_ref
            JOIN accounts ta ON ta.account_ref = t.to_account_ref
            JOIN banks fb ON fb.bank_id = t.from_bank_id
            JOIN banks tb ON tb.bank_id = t.to_bank_id
            WHERE t.transaction_ref = ?
            """,
            [transaction_ref],
        )
        if row is None:
            raise NotFoundError("Transaction was not found")
        return row

    def get_transaction_review_row(self, transaction_ref: str) -> tuple[Any, ...]:
        row = self._fetchone(
            """
            SELECT transaction_ref, snapshot_id, detector_cutoff, sender_band, receiver_band,
                   aml_review_priority, derivation_code, derivation_text, alert_involvement,
                   sender_related_alert_ref, receiver_related_alert_ref
            FROM transaction_review_states WHERE transaction_ref = ?
            """,
            [transaction_ref],
        )
        if row is None:
            raise DataIntegrityError("Transaction review state is missing")
        return row

    def get_alert_row(self, alert_ref: str) -> tuple[Any, ...]:
        row = self._fetchone(
            """
            SELECT alert_ref, account_ref, entry_snapshot_id, entry_cutoff, entry_score,
                   entry_rank, entry_percentile, reason_code, created_state
            FROM network_alerts WHERE alert_ref = ?
            """,
            [alert_ref],
        )
        if row is None:
            raise NotFoundError("Network Pattern Alert was not found")
        return row

    def get_snapshot_row(self, snapshot_id: str) -> tuple[Any, ...]:
        row = self._fetchone(
            """
            SELECT snapshot_id, source_dataset, cutoff_timestamp, algorithm_name, algorithm_variant,
                   algorithm_version, upstream_code_provenance, identity_rule_version,
                   eligibility_rule_version, community_algorithm, community_resolution,
                   community_seed, config_hash, status, account_count, eligible_account_count,
                   scored_account_count
            FROM detector_snapshots WHERE snapshot_id = ?
            """,
            [snapshot_id],
        )
        if row is None:
            raise NotFoundError("Detector snapshot was not found")
        return row

    def latest_complete_snapshot_row(self, at_or_before: datetime | None = None) -> tuple[Any, ...]:
        params: list[Any] = []
        where = "status = 'COMPLETE'"
        if at_or_before is not None:
            where += " AND cutoff_timestamp <= ?"
            params.append(at_or_before)
        row = self._fetchone(
            f"""
            SELECT snapshot_id, source_dataset, cutoff_timestamp, algorithm_name, algorithm_variant,
                   algorithm_version, upstream_code_provenance, identity_rule_version,
                   eligibility_rule_version, community_algorithm, community_resolution,
                   community_seed, config_hash, status, account_count, eligible_account_count,
                   scored_account_count
            FROM detector_snapshots
            WHERE {where}
            ORDER BY cutoff_timestamp DESC, snapshot_id DESC
            LIMIT 1
            """,
            params,
        )
        if row is None:
            raise DataIntegrityError("No COMPLETE detector snapshot is available for context")
        return row

    def get_account_detector_state_row(self, snapshot_id: str, account_ref: str) -> tuple[Any, ...]:
        row = self._fetchone(
            """
            SELECT snapshot_id, account_ref, scoring_eligible, network_pattern_score, rank,
                   percentile, network_review_band, unscored_reason
            FROM account_detector_states
            WHERE snapshot_id = ? AND account_ref = ?
            """,
            [snapshot_id, account_ref],
        )
        if row is None:
            raise DataIntegrityError("Account detector state is missing for resolved snapshot")
        return row

    def get_account_detector_support_row(
        self, snapshot_id: str, account_ref: str
    ) -> tuple[Any, ...] | None:
        return self._fetchone(
            """
            SELECT snapshot_id, account_ref, first_order_neighbor_count,
                   second_order_neighbor_count, community_id_or_stable_snapshot_local_index,
                   block_measure_1, block_measure_2, block_measure_3, network_pattern_score
            FROM account_detector_support
            WHERE snapshot_id = ? AND account_ref = ?
            """,
            [snapshot_id, account_ref],
        )

    def account_activity_row(self, account_ref: str, context_time: datetime) -> tuple[Any, ...]:
        return self._fetchone(
            """
            WITH prior AS (
                SELECT transaction_timestamp, from_account_ref, to_account_ref,
                       CASE
                         WHEN from_account_ref = ? AND to_account_ref <> ? THEN to_account_ref
                         WHEN to_account_ref = ? AND from_account_ref <> ? THEN from_account_ref
                         ELSE NULL
                       END AS counterparty_ref
                FROM transactions
                WHERE transaction_timestamp < ?
                  AND (from_account_ref = ? OR to_account_ref = ?)
            )
            SELECT
                SUM(CASE WHEN to_account_ref = ? THEN 1 ELSE 0 END)::BIGINT,
                SUM(CASE WHEN from_account_ref = ? THEN 1 ELSE 0 END)::BIGINT,
                COUNT(DISTINCT counterparty_ref)::BIGINT,
                COUNT(DISTINCT CASE WHEN to_account_ref = ? THEN counterparty_ref END)::BIGINT,
                COUNT(DISTINCT CASE WHEN from_account_ref = ? THEN counterparty_ref END)::BIGINT,
                MIN(transaction_timestamp), MAX(transaction_timestamp)
            FROM prior
            """,
            [
                account_ref, account_ref, account_ref, account_ref,
                context_time, account_ref, account_ref,
                account_ref, account_ref, account_ref, account_ref,
            ],
        ) or (0, 0, 0, 0, 0, None, None)

    def amount_history_stats(
        self,
        *,
        account_ref: str,
        context_time: datetime,
        side: str,
        currency: str,
        selected_amount: Decimal,
    ) -> tuple[int, Decimal | None, int]:
        if side == "SENDER_PAID":
            predicate = "from_account_ref = ? AND payment_currency = ?"
            amount_col = "amount_paid"
        elif side == "RECEIVER_RECEIVED":
            predicate = "to_account_ref = ? AND receiving_currency = ?"
            amount_col = "amount_received"
        else:
            raise InvalidInputError("Unknown amount side")
        row = self._fetchone(
            f"""
            SELECT COUNT(*)::BIGINT, MEDIAN({amount_col}),
                   SUM(CASE WHEN {amount_col} <= ? THEN 1 ELSE 0 END)::BIGINT
            FROM transactions
            WHERE {predicate} AND transaction_timestamp < ?
            """,
            [selected_amount, account_ref, currency, context_time],
        )
        if row is None:
            return (0, None, 0)
        return int(row[0] or 0), row[1], int(row[2] or 0)

    def support_refs_for_amount(
        self, *, account_ref: str, context_time: datetime, side: str, currency: str
    ) -> list[str]:
        if side == "SENDER_PAID":
            predicate = "from_account_ref = ? AND payment_currency = ?"
        elif side == "RECEIVER_RECEIVED":
            predicate = "to_account_ref = ? AND receiving_currency = ?"
        else:
            raise InvalidInputError("Unknown amount side")
        return [
            str(row[0])
            for row in self._fetchall(
                f"""
                SELECT transaction_ref
                FROM transactions
                WHERE {predicate} AND transaction_timestamp < ?
                ORDER BY transaction_timestamp DESC, transaction_ref ASC
                LIMIT 51
                """,
                [account_ref, currency, context_time],
            )
        ]

    def relationship_row(
        self, account_ref: str, counterparty_ref: str, context_time: datetime
    ) -> tuple[Any, ...]:
        return self._fetchone(
            """
            SELECT
              COUNT(*)::BIGINT,
              SUM(CASE WHEN from_account_ref = ? AND to_account_ref = ? THEN 1 ELSE 0 END)::BIGINT,
              SUM(CASE WHEN from_account_ref = ? AND to_account_ref = ? THEN 1 ELSE 0 END)::BIGINT,
              MIN(transaction_timestamp), MAX(transaction_timestamp)
            FROM transactions
            WHERE transaction_timestamp < ?
              AND ((from_account_ref = ? AND to_account_ref = ?)
                   OR (from_account_ref = ? AND to_account_ref = ?))
            """,
            [
                account_ref, counterparty_ref, counterparty_ref, account_ref, context_time,
                account_ref, counterparty_ref, counterparty_ref, account_ref,
            ],
        ) or (0, 0, 0, None, None)

    def velocity_row(
        self, account_ref: str, context_time: datetime, window: timedelta
    ) -> tuple[int, int, int]:
        start = context_time - window
        row = self._fetchone(
            """
            SELECT
              SUM(CASE WHEN to_account_ref = ? THEN 1 ELSE 0 END)::BIGINT,
              SUM(CASE WHEN from_account_ref = ? THEN 1 ELSE 0 END)::BIGINT,
              COUNT(*)::BIGINT
            FROM transactions
            WHERE transaction_timestamp >= ? AND transaction_timestamp < ?
              AND (from_account_ref = ? OR to_account_ref = ?)
            """,
            [account_ref, account_ref, start, context_time, account_ref, account_ref],
        )
        if row is None:
            return (0, 0, 0)
        return tuple(int(value or 0) for value in row)  # type: ignore[return-value]

    def fan_row(self, account_ref: str, context_time: datetime) -> tuple[int, int]:
        start = context_time - timedelta(hours=24)
        row = self._fetchone(
            """
            SELECT
              COUNT(DISTINCT CASE
                WHEN to_account_ref = ? AND from_account_ref <> ? THEN from_account_ref END)::BIGINT,
              COUNT(DISTINCT CASE
                WHEN from_account_ref = ? AND to_account_ref <> ? THEN to_account_ref END)::BIGINT
            FROM transactions
            WHERE transaction_timestamp >= ? AND transaction_timestamp < ?
              AND (from_account_ref = ? OR to_account_ref = ?)
            """,
            [account_ref, account_ref, account_ref, account_ref, start, context_time, account_ref, account_ref],
        )
        if row is None:
            return (0, 0)
        return int(row[0] or 0), int(row[1] or 0)

    def recent_alert_transaction_count(self, account_ref: str, entry_cutoff: datetime) -> int:
        start = entry_cutoff - timedelta(hours=24)
        row = self._fetchone(
            """
            SELECT COUNT(DISTINCT transaction_ref)::BIGINT
            FROM transactions
            WHERE transaction_timestamp >= ? AND transaction_timestamp < ?
              AND (from_account_ref = ? OR to_account_ref = ?)
            """,
            [start, entry_cutoff, account_ref, account_ref],
        )
        return int((row or (0,))[0] or 0)

    def support_refs_for_alert(self, account_ref: str, entry_cutoff: datetime) -> list[str]:
        start = entry_cutoff - timedelta(hours=24)
        return [
            str(row[0])
            for row in self._fetchall(
                """
                SELECT transaction_ref
                FROM transactions
                WHERE transaction_timestamp >= ? AND transaction_timestamp < ?
                  AND (from_account_ref = ? OR to_account_ref = ?)
                ORDER BY transaction_timestamp DESC, transaction_ref ASC
                LIMIT 51
                """,
                [start, entry_cutoff, account_ref, account_ref],
            )
        ]

    def network_counterparty_count(self, account_ref: str, context_time: datetime) -> int:
        row = self._fetchone(
            """
            SELECT COUNT(DISTINCT CASE
                     WHEN from_account_ref = ? THEN to_account_ref ELSE from_account_ref END)::BIGINT
            FROM transactions
            WHERE transaction_timestamp < ?
              AND (from_account_ref = ? OR to_account_ref = ?)
              AND from_account_ref <> to_account_ref
            """,
            [account_ref, context_time, account_ref, account_ref],
        )
        return int((row or (0,))[0] or 0)

    def network_rows(
        self,
        account_ref: str,
        context_time: datetime,
        *,
        limit: int,
        exclude_counterparty_ref: str | None = None,
    ) -> list[tuple[Any, ...]]:
        if not 0 <= limit <= 24:
            raise InvalidInputError("Network relationship query limit must be between 0 and 24")
        if limit == 0:
            return []
        exclusion = ""
        params: list[Any] = [
            account_ref, account_ref, account_ref, context_time, account_ref, account_ref
        ]
        if exclude_counterparty_ref is not None:
            exclusion = " AND CASE WHEN from_account_ref = ? THEN to_account_ref ELSE from_account_ref END <> ?"
            params.extend([account_ref, exclude_counterparty_ref])
        params.append(limit)
        return self._fetchall(
            f"""
            WITH directed AS (
              SELECT
                CASE WHEN from_account_ref = ? THEN to_account_ref ELSE from_account_ref END AS cp,
                CASE WHEN to_account_ref = ? THEN 1 ELSE 0 END AS incoming,
                CASE WHEN from_account_ref = ? THEN 1 ELSE 0 END AS outgoing,
                transaction_timestamp
              FROM transactions
              WHERE transaction_timestamp < ?
                AND (from_account_ref = ? OR to_account_ref = ?)
                AND from_account_ref <> to_account_ref
                {exclusion}
            ), aggregated AS (
              SELECT cp,
                     SUM(incoming)::BIGINT AS incoming_count,
                     SUM(outgoing)::BIGINT AS outgoing_count,
                     COUNT(*)::BIGINT AS total_count,
                     MIN(transaction_timestamp) AS first_timestamp,
                     MAX(transaction_timestamp) AS last_timestamp
              FROM directed
              GROUP BY cp
            )
            SELECT a.account_ref, a.source_dataset, a.bank_id, a.account_id,
                   b.mapping_version, b.country_name, b.iso_alpha2,
                   b.centroid_latitude, b.centroid_longitude,
                   ag.incoming_count, ag.outgoing_count, ag.total_count,
                   ag.first_timestamp, ag.last_timestamp
            FROM aggregated ag
            JOIN accounts a ON a.account_ref = ag.cp
            JOIN banks b ON b.bank_id = a.bank_id
            ORDER BY ag.total_count DESC, ag.last_timestamp DESC, a.account_ref ASC
            LIMIT ?
            """,
            params,
        )

    def network_relationship_row(
        self, account_ref: str, counterparty_ref: str, context_time: datetime
    ) -> tuple[Any, ...]:
        """Return one relationship aggregate with its counterparty identity."""
        row = self._fetchone(
            """
            WITH aggregate AS (
              SELECT
                SUM(CASE WHEN to_account_ref = ? THEN 1 ELSE 0 END)::BIGINT AS incoming_count,
                SUM(CASE WHEN from_account_ref = ? THEN 1 ELSE 0 END)::BIGINT AS outgoing_count,
                COUNT(*)::BIGINT AS total_count,
                MIN(transaction_timestamp) AS first_timestamp,
                MAX(transaction_timestamp) AS last_timestamp
              FROM transactions
              WHERE transaction_timestamp < ?
                AND ((from_account_ref = ? AND to_account_ref = ?)
                     OR (from_account_ref = ? AND to_account_ref = ?))
            )
            SELECT a.account_ref, a.source_dataset, a.bank_id, a.account_id,
                   b.mapping_version, b.country_name, b.iso_alpha2,
                   b.centroid_latitude, b.centroid_longitude,
                   ag.incoming_count, ag.outgoing_count, ag.total_count,
                   ag.first_timestamp, ag.last_timestamp
            FROM accounts a
            JOIN banks b ON b.bank_id = a.bank_id
            CROSS JOIN aggregate ag
            WHERE a.account_ref = ?
            """,
            [
                account_ref, account_ref, context_time,
                account_ref, counterparty_ref, counterparty_ref, account_ref,
                counterparty_ref,
            ],
        )
        if row is None:
            raise DataIntegrityError("Network counterparty identity is missing")
        return row

    def account_involvement_count(self, account_ref: str, context_time: datetime) -> int:
        row = self._fetchone(
            """
            SELECT COUNT(DISTINCT transaction_ref)::BIGINT
            FROM transactions
            WHERE transaction_timestamp < ? AND (from_account_ref = ? OR to_account_ref = ?)
            """,
            [context_time, account_ref, account_ref],
        )
        return int((row or (0,))[0] or 0)

    def support_refs_for_relationship(
        self, account_ref: str, counterparty_ref: str, context_time: datetime
    ) -> list[str]:
        return self._support_ref_query(
            """
            transaction_timestamp < ? AND
            ((from_account_ref = ? AND to_account_ref = ?) OR
             (from_account_ref = ? AND to_account_ref = ?))
            """,
            [context_time, account_ref, counterparty_ref, counterparty_ref, account_ref],
        )

    def support_refs_for_account(self, account_ref: str, context_time: datetime) -> list[str]:
        return self._support_ref_query(
            "transaction_timestamp < ? AND (from_account_ref = ? OR to_account_ref = ?)",
            [context_time, account_ref, account_ref],
        )

    def support_refs_for_network_behavior(
        self, account_ref: str, context_time: datetime
    ) -> list[str]:
        return self._support_ref_query(
            """
            transaction_timestamp >= ? AND transaction_timestamp < ?
            AND (from_account_ref = ? OR to_account_ref = ?)
            """,
            [context_time - timedelta(hours=24), context_time, account_ref, account_ref],
        )

    def _support_ref_query(self, where: str, params: list[Any]) -> list[str]:
        return [
            str(row[0])
            for row in self._fetchall(
                f"""
                SELECT transaction_ref FROM transactions
                WHERE {where}
                ORDER BY transaction_timestamp DESC, transaction_ref ASC
                LIMIT 51
                """,
                params,
            )
        ]

    def supporting_transaction_rows(
        self, refs: Iterable[str], *, max_refs: int = 50
    ) -> list[tuple[Any, ...]]:
        if not 1 <= max_refs <= 450:
            raise InvalidInputError("Supporting transaction batch limit is invalid")
        bounded = list(dict.fromkeys(refs))
        if len(bounded) > max_refs:
            if max_refs == 50:
                raise ResultTooLargeError(
                    "Display evidence support is limited to 50 transactions"
                )
            raise ResultTooLargeError("Supporting transaction batch exceeded its bounded limit")
        if not bounded:
            return []
        transaction_by_ref: dict[str, tuple[Any, ...]] = {}
        review_by_ref: dict[str, tuple[Any, ...]] = {}
        for start in range(0, len(bounded), 50):
            chunk = bounded[start : start + 50]
            placeholders = ",".join("?" for _ in chunk)
            for row in self._fetchall(
                f"""
                SELECT transaction_ref, transaction_timestamp,
                       from_account_ref, from_bank_id, from_account_id,
                       to_account_ref, to_bank_id, to_account_id,
                       amount_paid, payment_currency, amount_received,
                       receiving_currency, payment_format, cross_currency
                FROM transactions
                WHERE transaction_ref IN ({placeholders})
                """,
                chunk,
            ):
                transaction_by_ref[str(row[0])] = row
            for row in self._fetchall(
                f"""
                SELECT transaction_ref, aml_review_priority,
                       sender_related_alert_ref, receiver_related_alert_ref
                FROM transaction_review_states
                WHERE transaction_ref IN ({placeholders})
                """,
                chunk,
            ):
                review_by_ref[str(row[0])] = row
        if len(transaction_by_ref) != len(bounded):
            raise DataIntegrityError("Evidence support refers to a missing transaction")
        if len(review_by_ref) != len(bounded):
            raise DataIntegrityError("Evidence support transaction review state is missing")

        bank_ids = list(
            dict.fromkeys(
                str(row[index])
                for row in transaction_by_ref.values()
                for index in (3, 6)
            )
        )
        bank_placeholders = ",".join("?" for _ in bank_ids)
        bank_by_id = {
            str(row[0]): row
            for row in self._fetchall(
                f"""
                SELECT bank_id, mapping_version, country_name, iso_alpha2,
                       centroid_latitude, centroid_longitude
                FROM banks
                WHERE bank_id IN ({bank_placeholders})
                """,
                bank_ids,
            )
        }
        if len(bank_by_id) != len(bank_ids):
            raise DataIntegrityError("Evidence support Bank Country identity is missing")

        alert_refs = list(
            dict.fromkeys(
                str(row[index])
                for row in review_by_ref.values()
                for index in (2, 3)
                if row[index] is not None
            )
        )
        alert_cutoffs: dict[str, Any] = {}
        if alert_refs:
            alert_placeholders = ",".join("?" for _ in alert_refs)
            alert_cutoffs = {
                str(row[0]): row[1]
                for row in self._fetchall(
                    f"""
                    SELECT alert_ref, entry_cutoff
                    FROM network_alerts
                    WHERE alert_ref IN ({alert_placeholders})
                    """,
                    alert_refs,
                )
            }

        def related_alert(review: tuple[Any, ...]) -> str | None:
            sender = str(review[2]) if review[2] is not None else None
            receiver = str(review[3]) if review[3] is not None else None
            if sender is None:
                return receiver
            if receiver is None:
                return sender
            sender_cutoff = alert_cutoffs.get(sender)
            receiver_cutoff = alert_cutoffs.get(receiver)
            if (
                sender_cutoff is not None
                and receiver_cutoff is not None
                and sender_cutoff != receiver_cutoff
            ):
                return sender if sender_cutoff > receiver_cutoff else receiver
            return sender if sender <= receiver else receiver

        rows: list[tuple[Any, ...]] = []
        for ref in bounded:
            transaction = transaction_by_ref[ref]
            review = review_by_ref[ref]
            sender_bank = bank_by_id[str(transaction[3])]
            receiver_bank = bank_by_id[str(transaction[6])]
            rows.append(
                (
                    transaction[0], transaction[1],
                    transaction[2], transaction[3], transaction[4],
                    *sender_bank[1:],
                    transaction[5], transaction[6], transaction[7],
                    *receiver_bank[1:],
                    transaction[8], transaction[9], transaction[10],
                    transaction[11], transaction[12], review[1],
                    related_alert(review), transaction[13],
                )
            )
        return rows

    def activity_bucket_rows(
        self,
        account_ref: str,
        context_time: datetime,
        *,
        range_start: datetime | None = None,
    ) -> list[tuple[Any, ...]]:
        range_predicate = "AND transaction_timestamp >= ?" if range_start is not None else ""
        params: list[Any] = [account_ref, account_ref, account_ref, context_time]
        if range_start is not None:
            params.append(range_start)
        params.extend([account_ref, account_ref])
        return self._fetchall(
            f"""
            SELECT CAST(transaction_timestamp AS DATE) AS day,
                   CASE WHEN to_account_ref = ? THEN 'INCOMING' ELSE 'OUTGOING' END AS direction,
                   CASE WHEN to_account_ref = ? THEN receiving_currency ELSE payment_currency END AS currency,
                   COUNT(*)::BIGINT,
                   SUM(CASE WHEN to_account_ref = ? THEN amount_received ELSE amount_paid END) AS total_amount
            FROM transactions
            WHERE transaction_timestamp < ?
              {range_predicate}
              AND (from_account_ref = ? OR to_account_ref = ?)
            GROUP BY day, direction, currency
            ORDER BY day ASC, direction ASC, currency ASC
            """,
            params,
        )

    def bank_country_flow_rows(self, account_ref: str, context_time: datetime) -> list[tuple[Any, ...]]:
        return self._fetchall(
            """
            WITH flow AS (
              SELECT
                CASE WHEN t.to_account_ref = ? THEN sb.country_name ELSE rb.country_name END AS country_name,
                CASE WHEN t.to_account_ref = ? THEN sb.iso_alpha2 ELSE rb.iso_alpha2 END AS iso,
                CASE WHEN t.to_account_ref = ? THEN t.from_account_ref ELSE t.to_account_ref END AS cp,
                CASE WHEN t.to_account_ref = ? THEN 1 ELSE 0 END AS incoming,
                CASE WHEN t.from_account_ref = ? THEN 1 ELSE 0 END AS outgoing,
                t.transaction_timestamp
              FROM transactions t
              JOIN banks sb ON sb.bank_id = t.from_bank_id
              JOIN banks rb ON rb.bank_id = t.to_bank_id
              WHERE t.transaction_timestamp < ?
                AND (t.from_account_ref = ? OR t.to_account_ref = ?)
                AND t.from_account_ref <> t.to_account_ref
            )
            SELECT country_name, iso, SUM(incoming)::BIGINT, SUM(outgoing)::BIGINT,
                   COUNT(DISTINCT cp)::BIGINT, MAX(transaction_timestamp) AS latest,
                   COUNT(*)::BIGINT AS total_count
            FROM flow
            GROUP BY country_name, iso
            ORDER BY total_count DESC, iso ASC
            """,
            [account_ref, account_ref, account_ref, account_ref, account_ref,
             context_time, account_ref, account_ref],
        )

    def alert_history_rows(
        self, account_ref: str, context_time: datetime
    ) -> tuple[list[tuple[Any, ...]], int]:
        rows = self._fetchall(
            """
            SELECT alert_ref, entry_snapshot_id, entry_cutoff, reason_code,
                   COUNT(*) OVER ()::BIGINT AS alert_history_total
            FROM network_alerts
            WHERE account_ref = ? AND entry_cutoff <= ?
            ORDER BY entry_cutoff DESC, alert_ref ASC
            LIMIT 100
            """,
            [account_ref, context_time],
        )
        return rows, int(rows[0][4]) if rows else 0

    @staticmethod
    def _encode_page_cursor(kind: str, values: list[Any]) -> str:
        raw = json.dumps(
            {"kind": kind, "values": values, "version": 1},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @classmethod
    def _decode_page_cursor(cls, cursor: str, kind: str) -> list[Any]:
        try:
            if not cursor or not isinstance(cursor, str):
                raise ValueError
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
            if (
                not isinstance(payload, dict)
                or set(payload) != {"kind", "values", "version"}
                or payload.get("kind") != kind
                or payload.get("version") != 1
                or not isinstance(payload.get("values"), list)
            ):
                raise ValueError
            canonical = cls._encode_page_cursor(kind, payload["values"])
            if canonical != cursor:
                raise ValueError
            return payload["values"]
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError, binascii.Error) as exc:
            raise InvalidInputError(f"{kind.replace('_', ' ').title()} cursor is invalid") from exc

    @staticmethod
    def _cursor_timestamp(value: datetime) -> str:
        return value.isoformat(timespec="microseconds")

    @staticmethod
    def _parse_page_timestamp(value: Any) -> datetime:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None or value != parsed.isoformat(timespec="microseconds"):
            raise ValueError
        return parsed

    @staticmethod
    def _validate_page_limit(limit: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise InvalidInputError("List limit must be between 1 and 100")

    def list_alert_rows(
        self,
        *,
        cursor: str | None,
        limit: int,
        q: str | None,
        bank_country: str | None,
        include_alert_refs: tuple[str, ...] | None,
        exclude_alert_refs: tuple[str, ...] | None,
    ) -> tuple[list[tuple[Any, ...]], str | None, bool]:
        self._validate_page_limit(limit)
        if include_alert_refs is not None and exclude_alert_refs is not None:
            raise InvalidInputError("Alert include/exclude membership filters are mutually exclusive")
        clauses: list[str] = []
        params: list[Any] = []
        cursor_values: list[Any] | None = None
        if cursor is not None:
            cursor_values = self._decode_page_cursor(cursor, "alerts")
            if len(cursor_values) != 2:
                raise InvalidInputError("Alerts cursor is invalid")
            try:
                cursor_time = self._parse_page_timestamp(cursor_values[0])
                cursor_ref = str(cursor_values[1])
                if not cursor_ref:
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise InvalidInputError("Alerts cursor is invalid") from exc
        else:
            cursor_time = None
            cursor_ref = None
        if q:
            clauses.append(
                "(starts_with(na.alert_ref, ?) OR starts_with(na.account_ref, ?) "
                "OR starts_with(a.account_id, ?) OR starts_with(a.bank_id, ?))"
            )
            params.extend([q, q, q, q])
        if bank_country:
            clauses.append("(b.country_name = ? OR b.iso_alpha2 = ?)")
            params.extend([bank_country, bank_country])
        if include_alert_refs is not None:
            if not include_alert_refs:
                return [], None, False
            placeholders = ", ".join("?" for _ in include_alert_refs)
            clauses.append(f"na.alert_ref IN ({placeholders})")
            params.extend(include_alert_refs)
        if exclude_alert_refs:
            placeholders = ", ".join("?" for _ in exclude_alert_refs)
            clauses.append(f"na.alert_ref NOT IN ({placeholders})")
            params.extend(exclude_alert_refs)
        if cursor_time is not None and cursor_ref is not None:
            clauses.append("(na.entry_cutoff < ? OR (na.entry_cutoff = ? AND na.alert_ref > ?))")
            params.extend([cursor_time, cursor_time, cursor_ref])
        where = " AND ".join(clauses) if clauses else "TRUE"
        params.append(limit + 1)
        rows = self._fetchall(
            f"""
            WITH page_candidates AS (
                SELECT na.alert_ref, na.account_ref, a.bank_id, a.account_id,
                       b.mapping_version, b.country_name, b.iso_alpha2,
                       b.centroid_latitude, b.centroid_longitude,
                       ads.network_review_band, na.entry_snapshot_id, na.entry_cutoff,
                       na.reason_code
                FROM network_alerts na
                JOIN accounts a ON a.account_ref = na.account_ref
                JOIN banks b ON b.bank_id = a.bank_id
                JOIN account_detector_states ads
                  ON ads.snapshot_id = na.entry_snapshot_id AND ads.account_ref = na.account_ref
                WHERE {where}
                ORDER BY na.entry_cutoff DESC, na.alert_ref ASC
                LIMIT ?
            )
            SELECT pc.*,
                   (
                     SELECT COUNT(*)::BIGINT
                     FROM transactions t
                     WHERE t.transaction_timestamp >= pc.entry_cutoff - INTERVAL '24 hours'
                       AND t.transaction_timestamp < pc.entry_cutoff
                       AND (t.from_account_ref = pc.account_ref OR t.to_account_ref = pc.account_ref)
                   ) AS relevant_recent_transaction_count
            FROM page_candidates pc
            ORDER BY pc.entry_cutoff DESC, pc.alert_ref ASC
            """,
            params,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if has_more and page:
            next_cursor = self._encode_page_cursor(
                "alerts", [self._cursor_timestamp(page[-1][11]), str(page[-1][0])]
            )
        return page, next_cursor, has_more

    def _transaction_summary_rows(
        self,
        where: str,
        params: list[Any],
        *,
        limit: int,
        candidate_joins: str = "",
    ) -> list[tuple[Any, ...]]:
        """Select a bounded transaction page before applying display-only enrichment."""
        return self._fetchall(
            f"""
            WITH page_candidates AS MATERIALIZED (
                SELECT t.transaction_ref, t.transaction_timestamp,
                       t.from_account_ref, t.from_bank_id, t.from_account_id,
                       t.to_account_ref, t.to_bank_id, t.to_account_id,
                       t.amount_paid, t.payment_currency, t.amount_received,
                       t.receiving_currency, t.payment_format, t.cross_currency
                FROM transactions t
                {candidate_joins}
                WHERE {where}
                ORDER BY t.transaction_timestamp DESC, t.transaction_ref DESC
                LIMIT ?
            )
            SELECT pc.transaction_ref, pc.transaction_timestamp,
                   pc.from_account_ref, pc.from_bank_id, pc.from_account_id,
                   sb.mapping_version, sb.country_name, sb.iso_alpha2,
                   sb.centroid_latitude, sb.centroid_longitude,
                   pc.to_account_ref, pc.to_bank_id, pc.to_account_id,
                   rb.mapping_version, rb.country_name, rb.iso_alpha2,
                   rb.centroid_latitude, rb.centroid_longitude,
                   pc.amount_paid, pc.payment_currency, pc.amount_received,
                   pc.receiving_currency, pc.payment_format, trs.aml_review_priority,
                   CASE
                     WHEN trs.sender_related_alert_ref IS NULL THEN trs.receiver_related_alert_ref
                     WHEN trs.receiver_related_alert_ref IS NULL THEN trs.sender_related_alert_ref
                     WHEN sna.entry_cutoff > rna.entry_cutoff THEN trs.sender_related_alert_ref
                     WHEN rna.entry_cutoff > sna.entry_cutoff THEN trs.receiver_related_alert_ref
                     WHEN trs.sender_related_alert_ref <= trs.receiver_related_alert_ref
                       THEN trs.sender_related_alert_ref
                     ELSE trs.receiver_related_alert_ref
                   END AS related_alert,
                   pc.cross_currency
            FROM page_candidates pc
            JOIN banks sb ON sb.bank_id = pc.from_bank_id
            JOIN banks rb ON rb.bank_id = pc.to_bank_id
            JOIN transaction_review_states trs ON trs.transaction_ref = pc.transaction_ref
            LEFT JOIN network_alerts sna ON sna.alert_ref = trs.sender_related_alert_ref
            LEFT JOIN network_alerts rna ON rna.alert_ref = trs.receiver_related_alert_ref
            ORDER BY pc.transaction_timestamp DESC, pc.transaction_ref DESC
            """,
            [*params, limit],
        )

    def list_transaction_rows(
        self,
        *,
        cursor: str | None,
        limit: int,
        q: str | None,
        priority: str | None,
        alert_involvement: bool | None,
        date_from: datetime | None,
        date_to: datetime | None,
        currency: str | None,
        payment_format: str | None,
        sending_bank_country: str | None,
        receiving_bank_country: str | None,
    ) -> tuple[list[tuple[Any, ...]], str | None, bool]:
        self._validate_page_limit(limit)
        clauses: list[str] = []
        params: list[Any] = []
        candidate_joins: list[str] = []
        if cursor is not None:
            values = self._decode_page_cursor(cursor, "transactions")
            if len(values) != 2:
                raise InvalidInputError("Transactions cursor is invalid")
            try:
                cursor_time = self._parse_page_timestamp(values[0])
                cursor_ref = str(values[1])
                if not cursor_ref:
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise InvalidInputError("Transactions cursor is invalid") from exc
        else:
            cursor_time = None
            cursor_ref = None
        if q:
            clauses.append(
                "(starts_with(t.transaction_ref, ?) OR starts_with(t.from_account_id, ?) "
                "OR starts_with(t.to_account_id, ?) OR starts_with(t.from_bank_id, ?) "
                "OR starts_with(t.to_bank_id, ?))"
            )
            params.extend([q, q, q, q, q])
        if priority is not None:
            candidate_joins.append(
                "JOIN transaction_review_states trs ON trs.transaction_ref = t.transaction_ref"
            )
            clauses.append("trs.aml_review_priority = ?")
            params.append(priority)
        if alert_involvement is not None:
            if not any("transaction_review_states" in join for join in candidate_joins):
                candidate_joins.append(
                    "JOIN transaction_review_states trs ON trs.transaction_ref = t.transaction_ref"
                )
            clauses.append("trs.alert_involvement = ?")
            params.append(alert_involvement)
        if date_from is not None:
            clauses.append("t.transaction_timestamp >= ?")
            params.append(date_from)
        if date_to is not None:
            clauses.append("t.transaction_timestamp < ?")
            params.append(date_to)
        if currency:
            clauses.append("(t.payment_currency = ? OR t.receiving_currency = ?)")
            params.extend([currency, currency])
        if payment_format:
            clauses.append("t.payment_format = ?")
            params.append(payment_format)
        if sending_bank_country:
            candidate_joins.append(
                "JOIN banks sb ON sb.bank_id = t.from_bank_id"
            )
            clauses.append("(sb.country_name = ? OR sb.iso_alpha2 = ?)")
            params.extend([sending_bank_country, sending_bank_country])
        if receiving_bank_country:
            candidate_joins.append(
                "JOIN banks rb ON rb.bank_id = t.to_bank_id"
            )
            clauses.append("(rb.country_name = ? OR rb.iso_alpha2 = ?)")
            params.extend([receiving_bank_country, receiving_bank_country])
        if cursor_time is not None and cursor_ref is not None:
            clauses.append(
                "(t.transaction_timestamp < ? OR "
                "(t.transaction_timestamp = ? AND t.transaction_ref < ?))"
            )
            params.extend([cursor_time, cursor_time, cursor_ref])
        where = " AND ".join(clauses) if clauses else "TRUE"
        rows = self._transaction_summary_rows(
            where,
            params,
            limit=limit + 1,
            candidate_joins="\n".join(candidate_joins),
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if has_more and page:
            next_cursor = self._encode_page_cursor(
                "transactions", [self._cursor_timestamp(page[-1][1]), str(page[-1][0])]
            )
        return page, next_cursor, has_more

    def list_account_rows(
        self,
        *,
        snapshot_id: str,
        cursor: str | None,
        limit: int,
        q: str | None,
        band: str | None,
        bank_country: str | None,
        alert_involvement: bool | None,
    ) -> tuple[list[tuple[Any, ...]], str | None, bool]:
        self._validate_page_limit(limit)
        clauses: list[str] = []
        params: list[Any] = [snapshot_id]
        if cursor is not None:
            values = self._decode_page_cursor(cursor, "accounts")
            if len(values) != 3:
                raise InvalidInputError("Accounts cursor is invalid")
            try:
                cursor_band_order = int(values[0])
                cursor_score = None if values[1] is None else float(values[1])
                cursor_ref = str(values[2])
                if (
                    cursor_band_order not in {1, 2, 3, 4}
                    or not cursor_ref
                    or (cursor_score is not None and not math.isfinite(cursor_score))
                ):
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise InvalidInputError("Accounts cursor is invalid") from exc
        else:
            cursor_band_order = None
            cursor_score = None
            cursor_ref = None
        if q:
            clauses.append("(starts_with(account_id, ?) OR starts_with(bank_id, ?))")
            params.extend([q, q])
        if band is not None:
            clauses.append("network_review_band = ?")
            params.append(band)
        if bank_country:
            clauses.append("(country_name = ? OR iso_alpha2 = ?)")
            params.extend([bank_country, bank_country])
        if alert_involvement is not None:
            clauses.append("alert_involvement = ?")
            params.append(alert_involvement)
        if cursor_band_order is not None and cursor_ref is not None:
            if cursor_score is None:
                clauses.append(
                    "(band_order > ? OR (band_order = ? AND network_pattern_score IS NULL "
                    "AND account_ref > ?))"
                )
                params.extend([cursor_band_order, cursor_band_order, cursor_ref])
            else:
                clauses.append(
                    "(band_order > ? OR (band_order = ? AND "
                    "(network_pattern_score < ? OR network_pattern_score IS NULL OR "
                    "(network_pattern_score = ? AND account_ref > ?))))"
                )
                params.extend(
                    [cursor_band_order, cursor_band_order, cursor_score, cursor_score, cursor_ref]
                )
        where = " AND ".join(clauses) if clauses else "TRUE"
        params.append(limit + 1)
        rows = self._fetchall(
            f"""
            WITH base AS (
                SELECT a.account_ref, a.bank_id, a.account_id,
                       b.mapping_version, b.country_name, b.iso_alpha2,
                       b.centroid_latitude, b.centroid_longitude,
                       ads.network_review_band, ads.network_pattern_score,
                       ds.snapshot_id, ds.cutoff_timestamp,
                       CASE ads.network_review_band
                         WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2
                         WHEN 'LOW' THEN 3 WHEN 'UNSCORED' THEN 4 ELSE 5
                       END AS band_order,
                       EXISTS(
                         SELECT 1 FROM network_alerts na
                         WHERE na.account_ref = a.account_ref
                           AND na.entry_cutoff <= ds.cutoff_timestamp
                       ) AS alert_involvement
                FROM accounts a
                JOIN banks b ON b.bank_id = a.bank_id
                JOIN account_detector_states ads ON ads.account_ref = a.account_ref
                JOIN detector_snapshots ds ON ds.snapshot_id = ads.snapshot_id
                WHERE ads.snapshot_id = ? AND ds.status = 'COMPLETE'
            ), page_candidates AS (
                SELECT * FROM base
                WHERE {where}
                ORDER BY band_order ASC, network_pattern_score DESC NULLS LAST, account_ref ASC
                LIMIT ?
            )
            SELECT pc.account_ref, pc.bank_id, pc.account_id,
                   pc.mapping_version, pc.country_name, pc.iso_alpha2,
                   pc.centroid_latitude, pc.centroid_longitude,
                   pc.network_review_band, pc.network_pattern_score,
                   pc.snapshot_id, pc.cutoff_timestamp,
                   (
                     SELECT COUNT(*)::BIGINT FROM transactions t
                     WHERE t.to_account_ref = pc.account_ref
                       AND t.transaction_timestamp < pc.cutoff_timestamp
                   ) AS incoming_count,
                   (
                     SELECT COUNT(*)::BIGINT FROM transactions t
                     WHERE t.from_account_ref = pc.account_ref
                       AND t.transaction_timestamp < pc.cutoff_timestamp
                   ) AS outgoing_count,
                   pc.alert_involvement
            FROM page_candidates pc
            ORDER BY pc.band_order ASC, pc.network_pattern_score DESC NULLS LAST, pc.account_ref ASC
            """,
            params,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if has_more and page:
            band_value = str(page[-1][8])
            band_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNSCORED": 4}.get(band_value)
            if band_order is None:
                raise DataIntegrityError("Account list contains an unknown persisted review band")
            score = None if page[-1][9] is None else float(page[-1][9])
            next_cursor = self._encode_page_cursor(
                "accounts", [band_order, score, str(page[-1][0])]
            )
        return page, next_cursor, has_more

    def list_account_transaction_rows(
        self,
        *,
        account_ref: str,
        context_time: datetime,
        limit: int,
        direction: Direction,
        currency: str | None,
        counterparty_account_ref: str | None,
        cursor: str | None,
    ) -> tuple[list[tuple[Any, ...]], str | None, bool]:
        if not 1 <= limit <= 100:
            raise InvalidInputError("Account transaction limit must be between 1 and 100")
        clauses = [
            "t.transaction_timestamp < ?",
            "(t.from_account_ref = ? OR t.to_account_ref = ?)",
        ]
        params: list[Any] = [context_time, account_ref, account_ref]
        if direction is Direction.INCOMING:
            clauses.append("t.to_account_ref = ?")
            params.append(account_ref)
        elif direction is Direction.OUTGOING:
            clauses.append("t.from_account_ref = ?")
            params.append(account_ref)
        if currency:
            clauses.append("(t.payment_currency = ? OR t.receiving_currency = ?)")
            params.extend([currency, currency])
        if counterparty_account_ref:
            clauses.append(
                "((t.from_account_ref = ? AND t.to_account_ref = ?) OR "
                "(t.from_account_ref = ? AND t.to_account_ref = ?))"
            )
            params.extend([account_ref, counterparty_account_ref, counterparty_account_ref, account_ref])
        if cursor:
            cursor_time, cursor_ref = self.decode_cursor(cursor)
            clauses.append(
                "(t.transaction_timestamp < ? OR "
                "(t.transaction_timestamp = ? AND t.transaction_ref < ?))"
            )
            params.extend([cursor_time, cursor_time, cursor_ref])
        rows = self._transaction_summary_rows(
            " AND ".join(clauses),
            params,
            limit=limit + 1,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if has_more and page:
            next_cursor = self.encode_cursor(page[-1][1], str(page[-1][0]))
        return page, next_cursor, has_more

    @staticmethod
    def encode_cursor(timestamp: datetime, transaction_ref: str) -> str:
        raw = json.dumps(
            [timestamp.strftime("%Y-%m-%dT%H:%M:%S"), transaction_ref],
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def decode_cursor(cursor: str) -> tuple[datetime, str]:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
            if not isinstance(payload, list) or len(payload) != 2:
                raise ValueError
            timestamp = datetime.strptime(payload[0], "%Y-%m-%dT%H:%M:%S")
            transaction_ref = str(payload[1])
            if not transaction_ref:
                raise ValueError
            return timestamp, transaction_ref
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidInputError("Account transaction cursor is invalid") from exc

    def _fetchone(self, statement: str, parameters: list[Any] | None = None) -> tuple[Any, ...] | None:
        try:
            with self._lock:
                if parameters is None:
                    return self._connection.execute(statement).fetchone()
                return self._connection.execute(statement, parameters).fetchone()
        except duckdb.Error as exc:
            raise DataIntegrityError() from exc

    def _fetchall(self, statement: str, parameters: list[Any] | None = None) -> list[tuple[Any, ...]]:
        try:
            with self._lock:
                if parameters is None:
                    return self._connection.execute(statement).fetchall()
                return self._connection.execute(statement, parameters).fetchall()
        except duckdb.Error as exc:
            raise DataIntegrityError() from exc
