"""The single txref-v1 canonicalization implementation."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

from trailsight_data.errors import (
    CanonicalizationError,
    DuplicateTransactionReferenceError,
)
from trailsight_data.models import CanonicalTransaction

TXREF_VERSION = "txref-v1"
TXREF_PREFIX = "tsx_"
ASCII_WHITESPACE = " \t\n\r\v\f"

TRANSACTION_SOURCE_ALLOWLIST = (
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
)

FINGERPRINT_FIELD_ORDER = (
    "Timestamp",
    "From Bank",
    "From Account",
    "To Bank",
    "To Account",
    "Amount Paid",
    "Payment Currency",
    "Amount Received",
    "Receiving Currency",
    "Payment Format",
)


def canonical_text(value: object, *, field: str = "text") -> str:
    if value is None:
        raise CanonicalizationError(f"{field} is null")
    return unicodedata.normalize("NFC", str(value)).strip(ASCII_WHITESPACE)


def parse_source_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = canonical_text(value, field="Timestamp")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise CanonicalizationError(f"Timestamp is invalid: {raw!r}") from exc
    if parsed.tzinfo is not None:
        raise CanonicalizationError("Timestamp must not include timezone information")
    return parsed


def canonical_timestamp(value: object) -> str:
    return parse_source_timestamp(value).strftime("%Y-%m-%dT%H:%M:%S.%f")


def parse_source_decimal(value: object, *, field: str = "amount") -> Decimal:
    if isinstance(value, Decimal):
        parsed = value
    else:
        if isinstance(value, float) and not math.isfinite(value):
            raise CanonicalizationError(f"{field} is not a finite decimal")
        raw = canonical_text(value, field=field)
        try:
            parsed = Decimal(raw)
        except (InvalidOperation, ValueError) as exc:
            raise CanonicalizationError(f"{field} is invalid: {raw!r}") from exc
    if not parsed.is_finite():
        raise CanonicalizationError(f"{field} is not a finite decimal")
    return parsed


def canonical_decimal(value: object) -> str:
    parsed = parse_source_decimal(value)
    if parsed == 0:
        return "0"
    rendered = format(parsed, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered.startswith("+"):
        rendered = rendered[1:]
    return rendered


def canonical_payload(row: Mapping[str, object]) -> tuple[str, ...]:
    return (
        TXREF_VERSION,
        canonical_timestamp(row["Timestamp"]),
        canonical_text(row["From Bank"], field="From Bank"),
        canonical_text(row["From Account"], field="From Account"),
        canonical_text(row["To Bank"], field="To Bank"),
        canonical_text(row["To Account"], field="To Account"),
        canonical_decimal(row["Amount Paid"]),
        canonical_text(row["Payment Currency"], field="Payment Currency"),
        canonical_decimal(row["Amount Received"]),
        canonical_text(row["Receiving Currency"], field="Receiving Currency"),
        canonical_text(row["Payment Format"], field="Payment Format"),
    )


def serialize_canonical_payload(payload: tuple[str, ...]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def transaction_ref_for(row: Mapping[str, object]) -> str:
    serialized = serialize_canonical_payload(canonical_payload(row))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"{TXREF_PREFIX}{digest}"


def canonicalize_transaction(row: Mapping[str, object]) -> CanonicalTransaction:
    try:
        payload = canonical_payload(row)
    except KeyError as exc:
        raise CanonicalizationError(f"missing transaction field: {exc.args[0]}") from exc
    serialized = serialize_canonical_payload(payload)
    transaction_ref = f"{TXREF_PREFIX}{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"
    return CanonicalTransaction(
        transaction_ref=transaction_ref,
        timestamp=parse_source_timestamp(payload[1]),
        from_bank=payload[2],
        from_account=payload[3],
        to_bank=payload[4],
        to_account=payload[5],
        amount_paid=parse_source_decimal(payload[6], field="Amount Paid"),
        payment_currency=payload[7],
        amount_received=parse_source_decimal(payload[8], field="Amount Received"),
        receiving_currency=payload[9],
        payment_format=payload[10],
        canonical_payload_json=serialized,
    )


def ensure_unique_transaction_refs(transactions: Iterable[CanonicalTransaction]) -> int:
    seen: dict[str, str] = {}
    count = 0
    for transaction in transactions:
        prior_payload = seen.get(transaction.transaction_ref)
        if prior_payload is not None:
            collision_kind = (
                "duplicate canonical payload"
                if prior_payload == transaction.canonical_payload_json
                else "SHA-256 collision"
            )
            raise DuplicateTransactionReferenceError(
                f"{collision_kind} for transaction_ref {transaction.transaction_ref}"
            )
        seen[transaction.transaction_ref] = transaction.canonical_payload_json
        count += 1
    return count
