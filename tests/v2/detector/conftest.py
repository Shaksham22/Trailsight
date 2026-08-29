from __future__ import annotations

import csv
from pathlib import Path

import pytest

from trailsight_v2.data.constants import REQUIRED_SOURCE_COLUMNS
from trailsight_v2.data.prepare import prepare_runtime_database


def source_row(**overrides: str) -> dict[str, str]:
    row = {
        "Timestamp": "2022/09/01 00:20",
        "From Bank": "001",
        "Account": "A",
        "To Bank": "002",
        "Account.1": "B",
        "Amount Received": "100.00",
        "Receiving Currency": "USD",
        "Amount Paid": "100",
        "Payment Currency": "USD",
        "Payment Format": "ACH",
        "Is Laundering": "0",
    }
    row.update(overrides)
    return row


def multi_day_rows() -> list[dict[str, str]]:
    return [
        source_row(),
        source_row(
            **{
                "Timestamp": "2022/09/01 08:00",
                "From Bank": "002",
                "Account": "B",
                "To Bank": "003",
                "Account.1": "C",
            }
        ),
        source_row(
            **{
                "Timestamp": "2022/09/02 00:00",
                "From Bank": "003",
                "Account": "C",
                "To Bank": "004",
                "Account.1": "D",
            }
        ),
        source_row(
            **{
                "Timestamp": "2022/09/02 16:00",
                "From Bank": "001",
                "Account": "A",
                "To Bank": "004",
                "Account.1": "D",
                "Is Laundering": "1",
            }
        ),
    ]


@pytest.fixture
def make_detector_source(tmp_path: Path):
    def factory(
        rows: list[dict[str, str]] | None = None,
        *,
        filename: str = "HI-Small_Trans.csv",
    ) -> Path:
        path = tmp_path / filename
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=REQUIRED_SOURCE_COLUMNS,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows or multi_day_rows())
        return path

    return factory


@pytest.fixture
def prepared_detector_db(make_detector_source, tmp_path: Path) -> tuple[Path, Path]:
    source = make_detector_source()
    database = tmp_path / "runtime.duckdb"
    prepare_runtime_database(source_path=source, output_path=database)
    return database, source

