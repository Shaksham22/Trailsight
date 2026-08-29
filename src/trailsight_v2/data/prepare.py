"""Prepare the runtime-safe V2 DuckDB from the external IBM HI-Small source."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from trailsight_v2.data.bank_country import bank_country_for
from trailsight_v2.data.constants import (
    BANK_COUNTRY_VERSION,
    DATA_CONTRACT_VERSION,
    IBM_SOURCE_PATH_ENV,
    SOURCE_DATASET,
)
from trailsight_v2.data.errors import DataPreparationError, V2DataError
from trailsight_v2.data.schema import assert_ground_truth_firewall, create_wp01_schema
from trailsight_v2.data.source import iter_canonical_transactions, validate_source

INSERT_TRANSACTION_SQL = """
INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip()


@dataclass(frozen=True, slots=True)
class PreparationSummary:
    source_path: Path
    source_sha256: str
    row_count: int
    account_count: int
    bank_count: int
    edge_delta_count: int
    min_timestamp: datetime
    max_timestamp: datetime
    derived_snapshot_cutoff_count: int
    output_path: Path
    output_size_bytes: int
    preparation_wall_clock_seconds: float

    def lines(self) -> tuple[str, ...]:
        return (
            f"source_dataset={SOURCE_DATASET}",
            f"source_path={self.source_path}",
            f"raw_source_sha256={self.source_sha256}",
            f"row_count={self.row_count}",
            f"account_count={self.account_count}",
            f"bank_count={self.bank_count}",
            f"detector_edge_day_delta_count={self.edge_delta_count}",
            f"min_timestamp={self.min_timestamp.isoformat(sep=' ')}",
            f"max_timestamp={self.max_timestamp.isoformat(sep=' ')}",
            f"derived_snapshot_cutoff_count={self.derived_snapshot_cutoff_count}",
            f"runtime_db_path={self.output_path}",
            f"runtime_db_size_bytes={self.output_size_bytes}",
            f"preparation_wall_clock_seconds={self.preparation_wall_clock_seconds:.3f}",
            "runtime_schema_firewall=PASS",
        )


def resolve_source_path(source_path: str | Path | None = None) -> Path:
    if source_path is not None:
        return Path(source_path).expanduser().resolve()
    configured = os.environ.get(IBM_SOURCE_PATH_ENV)
    if not configured:
        raise DataPreparationError(
            f"set {IBM_SOURCE_PATH_ENV} to the external IBM HI-Small transaction CSV "
            "or pass --source"
        )
    return Path(configured).expanduser().resolve()


def _transaction_values(transaction) -> tuple[object, ...]:
    return (
        transaction.transaction_ref,
        transaction.source_dataset,
        transaction.source_row_ordinal,
        transaction.transaction_timestamp,
        transaction.from_bank_id,
        transaction.from_account_id,
        transaction.from_account_ref,
        transaction.to_bank_id,
        transaction.to_account_id,
        transaction.to_account_ref,
        transaction.amount_received,
        transaction.receiving_currency,
        transaction.amount_paid,
        transaction.payment_currency,
        transaction.payment_format,
        transaction.cross_currency,
    )


def _populate_banks(connection: duckdb.DuckDBPyConnection) -> int:
    bank_ids = [
        row[0]
        for row in connection.execute(
            """
            SELECT bank_id
            FROM (
                SELECT from_bank_id AS bank_id FROM transactions
                UNION
                SELECT to_bank_id AS bank_id FROM transactions
            )
            ORDER BY bank_id
            """
        ).fetchall()
    ]
    rows = []
    for bank_id in bank_ids:
        country = bank_country_for(bank_id)
        rows.append(
            (
                bank_id,
                BANK_COUNTRY_VERSION,
                country.country_name,
                country.iso_alpha2,
                country.centroid_latitude,
                country.centroid_longitude,
            )
        )
    if rows:
        connection.executemany("INSERT INTO banks VALUES (?, ?, ?, ?, ?, ?)", rows)
    return len(rows)


def _populate_accounts(connection: duckdb.DuckDBPyConnection) -> int:
    collision = connection.execute(
        """
        SELECT account_ref
        FROM (
            SELECT DISTINCT from_account_ref AS account_ref, source_dataset,
                            from_bank_id AS bank_id, from_account_id AS account_id
            FROM transactions
            UNION
            SELECT DISTINCT to_account_ref AS account_ref, source_dataset,
                            to_bank_id AS bank_id, to_account_id AS account_id
            FROM transactions
        )
        GROUP BY account_ref
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    if collision is not None:
        raise DataPreparationError(
            f"account-ref-v1 short-hash collision detected for {collision[0]}"
        )
    connection.execute(
        """
        INSERT INTO accounts
        SELECT identities.account_ref,
               identities.source_dataset,
               identities.bank_id,
               identities.account_id,
               banks.iso_alpha2 AS bank_country_code
        FROM (
            SELECT DISTINCT from_account_ref AS account_ref, source_dataset,
                            from_bank_id AS bank_id, from_account_id AS account_id
            FROM transactions
            UNION
            SELECT DISTINCT to_account_ref AS account_ref, source_dataset,
                            to_bank_id AS bank_id, to_account_id AS account_id
            FROM transactions
        ) AS identities
        JOIN banks USING (bank_id)
        ORDER BY identities.account_ref
        """
    )
    return connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]


def _populate_edge_day_deltas(connection: duckdb.DuckDBPyConnection) -> int:
    connection.execute(
        """
        INSERT INTO detector_edge_day_deltas
        SELECT MIN(CAST(transaction_timestamp AS DATE)) AS edge_day,
               LEAST(from_account_ref, to_account_ref) AS account_ref_a,
               GREATEST(from_account_ref, to_account_ref) AS account_ref_b
        FROM transactions
        WHERE from_account_ref <> to_account_ref
        GROUP BY LEAST(from_account_ref, to_account_ref),
                 GREATEST(from_account_ref, to_account_ref)
        ORDER BY edge_day, account_ref_a, account_ref_b
        """
    )
    return connection.execute("SELECT COUNT(*) FROM detector_edge_day_deltas").fetchone()[0]


def prepare_runtime_database(
    *,
    output_path: str | Path,
    source_path: str | Path | None = None,
    batch_size: int = 10_000,
) -> PreparationSummary:
    started = time.perf_counter()
    source = resolve_source_path(source_path)
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.unlink(missing_ok=True)

    connection: duckdb.DuckDBPyConnection | None = None
    try:
        validation = validate_source(source)
        connection = duckdb.connect(str(temporary))
        create_wp01_schema(connection)

        batch: list[tuple[object, ...]] = []
        for transaction in iter_canonical_transactions(source):
            batch.append(_transaction_values(transaction))
            if len(batch) >= batch_size:
                connection.executemany(INSERT_TRANSACTION_SQL, batch)
                batch.clear()
        if batch:
            connection.executemany(INSERT_TRANSACTION_SQL, batch)

        row_count, min_timestamp, max_timestamp = connection.execute(
            "SELECT COUNT(*), MIN(transaction_timestamp), MAX(transaction_timestamp) FROM transactions"
        ).fetchone()
        if row_count == 0 or min_timestamp is None or max_timestamp is None:
            raise DataPreparationError("IBM HI-Small transaction source contains no data rows")

        bank_count = _populate_banks(connection)
        account_count = _populate_accounts(connection)
        edge_delta_count = _populate_edge_day_deltas(connection)

        prepared_at = datetime.now(timezone.utc).replace(tzinfo=None)
        connection.execute(
            "INSERT INTO source_manifest VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                SOURCE_DATASET,
                str(validation.source_path),
                validation.sha256,
                row_count,
                min_timestamp,
                max_timestamp,
                prepared_at,
                DATA_CONTRACT_VERSION,
            ),
        )
        assert_ground_truth_firewall(connection)
        connection.execute("CHECKPOINT")
        connection.close()
        connection = None
        temporary.replace(output)

        first_day = min_timestamp.date()
        last_day = max_timestamp.date()
        cutoff_count = (last_day - first_day).days + 2
        wall_clock = time.perf_counter() - started
        return PreparationSummary(
            source_path=validation.source_path,
            source_sha256=validation.sha256,
            row_count=row_count,
            account_count=account_count,
            bank_count=bank_count,
            edge_delta_count=edge_delta_count,
            min_timestamp=min_timestamp,
            max_timestamp=max_timestamp,
            derived_snapshot_cutoff_count=cutoff_count,
            output_path=output,
            output_size_bytes=output.stat().st_size,
            preparation_wall_clock_seconds=wall_clock,
        )
    except (V2DataError, duckdb.Error, OSError) as exc:
        if connection is not None:
            connection.close()
        temporary.unlink(missing_ok=True)
        if isinstance(exc, DataPreparationError):
            raise
        raise DataPreparationError(str(exc)) from exc
