from __future__ import annotations

import json
from pathlib import Path

import pytest

from trailsight_v2.data.bank_country import BANK_COUNTRY_V1, bank_country_for
from trailsight_v2.data.constants import BANK_COUNTRY_VERSION
from trailsight_v2.data.errors import CanonicalizationError


def test_bank_country_mapping_is_deterministic_and_versioned() -> None:
    assert bank_country_for("001") == bank_country_for("001")
    assert BANK_COUNTRY_VERSION == "bank-country-v1"
    assert len(BANK_COUNTRY_V1) == 24


def test_bank_country_mapping_uses_only_normalized_bank_id() -> None:
    with pytest.raises(CanonicalizationError, match="canonical normalized bank_id"):
        bank_country_for("\t001 ")
    # There is no amount/currency/label parameter in the mapping API by contract.
    assert bank_country_for.__code__.co_argcount == 1


def test_checked_in_metadata_matches_runtime_frozen_list() -> None:
    metadata_path = Path("data/v2/metadata/bank_country_v1.json")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["mapping_version"] == BANK_COUNTRY_VERSION
    actual = [
        (
            item["country_name"],
            item["iso_alpha2"],
            item["centroid_latitude"],
            item["centroid_longitude"],
        )
        for item in payload["countries"]
    ]
    expected = [
        (
            item.country_name,
            item.iso_alpha2,
            item.centroid_latitude,
            item.centroid_longitude,
        )
        for item in BANK_COUNTRY_V1
    ]
    assert actual == expected
    assert all(len(item.iso_alpha2) == 2 for item in BANK_COUNTRY_V1)
    assert all(-90 <= item.centroid_latitude <= 90 for item in BANK_COUNTRY_V1)
    assert all(-180 <= item.centroid_longitude <= 180 for item in BANK_COUNTRY_V1)
