"""DuckDB staging and atomic frozen-runtime database generation."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

import duckdb

from trailsight_data.canonical import canonical_decimal
from trailsight_data.errors import DuplicateTransactionReferenceError, RuntimeValidationError
from trailsight_data.models import CaseSlice, RuntimeTransaction, RuntimeValidationReport
from trailsight_data.validation import validate_runtime_connection


def create_source_transactions_table(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE source_transactions (
            transaction_ref TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            from_bank TEXT NOT NULL,
            from_account TEXT NOT NULL,
            to_bank TEXT NOT NULL,
            to_account TEXT NOT NULL,
            amount_paid TEXT NOT NULL,
            payment_currency TEXT NOT NULL,
            amount_received TEXT NOT NULL,
            receiving_currency TEXT NOT NULL,
            payment_format TEXT NOT NULL
        )
        """
    )


def insert_staging_transactions(
    connection: duckdb.DuckDBPyConnection,
    transactions: tuple[RuntimeTransaction, ...] | list[RuntimeTransaction],
) -> None:
    connection.executemany(
        "INSERT INTO source_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                transaction.transaction_ref,
                transaction.timestamp,
                transaction.from_bank,
                transaction.from_account,
                transaction.to_bank,
                transaction.to_account,
                canonical_decimal(transaction.amount_paid),
                transaction.payment_currency,
                canonical_decimal(transaction.amount_received),
                transaction.receiving_currency,
                transaction.payment_format,
            )
            for transaction in transactions
        ],
    )


def create_staging_database(
    normalized_csv_path: str | Path,
    staging_database_path: str | Path,
) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(str(staging_database_path))
    try:
        create_source_transactions_table(connection)
        connection.execute(
            """
            INSERT INTO source_transactions
            SELECT
                transaction_ref,
                CAST(timestamp AS TIMESTAMP),
                from_bank,
                from_account,
                to_bank,
                to_account,
                amount_paid,
                payment_currency,
                amount_received,
                receiving_currency,
                payment_format
            FROM read_csv(?, header = true, all_varchar = true)
            """,
            [str(normalized_csv_path)],
        )
        return connection
    except Exception:
        connection.close()
        raise


def assert_no_duplicate_transaction_refs(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    duplicates = connection.execute(
        """
        SELECT transaction_ref, COUNT(*) AS duplicate_count
        FROM source_transactions
        GROUP BY transaction_ref
        HAVING COUNT(*) > 1
        ORDER BY transaction_ref
        LIMIT 20
        """
    ).fetchall()
    if duplicates:
        diagnostic = ", ".join(f"{reference} ({count})" for reference, count in duplicates)
        raise DuplicateTransactionReferenceError(
            f"duplicate/colliding txref-v1 values detected: {diagnostic}"
        )


def unique_runtime_transactions(
    case_slices: tuple[CaseSlice, ...],
) -> dict[str, RuntimeTransaction]:
    transactions: dict[str, RuntimeTransaction] = {}
    for case_slice in case_slices:
        for transaction in (case_slice.selected, *case_slice.history):
            prior = transactions.get(transaction.transaction_ref)
            if prior is not None and prior != transaction:
                raise RuntimeValidationError(
                    "one transaction_ref resolved to different permitted transaction values: "
                    f"{transaction.transaction_ref}"
                )
            transactions[transaction.transaction_ref] = transaction
    return transactions


def _create_runtime_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE cases (
            case_ref TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            selected_transaction_ref TEXT NOT NULL
        );

        CREATE TABLE transactions (
            transaction_ref TEXT PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            from_bank TEXT NOT NULL,
            from_account TEXT NOT NULL,
            to_bank TEXT NOT NULL,
            to_account TEXT NOT NULL,
            amount_paid DECIMAL(38, 18) NOT NULL,
            payment_currency TEXT NOT NULL,
            amount_received DECIMAL(38, 18) NOT NULL,
            receiving_currency TEXT NOT NULL,
            payment_format TEXT NOT NULL
        );

        CREATE TABLE case_transactions (
            case_ref TEXT NOT NULL,
            transaction_ref TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('selected', 'history')),
            UNIQUE (case_ref, transaction_ref)
        );

        CREATE TABLE entities (
            bank TEXT NOT NULL,
            account TEXT NOT NULL,
            entity_type TEXT NOT NULL CHECK (entity_type IN ('Person', 'Merchant')),
            UNIQUE (bank, account)
        );
        """
    )


def _populate_runtime_database(
    connection: duckdb.DuckDBPyConnection,
    case_slices: tuple[CaseSlice, ...],
    entities: Mapping[tuple[str, str], str],
) -> None:
    transactions = unique_runtime_transactions(case_slices)
    connection.executemany(
        "INSERT INTO cases VALUES (?, ?, ?)",
        [
            (
                case_slice.case.case_ref,
                case_slice.case.display_name,
                case_slice.case.selected_transaction_ref,
            )
            for case_slice in case_slices
        ],
    )
    connection.executemany(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                transaction.transaction_ref,
                transaction.timestamp,
                transaction.from_bank,
                transaction.from_account,
                transaction.to_bank,
                transaction.to_account,
                transaction.amount_paid,
                transaction.payment_currency,
                transaction.amount_received,
                transaction.receiving_currency,
                transaction.payment_format,
            )
            for transaction in sorted(
                transactions.values(), key=lambda item: item.transaction_ref
            )
        ],
    )
    case_transaction_rows: list[tuple[str, str, str]] = []
    for case_slice in case_slices:
        case_transaction_rows.append(
            (case_slice.case.case_ref, case_slice.selected.transaction_ref, "selected")
        )
        case_transaction_rows.extend(
            (case_slice.case.case_ref, transaction.transaction_ref, "history")
            for transaction in case_slice.history
        )
    connection.executemany(
        "INSERT INTO case_transactions VALUES (?, ?, ?)",
        sorted(case_transaction_rows),
    )
    connection.executemany(
        "INSERT INTO entities VALUES (?, ?, ?)",
        [
            (bank, account, entity_type)
            for (bank, account), entity_type in sorted(entities.items())
        ],
    )


def write_runtime_database_atomic(
    output_path: str | Path,
    case_slices: tuple[CaseSlice, ...],
    entities: Mapping[tuple[str, str], str],
    *,
    expected_demo_history: int | None = 74,
) -> RuntimeValidationReport:
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    temporary_path.unlink()
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        connection = duckdb.connect(str(temporary_path))
        _create_runtime_schema(connection)
        _populate_runtime_database(connection, case_slices, entities)
        report = validate_runtime_connection(
            connection, expected_demo_history=expected_demo_history
        )
        connection.close()
        connection = None
        os.replace(temporary_path, destination)
        return report
    except Exception:
        if connection is not None:
            connection.close()
        temporary_path.unlink(missing_ok=True)
        raise

