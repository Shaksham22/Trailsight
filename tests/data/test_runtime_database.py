from __future__ import annotations

import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from trailsight_data.database import (
    assert_no_duplicate_transaction_refs,
    create_source_transactions_table,
    insert_staging_transactions,
    write_runtime_database_atomic,
)
from trailsight_data.errors import DuplicateTransactionReferenceError
from trailsight_data.models import CaseDefinition, CaseSlice, RuntimeTransaction
from trailsight_data.validation import EXPECTED_TABLE_COLUMNS, validate_runtime_database


def runtime_transaction(
    reference_digit: str,
    timestamp: datetime,
    *,
    to_account: str,
    amount_paid: str,
) -> RuntimeTransaction:
    return RuntimeTransaction(
        transaction_ref="tsx_" + reference_digit * 64,
        timestamp=timestamp,
        from_bank="B1",
        from_account="A000001",
        to_bank="B2",
        to_account=to_account,
        amount_paid=Decimal(amount_paid),
        payment_currency="USD",
        amount_received=Decimal(amount_paid),
        receiving_currency="USD",
        payment_format="Card",
    )


def make_database(tmp_path: Path) -> Path:
    selected_time = datetime(2025, 1, 2)
    history = runtime_transaction(
        "1", selected_time - timedelta(days=1), to_account="A000002", amount_paid="1.10"
    )
    selected = runtime_transaction(
        "2", selected_time, to_account="A000003", amount_paid="2.20"
    )
    case = CaseDefinition("case-01", "Case 01", selected.transaction_ref, "test_fixture")
    output = tmp_path / "runtime.duckdb"
    write_runtime_database_atomic(
        output,
        (CaseSlice(case, selected, (history,)),),
        {
            ("B1", "A000001"): "Person",
            ("B2", "A000002"): "Merchant",
            ("B2", "A000003"): "Merchant",
        },
        expected_demo_history=None,
    )
    return output


def test_runtime_schema_firewall_and_exact_decimal_semantics(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    report = validate_runtime_database(database, expected_demo_history=None)
    assert report.table_row_counts == {
        "cases": 1,
        "transactions": 2,
        "case_transactions": 2,
        "entities": 3,
    }
    connection = duckdb.connect(str(database), read_only=True)
    try:
        columns_by_table = {
            table: tuple(
                row[0]
                for row in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'main' AND table_name = ?
                    ORDER BY ordinal_position
                    """,
                    [table],
                ).fetchall()
            )
            for table in EXPECTED_TABLE_COLUMNS
        }
        amount = connection.execute(
            "SELECT amount_paid FROM transactions WHERE transaction_ref = ?",
            ["tsx_" + "1" * 64],
        ).fetchone()[0]
    finally:
        connection.close()
    assert columns_by_table == EXPECTED_TABLE_COLUMNS
    assert all("is_laundering" not in columns for columns in columns_by_table.values())
    assert columns_by_table["entities"] == ("bank", "account", "entity_type")
    assert amount == Decimal("1.10")


def test_runtime_roles_are_constrained_and_case_has_one_selected(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    connection = duckdb.connect(str(database))
    try:
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM case_transactions
            WHERE case_ref = 'case-01' AND role = 'selected'
            """
        ).fetchone()[0] == 1
        with pytest.raises(duckdb.ConstraintException):
            connection.execute(
                "INSERT INTO case_transactions VALUES ('case-01', ?, 'future')",
                ["tsx_" + "3" * 64],
            )
    finally:
        connection.close()


def test_duplicate_txrefs_fail_before_runtime_write() -> None:
    timestamp = datetime(2025, 1, 1)
    duplicate = runtime_transaction(
        "4", timestamp, to_account="A000004", amount_paid="4.00"
    )
    connection = duckdb.connect(":memory:")
    try:
        create_source_transactions_table(connection)
        insert_staging_transactions(connection, [duplicate, duplicate])
        with pytest.raises(DuplicateTransactionReferenceError, match=duplicate.transaction_ref):
            assert_no_duplicate_transaction_refs(connection)
    finally:
        connection.close()


def test_configured_real_runtime_database() -> None:
    configured = os.environ.get("TRAILSIGHT_DB_PATH")
    if not configured:
        pytest.skip("TRAILSIGHT_DB_PATH is not configured")
    report = validate_runtime_database(Path(configured), expected_demo_history=74)
    assert report.table_row_counts["cases"] >= 4
    assert report.history_row_counts["demo-01"] == 74
