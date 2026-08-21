"""Internal data-preparation records; these are not WP02 domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CanonicalTransaction:
    transaction_ref: str
    timestamp: datetime
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount_paid: Decimal
    payment_currency: str
    amount_received: Decimal
    receiving_currency: str
    payment_format: str
    canonical_payload_json: str

    def normalized_csv_row(self) -> tuple[str, ...]:
        from trailsight_data.canonical import canonical_decimal, canonical_timestamp

        return (
            self.transaction_ref,
            canonical_timestamp(self.timestamp),
            self.from_bank,
            self.from_account,
            self.to_bank,
            self.to_account,
            canonical_decimal(self.amount_paid),
            self.payment_currency,
            canonical_decimal(self.amount_received),
            self.receiving_currency,
            self.payment_format,
        )


@dataclass(frozen=True, slots=True)
class RuntimeTransaction:
    transaction_ref: str
    timestamp: datetime
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount_paid: Decimal
    payment_currency: str
    amount_received: Decimal
    receiving_currency: str
    payment_format: str


@dataclass(frozen=True, slots=True)
class CaseDefinition:
    case_ref: str
    display_name: str
    selected_transaction_ref: str
    selection_kind: str


@dataclass(frozen=True, slots=True)
class CaseSlice:
    case: CaseDefinition
    selected: RuntimeTransaction
    history: tuple[RuntimeTransaction, ...]


@dataclass(frozen=True, slots=True)
class SourceValidationResult:
    source_root: str
    tx_path: str
    person_path: str
    merchant_path: str
    commit: str | None
    commit_verified: bool


@dataclass(frozen=True, slots=True)
class RuntimeValidationReport:
    table_row_counts: dict[str, int]
    history_row_counts: dict[str, int]

