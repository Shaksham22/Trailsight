from __future__ import annotations

import csv
from pathlib import Path

import pytest

from trailsight_v2.data.constants import REQUIRED_SOURCE_COLUMNS


def source_row(**overrides: str) -> dict[str, str]:
    row = {
        "Timestamp": "2022/09/01 00:20",
        "From Bank": "001",
        "Account": "A001",
        "To Bank": "Bank-B",
        "Account.1": "A002",
        "Amount Received": "100.00",
        "Receiving Currency": "USD",
        "Amount Paid": "100",
        "Payment Currency": "USD",
        "Payment Format": "ACH",
        "Is Laundering": "0",
    }
    row.update(overrides)
    return row


@pytest.fixture
def make_ibm_csv(tmp_path: Path):
    def factory(
        rows: list[dict[str, str]] | None = None,
        *,
        header: tuple[str, ...] = REQUIRED_SOURCE_COLUMNS,
        filename: str = "HI-Small_Trans.csv",
    ) -> Path:
        path = tmp_path / filename
        actual_rows = rows or [source_row()]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
            writer.writeheader()
            for row in actual_rows:
                writer.writerow({name: row.get(name, "") for name in header})
        return path

    return factory
