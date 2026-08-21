from __future__ import annotations

import csv
from pathlib import Path

import pytest

from trailsight_data.source import REQUIRED_TRANSACTION_HEADERS


def write_csv(path: Path, header: tuple[str, ...] | list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


@pytest.fixture
def make_source(tmp_path: Path):
    def factory(
        *,
        tx_header: tuple[str, ...] | list[str] = REQUIRED_TRANSACTION_HEADERS,
        tx_rows: list[list[str]] | None = None,
    ) -> Path:
        source_root = tmp_path / "TransXion"
        write_csv(
            source_root / "data" / "tx.csv",
            tx_header,
            tx_rows
            or [
                [
                    "2025-01-01 00:00:29",
                    "3295718",
                    "A009852",
                    "2657408",
                    "A010012",
                    "4.4",
                    "CHF",
                    "8.06",
                    "AUD",
                    "Mobile",
                    "0",
                ]
            ],
        )
        write_csv(
            source_root / "data" / "person.csv",
            ["person_id", "bank_account_number", "bank", "person_age"],
            [["p1", "A009852", "3295718", "22"]],
        )
        write_csv(
            source_root / "data" / "merchant.csv",
            ["merchant_id", "bank_account_number", "bank", "description"],
            [["m1", "A010012", "2657408", "merchant"]],
        )
        return source_root

    return factory

