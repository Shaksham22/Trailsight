"""Post-write validation for the frozen runtime database."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import duckdb

from trailsight_data.errors import RuntimeValidationError
from trailsight_data.models import RuntimeValidationReport

EXPECTED_TABLE_COLUMNS = {
    "cases": ("case_ref", "display_name", "selected_transaction_ref"),
    "transactions": (
        "transaction_ref",
        "timestamp",
        "from_bank",
        "from_account",
        "to_bank",
        "to_account",
        "amount_paid",
        "payment_currency",
        "amount_received",
        "receiving_currency",
        "payment_format",
    ),
    "case_transactions": ("case_ref", "transaction_ref", "role"),
    "entities": ("bank", "account", "entity_type"),
}

PROHIBITED_PROFILE_COLUMNS = frozenset(
    {
        "person_id",
        "merchant_id",
        "person_age",
        "person_education",
        "person_gender",
        "person_marital_status",
        "person_occupation",
        "description",
        "type",
        "registered_capital",
        "industry",
        "operating_status",
        "establishment_date",
        "legal_representative_id",
    }
)


def _fail(message: str) -> None:
    raise RuntimeValidationError(message)


def _validate_schema(connection: duckdb.DuckDBPyConnection) -> None:
    table_names = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
            """
        ).fetchall()
    }
    if table_names != set(EXPECTED_TABLE_COLUMNS):
        _fail(
            "runtime table mismatch: "
            f"expected {sorted(EXPECTED_TABLE_COLUMNS)}, actual {sorted(table_names)}"
        )

    all_columns: set[str] = set()
    for table_name, expected_columns in EXPECTED_TABLE_COLUMNS.items():
        actual_columns = tuple(
            str(row[0])
            for row in connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'main' AND table_name = ?
                ORDER BY ordinal_position
                """,
                [table_name],
            ).fetchall()
        )
        if actual_columns != expected_columns:
            _fail(
                f"runtime columns mismatch for {table_name}: "
                f"expected {expected_columns}, actual {actual_columns}"
            )
        all_columns.update(actual_columns)

    normalized_columns = {name.lower().replace("_", " ") for name in all_columns}
    if "is laundering" in normalized_columns:
        _fail("hidden-label firewall failed: Is Laundering is present")
    prohibited = PROHIBITED_PROFILE_COLUMNS.intersection(all_columns)
    if prohibited:
        _fail(f"prohibited profile columns are present: {sorted(prohibited)}")

    amount_types = dict(
        connection.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = 'transactions'
              AND column_name IN ('amount_paid', 'amount_received')
            """
        ).fetchall()
    )
    if set(amount_types) != {"amount_paid", "amount_received"} or any(
        not str(data_type).startswith("DECIMAL") for data_type in amount_types.values()
    ):
        _fail(f"transaction amounts are not exact DECIMAL columns: {amount_types}")


def _validate_case_integrity(
    connection: duckdb.DuckDBPyConnection,
) -> dict[str, int]:
    cases = connection.execute(
        "SELECT case_ref, selected_transaction_ref FROM cases ORDER BY case_ref"
    ).fetchall()
    if not cases:
        _fail("runtime database contains no cases")

    history_counts: dict[str, int] = {}
    for case_ref, selected_ref in cases:
        transaction_count = connection.execute(
            "SELECT COUNT(*) FROM transactions WHERE transaction_ref = ?", [selected_ref]
        ).fetchone()[0]
        if transaction_count != 1:
            _fail(
                f"case {case_ref} selected transaction appears {transaction_count} times"
            )

        selected_roles = connection.execute(
            """
            SELECT transaction_ref
            FROM case_transactions
            WHERE case_ref = ? AND role = 'selected'
            """,
            [case_ref],
        ).fetchall()
        if selected_roles != [(selected_ref,)]:
            _fail(f"case {case_ref} does not have exactly its selected transaction role")

        invalid_history = connection.execute(
            """
            SELECT COUNT(*)
            FROM case_transactions AS case_tx
            JOIN transactions AS history_tx
              ON history_tx.transaction_ref = case_tx.transaction_ref
            JOIN transactions AS selected_tx
              ON selected_tx.transaction_ref = ?
            WHERE case_tx.case_ref = ?
              AND case_tx.role = 'history'
              AND (
                    history_tx.timestamp >= selected_tx.timestamp
                 OR history_tx.from_bank <> selected_tx.from_bank
                 OR history_tx.from_account <> selected_tx.from_account
              )
            """,
            [selected_ref, case_ref],
        ).fetchone()[0]
        if invalid_history:
            _fail(f"case {case_ref} contains {invalid_history} invalid history rows")

        history_counts[str(case_ref)] = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM case_transactions
                WHERE case_ref = ? AND role = 'history'
                """,
                [case_ref],
            ).fetchone()[0]
        )

    orphan_case_transactions = connection.execute(
        """
        SELECT COUNT(*)
        FROM case_transactions AS case_tx
        LEFT JOIN cases ON cases.case_ref = case_tx.case_ref
        LEFT JOIN transactions ON transactions.transaction_ref = case_tx.transaction_ref
        WHERE cases.case_ref IS NULL OR transactions.transaction_ref IS NULL
        """
    ).fetchone()[0]
    if orphan_case_transactions:
        _fail(f"runtime database has {orphan_case_transactions} orphan case transaction rows")

    missing_entities = connection.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT from_bank AS bank, from_account AS account FROM transactions
            UNION
            SELECT to_bank AS bank, to_account AS account FROM transactions
        ) AS identities
        LEFT JOIN entities
          ON entities.bank = identities.bank AND entities.account = identities.account
        WHERE entities.bank IS NULL
        """
    ).fetchone()[0]
    if missing_entities:
        _fail(f"runtime database has {missing_entities} transaction identities without entities")

    return history_counts


def _validate_eval_case_characteristics(connection: duckdb.DuckDBPyConnection) -> None:
    for case_ref, minimum, maximum in (
        ("eval-amount-insufficient-01", 0, 4),
        ("eval-amount-limited-01", 5, 19),
    ):
        exists = connection.execute(
            "SELECT COUNT(*) FROM cases WHERE case_ref = ?", [case_ref]
        ).fetchone()[0]
        if not exists:
            continue
        prior_same_currency = connection.execute(
            """
            SELECT COUNT(*)
            FROM cases
            JOIN transactions AS selected_tx
              ON selected_tx.transaction_ref = cases.selected_transaction_ref
            JOIN case_transactions AS case_tx
              ON case_tx.case_ref = cases.case_ref AND case_tx.role = 'history'
            JOIN transactions AS history_tx
              ON history_tx.transaction_ref = case_tx.transaction_ref
            WHERE cases.case_ref = ?
              AND history_tx.payment_currency = selected_tx.payment_currency
            """,
            [case_ref],
        ).fetchone()[0]
        if not minimum <= prior_same_currency <= maximum:
            _fail(
                f"case {case_ref} has {prior_same_currency} prior same-currency rows; "
                f"expected {minimum}..{maximum}"
            )

    repeat_case = "eval-repeat-counterparty-01"
    exists = connection.execute(
        "SELECT COUNT(*) FROM cases WHERE case_ref = ?", [repeat_case]
    ).fetchone()[0]
    if exists:
        previous_interactions = connection.execute(
            """
            SELECT COUNT(*)
            FROM cases
            JOIN transactions AS selected_tx
              ON selected_tx.transaction_ref = cases.selected_transaction_ref
            JOIN case_transactions AS case_tx
              ON case_tx.case_ref = cases.case_ref AND case_tx.role = 'history'
            JOIN transactions AS history_tx
              ON history_tx.transaction_ref = case_tx.transaction_ref
            WHERE cases.case_ref = ?
              AND history_tx.to_bank = selected_tx.to_bank
              AND history_tx.to_account = selected_tx.to_account
            """,
            [repeat_case],
        ).fetchone()[0]
        if previous_interactions < 1:
            _fail(f"case {repeat_case} has no previous interaction with its counterparty")


def _validate_demo(
    connection: duckdb.DuckDBPyConnection,
    *,
    expected_demo_history: int | None,
) -> None:
    demo_exists = connection.execute(
        "SELECT COUNT(*) FROM cases WHERE case_ref = 'demo-01'"
    ).fetchone()[0]
    if not demo_exists:
        if expected_demo_history is not None:
            _fail("required demo-01 case is absent")
        return

    row = connection.execute(
        """
        SELECT
            tx.from_account,
            tx.to_account,
            tx.amount_paid,
            tx.payment_currency,
            tx.amount_received,
            tx.receiving_currency,
            tx.payment_format
        FROM cases
        JOIN transactions AS tx
          ON tx.transaction_ref = cases.selected_transaction_ref
        WHERE cases.case_ref = 'demo-01'
        """
    ).fetchone()
    expected = (
        "A016568",
        "A013644",
        Decimal("69.54"),
        "CNY",
        Decimal("9.40"),
        "USD",
        "Cash",
    )
    if row != expected:
        _fail(f"demo-01 source-derived fixture mismatch: expected {expected}, actual {row}")

    if expected_demo_history is not None:
        history_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM case_transactions
            WHERE case_ref = 'demo-01' AND role = 'history'
            """
        ).fetchone()[0]
        if history_count != expected_demo_history:
            _fail(
                "demo-01 permitted history mismatch: "
                f"expected {expected_demo_history}, actual {history_count}"
            )


def validate_runtime_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    expected_demo_history: int | None = 74,
) -> RuntimeValidationReport:
    _validate_schema(connection)
    history_counts = _validate_case_integrity(connection)
    _validate_eval_case_characteristics(connection)
    _validate_demo(connection, expected_demo_history=expected_demo_history)
    row_counts = {
        table_name: int(
            connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        )
        for table_name in EXPECTED_TABLE_COLUMNS
    }
    return RuntimeValidationReport(
        table_row_counts=row_counts,
        history_row_counts=history_counts,
    )


def validate_runtime_database(
    database_path: str | Path,
    *,
    expected_demo_history: int | None = 74,
) -> RuntimeValidationReport:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise RuntimeValidationError(f"runtime database does not exist: {path}")
    connection = duckdb.connect(str(path), read_only=True)
    try:
        return validate_runtime_connection(
            connection, expected_demo_history=expected_demo_history
        )
    finally:
        connection.close()

