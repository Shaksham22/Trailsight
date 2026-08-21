"""Read-only repository for the frozen WP01 DuckDB contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import re
from threading import RLock
from typing import Any, Iterable

import duckdb

from trailsight.contracts import EntityType
from trailsight.errors import CaseNotFoundError, DataIntegrityError


@dataclass(frozen=True, slots=True)
class CaseRecord:
    case_ref: str
    display_name: str
    selected_transaction_ref: str


@dataclass(frozen=True, slots=True)
class RuntimeTransaction:
    transaction_ref: str
    timestamp: datetime
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount_paid: Decimal
    payment_currency: str
    amount_received: Decimal
    receiving_currency: str
    payment_format: str


_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "cases": {"case_ref", "display_name", "selected_transaction_ref"},
    "transactions": {
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
    },
    "case_transactions": {"case_ref", "transaction_ref", "role"},
    "entities": {"bank", "account", "entity_type"},
}

_TRANSACTION_PROJECTION = """
    t.transaction_ref,
    t.timestamp,
    t.from_bank,
    t.from_account,
    t.to_bank,
    t.to_account,
    t.amount_paid,
    t.payment_currency,
    t.amount_received,
    t.receiving_currency,
    t.payment_format
"""

_CASE_REF = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_TRANSACTION_REF = re.compile(r"^tsx_[0-9a-f]{64}$")


class RuntimeRepository:
    """Retrieve runtime rows from one DuckDB connection opened read-only."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._lock = RLock()
        if not self.database_path.is_file():
            raise DataIntegrityError("Configured runtime DuckDB does not exist")

        try:
            self._connection = duckdb.connect(
                database=str(self.database_path),
                read_only=True,
            )
            self._connection.execute("SELECT 1").fetchone()
            self._validate_schema()
        except DataIntegrityError:
            self._close_after_failed_initialization()
            raise
        except Exception as exc:
            self._close_after_failed_initialization()
            raise DataIntegrityError(
                "Configured runtime DuckDB could not be opened read-only"
            ) from exc

    def _close_after_failed_initialization(self) -> None:
        connection = getattr(self, "_connection", None)
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def _validate_schema(self) -> None:
        rows = self._fetchall(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'main'
            ORDER BY table_name, ordinal_position
            """
        )
        schema: dict[str, dict[str, str]] = {}
        for table_name, column_name, data_type in rows:
            schema.setdefault(str(table_name), {})[str(column_name)] = str(data_type)

        forbidden_columns = [
            f"{table}.{column}"
            for table, columns in schema.items()
            for column in columns
            if column.casefold() == "is laundering"
        ]
        if forbidden_columns:
            raise DataIntegrityError(
                "Forbidden hidden-label column exists in the runtime database"
            )

        missing_tables = sorted(set(_REQUIRED_COLUMNS) - set(schema))
        if missing_tables:
            raise DataIntegrityError("Runtime DuckDB is missing required tables")

        for table_name, required_columns in _REQUIRED_COLUMNS.items():
            present_columns = set(schema[table_name])
            if not required_columns.issubset(present_columns):
                raise DataIntegrityError(
                    f"Runtime table {table_name!r} is missing required columns"
                )

        transaction_types = schema["transactions"]
        if transaction_types["timestamp"] != "TIMESTAMP":
            raise DataIntegrityError("Runtime transaction timestamp must be TIMESTAMP")
        for amount_column in ("amount_paid", "amount_received"):
            if not transaction_types[amount_column].startswith("DECIMAL"):
                raise DataIntegrityError(
                    "Runtime transaction monetary values must use DECIMAL"
                )

    def close(self) -> None:
        """Close the read-only connection."""

        with self._lock:
            self._connection.close()

    def list_cases(self) -> list[CaseRecord]:
        rows = self._fetchall(
            """
            SELECT case_ref, display_name, selected_transaction_ref
            FROM cases
            ORDER BY case_ref ASC
            """
        )
        return [self._row_to_case(row) for row in rows]

    def get_case(self, case_ref: str) -> CaseRecord:
        rows = self._fetchall(
            """
            SELECT case_ref, display_name, selected_transaction_ref
            FROM cases
            WHERE case_ref = ?
            """,
            [case_ref],
        )
        if not rows:
            raise CaseNotFoundError(case_ref)
        if len(rows) != 1:
            raise DataIntegrityError("Runtime case identity is not unique")
        return self._row_to_case(rows[0])

    def get_selected_transaction(self, case_ref: str) -> RuntimeTransaction:
        case = self.get_case(case_ref)
        rows = self._fetchall(
            f"""
            SELECT {_TRANSACTION_PROJECTION}, ct.transaction_ref
            FROM case_transactions AS ct
            JOIN transactions AS t
              ON t.transaction_ref = ct.transaction_ref
            WHERE ct.case_ref = ?
              AND ct.role = 'selected'
            """,
            [case_ref],
        )
        if len(rows) != 1:
            raise DataIntegrityError(
                "A runtime case must have exactly one selected transaction"
            )
        if str(rows[0][11]) != case.selected_transaction_ref:
            raise DataIntegrityError(
                "Case metadata and selected case transaction do not match"
            )
        return self._row_to_transaction(rows[0][:11])

    def get_case_history(
        self,
        case_ref: str,
        *,
        sender_bank: str,
        sender_account: str,
    ) -> list[RuntimeTransaction]:
        """Return only case-permitted history after sender-integrity validation."""

        self.get_case(case_ref)
        rows = self._fetchall(
            f"""
            SELECT {_TRANSACTION_PROJECTION}
            FROM case_transactions AS ct
            JOIN transactions AS t
              ON t.transaction_ref = ct.transaction_ref
            WHERE ct.case_ref = ?
              AND ct.role = 'history'
            ORDER BY t.timestamp ASC, t.transaction_ref ASC
            """,
            [case_ref],
        )
        transactions = [self._row_to_transaction(row) for row in rows]
        for transaction in transactions:
            if (
                transaction.from_bank != sender_bank
                or transaction.from_account != sender_account
            ):
                raise DataIntegrityError(
                    "Case history contains a transaction from a different sender"
                )
        return transactions

    def get_entity_type(self, bank: str, account: str) -> EntityType:
        rows = self._fetchall(
            """
            SELECT entity_type
            FROM entities
            WHERE bank = ? AND account = ?
            """,
            [bank, account],
        )
        if len(rows) != 1:
            raise DataIntegrityError(
                "Runtime transaction entity identity cannot be resolved uniquely"
            )
        try:
            return EntityType(str(rows[0][0]))
        except ValueError as exc:
            raise DataIntegrityError("Runtime entity type is invalid") from exc

    @staticmethod
    def _row_to_case(row: Iterable[Any]) -> CaseRecord:
        values = tuple(row)
        if len(values) != 3 or not all(isinstance(value, str) for value in values):
            raise DataIntegrityError("Runtime case row has invalid values")
        if _CASE_REF.fullmatch(values[0]) is None:
            raise DataIntegrityError("Runtime case reference has an invalid format")
        if _TRANSACTION_REF.fullmatch(values[2]) is None:
            raise DataIntegrityError(
                "Runtime selected transaction reference has an invalid format"
            )
        return CaseRecord(*values)

    @staticmethod
    def _row_to_transaction(row: Iterable[Any]) -> RuntimeTransaction:
        values = tuple(row)
        if len(values) != 11:
            raise DataIntegrityError("Runtime transaction row has invalid shape")
        if not isinstance(values[1], datetime):
            raise DataIntegrityError("Runtime transaction timestamp is invalid")
        if values[1].tzinfo is not None:
            raise DataIntegrityError("Runtime transaction timestamp must be timezone-naive")
        if not isinstance(values[6], Decimal) or not isinstance(values[8], Decimal):
            raise DataIntegrityError("Runtime transaction amounts must use DECIMAL")
        text_indexes = (0, 2, 3, 4, 5, 7, 9, 10)
        if not all(isinstance(values[index], str) for index in text_indexes):
            raise DataIntegrityError("Runtime transaction text values are invalid")
        if _TRANSACTION_REF.fullmatch(values[0]) is None:
            raise DataIntegrityError("Runtime transaction reference has an invalid format")
        return RuntimeTransaction(*values)

    def _fetchall(
        self, statement: str, parameters: list[Any] | None = None
    ) -> list[tuple[Any, ...]]:
        with self._lock:
            if parameters is None:
                return self._connection.execute(statement).fetchall()
            return self._connection.execute(statement, parameters).fetchall()
