from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb


def txref(index: int) -> str:
    return f"tsx_{index:064x}"


def build_primary_runtime_database(path: Path) -> Path:
    """Build a compact, source-shaped replica of the approved demo fixture."""

    selected_timestamp = datetime(2025, 5, 8, 16, 18, 46)
    selected = {
        "transaction_ref": txref(10_000),
        "timestamp": selected_timestamp,
        "from_bank": "Demo Sender Bank",
        "from_account": "A016568",
        "to_bank": "Demo Counterparty Bank",
        "to_account": "A013644",
        "amount_paid": Decimal("69.54"),
        "payment_currency": "CNY",
        "amount_received": Decimal("9.40"),
        "receiving_currency": "USD",
        "payment_format": "Cash",
    }

    # 67 of 70 CNY amounts are <= 69.54, and the middle pair is 15.09/15.10.
    cny_amounts = (
        [Decimal("10")] * 34
        + [Decimal("15.09"), Decimal("15.10")]
        + [Decimal("20")] * 31
        + [Decimal("100")] * 3
    )
    history: list[dict[str, object]] = []
    for index, amount in enumerate(cny_amounts, start=1):
        history.append(
            {
                "transaction_ref": txref(index),
                "timestamp": selected_timestamp - timedelta(days=index),
                "from_bank": selected["from_bank"],
                "from_account": selected["from_account"],
                "to_bank": "Historical Counterparty Bank",
                "to_account": f"A{300_000 + (20 * index) + 1:06d}",
                "amount_paid": amount,
                "payment_currency": "CNY",
                "amount_received": Decimal("1"),
                "receiving_currency": "USD",
                "payment_format": "Transfer",
            }
        )
    for offset in range(1, 5):
        index = 70 + offset
        history.append(
            {
                "transaction_ref": txref(index),
                "timestamp": selected_timestamp - timedelta(days=index),
                "from_bank": selected["from_bank"],
                "from_account": selected["from_account"],
                "to_bank": "Historical Counterparty Bank",
                "to_account": f"A{400_000 + (20 * offset) + 2:06d}",
                "amount_paid": Decimal("12"),
                "payment_currency": "EUR",
                "amount_received": Decimal("13"),
                "receiving_currency": "USD",
                "payment_format": "Transfer",
            }
        )

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
        "INSERT INTO cases VALUES ('demo-01', 'Demo 01', ?)",
        [selected["transaction_ref"]],
    )

    rows = [selected, *history]
    for row in rows:
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
        "INSERT INTO case_transactions VALUES ('demo-01', ?, 'selected')",
        [selected["transaction_ref"]],
    )
    connection.executemany(
        "INSERT INTO case_transactions VALUES ('demo-01', ?, 'history')",
        [[row["transaction_ref"]] for row in history],
    )

    identities = {
        (str(row["from_bank"]), str(row["from_account"])) for row in rows
    } | {(str(row["to_bank"]), str(row["to_account"])) for row in rows}
    for bank, account in sorted(identities):
        entity_type = (
            "Person"
            if (bank, account)
            == (selected["from_bank"], selected["from_account"])
            else "Merchant"
        )
        connection.execute(
            "INSERT INTO entities VALUES (?, ?, ?)", [bank, account, entity_type]
        )
    connection.close()
    return path


def build_runtime_database(tmp_path: Path) -> Path:
    return build_primary_runtime_database(tmp_path / "trailsight.duckdb")


def build_static_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "dist"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text(
        "<!doctype html><html><body>Trailsight integration build</body></html>",
        encoding="utf-8",
    )
    (directory / "assets" / "app.js").write_text(
        "window.TRAILSIGHT_STATIC_TEST = true;\n", encoding="utf-8"
    )
    return directory
