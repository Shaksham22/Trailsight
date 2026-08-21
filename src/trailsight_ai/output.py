"""Typed structured-output contracts for model and support-judge responses."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_DISPLAY_LABEL = re.compile(r"\[E[1-9][0-9]*\]", re.IGNORECASE)


class AIOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Finding(AIOutputModel):
    text: str
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("finding text must not be empty")
        if _DISPLAY_LABEL.search(text):
            raise ValueError("display evidence labels do not belong in model prose")
        return text

    @field_validator("evidence_ids")
    @classmethod
    def non_empty_evidence_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("evidence IDs must not be empty")
        return normalized


class InvestigationModelOutput(AIOutputModel):
    status: Literal["success", "partial", "unavailable"]
    findings: list[Finding] = Field(max_length=4)
    limits: list[str] = Field(max_length=3)

    @field_validator("limits")
    @classmethod
    def non_empty_limits(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("limits must not contain empty strings")
        return normalized

    @model_validator(mode="after")
    def unavailable_shape(self) -> InvestigationModelOutput:
        if self.status == "unavailable" and self.findings:
            raise ValueError("unavailable output must not contain findings")
        return self


class SupportJudgeOutput(AIOutputModel):
    verdict: Literal["supported", "contradicted", "unsupported"]
    reason: str

    @field_validator("reason")
    @classmethod
    def non_empty_reason(cls, value: str) -> str:
        reason = value.strip()
        if not reason:
            raise ValueError("judge reason must not be empty")
        return reason


def validate_output_for_mode(
    output: InvestigationModelOutput,
    *,
    mode: Literal["initial", "follow_up"],
) -> InvestigationModelOutput:
    """Apply run-mode cardinality rules after SDK schema validation."""

    finding_count = len(output.findings)
    if output.status == "success":
        minimum, maximum = (2, 4) if mode == "initial" else (1, 3)
        if not minimum <= finding_count <= maximum:
            raise ValueError(
                f"{mode} success requires {minimum} to {maximum} findings"
            )
    elif output.status == "partial":
        maximum = 4 if mode == "initial" else 3
        if not 1 <= finding_count <= maximum:
            raise ValueError(f"{mode} partial requires 1 to {maximum} findings")
        if not output.limits:
            raise ValueError("partial output must explain at least one limit")
    elif output.status == "unavailable":
        if finding_count != 0 or not output.limits:
            raise ValueError(
                "unavailable output requires zero findings and at least one limit"
            )
    return output
