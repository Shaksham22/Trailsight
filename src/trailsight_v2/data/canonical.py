"""Frozen V2 canonicalization for IBM HI-Small identities."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

from trailsight_v2.data.constants import (
    ACCOUNT_REF_VERSION,
    ASCII_WHITESPACE,
    SOURCE_DATASET,
    TRANSACTION_REF_VERSION,
)
from trailsight_v2.data.errors import CanonicalizationError


@dataclass(frozen=True, slots=True)
class CanonicalAccount:
    source_dataset: str
    bank_id: str
    account_id: str
    account_ref: str


@dataclass(frozen=True, slots=True)
class CanonicalTransaction:
    transaction_ref: str
    source_dataset: str
    source_row_ordinal: int
    transaction_timestamp: datetime
    from_bank_id: str
    from_account_id: str
    from_account_ref: str
    to_bank_id: str
    to_account_id: str
    to_account_ref: str
    amount_received: Decimal
    receiving_currency: str
    amount_paid: Decimal
    payment_currency: str
    payment_format: str
    cross_currency: bool


def _compact_json(values: list[object]) -> bytes:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def canonical_text(value: object, *, field: str) -> str:
    if value is None:
        raise CanonicalizationError(f"{field} is missing")
    if not isinstance(value, str):
        raise CanonicalizationError(f"{field} must be read from source as a string")
    normalized = unicodedata.normalize("NFC", value).strip(ASCII_WHITESPACE)
    if not normalized:
        raise CanonicalizationError(f"{field} is empty after ASCII-whitespace trim")
    return normalized


def normalize_source_id(value: object, *, field: str) -> str:
    """Apply the frozen IBM bank/account identifier rule exactly once."""
    return canonical_text(value, field=field)


def parse_source_timestamp(value: object) -> datetime:
    raw = canonical_text(value, field="Timestamp")
    parsed: datetime | None = None
    for parser in (
        lambda text: datetime.fromisoformat(text),
        lambda text: datetime.strptime(text, "%Y/%m/%d %H:%M:%S"),
        lambda text: datetime.strptime(text, "%Y/%m/%d %H:%M"),
    ):
        try:
            parsed = parser(raw)
            break
        except ValueError:
            continue
    if parsed is None:
        raise CanonicalizationError(f"Timestamp is invalid: {raw!r}")
    if parsed.tzinfo is not None:
        raise CanonicalizationError("Timestamp must not include timezone information")
    return parsed


def canonical_timestamp(value: object) -> str:
    parsed = parse_source_timestamp(value)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S")


def parse_source_decimal(value: object, *, field: str) -> Decimal:
    if value is None:
        raise CanonicalizationError(f"{field} is missing")
    if isinstance(value, float) and not math.isfinite(value):
        raise CanonicalizationError(f"{field} must be finite")
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, str):
        raw = canonical_text(value, field=field)
        try:
            parsed = Decimal(raw)
        except InvalidOperation as exc:
            raise CanonicalizationError(f"{field} is not a valid decimal: {raw!r}") from exc
    else:
        raise CanonicalizationError(f"{field} must be read from source as a string")
    if not parsed.is_finite():
        raise CanonicalizationError(f"{field} must be finite")
    return parsed


def canonical_decimal(value: object, *, field: str = "amount") -> str:
    parsed = parse_source_decimal(value, field=field)
    if parsed == 0:
        return "0"
    rendered = format(parsed, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered.startswith("+"):
        rendered = rendered[1:]
    return rendered


def canonical_account_tuple(
    bank_id: object,
    account_id: object,
    *,
    source_dataset: str = SOURCE_DATASET,
) -> tuple[str, str, str]:
    if not isinstance(source_dataset, str) or not source_dataset:
        raise CanonicalizationError("source_dataset must be a non-empty string")
    return (
        source_dataset,
        normalize_source_id(bank_id, field="bank_id"),
        normalize_source_id(account_id, field="account_id"),
    )


def account_ref_for(
    bank_id: object,
    account_id: object,
    *,
    source_dataset: str = SOURCE_DATASET,
) -> str:
    source, bank, account = canonical_account_tuple(
        bank_id, account_id, source_dataset=source_dataset
    )
    payload = [ACCOUNT_REF_VERSION, source, bank, account]
    digest = hashlib.sha256(_compact_json(payload)).hexdigest()
    return f"acct_{digest[:24]}"


def canonical_account(
    bank_id: object,
    account_id: object,
    *,
    source_dataset: str = SOURCE_DATASET,
) -> CanonicalAccount:
    source, bank, account = canonical_account_tuple(
        bank_id, account_id, source_dataset=source_dataset
    )
    return CanonicalAccount(
        source_dataset=source,
        bank_id=bank,
        account_id=account,
        account_ref=account_ref_for(bank, account, source_dataset=source),
    )


def transaction_identity_payload(
    row: Mapping[str, object],
    *,
    source_row_ordinal: int,
    source_dataset: str = SOURCE_DATASET,
) -> list[object]:
    if source_row_ordinal < 1:
        raise CanonicalizationError("source_row_ordinal must be 1-based")
    from_bank_id = normalize_source_id(row.get("From Bank"), field="From Bank")
    from_account_id = normalize_source_id(row.get("Account"), field="Account")
    to_bank_id = normalize_source_id(row.get("To Bank"), field="To Bank")
    to_account_id = normalize_source_id(row.get("Account.1"), field="Account.1")
    return [
        TRANSACTION_REF_VERSION,
        source_dataset,
        source_row_ordinal,
        canonical_timestamp(row.get("Timestamp")),
        from_bank_id,
        from_account_id,
        to_bank_id,
        to_account_id,
        canonical_decimal(row.get("Amount Received"), field="Amount Received"),
        canonical_text(row.get("Receiving Currency"), field="Receiving Currency"),
        canonical_decimal(row.get("Amount Paid"), field="Amount Paid"),
        canonical_text(row.get("Payment Currency"), field="Payment Currency"),
        canonical_text(row.get("Payment Format"), field="Payment Format"),
    ]


def transaction_ref_for(
    row: Mapping[str, object],
    *,
    source_row_ordinal: int,
    source_dataset: str = SOURCE_DATASET,
) -> str:
    payload = transaction_identity_payload(
        row, source_row_ordinal=source_row_ordinal, source_dataset=source_dataset
    )
    digest = hashlib.sha256(_compact_json(payload)).hexdigest()
    return f"txn_{digest}"


def canonicalize_transaction(
    row: Mapping[str, object],
    *,
    source_row_ordinal: int,
    source_dataset: str = SOURCE_DATASET,
) -> CanonicalTransaction:
    payload = transaction_identity_payload(
        row, source_row_ordinal=source_row_ordinal, source_dataset=source_dataset
    )
    (
        _,
        source,
        ordinal,
        timestamp,
        from_bank,
        from_account,
        to_bank,
        to_account,
        amount_received,
        receiving_currency,
        amount_paid,
        payment_currency,
        payment_format,
    ) = payload
    from_ref = account_ref_for(from_bank, from_account, source_dataset=source)
    to_ref = account_ref_for(to_bank, to_account, source_dataset=source)
    return CanonicalTransaction(
        transaction_ref=f"txn_{hashlib.sha256(_compact_json(payload)).hexdigest()}",
        source_dataset=source,
        source_row_ordinal=ordinal,
        transaction_timestamp=datetime.fromisoformat(timestamp),
        from_bank_id=from_bank,
        from_account_id=from_account,
        from_account_ref=from_ref,
        to_bank_id=to_bank,
        to_account_id=to_account,
        to_account_ref=to_ref,
        amount_received=Decimal(amount_received),
        receiving_currency=receiving_currency,
        amount_paid=Decimal(amount_paid),
        payment_currency=payment_currency,
        payment_format=payment_format,
        cross_currency=receiving_currency != payment_currency,
    )
