from __future__ import annotations

from pathlib import Path

from trailsight.contracts import (
    AmountHistoryFacts,
    CounterpartyHistoryFacts,
    CurrencyDimension,
    CurrencyHistoryFacts,
    EntityRef,
    EntityType,
    EvidenceType,
    HistoryQuality,
    InternalEvidence,
    RegionRelationship,
    SelectedTransaction,
    SenderHistoryFacts,
    UITarget,
)
from trailsight.errors import CaseNotFoundError, EvidenceResolutionError
from trailsight_ai.config import AIConfig, known_prompt_path


def txref(index: int) -> str:
    return f"tsx_{index:064x}"


def selected_evidence(case_ref: str = "demo-01") -> InternalEvidence:
    selected = SelectedTransaction(
        transaction_ref=txref(100),
        timestamp="2025-05-08T16:18:46.000000",
        sender=EntityRef(
            bank="Sender Bank",
            account="A016568",
            entity_type=EntityType.PERSON,
            synthetic_region=8,
        ),
        counterparty=EntityRef(
            bank="Receiver Bank",
            account="A013644",
            entity_type=EntityType.MERCHANT,
            synthetic_region=4,
        ),
        amount_paid="69.54",
        payment_currency="CNY",
        amount_received="9.4",
        receiving_currency="USD",
        payment_format="Cash",
        cross_currency=True,
        currency_pair="CNY → USD",
        region_relationship=RegionRelationship.CROSS_REGION,
    )
    return InternalEvidence(
        evidence_id=f"ev:{case_ref}:selected",
        evidence_type=EvidenceType.SELECTED_TRANSACTION,
        case_ref=case_ref,
        facts=selected,
        supporting_transaction_refs=[selected.transaction_ref],
        ui_target=UITarget.SELECTED_TRANSACTION,
    )


def sender_evidence(case_ref: str = "demo-01") -> InternalEvidence:
    return InternalEvidence(
        evidence_id=f"ev:{case_ref}:sender-history",
        evidence_type=EvidenceType.SENDER_HISTORY,
        case_ref=case_ref,
        facts=SenderHistoryFacts(prior_outgoing_count=74),
        supporting_transaction_refs=[txref(1), txref(2)],
        ui_target=UITarget.SENDER_HISTORY,
    )


def amount_evidence(case_ref: str = "demo-01") -> InternalEvidence:
    return InternalEvidence(
        evidence_id=f"ev:{case_ref}:amount-history",
        evidence_type=EvidenceType.AMOUNT_HISTORY,
        case_ref=case_ref,
        facts=AmountHistoryFacts(
            history_quality=HistoryQuality.SUFFICIENT,
            sample_size=70,
            selected_amount="69.54",
            payment_currency="CNY",
            historical_median="15.095",
            empirical_percentile=95.7142857,
        ),
        supporting_transaction_refs=[txref(1), txref(2)],
        ui_target=UITarget.AMOUNT_CONTEXT,
    )


def counterparty_evidence(case_ref: str = "demo-01") -> InternalEvidence:
    return InternalEvidence(
        evidence_id=f"ev:{case_ref}:counterparty-history",
        evidence_type=EvidenceType.COUNTERPARTY_HISTORY,
        case_ref=case_ref,
        facts=CounterpartyHistoryFacts(
            seen_before=False,
            previous_interaction_count=0,
            first_previous_timestamp=None,
            most_recent_previous_timestamp=None,
        ),
        supporting_transaction_refs=[],
        ui_target=UITarget.COUNTERPARTY_HISTORY,
    )


def currency_evidence(
    case_ref: str = "demo-01",
    dimension: str = "payment",
    currency: str = "CNY",
) -> InternalEvidence:
    return InternalEvidence(
        evidence_id=f"ev:{case_ref}:currency:{dimension}:{currency}",
        evidence_type=EvidenceType.CURRENCY_HISTORY,
        case_ref=case_ref,
        facts=CurrencyHistoryFacts(
            dimension=CurrencyDimension(dimension),
            currency=currency,
            seen_before=True,
            previous_count=70,
            first_previous_timestamp="2025-01-01T00:00:00.000000",
            most_recent_previous_timestamp="2025-05-01T00:00:00.000000",
        ),
        supporting_transaction_refs=[txref(1)],
        ui_target=UITarget.HISTORICAL_EVIDENCE,
    )


class FakeService:
    def __init__(self) -> None:
        evidence = [
            selected_evidence(),
            sender_evidence(),
            amount_evidence(),
            counterparty_evidence(),
            currency_evidence(),
        ]
        self.evidence = {item.evidence_id: item for item in evidence}
        self.resolve_calls: list[str] = []

    def get_selected_transaction_evidence(self, case_ref: str) -> InternalEvidence:
        evidence_id = f"ev:{case_ref}:selected"
        if evidence_id not in self.evidence:
            raise CaseNotFoundError("missing")
        return self.evidence[evidence_id]

    def resolve_evidence(self, evidence_id: str) -> InternalEvidence:
        self.resolve_calls.append(evidence_id)
        if evidence_id not in self.evidence:
            raise EvidenceResolutionError("missing")
        return self.evidence[evidence_id]


def make_ai_config(tmp_path: Path) -> AIConfig:
    return AIConfig(
        model_identifier="configured-test-model",
        prompt_version="investigation-v1",
        prompt_path=known_prompt_path("investigation-v1"),
        api_key="test-key-not-for-network",
        trace_path=tmp_path / "traces" / "investigations.jsonl",
        input_usd_per_million=None,
        output_usd_per_million=None,
        eval_judge_model="configured-test-model",
    )
