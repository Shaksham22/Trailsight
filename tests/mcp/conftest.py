from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pytest

from trailsight.data.runtime_repository import RuntimeRepository
from trailsight.domain.service import InvestigationService


def txref(index: int) -> str:
    return f"tsx_{index:064x}"


def transaction(
    index: int,
    timestamp: datetime,
    *,
    from_bank: str = "Sender Bank",
    from_account: str = "A016568",
    to_bank: str = "Receiver Bank",
    to_account: str = "A013644",
    amount_paid: str = "10.00",
    payment_currency: str = "CNY",
    amount_received: str = "1.00",
    receiving_currency: str = "USD",
    payment_format: str = "Cash",
) -> dict[str, Any]:
    return {
        "transaction_ref": txref(index),
        "timestamp": timestamp,
        "from_bank": from_bank,
        "from_account": from_account,
        "to_bank": to_bank,
        "to_account": to_account,
        "amount_paid": Decimal(amount_paid),
        "payment_currency": payment_currency,
        "amount_received": Decimal(amount_received),
        "receiving_currency": receiving_currency,
        "payment_format": payment_format,
    }


def selected_transaction(**overrides: Any) -> dict[str, Any]:
    values = transaction(
        10_000,
        datetime(2025, 2, 1, 12, 0, 0),
        amount_paid="69.54",
        amount_received="9.40",
    )
    values.update(overrides)
    return values


def build_runtime_database(
    path: Path,
    *,
    selected: dict[str, Any] | None = None,
    history: Iterable[dict[str, Any]] = (),
    other_transactions: Iterable[dict[str, Any]] = (),
    case_ref: str = "demo-01",
) -> Path:
    selected_row = selected_transaction() if selected is None else selected
    history_rows = list(history)
    all_rows = [selected_row, *history_rows, *list(other_transactions)]

    connection = duckdb.connect(str(path))
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
            amount_paid DECIMAL(38, 10) NOT NULL,
            payment_currency TEXT NOT NULL,
            amount_received DECIMAL(38, 10) NOT NULL,
            receiving_currency TEXT NOT NULL,
            payment_format TEXT NOT NULL
        );
        CREATE TABLE case_transactions (
            case_ref TEXT NOT NULL,
            transaction_ref TEXT NOT NULL,
            role TEXT NOT NULL,
            UNIQUE (case_ref, transaction_ref)
        );
        CREATE TABLE entities (
            bank TEXT NOT NULL,
            account TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            UNIQUE (bank, account)
        );
        """
    )
    connection.execute(
        "INSERT INTO cases VALUES (?, 'Demo 01', ?)",
        [case_ref, selected_row["transaction_ref"]],
    )
    for row in all_rows:
        connection.execute(
            """
            INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["transaction_ref"],
                row["timestamp"],
                row["from_bank"],
                row["from_account"],
                row["to_bank"],
                row["to_account"],
                row["amount_paid"],
                row["payment_currency"],
                row["amount_received"],
                row["receiving_currency"],
                row["payment_format"],
            ],
        )
    connection.execute(
        "INSERT INTO case_transactions VALUES (?, ?, 'selected')",
        [case_ref, selected_row["transaction_ref"]],
    )
    for row in history_rows:
        connection.execute(
            "INSERT INTO case_transactions VALUES (?, ?, 'history')",
            [case_ref, row["transaction_ref"]],
        )

    identities = {
        (row["from_bank"], row["from_account"]) for row in all_rows
    } | {(row["to_bank"], row["to_account"]) for row in all_rows}
    selected_sender = (selected_row["from_bank"], selected_row["from_account"])
    for bank, account in sorted(identities):
        entity_type = "Person" if (bank, account) == selected_sender else "Merchant"
        connection.execute(
            "INSERT INTO entities VALUES (?, ?, ?)",
            [bank, account, entity_type],
        )
    connection.close()
    return path


@pytest.fixture
def service_builder(
    tmp_path: Path,
) -> Callable[..., tuple[InvestigationService, RuntimeRepository, Path]]:
    repositories: list[RuntimeRepository] = []
    counter = 0

    def build(**kwargs: Any) -> tuple[InvestigationService, RuntimeRepository, Path]:
        nonlocal counter
        counter += 1
        path = build_runtime_database(tmp_path / f"runtime-{counter}.duckdb", **kwargs)
        repository = RuntimeRepository(path)
        repositories.append(repository)
        return InvestigationService(repository), repository, path

    yield build

    for repository in repositories:
        repository.close()
