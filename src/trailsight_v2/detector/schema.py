"""Exact persisted WP02 DuckDB table contract."""

from __future__ import annotations

from typing import TYPE_CHECKING

from trailsight_v2.data.schema import runtime_schema_columns
from trailsight_v2.detector.errors import DetectorContractError

if TYPE_CHECKING:
    import duckdb


WP02_RUNTIME_TABLES = (
    "detector_snapshots",
    "account_detector_states",
    "account_detector_support",
    "transaction_review_states",
    "network_alerts",
)

WP02_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "detector_snapshots": (
        "snapshot_id",
        "source_dataset",
        "cutoff_timestamp",
        "algorithm_name",
        "algorithm_variant",
        "algorithm_version",
        "upstream_code_provenance",
        "identity_rule_version",
        "eligibility_rule_version",
        "community_algorithm",
        "community_resolution",
        "community_seed",
        "config_hash",
        "status",
        "started_at",
        "completed_at",
        "account_count",
        "eligible_account_count",
        "scored_account_count",
        "failure_message_safe",
    ),
    "account_detector_states": (
        "snapshot_id",
        "account_ref",
        "scoring_eligible",
        "network_pattern_score",
        "rank",
        "percentile",
        "network_review_band",
        "unscored_reason",
    ),
    "account_detector_support": (
        "snapshot_id",
        "account_ref",
        "first_order_neighbor_count",
        "second_order_neighbor_count",
        "community_id_or_stable_snapshot_local_index",
        "block_measure_1",
        "block_measure_2",
        "block_measure_3",
        "network_pattern_score",
    ),
    "transaction_review_states": (
        "transaction_ref",
        "snapshot_id",
        "detector_cutoff",
        "sender_band",
        "receiver_band",
        "aml_review_priority",
        "derivation_code",
        "derivation_text",
        "alert_involvement",
        "sender_related_alert_ref",
        "receiver_related_alert_ref",
    ),
    "network_alerts": (
        "alert_ref",
        "account_ref",
        "entry_snapshot_id",
        "entry_cutoff",
        "entry_score",
        "entry_rank",
        "entry_percentile",
        "reason_code",
        "created_state",
    ),
}


def create_detector_schema(connection: "duckdb.DuckDBPyConnection") -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS detector_snapshots (
            snapshot_id VARCHAR PRIMARY KEY,
            source_dataset VARCHAR NOT NULL,
            cutoff_timestamp TIMESTAMP NOT NULL,
            algorithm_name VARCHAR NOT NULL,
            algorithm_variant VARCHAR NOT NULL,
            algorithm_version VARCHAR NOT NULL,
            upstream_code_provenance VARCHAR NOT NULL,
            identity_rule_version VARCHAR NOT NULL,
            eligibility_rule_version VARCHAR NOT NULL,
            community_algorithm VARCHAR NOT NULL,
            community_resolution DOUBLE NOT NULL,
            community_seed BIGINT NOT NULL,
            config_hash VARCHAR NOT NULL,
            status VARCHAR NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETE', 'FAILED')),
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            account_count BIGINT NOT NULL,
            eligible_account_count BIGINT NOT NULL,
            scored_account_count BIGINT NOT NULL,
            failure_message_safe VARCHAR,
            UNIQUE (source_dataset, cutoff_timestamp, config_hash)
        );

        CREATE TABLE IF NOT EXISTS account_detector_states (
            snapshot_id VARCHAR NOT NULL,
            account_ref VARCHAR NOT NULL,
            scoring_eligible BOOLEAN NOT NULL,
            network_pattern_score DOUBLE,
            rank BIGINT,
            percentile DOUBLE,
            network_review_band VARCHAR NOT NULL
                CHECK (network_review_band IN ('HIGH', 'MEDIUM', 'LOW', 'UNSCORED')),
            unscored_reason VARCHAR
                CHECK (unscored_reason IS NULL OR unscored_reason IN (
                    'NOT_YET_OBSERVED', 'NO_FIRST_ORDER_CONTEXT',
                    'NO_SECOND_ORDER_CONTEXT', 'NON_FINITE_SCORE'
                )),
            PRIMARY KEY (snapshot_id, account_ref),
            CHECK (
                (scoring_eligible AND network_pattern_score IS NOT NULL
                    AND rank IS NOT NULL AND percentile IS NOT NULL
                    AND network_review_band <> 'UNSCORED' AND unscored_reason IS NULL)
                OR
                (NOT scoring_eligible AND network_pattern_score IS NULL
                    AND rank IS NULL AND percentile IS NULL
                    AND network_review_band = 'UNSCORED' AND unscored_reason IS NOT NULL)
            )
        );

        CREATE TABLE IF NOT EXISTS account_detector_support (
            snapshot_id VARCHAR NOT NULL,
            account_ref VARCHAR NOT NULL,
            first_order_neighbor_count BIGINT NOT NULL,
            second_order_neighbor_count BIGINT NOT NULL,
            community_id_or_stable_snapshot_local_index BIGINT NOT NULL,
            block_measure_1 DOUBLE NOT NULL,
            block_measure_2 DOUBLE NOT NULL,
            block_measure_3 DOUBLE NOT NULL,
            network_pattern_score DOUBLE NOT NULL,
            PRIMARY KEY (snapshot_id, account_ref)
        );

        CREATE TABLE IF NOT EXISTS transaction_review_states (
            transaction_ref VARCHAR PRIMARY KEY,
            snapshot_id VARCHAR,
            detector_cutoff TIMESTAMP,
            sender_band VARCHAR NOT NULL
                CHECK (sender_band IN ('HIGH', 'MEDIUM', 'LOW', 'UNSCORED')),
            receiver_band VARCHAR NOT NULL
                CHECK (receiver_band IN ('HIGH', 'MEDIUM', 'LOW', 'UNSCORED')),
            aml_review_priority VARCHAR NOT NULL
                CHECK (aml_review_priority IN ('HIGH', 'MEDIUM', 'LOW', 'UNSCORED')),
            derivation_code VARCHAR NOT NULL,
            derivation_text VARCHAR NOT NULL,
            alert_involvement BOOLEAN NOT NULL,
            sender_related_alert_ref VARCHAR,
            receiver_related_alert_ref VARCHAR
        );

        CREATE TABLE IF NOT EXISTS network_alerts (
            alert_ref VARCHAR PRIMARY KEY,
            account_ref VARCHAR NOT NULL,
            entry_snapshot_id VARCHAR NOT NULL,
            entry_cutoff TIMESTAMP NOT NULL,
            entry_score DOUBLE NOT NULL,
            entry_rank BIGINT NOT NULL,
            entry_percentile DOUBLE NOT NULL,
            reason_code VARCHAR NOT NULL CHECK (reason_code = 'ENTERED_HIGH'),
            created_state VARCHAR NOT NULL CHECK (created_state = 'NOT_REVIEWED'),
            UNIQUE (account_ref, entry_snapshot_id)
        );
        """
    )
    assert_detector_schema(connection)


def assert_detector_schema(connection: "duckdb.DuckDBPyConnection") -> None:
    actual = runtime_schema_columns(connection)
    errors: list[str] = []
    for table_name, expected_columns in WP02_TABLE_COLUMNS.items():
        columns = actual.get(table_name)
        if columns is None:
            errors.append(f"missing table {table_name}")
        elif columns != expected_columns:
            errors.append(
                f"{table_name} columns {columns!r} do not match {expected_columns!r}"
            )
    if errors:
        raise DetectorContractError("invalid WP02 persisted schema: " + "; ".join(errors))

