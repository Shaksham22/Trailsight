"""Exact model-facing input and output contracts for the Trailsight MCP tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from trailsight.contracts import (
    CanonicalDecimalString,
    CanonicalTimestamp,
    CaseRef,
    CurrencyCode,
    CurrencyDimension,
    HistoryQuality,
    RegionRelationship,
)


MAX_SERIALIZED_RESULT_BYTES = 4096

ErrorCode = Literal[
    "invalid_case",
    "invalid_input",
    "domain_error",
    "result_too_large",
]


class McpContractModel(BaseModel):
    """Forbid unapproved fields at every MCP contract boundary."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_serialization_defaults_required=True,
    )


class CaseRefInput(McpContractModel):
    case_ref: CaseRef


class CurrencyHistoryInput(McpContractModel):
    case_ref: CaseRef
    dimension: CurrencyDimension
    currency: CurrencyCode


class SenderHistoryResult(McpContractModel):
    status: Literal["ok", "not_found", "error"]
    evidence_id: str | None = None
    prior_outgoing_count: int | None = Field(default=None, ge=0)
    error_code: ErrorCode | None = None


class AmountHistoryResult(McpContractModel):
    status: Literal["ok", "insufficient_history", "not_found", "error"]
    evidence_id: str | None = None
    payment_currency: str | None = None
    selected_amount: CanonicalDecimalString | None = None
    sample_size: int | None = Field(default=None, ge=0)
    history_quality: HistoryQuality | None = None
    historical_median: CanonicalDecimalString | None = None
    empirical_percentile: float | None = Field(default=None, ge=0, le=100)
    error_code: ErrorCode | None = None


class CounterpartyHistoryResult(McpContractModel):
    status: Literal["ok", "not_found", "error"]
    evidence_id: str | None = None
    seen_before: bool | None = None
    previous_interaction_count: int | None = Field(default=None, ge=0)
    first_previous_timestamp: CanonicalTimestamp | None = None
    most_recent_previous_timestamp: CanonicalTimestamp | None = None
    error_code: ErrorCode | None = None


class RegionHistoryResult(McpContractModel):
    status: Literal["ok", "not_found", "error"]
    evidence_id: str | None = None
    sender_region: int | None = Field(default=None, ge=0, le=19)
    receiver_region: int | None = Field(default=None, ge=0, le=19)
    region_relationship: RegionRelationship | None = None
    receiver_region_seen_before: bool | None = None
    previous_receiver_region_count: int | None = Field(default=None, ge=0)
    error_code: ErrorCode | None = None


class CurrencyHistoryResult(McpContractModel):
    status: Literal["ok", "not_found", "error"]
    evidence_id: str | None = None
    dimension: CurrencyDimension | None = None
    currency: CurrencyCode | None = None
    seen_before: bool | None = None
    previous_count: int | None = Field(default=None, ge=0)
    first_previous_timestamp: CanonicalTimestamp | None = None
    most_recent_previous_timestamp: CanonicalTimestamp | None = None
    error_code: ErrorCode | None = None


McpResult = (
    SenderHistoryResult
    | AmountHistoryResult
    | CounterpartyHistoryResult
    | RegionHistoryResult
    | CurrencyHistoryResult
)


def serialize_result(result: McpResult) -> bytes:
    """Serialize one complete model-facing projection as compact UTF-8 JSON."""

    return result.model_dump_json().encode("utf-8")
