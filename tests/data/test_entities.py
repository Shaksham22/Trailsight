from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from trailsight_data.entities import (
    build_entity_index,
    select_runtime_entities,
    synthetic_region_for_account,
)
from trailsight_data.errors import EntityMappingError
from trailsight_data.models import RuntimeTransaction


def write_profile(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def transaction() -> RuntimeTransaction:
    return RuntimeTransaction(
        transaction_ref="tsx_" + "1" * 64,
        timestamp=datetime(2025, 1, 1),
        from_bank="B1",
        from_account="A016568",
        to_bank="B2",
        to_account="A013644",
        amount_paid=Decimal("69.54"),
        payment_currency="CNY",
        amount_received=Decimal("9.40"),
        receiving_currency="USD",
        payment_format="Cash",
    )


def test_person_and_merchant_map_to_minimal_entity_types(tmp_path: Path) -> None:
    person = tmp_path / "person.csv"
    merchant = tmp_path / "merchant.csv"
    write_profile(
        person,
        ["person_id", "bank_account_number", "bank", "person_age", "person_gender"],
        [["p1", "A016568", "B1", "22", "female"]],
    )
    write_profile(
        merchant,
        ["merchant_id", "bank_account_number", "bank", "description", "industry"],
        [["m1", "A013644", "B2", "description", "industry"]],
    )
    index = build_entity_index(person, merchant)
    selected = select_runtime_entities(index, [transaction()])
    assert selected == {
        ("B1", "A016568"): "Person",
        ("B2", "A013644"): "Merchant",
    }
    assert all(len(identity) == 2 for identity in selected)


def test_conflicting_person_and_merchant_identity_fails(tmp_path: Path) -> None:
    person = tmp_path / "person.csv"
    merchant = tmp_path / "merchant.csv"
    header = ["id", "bank_account_number", "bank"]
    write_profile(person, header, [["p1", "A000001", "B1"]])
    write_profile(merchant, header, [["m1", "A000001", "B1"]])
    with pytest.raises(EntityMappingError, match="conflicting entity types"):
        build_entity_index(person, merchant)


def test_synthetic_region_uses_numeric_suffix_modulo_20() -> None:
    assert synthetic_region_for_account("A016568") == 8
    assert synthetic_region_for_account("A013644") == 4
    with pytest.raises(EntityMappingError, match="no numeric suffix"):
        synthetic_region_for_account("ACCOUNT")


def test_missing_runtime_entity_fails() -> None:
    with pytest.raises(EntityMappingError, match="missing from profiles"):
        select_runtime_entities({("B1", "A016568"): "Person"}, [transaction()])

