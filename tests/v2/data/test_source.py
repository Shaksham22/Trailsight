from __future__ import annotations

import csv
from pathlib import Path

import pytest

from trailsight_v2.data.constants import REQUIRED_SOURCE_COLUMNS
from trailsight_v2.data.errors import SourceValidationError
from trailsight_v2.data.source import iter_canonical_transactions, validate_source


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


def write_raw_duplicate_account_csv(path: Path, *, laundering: str = "1") -> Path:
    raw_header = tuple(
        "Account" if name == "Account.1" else name for name in REQUIRED_SOURCE_COLUMNS
    )
    values = [
        "2022/09/01 00:20",
        "0007",
        "00123",
        "Bank-B",
        "00999",
        "100.00",
        "USD",
        "100",
        "USD",
        "ACH",
        laundering,
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(raw_header)
        writer.writerow(values)
    return path


def test_required_ibm_header_validates(make_ibm_csv) -> None:
    path = make_ibm_csv()
    result = validate_source(path)
    assert result.header == REQUIRED_SOURCE_COLUMNS
    assert len(result.sha256) == 64


def test_real_raw_duplicate_account_header_maps_by_position(tmp_path: Path) -> None:
    path = write_raw_duplicate_account_csv(tmp_path / "raw-duplicate-account.csv")

    result = validate_source(path)
    transaction = next(iter_canonical_transactions(path))

    assert result.header.count("Account") == 2
    assert "Account.1" not in result.header
    assert transaction.source_row_ordinal == 1
    assert transaction.from_bank_id == "0007"
    assert transaction.from_account_id == "00123"
    assert transaction.to_bank_id == "Bank-B"
    assert transaction.to_account_id == "00999"
    assert not hasattr(transaction, "is_laundering")


def test_raw_duplicate_and_disambiguated_headers_preserve_transaction_identity(
    make_ibm_csv, tmp_path: Path
) -> None:
    raw_path = write_raw_duplicate_account_csv(
        tmp_path / "raw.csv",
        laundering="1",
    )
    logical_path = make_ibm_csv(
        [
            source_row(
                **{
                    "From Bank": "0007",
                    "Account": "00123",
                    "To Bank": "Bank-B",
                    "Account.1": "00999",
                    "Is Laundering": "0",
                }
            )
        ],
        filename="logical.csv",
    )

    raw_transaction = next(iter_canonical_transactions(raw_path))
    logical_transaction = next(iter_canonical_transactions(logical_path))

    assert raw_transaction.source_row_ordinal == logical_transaction.source_row_ordinal == 1
    assert raw_transaction.transaction_ref == logical_transaction.transaction_ref
    assert raw_transaction.from_account_ref == logical_transaction.from_account_ref
    assert raw_transaction.to_account_ref == logical_transaction.to_account_ref


def test_missing_required_ibm_header_is_rejected(make_ibm_csv) -> None:
    header = tuple(name for name in REQUIRED_SOURCE_COLUMNS if name != "Account.1")
    path = make_ibm_csv(header=header)
    with pytest.raises(SourceValidationError, match="header mismatch"):
        validate_source(path)


def test_ambiguous_malformed_account_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "ambiguous.csv"
    header = list(REQUIRED_SOURCE_COLUMNS)
    header[4] = "Account"
    header.append("Account.1")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerow(["x"] * len(header))
    with pytest.raises(SourceValidationError, match="header mismatch"):
        validate_source(path)


def test_duplicate_non_account_required_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.csv"
    header = list(REQUIRED_SOURCE_COLUMNS) + ["From Bank"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerow(["x"] * len(header))
    with pytest.raises(SourceValidationError, match="header mismatch"):
        validate_source(path)


def test_stream_reader_keeps_identifiers_as_strings_and_never_projects_hidden_label(make_ibm_csv) -> None:
    path = make_ibm_csv(
        [source_row(**{"From Bank": "0007", "Account": "00123", "Is Laundering": "1"})]
    )
    transaction = next(iter_canonical_transactions(path))
    assert transaction.from_bank_id == "0007"
    assert transaction.from_account_id == "00123"
    assert not hasattr(transaction, "is_laundering")


def test_malformed_identifier_is_rejected_with_source_row(make_ibm_csv) -> None:
    path = make_ibm_csv([source_row(**{"From Bank": "   "})])
    with pytest.raises(SourceValidationError, match="source row 1"):
        list(iter_canonical_transactions(path))
