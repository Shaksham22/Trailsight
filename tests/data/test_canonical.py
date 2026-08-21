from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from trailsight_data.canonical import (
    canonical_decimal,
    canonical_payload,
    canonical_timestamp,
    canonicalize_transaction,
    ensure_unique_transaction_refs,
    transaction_ref_for,
)
from trailsight_data.errors import DuplicateTransactionReferenceError


def source_row(**overrides: str) -> dict[str, str]:
    row = {
        "Timestamp": "2025-01-01 00:00:29",
        "From Bank": "3295718",
        "From Account": "A009852",
        "To Bank": "2657408",
        "To Account": "A010012",
        "Amount Received": "4.4",
        "Receiving Currency": "CHF",
        "Amount Paid": "8.06",
        "Payment Currency": "AUD",
        "Payment Format": "Mobile",
        "Is Laundering": "0",
    }
    row.update(overrides)
    return row


def test_known_fixture_has_stable_txref_v1_hash() -> None:
    assert transaction_ref_for(source_row()) == (
        "tsx_cf018d6a68de5115435af51be2bec4cab7aeb2ad669f34a3c293b94a657bb14b"
    )


def test_fixed_fingerprint_field_order() -> None:
    payload = canonical_payload(source_row())
    assert payload == (
        "txref-v1",
        "2025-01-01T00:00:29.000000",
        "3295718",
        "A009852",
        "2657408",
        "A010012",
        "8.06",
        "AUD",
        "4.4",
        "CHF",
        "Mobile",
    )


def test_timestamp_has_six_fractional_digits_without_timezone() -> None:
    assert canonical_timestamp("2025-05-08 16:18:46") == (
        "2025-05-08T16:18:46.000000"
    )
    assert canonical_timestamp(datetime(2025, 5, 8, 16, 18, 46, 123)) == (
        "2025-05-08T16:18:46.000123"
    )


@pytest.mark.parametrize("amount", ["69.54", "69.540", "69.5400"])
def test_insignificant_decimal_zeros_do_not_change_txref(amount: str) -> None:
    assert transaction_ref_for(source_row(**{"Amount Paid": amount})) == transaction_ref_for(
        source_row(**{"Amount Paid": "69.54"})
    )
    assert canonical_decimal(amount) == "69.54"


def test_text_case_is_preserved() -> None:
    assert transaction_ref_for(source_row(**{"Payment Format": "Mobile"})) != (
        transaction_ref_for(source_row(**{"Payment Format": "mobile"}))
    )


def test_surrounding_ascii_whitespace_is_removed() -> None:
    padded = source_row(
        **{
            "From Bank": "\t3295718 ",
            "From Account": " A009852\r",
            "Payment Currency": " AUD\n",
        }
    )
    assert transaction_ref_for(padded) == transaction_ref_for(source_row())


def test_unicode_nfc_normalization_is_stable() -> None:
    assert transaction_ref_for(source_row(**{"Payment Format": "Caf\u00e9"})) == (
        transaction_ref_for(source_row(**{"Payment Format": "Cafe\u0301"}))
    )


def test_hidden_label_cannot_affect_txref() -> None:
    assert transaction_ref_for(source_row(**{"Is Laundering": "0"})) == (
        transaction_ref_for(source_row(**{"Is Laundering": "1"}))
    )


def test_duplicate_and_collision_refs_fail_loudly() -> None:
    first = canonicalize_transaction(source_row())
    collision = dataclasses.replace(
        canonicalize_transaction(source_row(**{"To Account": "A999999"})),
        transaction_ref=first.transaction_ref,
    )
    with pytest.raises(DuplicateTransactionReferenceError, match="SHA-256 collision"):
        ensure_unique_transaction_refs([first, collision])
    with pytest.raises(
        DuplicateTransactionReferenceError, match="duplicate canonical payload"
    ):
        ensure_unique_transaction_refs([first, first])

