"""Single deterministic factual service for Trailsight investigations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re

from trailsight.contracts import (
    AmountHistoryContext,
    AmountHistoryFacts,
    CaseSummary,
    CounterpartyHistoryContext,
    CounterpartyHistoryFacts,
    CurrencyDimension,
    CurrencyHistoryFacts,
    EntityRef,
    EvidenceType,
    HistoricalTransactionRow,
    HistoryQuality,
    InternalEvidence,
    RegionHistoryContext,
    RegionHistoryFacts,
    RegionRelationship,
    SelectedTransaction,
    SenderHistoryContext,
    SenderHistoryFacts,
    UITarget,
    WorkspaceResponse,
)
from trailsight.data.runtime_repository import (
    CaseRecord,
    RuntimeRepository,
    RuntimeTransaction,
)
from trailsight.domain.amount import exact_median, normalize_decimal
from trailsight.domain.synthetic_region import derive_synthetic_region
from trailsight.errors import DataIntegrityError, DomainInputError, EvidenceResolutionError


_CASE_REF_PATTERN = r"[a-z0-9][a-z0-9-]{0,63}"
_SIMPLE_EVIDENCE_ID = re.compile(
    rf"^ev:({_CASE_REF_PATTERN}):(selected|sender-history|amount-history|counterparty-history|region-history)$"
)
_CURRENCY_EVIDENCE_ID = re.compile(
    rf"^ev:({_CASE_REF_PATTERN}):currency:(payment|receiving):([A-Z]{{3}})$"
)
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class _CaseState:
    case: CaseRecord
    selected_raw: RuntimeTransaction
    selected: SelectedTransaction
    history: tuple[RuntimeTransaction, ...]


class InvestigationService:
    """Own every factual calculation shared by FastAPI, MCP, and AI validation."""

    def __init__(self, repository: RuntimeRepository) -> None:
        self._repository = repository

    def get_workspace(self, case_ref: str) -> WorkspaceResponse:
        """Assemble the complete deterministic, non-AI case workspace."""

        selected_evidence = self.get_selected_transaction_evidence(case_ref)
        sender_evidence = self.get_sender_history_evidence(case_ref)
        amount_evidence = self.get_amount_history_evidence(case_ref)
        counterparty_evidence = self.get_counterparty_history_evidence(case_ref)
        region_evidence = self.get_region_history_evidence(case_ref)

        selected = selected_evidence.facts
        sender_facts = sender_evidence.facts
        amount_facts = amount_evidence.facts
        counterparty_facts = counterparty_evidence.facts
        region_facts = region_evidence.facts
        if not isinstance(selected, SelectedTransaction):
            raise DataIntegrityError("Selected evidence facts have an invalid type")
        if not isinstance(sender_facts, SenderHistoryFacts):
            raise DataIntegrityError("Sender evidence facts have an invalid type")
        if not isinstance(amount_facts, AmountHistoryFacts):
            raise DataIntegrityError("Amount evidence facts have an invalid type")
        if not isinstance(counterparty_facts, CounterpartyHistoryFacts):
            raise DataIntegrityError("Counterparty evidence facts have an invalid type")
        if not isinstance(region_facts, RegionHistoryFacts):
            raise DataIntegrityError("Region evidence facts have an invalid type")

        state = self._load_case_state(case_ref)
        historical_transactions = self._historical_rows(state.history)
        historical_transactions.sort(key=lambda row: row.transaction_ref)
        historical_transactions.sort(key=lambda row: row.timestamp, reverse=True)

        return WorkspaceResponse(
            case_ref=state.case.case_ref,
            display_name=state.case.display_name,
            selected_transaction=selected,
            sender_history=SenderHistoryContext(
                evidence_id=sender_evidence.evidence_id,
                prior_outgoing_count=sender_facts.prior_outgoing_count,
            ),
            amount_history=AmountHistoryContext(
                evidence_id=amount_evidence.evidence_id,
                **amount_facts.model_dump(),
            ),
            counterparty_history=CounterpartyHistoryContext(
                evidence_id=counterparty_evidence.evidence_id,
                **counterparty_facts.model_dump(),
            ),
            region_history=RegionHistoryContext(
                evidence_id=region_evidence.evidence_id,
                **region_facts.model_dump(),
            ),
            historical_transactions=historical_transactions,
        )

    def get_selected_transaction_evidence(self, case_ref: str) -> InternalEvidence:
        case, selected_raw, selected = self._load_selected(case_ref)
        return InternalEvidence(
            evidence_id=f"ev:{case.case_ref}:selected",
            evidence_type=EvidenceType.SELECTED_TRANSACTION,
            case_ref=case.case_ref,
            facts=selected,
            supporting_transaction_refs=[selected_raw.transaction_ref],
            ui_target=UITarget.SELECTED_TRANSACTION,
        )

    def get_sender_history_evidence(self, case_ref: str) -> InternalEvidence:
        state = self._load_case_state(case_ref)
        return InternalEvidence(
            evidence_id=f"ev:{state.case.case_ref}:sender-history",
            evidence_type=EvidenceType.SENDER_HISTORY,
            case_ref=state.case.case_ref,
            facts=SenderHistoryFacts(prior_outgoing_count=len(state.history)),
            supporting_transaction_refs=[row.transaction_ref for row in state.history],
            ui_target=UITarget.SENDER_HISTORY,
        )

    def get_amount_history_evidence(self, case_ref: str) -> InternalEvidence:
        state = self._load_case_state(case_ref)
        matching = [
            row
            for row in state.history
            if row.payment_currency == state.selected_raw.payment_currency
        ]
        sample_size = len(matching)
        median: str | None = None
        percentile: float | None = None
        if sample_size < 5:
            quality = HistoryQuality.INSUFFICIENT
        elif sample_size < 20:
            quality = HistoryQuality.LIMITED
            median = normalize_decimal(exact_median([row.amount_paid for row in matching]))
        else:
            quality = HistoryQuality.SUFFICIENT
            median = normalize_decimal(exact_median([row.amount_paid for row in matching]))
            at_or_below = sum(
                row.amount_paid <= state.selected_raw.amount_paid for row in matching
            )
            exact_percentile = (
                Decimal(100) * Decimal(at_or_below) / Decimal(sample_size)
            )
            percentile = float(exact_percentile)

        facts = AmountHistoryFacts(
            history_quality=quality,
            sample_size=sample_size,
            selected_amount=normalize_decimal(state.selected_raw.amount_paid),
            payment_currency=state.selected_raw.payment_currency,
            historical_median=median,
            empirical_percentile=percentile,
        )
        return InternalEvidence(
            evidence_id=f"ev:{state.case.case_ref}:amount-history",
            evidence_type=EvidenceType.AMOUNT_HISTORY,
            case_ref=state.case.case_ref,
            facts=facts,
            supporting_transaction_refs=[row.transaction_ref for row in matching],
            ui_target=UITarget.AMOUNT_CONTEXT,
        )

    def get_counterparty_history_evidence(self, case_ref: str) -> InternalEvidence:
        state = self._load_case_state(case_ref)
        matching = [
            row
            for row in state.history
            if row.to_bank == state.selected_raw.to_bank
            and row.to_account == state.selected_raw.to_account
        ]
        timestamps = [row.timestamp for row in matching]
        facts = CounterpartyHistoryFacts(
            seen_before=bool(matching),
            previous_interaction_count=len(matching),
            first_previous_timestamp=(
                self._canonical_timestamp(min(timestamps)) if timestamps else None
            ),
            most_recent_previous_timestamp=(
                self._canonical_timestamp(max(timestamps)) if timestamps else None
            ),
        )
        return InternalEvidence(
            evidence_id=f"ev:{state.case.case_ref}:counterparty-history",
            evidence_type=EvidenceType.COUNTERPARTY_HISTORY,
            case_ref=state.case.case_ref,
            facts=facts,
            supporting_transaction_refs=[row.transaction_ref for row in matching],
            ui_target=UITarget.COUNTERPARTY_HISTORY,
        )

    def get_region_history_evidence(self, case_ref: str) -> InternalEvidence:
        state = self._load_case_state(case_ref)
        sender_region = state.selected.sender.synthetic_region
        receiver_region = state.selected.counterparty.synthetic_region
        matching = [
            row
            for row in state.history
            if derive_synthetic_region(row.to_account) == receiver_region
        ]
        facts = RegionHistoryFacts(
            sender_region=sender_region,
            receiver_region=receiver_region,
            region_relationship=state.selected.region_relationship,
            receiver_region_seen_before=bool(matching),
            previous_receiver_region_count=len(matching),
        )
        return InternalEvidence(
            evidence_id=f"ev:{state.case.case_ref}:region-history",
            evidence_type=EvidenceType.REGION_HISTORY,
            case_ref=state.case.case_ref,
            facts=facts,
            supporting_transaction_refs=[row.transaction_ref for row in matching],
            ui_target=UITarget.SYNTHETIC_REGION_HISTORY,
        )

    def get_currency_history_evidence(
        self,
        case_ref: str,
        dimension: CurrencyDimension | str,
        currency: str,
    ) -> InternalEvidence:
        try:
            validated_dimension = CurrencyDimension(dimension)
        except ValueError as exc:
            raise DomainInputError("Currency dimension must be payment or receiving") from exc
        if not isinstance(currency, str) or _CURRENCY_CODE.fullmatch(currency) is None:
            raise DomainInputError("Currency must be exactly three uppercase ASCII letters")

        state = self._load_case_state(case_ref)
        if validated_dimension is CurrencyDimension.PAYMENT:
            matching = [row for row in state.history if row.payment_currency == currency]
        else:
            matching = [row for row in state.history if row.receiving_currency == currency]

        timestamps = [row.timestamp for row in matching]
        facts = CurrencyHistoryFacts(
            dimension=validated_dimension,
            currency=currency,
            seen_before=bool(matching),
            previous_count=len(matching),
            first_previous_timestamp=(
                self._canonical_timestamp(min(timestamps)) if timestamps else None
            ),
            most_recent_previous_timestamp=(
                self._canonical_timestamp(max(timestamps)) if timestamps else None
            ),
        )
        return InternalEvidence(
            evidence_id=(
                f"ev:{state.case.case_ref}:currency:{validated_dimension.value}:{currency}"
            ),
            evidence_type=EvidenceType.CURRENCY_HISTORY,
            case_ref=state.case.case_ref,
            facts=facts,
            supporting_transaction_refs=[row.transaction_ref for row in matching],
            ui_target=UITarget.HISTORICAL_EVIDENCE,
        )

    def resolve_evidence(self, evidence_id: str) -> InternalEvidence:
        if not isinstance(evidence_id, str):
            raise EvidenceResolutionError("Evidence ID must be a string")

        simple_match = _SIMPLE_EVIDENCE_ID.fullmatch(evidence_id)
        if simple_match is not None:
            case_ref, evidence_kind = simple_match.groups()
            resolver = {
                "selected": self.get_selected_transaction_evidence,
                "sender-history": self.get_sender_history_evidence,
                "amount-history": self.get_amount_history_evidence,
                "counterparty-history": self.get_counterparty_history_evidence,
                "region-history": self.get_region_history_evidence,
            }[evidence_kind]
            resolved = resolver(case_ref)
        else:
            currency_match = _CURRENCY_EVIDENCE_ID.fullmatch(evidence_id)
            if currency_match is None:
                raise EvidenceResolutionError("Evidence ID format is not supported")
            case_ref, dimension, currency = currency_match.groups()
            resolved = self.get_currency_history_evidence(
                case_ref,
                CurrencyDimension(dimension),
                currency,
            )

        if resolved.evidence_id != evidence_id:
            raise EvidenceResolutionError(
                "Resolved evidence does not match the requested evidence ID"
            )
        return resolved

    def _list_cases(self) -> list[CaseSummary]:
        return [
            CaseSummary(case_ref=case.case_ref, display_name=case.display_name)
            for case in self._repository.list_cases()
        ]

    def _close(self) -> None:
        self._repository.close()

    def _load_selected(
        self, case_ref: str
    ) -> tuple[CaseRecord, RuntimeTransaction, SelectedTransaction]:
        case = self._repository.get_case(case_ref)
        selected_raw = self._repository.get_selected_transaction(case_ref)
        selected = self._selected_transaction(selected_raw)
        return case, selected_raw, selected

    def _load_case_state(self, case_ref: str) -> _CaseState:
        case, selected_raw, selected = self._load_selected(case_ref)
        history = self._repository.get_case_history(
            case_ref,
            sender_bank=selected_raw.from_bank,
            sender_account=selected_raw.from_account,
        )
        for row in history:
            if (
                row.from_bank != selected_raw.from_bank
                or row.from_account != selected_raw.from_account
            ):
                raise DataIntegrityError(
                    "Runtime history sender does not match Bank + Account identity"
                )
            if row.timestamp >= selected_raw.timestamp:
                raise DataIntegrityError(
                    "Runtime case history must be strictly earlier than the selected transaction"
                )
        ordered = tuple(sorted(history, key=lambda row: (row.timestamp, row.transaction_ref)))
        return _CaseState(
            case=case,
            selected_raw=selected_raw,
            selected=selected,
            history=ordered,
        )

    def _selected_transaction(self, row: RuntimeTransaction) -> SelectedTransaction:
        sender_region = derive_synthetic_region(row.from_account)
        receiver_region = derive_synthetic_region(row.to_account)
        sender = EntityRef(
            bank=row.from_bank,
            account=row.from_account,
            entity_type=self._repository.get_entity_type(row.from_bank, row.from_account),
            synthetic_region=sender_region,
        )
        counterparty = EntityRef(
            bank=row.to_bank,
            account=row.to_account,
            entity_type=self._repository.get_entity_type(row.to_bank, row.to_account),
            synthetic_region=receiver_region,
        )
        return SelectedTransaction(
            transaction_ref=row.transaction_ref,
            timestamp=self._canonical_timestamp(row.timestamp),
            sender=sender,
            counterparty=counterparty,
            amount_paid=normalize_decimal(row.amount_paid),
            payment_currency=row.payment_currency,
            amount_received=normalize_decimal(row.amount_received),
            receiving_currency=row.receiving_currency,
            payment_format=row.payment_format,
            cross_currency=row.payment_currency != row.receiving_currency,
            currency_pair=f"{row.payment_currency} → {row.receiving_currency}",
            region_relationship=(
                RegionRelationship.SAME_REGION
                if sender_region == receiver_region
                else RegionRelationship.CROSS_REGION
            ),
        )

    def _historical_rows(
        self, history: tuple[RuntimeTransaction, ...]
    ) -> list[HistoricalTransactionRow]:
        return [
            HistoricalTransactionRow(
                transaction_ref=row.transaction_ref,
                timestamp=self._canonical_timestamp(row.timestamp),
                counterparty_bank=row.to_bank,
                counterparty_account=row.to_account,
                counterparty_type=self._repository.get_entity_type(
                    row.to_bank, row.to_account
                ),
                amount_paid=normalize_decimal(row.amount_paid),
                payment_currency=row.payment_currency,
                receiving_currency=row.receiving_currency,
                receiver_region=derive_synthetic_region(row.to_account),
                payment_format=row.payment_format,
            )
            for row in history
        ]

    @staticmethod
    def _canonical_timestamp(value: datetime) -> str:
        if value.tzinfo is not None:
            raise DataIntegrityError("Runtime timestamps must not contain a timezone")
        return value.strftime("%Y-%m-%dT%H:%M:%S.%f")
