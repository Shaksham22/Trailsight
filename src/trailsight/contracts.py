"""Shared Pydantic contracts owned by the deterministic backend package."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


CaseRef = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
]
CanonicalTimestamp = Annotated[
    str,
    StringConstraints(
        pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}$"
    ),
]
CanonicalDecimalString = Annotated[
    str,
    StringConstraints(
        pattern=r"^(?:0|-?(?:[1-9][0-9]*(?:\.[0-9]*[1-9])?|0\.[0-9]*[1-9]))$"
    ),
]
TransactionRef = Annotated[
    str, StringConstraints(pattern=r"^tsx_[0-9a-f]{64}$")
]
EvidenceId = Annotated[str, StringConstraints(min_length=1)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntityType(str, Enum):
    PERSON = "Person"
    MERCHANT = "Merchant"


class HistoryQuality(str, Enum):
    INSUFFICIENT = "insufficient"
    LIMITED = "limited"
    SUFFICIENT = "sufficient"


class CurrencyDimension(str, Enum):
    PAYMENT = "payment"
    RECEIVING = "receiving"


class EvidenceType(str, Enum):
    SELECTED_TRANSACTION = "selected_transaction"
    SENDER_HISTORY = "sender_history"
    AMOUNT_HISTORY = "amount_history"
    COUNTERPARTY_HISTORY = "counterparty_history"
    REGION_HISTORY = "region_history"
    CURRENCY_HISTORY = "currency_history"


class UITarget(str, Enum):
    SELECTED_TRANSACTION = "selected_transaction"
    SENDER_HISTORY = "sender_history"
    AMOUNT_CONTEXT = "amount_context"
    COUNTERPARTY_HISTORY = "counterparty_history"
    SYNTHETIC_REGION_HISTORY = "synthetic_region_history"
    HISTORICAL_EVIDENCE = "historical_evidence"


class RegionRelationship(str, Enum):
    SAME_REGION = "same_region"
    CROSS_REGION = "cross_region"


class InvestigationRunStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    MODEL_ERROR = "model_error"
    TOOL_ERROR = "tool_error"
    STRUCTURED_OUTPUT_INVALID = "structured_output_invalid"
    EVIDENCE_VALIDATION_FAILED = "evidence_validation_failed"


class EntityRef(ContractModel):
    bank: str
    account: str
    entity_type: EntityType
    synthetic_region: int = Field(ge=0, le=19)


class SelectedTransaction(ContractModel):
    transaction_ref: TransactionRef
    timestamp: CanonicalTimestamp
    sender: EntityRef
    counterparty: EntityRef
    amount_paid: CanonicalDecimalString
    payment_currency: str
    amount_received: CanonicalDecimalString
    receiving_currency: str
    payment_format: str
    cross_currency: bool
    currency_pair: str
    region_relationship: RegionRelationship


class SenderHistoryContext(ContractModel):
    evidence_id: EvidenceId
    prior_outgoing_count: int = Field(ge=0)


class AmountHistoryContext(ContractModel):
    evidence_id: EvidenceId
    history_quality: HistoryQuality
    sample_size: int = Field(ge=0)
    selected_amount: CanonicalDecimalString
    payment_currency: str
    historical_median: CanonicalDecimalString | None
    empirical_percentile: float | None = Field(default=None, ge=0, le=100)


class CounterpartyHistoryContext(ContractModel):
    evidence_id: EvidenceId
    seen_before: bool
    previous_interaction_count: int = Field(ge=0)
    first_previous_timestamp: CanonicalTimestamp | None
    most_recent_previous_timestamp: CanonicalTimestamp | None


class RegionHistoryContext(ContractModel):
    evidence_id: EvidenceId
    sender_region: int = Field(ge=0, le=19)
    receiver_region: int = Field(ge=0, le=19)
    region_relationship: RegionRelationship
    receiver_region_seen_before: bool
    previous_receiver_region_count: int = Field(ge=0)


class HistoricalTransactionRow(ContractModel):
    transaction_ref: TransactionRef
    timestamp: CanonicalTimestamp
    counterparty_bank: str
    counterparty_account: str
    counterparty_type: EntityType
    amount_paid: CanonicalDecimalString
    payment_currency: str
    receiving_currency: str
    receiver_region: int = Field(ge=0, le=19)
    payment_format: str


class WorkspaceResponse(ContractModel):
    case_ref: CaseRef
    display_name: str
    selected_transaction: SelectedTransaction
    sender_history: SenderHistoryContext
    amount_history: AmountHistoryContext
    counterparty_history: CounterpartyHistoryContext
    region_history: RegionHistoryContext | None
    historical_transactions: list[HistoricalTransactionRow]


class CaseSummary(ContractModel):
    case_ref: CaseRef
    display_name: str


class CaseListResponse(ContractModel):
    cases: list[CaseSummary]


class ErrorDetail(ContractModel):
    code: str
    message: str


class ApplicationError(ContractModel):
    error: ErrorDetail


class RenderedCitation(ContractModel):
    label: Annotated[str, StringConstraints(pattern=r"^E[1-9][0-9]*$")]
    evidence_id: EvidenceId


class RenderedFinding(ContractModel):
    text: str
    citations: list[RenderedCitation]


class DisplayEvidence(ContractModel):
    label: Annotated[str, StringConstraints(pattern=r"^E[1-9][0-9]*$")]
    evidence_id: EvidenceId
    evidence_type: EvidenceType
    ui_target: UITarget
    supporting_transaction_refs: list[TransactionRef]


class InvestigationResponse(ContractModel):
    investigation_id: str
    case_ref: CaseRef
    parent_investigation_id: str | None
    run_status: InvestigationRunStatus
    findings: list[RenderedFinding]
    limits: list[str]
    evidence: list[DisplayEvidence]


class FollowUpRequest(ContractModel):
    question: str
    parent_investigation_id: str | None = None

    @field_validator("question", mode="before")
    @classmethod
    def validate_question(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("question must be a string")
        question = value.strip()
        if not 1 <= len(question) <= 500:
            raise ValueError("question must contain 1 to 500 characters after trimming")
        return question


class SenderHistoryFacts(ContractModel):
    prior_outgoing_count: int = Field(ge=0)


class AmountHistoryFacts(ContractModel):
    history_quality: HistoryQuality
    sample_size: int = Field(ge=0)
    selected_amount: CanonicalDecimalString
    payment_currency: str
    historical_median: CanonicalDecimalString | None
    empirical_percentile: float | None = Field(default=None, ge=0, le=100)


class CounterpartyHistoryFacts(ContractModel):
    seen_before: bool
    previous_interaction_count: int = Field(ge=0)
    first_previous_timestamp: CanonicalTimestamp | None
    most_recent_previous_timestamp: CanonicalTimestamp | None


class RegionHistoryFacts(ContractModel):
    sender_region: int = Field(ge=0, le=19)
    receiver_region: int = Field(ge=0, le=19)
    region_relationship: RegionRelationship
    receiver_region_seen_before: bool
    previous_receiver_region_count: int = Field(ge=0)


class CurrencyHistoryFacts(ContractModel):
    dimension: CurrencyDimension
    currency: CurrencyCode
    seen_before: bool
    previous_count: int = Field(ge=0)
    first_previous_timestamp: CanonicalTimestamp | None
    most_recent_previous_timestamp: CanonicalTimestamp | None


EvidenceFacts: TypeAlias = (
    SelectedTransaction
    | SenderHistoryFacts
    | AmountHistoryFacts
    | CounterpartyHistoryFacts
    | RegionHistoryFacts
    | CurrencyHistoryFacts
)


class InternalEvidence(ContractModel):
    evidence_id: EvidenceId
    evidence_type: EvidenceType
    case_ref: CaseRef
    facts: EvidenceFacts
    supporting_transaction_refs: list[TransactionRef]
    ui_target: UITarget


RegionHistoryDecision = Literal["retained"]
