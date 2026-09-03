"""Typed, bounded model-facing contracts for the seven Trailsight V2 MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class McpContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_serialization_defaults_required=True,
    )


ToolStatus = Literal["OK", "ERROR"]
ErrorCode = Literal[
    "NOT_FOUND",
    "INVALID_INPUT",
    "INVALID_CONTEXT",
    "DATA_INTEGRITY_ERROR",
    "RESULT_TOO_LARGE",
]


class AlertContextInput(McpContractModel):
    alert_ref: str = Field(min_length=1)


class TransactionContextInput(McpContractModel):
    transaction_ref: str = Field(min_length=1)


class AccountContextInput(McpContractModel):
    account_ref: str = Field(min_length=1)


class BehavioralIndicatorsInput(McpContractModel):
    account_ref: str | None = Field(default=None, min_length=1)


class RelationshipContextInput(McpContractModel):
    account_ref: str = Field(min_length=1)
    counterparty_account_ref: str = Field(min_length=1)


class NetworkContextInput(McpContractModel):
    account_ref: str = Field(min_length=1)


class SupportingEvidenceInput(McpContractModel):
    evidence_id: str = Field(min_length=1)


class AccountDisplaySummary(McpContractModel):
    account_ref: str
    bank_id: str
    account_id: str


class VelocitySummary(McpContractModel):
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)
    total_count: int = Field(ge=0)


class AmountBehaviorSummary(McpContractModel):
    side: str
    account_ref: str
    history_quality: str
    sample_size: int = Field(ge=0)
    selected_amount: str
    currency: str
    historical_median: str | None
    empirical_percentile: float | None = Field(default=None, ge=0, le=100)


class RelationshipSummary(McpContractModel):
    counterparty_account_ref: str
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    first_historical_timestamp: str | None
    last_historical_timestamp: str | None
    selected_relationship: bool


class RelationshipNoveltySummary(McpContractModel):
    account_ref: str
    counterparty_account_ref: str
    seen_before: bool
    new_counterparty: bool
    previous_interaction_count: int = Field(ge=0)
    root_to_counterparty_count: int = Field(ge=0)
    counterparty_to_root_count: int = Field(ge=0)
    first_previous_timestamp: str | None
    most_recent_previous_timestamp: str | None


class NetworkBehaviorSummary(McpContractModel):
    account_ref: str
    velocity_1h: VelocitySummary
    velocity_24h: VelocitySummary
    fan_in_24h: int = Field(ge=0)
    fan_out_24h: int = Field(ge=0)


class CrossCurrencySummary(McpContractModel):
    transaction_ref: str
    cross_currency: bool
    currency_pair: str


class BlockMeasureSupport(McpContractModel):
    block_measure_1: float | None
    block_measure_2: float | None
    block_measure_3: float | None


class SupportingTransactionSummary(McpContractModel):
    transaction_ref: str
    transaction_timestamp: str
    from_account_ref: str
    from_bank_id: str
    to_account_ref: str
    to_bank_id: str
    amount_paid: str
    payment_currency: str
    amount_received: str
    receiving_currency: str
    payment_format: str
    cross_currency: bool


class AlertContextResult(McpContractModel):
    status: ToolStatus
    evidence_id: str | None = None
    alert_ref: str | None = None
    account_ref: str | None = None
    entry_snapshot_id: str | None = None
    entry_cutoff: str | None = None
    network_review_band: str | None = None
    network_pattern_score: float | None = None
    rank: int | None = None
    percentile: float | None = None
    reason: str | None = None
    review_status: str | None = None
    error_code: ErrorCode | None = None


class TransactionContextResult(McpContractModel):
    status: ToolStatus
    evidence_ids: tuple[str, ...] = ()
    transaction_ref: str | None = None
    timestamp: str | None = None
    sender: AccountDisplaySummary | None = None
    receiver: AccountDisplaySummary | None = None
    amount_paid: str | None = None
    payment_currency: str | None = None
    amount_received: str | None = None
    receiving_currency: str | None = None
    payment_format: str | None = None
    cross_currency: bool | None = None
    sender_band: str | None = None
    receiver_band: str | None = None
    aml_review_priority: str | None = None
    snapshot_id: str | None = None
    detector_cutoff: str | None = None
    derivation_text: str | None = None
    sending_bank_country: str | None = None
    receiving_bank_country: str | None = None
    same_bank_country: bool | None = None
    error_code: ErrorCode | None = None


class AccountContextResult(McpContractModel):
    status: ToolStatus
    evidence_ids: tuple[str, ...] = ()
    account_ref: str | None = None
    bank_id: str | None = None
    account_id: str | None = None
    bank_country: str | None = None
    snapshot_id: str | None = None
    detector_cutoff: str | None = None
    network_review_band: str | None = None
    network_pattern_score: float | None = None
    rank: int | None = None
    eligible_account_count: int | None = Field(default=None, ge=0)
    percentile: float | None = None
    unscored_reason: str | None = None
    incoming_count: int | None = Field(default=None, ge=0)
    outgoing_count: int | None = Field(default=None, ge=0)
    distinct_counterparties: int | None = Field(default=None, ge=0)
    first_observed: str | None = None
    most_recent_observed: str | None = None
    error_code: ErrorCode | None = None


class BehavioralIndicatorsResult(McpContractModel):
    status: ToolStatus
    evidence_ids: tuple[str, ...] = ()
    amount_behavior: tuple[AmountBehaviorSummary, ...] | None = None
    counterparty_novelty: RelationshipNoveltySummary | None = None
    network_behavior: tuple[NetworkBehaviorSummary, ...] = ()
    cross_currency: CrossCurrencySummary | None = None
    error_code: ErrorCode | None = None


class RelationshipContextResult(McpContractModel):
    status: ToolStatus
    evidence_id: str | None = None
    seen_before: bool | None = None
    previous_interaction_count: int | None = Field(default=None, ge=0)
    root_to_counterparty_count: int | None = Field(default=None, ge=0)
    counterparty_to_root_count: int | None = Field(default=None, ge=0)
    first_previous_timestamp: str | None = None
    most_recent_previous_timestamp: str | None = None
    error_code: ErrorCode | None = None


class NetworkContextResult(McpContractModel):
    status: ToolStatus
    evidence_ids: tuple[str, ...] = ()
    account_ref: str | None = None
    snapshot_id: str | None = None
    detector_cutoff: str | None = None
    network_review_band: str | None = None
    eligible_account_count: int | None = Field(default=None, ge=0)
    first_order_neighbor_count: int | None = Field(default=None, ge=0)
    second_order_neighbor_count: int | None = Field(default=None, ge=0)
    block_measure_support: BlockMeasureSupport | None = None
    total_direct_counterparties: int | None = Field(default=None, ge=0)
    shown_counterparties: int | None = Field(default=None, ge=0, le=12)
    truncated: bool | None = None
    relationships: tuple[RelationshipSummary, ...] = ()
    error_code: ErrorCode | None = None


class SupportingEvidenceResult(McpContractModel):
    status: ToolStatus
    evidence_id: str | None = None
    supporting_transaction_count: int | None = Field(default=None, ge=0)
    transactions: tuple[SupportingTransactionSummary, ...] = ()
    truncated: bool | None = None
    error_code: ErrorCode | None = None


McpResult = (
    AlertContextResult
    | TransactionContextResult
    | AccountContextResult
    | BehavioralIndicatorsResult
    | RelationshipContextResult
    | NetworkContextResult
    | SupportingEvidenceResult
)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[McpContractModel]
    output_model: type[McpContractModel]
    adapter_method: str
    max_result_bytes: int


TOOL_SPECS = (
    ToolSpec(
        "get_alert_context",
        "Explain the current bounded Network Pattern Alert context and workflow review status.",
        AlertContextInput,
        AlertContextResult,
        "get_alert_context",
        4 * 1024,
    ),
    ToolSpec(
        "get_transaction_context",
        "Return selected transaction facts and deterministic AML Review Priority derivation.",
        TransactionContextInput,
        TransactionContextResult,
        "get_transaction_context",
        4 * 1024,
    ),
    ToolSpec(
        "get_account_context",
        "Return detector state and bounded observed activity for an authorized root account.",
        AccountContextInput,
        AccountContextResult,
        "get_account_context",
        5 * 1024,
    ),
    ToolSpec(
        "get_behavioral_indicators",
        "Return deterministic amount, relationship, velocity, fan-in/fan-out, and currency indicators.",
        BehavioralIndicatorsInput,
        BehavioralIndicatorsResult,
        "get_behavioral_indicators",
        8 * 1024,
    ),
    ToolSpec(
        "get_relationship_context",
        "Return deterministic prior interaction facts for one authorized direct counterparty.",
        RelationshipContextInput,
        RelationshipContextResult,
        "get_relationship_context",
        4 * 1024,
    ),
    ToolSpec(
        "get_network_context",
        "Return one-hop network summaries plus persisted GARG structural detector support.",
        NetworkContextInput,
        NetworkContextResult,
        "get_network_context",
        12 * 1024,
    ),
    ToolSpec(
        "get_supporting_evidence",
        "Return at most eight concrete transaction examples for evidence already issued in this run; valid structural evidence may return an OK empty result.",
        SupportingEvidenceInput,
        SupportingEvidenceResult,
        "get_supporting_evidence",
        12 * 1024,
    ),
)

TOOL_NAMES = tuple(spec.name for spec in TOOL_SPECS)


def serialize_result(result: McpResult) -> bytes:
    return result.model_dump_json().encode("utf-8")
