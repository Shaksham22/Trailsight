"""Structured model output and HTTP-facing AI response contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trailsight_v2.domain.models import InvestigationContextV2, SubjectType


class AIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvestigationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class InvestigationSummaryV2(AIModel):
    """The complete model-authored response for a bounded investigation packet.

    This schema intentionally contains no Evidence V2 identifiers. Packet construction
    and MCP scope are the runtime trust boundary; the application only validates that
    the provider returned this structural contract.
    """

    summary: str = Field(min_length=1, max_length=4000)
    observations: list[str] = Field(default_factory=list, max_length=8)
    patterns: list[str] = Field(default_factory=list, max_length=6)
    limits: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summary must be non-empty")
        return normalized

    @field_validator("observations", "patterns", "limits")
    @classmethod
    def normalize_sections(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("summary section items must be non-empty")
        return normalized


class InvestigationResponseV2(AIModel):
    investigation_id: str
    run_status: InvestigationStatus
    subject_type: SubjectType
    subject_ref: str
    context: InvestigationContextV2
    summary: str
    observations: tuple[str, ...]
    patterns: tuple[str, ...]
    limits: tuple[str, ...]


class CreateInvestigationRequestV2(AIModel):
    subject_type: SubjectType
    subject_ref: str = Field(min_length=1)
    origin_alert_ref: str | None = Field(default=None, min_length=1)
    origin_transaction_ref: str | None = Field(default=None, min_length=1)


class FollowUpRequestV2(AIModel):
    question: str = Field(min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("follow-up question must be non-empty")
        return question
