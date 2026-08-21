"""Deterministic case selection, catalog serialization, and past-only slicing."""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import yaml

from trailsight_data.errors import CaseSelectionError
from trailsight_data.models import CaseDefinition, CaseSlice, RuntimeTransaction

CASE_REF_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")

CASE_SPECS = (
    ("demo-01", "Demo 01", "fixed_demo"),
    (
        "eval-amount-insufficient-01",
        "Eval Amount Insufficient 01",
        "insufficient_amount_history",
    ),
    (
        "eval-amount-limited-01",
        "Eval Amount Limited 01",
        "limited_amount_history",
    ),
    (
        "eval-repeat-counterparty-01",
        "Eval Repeat Counterparty 01",
        "repeat_counterparty",
    ),
)

DEMO_TIMESTAMP = datetime(2025, 5, 8, 16, 18, 46)


def _one_transaction_ref(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[object] | None,
    *,
    selection_name: str,
) -> str:
    rows = connection.execute(query, parameters or []).fetchall()
    if len(rows) != 1:
        raise CaseSelectionError(
            f"{selection_name} selection expected exactly one row, found {len(rows)}"
        )
    return str(rows[0][0])


def _select_demo_ref(connection: duckdb.DuckDBPyConnection) -> str:
    return _one_transaction_ref(
        connection,
        """
        SELECT transaction_ref
        FROM source_transactions
        WHERE timestamp = ?
          AND from_account = ?
          AND to_account = ?
          AND amount_paid = ?
          AND payment_currency = ?
          AND amount_received = ?
          AND receiving_currency = ?
          AND payment_format = ?
        ORDER BY transaction_ref
        """,
        [
            DEMO_TIMESTAMP,
            "A016568",
            "A013644",
            "69.54",
            "CNY",
            "9.4",
            "USD",
            "Cash",
        ],
        selection_name="demo-01",
    )


def _select_amount_history_ref(
    connection: duckdb.DuckDBPyConnection,
    *,
    minimum: int,
    maximum: int,
    selection_name: str,
) -> str:
    return _one_transaction_ref(
        connection,
        """
        WITH transactions_per_timestamp AS (
            SELECT
                from_bank,
                from_account,
                payment_currency,
                timestamp,
                COUNT(*) AS rows_at_timestamp
            FROM source_transactions
            GROUP BY from_bank, from_account, payment_currency, timestamp
        ),
        prior_counts AS (
            SELECT
                from_bank,
                from_account,
                payment_currency,
                timestamp,
                COALESCE(
                    SUM(rows_at_timestamp) OVER (
                        PARTITION BY from_bank, from_account, payment_currency
                        ORDER BY timestamp
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ),
                    0
                ) AS prior_count
            FROM transactions_per_timestamp
        )
        SELECT source.transaction_ref
        FROM source_transactions AS source
        JOIN prior_counts AS prior
          ON prior.from_bank = source.from_bank
         AND prior.from_account = source.from_account
         AND prior.payment_currency = source.payment_currency
         AND prior.timestamp = source.timestamp
        WHERE prior.prior_count BETWEEN ? AND ?
        ORDER BY source.timestamp, source.transaction_ref
        LIMIT 1
        """,
        [minimum, maximum],
        selection_name=selection_name,
    )


def _select_repeat_counterparty_ref(connection: duckdb.DuckDBPyConnection) -> str:
    return _one_transaction_ref(
        connection,
        """
        WITH transactions_per_timestamp AS (
            SELECT
                from_bank,
                from_account,
                to_bank,
                to_account,
                timestamp,
                COUNT(*) AS rows_at_timestamp
            FROM source_transactions
            GROUP BY from_bank, from_account, to_bank, to_account, timestamp
        ),
        prior_counts AS (
            SELECT
                from_bank,
                from_account,
                to_bank,
                to_account,
                timestamp,
                COALESCE(
                    SUM(rows_at_timestamp) OVER (
                        PARTITION BY from_bank, from_account, to_bank, to_account
                        ORDER BY timestamp
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ),
                    0
                ) AS prior_count
            FROM transactions_per_timestamp
        )
        SELECT source.transaction_ref
        FROM source_transactions AS source
        JOIN prior_counts AS prior
          ON prior.from_bank = source.from_bank
         AND prior.from_account = source.from_account
         AND prior.to_bank = source.to_bank
         AND prior.to_account = source.to_account
         AND prior.timestamp = source.timestamp
        WHERE prior.prior_count >= 1
        ORDER BY source.timestamp, source.transaction_ref
        LIMIT 1
        """,
        None,
        selection_name="eval-repeat-counterparty-01",
    )


def select_required_cases(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[CaseDefinition, ...]:
    selected_refs = (
        _select_demo_ref(connection),
        _select_amount_history_ref(
            connection,
            minimum=0,
            maximum=4,
            selection_name="eval-amount-insufficient-01",
        ),
        _select_amount_history_ref(
            connection,
            minimum=5,
            maximum=19,
            selection_name="eval-amount-limited-01",
        ),
        _select_repeat_counterparty_ref(connection),
    )
    cases = tuple(
        CaseDefinition(
            case_ref=case_ref,
            display_name=display_name,
            selected_transaction_ref=selected_ref,
            selection_kind=selection_kind,
        )
        for (case_ref, display_name, selection_kind), selected_ref in zip(
            CASE_SPECS, selected_refs, strict=True
        )
    )
    validate_case_definitions(cases)
    return cases


def validate_case_definitions(cases: tuple[CaseDefinition, ...]) -> None:
    seen: set[str] = set()
    for case in cases:
        if CASE_REF_PATTERN.fullmatch(case.case_ref) is None:
            raise CaseSelectionError(f"invalid case_ref: {case.case_ref!r}")
        if case.case_ref in seen:
            raise CaseSelectionError(f"duplicate case_ref: {case.case_ref}")
        if not case.display_name or not case.selection_kind:
            raise CaseSelectionError(f"case metadata is incomplete: {case.case_ref}")
        if not re.fullmatch(r"tsx_[0-9a-f]{64}", case.selected_transaction_ref):
            raise CaseSelectionError(
                f"case {case.case_ref} has invalid selected_transaction_ref"
            )
        seen.add(case.case_ref)


def case_catalog_document(cases: tuple[CaseDefinition, ...]) -> dict[str, object]:
    validate_case_definitions(cases)
    return {
        "cases": [
            {
                "case_ref": case.case_ref,
                "display_name": case.display_name,
                "selected_transaction_ref": case.selected_transaction_ref,
                "selection_kind": case.selection_kind,
            }
            for case in cases
        ]
    }


def write_case_catalog_atomic(
    cases: tuple[CaseDefinition, ...],
    catalog_path: str | Path,
) -> None:
    destination = Path(catalog_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            yaml.safe_dump(
                case_catalog_document(cases),
                handle,
                sort_keys=False,
                allow_unicode=True,
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _runtime_transaction(row: tuple[object, ...]) -> RuntimeTransaction:
    return RuntimeTransaction(
        transaction_ref=str(row[0]),
        timestamp=row[1],
        from_bank=str(row[2]),
        from_account=str(row[3]),
        to_bank=str(row[4]),
        to_account=str(row[5]),
        amount_paid=Decimal(str(row[6])),
        payment_currency=str(row[7]),
        amount_received=Decimal(str(row[8])),
        receiving_currency=str(row[9]),
        payment_format=str(row[10]),
    )


def build_case_slices(
    connection: duckdb.DuckDBPyConnection,
    cases: tuple[CaseDefinition, ...],
) -> tuple[CaseSlice, ...]:
    validate_case_definitions(cases)
    slices: list[CaseSlice] = []
    projection = """
        transaction_ref, timestamp, from_bank, from_account, to_bank, to_account,
        amount_paid, payment_currency, amount_received, receiving_currency, payment_format
    """
    for case in cases:
        selected_rows = connection.execute(
            f"SELECT {projection} FROM source_transactions WHERE transaction_ref = ?",
            [case.selected_transaction_ref],
        ).fetchall()
        if len(selected_rows) != 1:
            raise CaseSelectionError(
                f"case {case.case_ref} selected reference resolved {len(selected_rows)} rows"
            )
        selected = _runtime_transaction(selected_rows[0])
        history_rows = connection.execute(
            f"""
            SELECT {projection}
            FROM source_transactions
            WHERE from_bank = ?
              AND from_account = ?
              AND timestamp < ?
            ORDER BY timestamp, transaction_ref
            """,
            [selected.from_bank, selected.from_account, selected.timestamp],
        ).fetchall()
        slices.append(
            CaseSlice(
                case=case,
                selected=selected,
                history=tuple(_runtime_transaction(row) for row in history_rows),
            )
        )
    return tuple(slices)
