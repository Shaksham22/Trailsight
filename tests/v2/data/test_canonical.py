from __future__ import annotations

import unicodedata

import pytest

from trailsight_v2.data.canonical import (
    account_ref_for,
    canonical_decimal,
    canonical_timestamp,
    canonicalize_transaction,
    normalize_source_id,
    transaction_ref_for,
)
from trailsight_v2.data.errors import CanonicalizationError


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


def test_source_id_normalization_preserves_case_punctuation_internal_space_and_zeroes() -> None:
    assert normalize_source_id("\t 00A-B  c \r", field="bank_id") == "00A-B  c"
    assert normalize_source_id("BankA", field="bank_id") != normalize_source_id(
        "banka", field="bank_id"
    )


def test_source_id_normalization_is_unicode_nfc() -> None:
    decomposed = "Cafe\u0301"
    assert normalize_source_id(decomposed, field="account_id") == unicodedata.normalize(
        "NFC", decomposed
    )


@pytest.mark.parametrize("value", [None, "", " \t\r\n", 123])
def test_source_id_rejects_missing_empty_or_non_string(value: object) -> None:
    with pytest.raises(CanonicalizationError):
        normalize_source_id(value, field="bank_id")


def test_account_ref_is_stable_and_bank_and_source_sensitive() -> None:
    first = account_ref_for("001", "A001")
    assert first == account_ref_for("001", "A001")
    assert first != account_ref_for("002", "A001")
    assert first != account_ref_for("001", "A001", source_dataset="other-simulation")
    assert first.startswith("acct_") and len(first) == 29


def test_timestamp_and_decimal_canonical_forms_follow_v2_contract() -> None:
    assert canonical_timestamp("2022/09/01 00:20") == "2022-09-01T00:20:00"
    assert canonical_timestamp("2022-09-01 00:20:01") == "2022-09-01T00:20:01"
    assert canonical_decimal("100.000", field="Amount Paid") == "100"
    assert canonical_decimal("0.00", field="Amount Paid") == "0"


def test_transaction_ref_is_deterministic_ordinal_sensitive_and_label_blind() -> None:
    row = source_row()
    same_operational_row_other_label = source_row(**{"Is Laundering": "1"})
    first = transaction_ref_for(row, source_row_ordinal=1)
    assert first == transaction_ref_for(same_operational_row_other_label, source_row_ordinal=1)
    assert first != transaction_ref_for(row, source_row_ordinal=2)
    assert first.startswith("txn_") and len(first) == 68


def test_transaction_ref_uses_normalized_source_ids_and_preserves_leading_zeroes() -> None:
    padded = source_row(**{"From Bank": "\t001 ", "Account": " A001\r"})
    assert transaction_ref_for(padded, source_row_ordinal=1) == transaction_ref_for(
        source_row(), source_row_ordinal=1
    )
    assert transaction_ref_for(
        source_row(**{"From Bank": "1"}), source_row_ordinal=1
    ) != transaction_ref_for(source_row(), source_row_ordinal=1)


def test_canonical_transaction_contains_no_hidden_truth_and_cross_currency_is_direct_fact() -> None:
    transaction = canonicalize_transaction(
        source_row(
            **{
                "Receiving Currency": "USD",
                "Payment Currency": "CAD",
                "Is Laundering": "1",
            }
        ),
        source_row_ordinal=7,
    )
    assert transaction.cross_currency is True
    assert "launder" not in {field.lower() for field in transaction.__dataclass_fields__}
