"""Validation and explicit-allowlist reading of the external TransXion source."""

from __future__ import annotations

import csv
import subprocess
from collections.abc import Iterator
from pathlib import Path

from trailsight_data.canonical import (
    TRANSACTION_SOURCE_ALLOWLIST,
    canonical_text,
    canonicalize_transaction,
)
from trailsight_data.errors import CanonicalizationError, SourceValidationError
from trailsight_data.models import CanonicalTransaction, SourceValidationResult

EXPECTED_SOURCE_COMMIT = "53932595c37c23b9f55ea5ddf5984e4d57b88369"

REQUIRED_TRANSACTION_HEADERS = (
    "Timestamp",
    "From Bank",
    "From Account",
    "To Bank",
    "To Account",
    "Amount Received",
    "Receiving Currency",
    "Amount Paid",
    "Payment Currency",
    "Payment Format",
    "Is Laundering",
)
REQUIRED_PROFILE_HEADERS = ("bank_account_number", "bank")
NORMALIZED_TRANSACTION_HEADERS = (
    "transaction_ref",
    "timestamp",
    "from_bank",
    "from_account",
    "to_bank",
    "to_account",
    "amount_paid",
    "payment_currency",
    "amount_received",
    "receiving_currency",
    "payment_format",
)
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def _read_header(path: Path) -> tuple[str, ...]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            row = next(csv.reader(handle), None)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SourceValidationError(f"cannot read CSV header: {path}") from exc
    if row is None:
        raise SourceValidationError(f"CSV file is empty: {path}")
    return tuple(row)


def _validate_headers(path: Path, required: tuple[str, ...]) -> tuple[str, ...]:
    header = _read_header(path)
    missing = [name for name in required if name not in header]
    ambiguous = [name for name in required if header.count(name) != 1]
    if missing:
        raise SourceValidationError(
            f"CSV schema mismatch for {path.name}; missing headers: {', '.join(missing)}"
        )
    if ambiguous:
        raise SourceValidationError(
            f"CSV schema mismatch for {path.name}; required headers are duplicated: "
            f"{', '.join(ambiguous)}"
        )
    return header


def _verify_git_commit(
    source_root: Path,
    *,
    expected_commit: str,
    allow_unverified_source: bool,
) -> tuple[str | None, bool]:
    if not (source_root / ".git").exists():
        if allow_unverified_source:
            return None, False
        raise SourceValidationError(
            "TransXion Git metadata is unavailable; use --allow-unverified-source only "
            "for developer fixtures"
        )

    result = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if allow_unverified_source:
            return None, False
        raise SourceValidationError("TransXion commit could not be verified")

    actual_commit = result.stdout.strip()
    if actual_commit != expected_commit:
        raise SourceValidationError(
            "TransXion source snapshot mismatch: "
            f"expected {expected_commit}, actual {actual_commit}"
        )
    return actual_commit, True


def validate_source(
    source_root: str | Path,
    *,
    expected_commit: str = EXPECTED_SOURCE_COMMIT,
    allow_unverified_source: bool = False,
) -> SourceValidationResult:
    root = Path(source_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SourceValidationError(f"TransXion source root does not exist: {root}")

    tx_path = root / "data" / "tx.csv"
    person_path = root / "data" / "person.csv"
    merchant_path = root / "data" / "merchant.csv"
    for required_path in (tx_path, person_path, merchant_path):
        if not required_path.is_file():
            raise SourceValidationError(f"required source file is missing: {required_path}")

    try:
        with tx_path.open("rb") as handle:
            prefix = handle.read(len(LFS_POINTER_PREFIX))
    except OSError as exc:
        raise SourceValidationError(f"cannot read source transaction file: {tx_path}") from exc
    if prefix == LFS_POINTER_PREFIX:
        raise SourceValidationError(
            "data/tx.csv is an unresolved Git LFS pointer, not transaction CSV content"
        )

    commit, verified = _verify_git_commit(
        root,
        expected_commit=expected_commit,
        allow_unverified_source=allow_unverified_source,
    )
    _validate_headers(tx_path, REQUIRED_TRANSACTION_HEADERS)
    _validate_headers(person_path, REQUIRED_PROFILE_HEADERS)
    _validate_headers(merchant_path, REQUIRED_PROFILE_HEADERS)

    return SourceValidationResult(
        source_root=str(root),
        tx_path=str(tx_path),
        person_path=str(person_path),
        merchant_path=str(merchant_path),
        commit=commit,
        commit_verified=verified,
    )


def iter_canonical_transactions(tx_path: str | Path) -> Iterator[CanonicalTransaction]:
    path = Path(tx_path)
    header = _validate_headers(path, REQUIRED_TRANSACTION_HEADERS)
    field_indexes = {field: header.index(field) for field in TRANSACTION_SOURCE_ALLOWLIST}
    maximum_index = max(field_indexes.values())

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader)
            for source_line, source_row in enumerate(reader, start=2):
                if len(source_row) <= maximum_index:
                    raise SourceValidationError(
                        f"transaction row {source_line} has fewer fields than the explicit allowlist"
                    )
                allowed_row = {
                    field: source_row[index] for field, index in field_indexes.items()
                }
                try:
                    yield canonicalize_transaction(allowed_row)
                except CanonicalizationError as exc:
                    raise SourceValidationError(
                        f"transaction row {source_line} cannot be canonicalized: {exc}"
                    ) from exc
    except (OSError, UnicodeError, csv.Error) as exc:
        if isinstance(exc, SourceValidationError):
            raise
        raise SourceValidationError(f"cannot read source transactions: {path}") from exc


def write_normalized_transactions(
    tx_path: str | Path,
    normalized_path: str | Path,
) -> int:
    output = Path(normalized_path)
    count = 0
    try:
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(NORMALIZED_TRANSACTION_HEADERS)
            for transaction in iter_canonical_transactions(tx_path):
                writer.writerow(transaction.normalized_csv_row())
                count += 1
    except OSError as exc:
        raise SourceValidationError(f"cannot write normalized staging data: {output}") from exc
    return count


def iter_profile_identities(
    profile_path: str | Path,
) -> Iterator[tuple[str, str]]:
    path = Path(profile_path)
    header = _validate_headers(path, REQUIRED_PROFILE_HEADERS)
    bank_index = header.index("bank")
    account_index = header.index("bank_account_number")
    maximum_index = max(bank_index, account_index)

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader)
            for source_line, source_row in enumerate(reader, start=2):
                if len(source_row) <= maximum_index:
                    raise SourceValidationError(
                        f"profile row {source_line} in {path.name} is missing identity fields"
                    )
                bank = canonical_text(source_row[bank_index], field="bank")
                account = canonical_text(
                    source_row[account_index], field="bank_account_number"
                )
                yield bank, account
    except (OSError, UnicodeError, csv.Error) as exc:
        if isinstance(exc, SourceValidationError):
            raise
        raise SourceValidationError(f"cannot read source profile: {path}") from exc
