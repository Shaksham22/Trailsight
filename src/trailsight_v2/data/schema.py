"""Runtime-safe DuckDB schema and ground-truth firewall assertions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

from trailsight_v2.data.constants import FORBIDDEN_RUNTIME_COLUMN_NAMES
from trailsight_v2.data.errors import GroundTruthLeakageError

WP01_RUNTIME_TABLES = (
    "source_manifest",
    "banks",
    "accounts",
    "transactions",
    "detector_edge_day_deltas",
)


def create_wp01_schema(connection: "duckdb.DuckDBPyConnection") -> None:
    connection.execute(
        """
        CREATE TABLE source_manifest (
            source_dataset VARCHAR PRIMARY KEY,
            external_file_path VARCHAR NOT NULL,
            raw_transaction_sha256 VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            min_timestamp TIMESTAMP NOT NULL,
            max_timestamp TIMESTAMP NOT NULL,
            preparation_timestamp TIMESTAMP NOT NULL,
            data_contract_version VARCHAR NOT NULL
        );

        CREATE TABLE banks (
            bank_id VARCHAR PRIMARY KEY,
            mapping_version VARCHAR NOT NULL,
            country_name VARCHAR NOT NULL,
            iso_alpha2 VARCHAR NOT NULL,
            centroid_latitude DOUBLE NOT NULL,
            centroid_longitude DOUBLE NOT NULL
        );

        CREATE TABLE accounts (
            account_ref VARCHAR PRIMARY KEY,
            source_dataset VARCHAR NOT NULL,
            bank_id VARCHAR NOT NULL,
            account_id VARCHAR NOT NULL,
            bank_country_code VARCHAR NOT NULL,
            UNIQUE (source_dataset, bank_id, account_id)
        );

        CREATE TABLE transactions (
            transaction_ref VARCHAR PRIMARY KEY,
            source_dataset VARCHAR NOT NULL,
            source_row_ordinal BIGINT NOT NULL,
            transaction_timestamp TIMESTAMP NOT NULL,
            from_bank_id VARCHAR NOT NULL,
            from_account_id VARCHAR NOT NULL,
            from_account_ref VARCHAR NOT NULL,
            to_bank_id VARCHAR NOT NULL,
            to_account_id VARCHAR NOT NULL,
            to_account_ref VARCHAR NOT NULL,
            amount_received DECIMAL(38, 18) NOT NULL,
            receiving_currency VARCHAR NOT NULL,
            amount_paid DECIMAL(38, 18) NOT NULL,
            payment_currency VARCHAR NOT NULL,
            payment_format VARCHAR NOT NULL,
            cross_currency BOOLEAN NOT NULL,
            UNIQUE (source_dataset, source_row_ordinal)
        );

        CREATE TABLE detector_edge_day_deltas (
            edge_day DATE NOT NULL,
            account_ref_a VARCHAR NOT NULL,
            account_ref_b VARCHAR NOT NULL,
            PRIMARY KEY (edge_day, account_ref_a, account_ref_b),
            CHECK (account_ref_a < account_ref_b)
        );
        """
    )


def runtime_schema_columns(connection: "duckdb.DuckDBPyConnection") -> dict[str, tuple[str, ...]]:
    rows = connection.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'main'
        ORDER BY table_name, ordinal_position
        """
    ).fetchall()
    result: dict[str, list[str]] = {}
    for table_name, column_name in rows:
        result.setdefault(table_name, []).append(column_name)
    return {name: tuple(columns) for name, columns in result.items()}


def assert_ground_truth_firewall(
    connection: "duckdb.DuckDBPyConnection",
    *,
    expected_tables: Iterable[str] = WP01_RUNTIME_TABLES,
) -> None:
    schema = runtime_schema_columns(connection)
    missing_tables = [name for name in expected_tables if name not in schema]
    if missing_tables:
        raise GroundTruthLeakageError(
            "runtime-safe schema is incomplete; missing tables: " + ", ".join(missing_tables)
        )
    leaked: list[str] = []
    for table_name, columns in schema.items():
        for column in columns:
            if column.lower() in FORBIDDEN_RUNTIME_COLUMN_NAMES:
                leaked.append(f"{table_name}.{column}")
    if leaked:
        raise GroundTruthLeakageError(
            "ground-truth firewall violation in runtime schema: " + ", ".join(leaked)
        )
