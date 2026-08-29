"""Sanitized one-record-per-run JSONL telemetry for Trailsight V2 AI."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import logging
from pathlib import Path
import threading
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


LOGGER = logging.getLogger(__name__)
TRACE_SCHEMA_VERSION = "investigation-trace-v2"
_TRACE_LOCK = threading.Lock()
_FORBIDDEN_RUNTIME_STRINGS = ("is laundering", "patterns.txt")


class TelemetryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TokenUsageV2(TelemetryModel):
    requests: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class MCPCallTraceV2(TelemetryModel):
    sequence: int = Field(ge=1)
    tool_name: str
    safe_input_summary: dict[str, Any]
    started_at: str
    latency_ms: float = Field(ge=0)
    result_status: str
    result_size_bytes: int = Field(ge=0)
    evidence_ids: tuple[str, ...] = ()

    @field_validator("safe_input_summary")
    @classmethod
    def safe_input_has_no_hidden_truth(cls, value: dict[str, Any]) -> dict[str, Any]:
        assert_runtime_safe(value)
        return value


class InvestigationTraceV2(TelemetryModel):
    trace_schema_version: Literal["investigation-trace-v2"] = TRACE_SCHEMA_VERSION
    investigation_id: str
    parent_investigation_id: str | None
    subject_type: str
    subject_ref: str
    origin_alert_ref: str | None
    origin_transaction_ref: str | None
    snapshot_id: str | None
    detector_cutoff: str | None
    prompt_version: str
    prompt_sha256: str
    model_identifier: str
    started_at: str
    finished_at: str
    latency_ms: float = Field(ge=0)
    run_status: str
    mcp_calls: tuple[MCPCallTraceV2, ...]
    referenced_evidence_ids: tuple[str, ...]
    validation_status: Literal["PASSED", "FAILED", "NOT_RUN"]
    token_usage: TokenUsageV2
    estimated_cost_usd: float | None
    failure_code: str | None

    @field_validator("model_identifier", "subject_ref")
    @classmethod
    def no_hidden_truth_in_text(cls, value: str) -> str:
        assert_runtime_safe(value)
        return value


def utc_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def estimate_cost_usd(
    usage: TokenUsageV2,
    *,
    input_usd_per_million: Decimal | None,
    output_usd_per_million: Decimal | None,
) -> float | None:
    if input_usd_per_million is None or output_usd_per_million is None:
        return None
    cost = (
        Decimal(usage.input_tokens) * input_usd_per_million
        + Decimal(usage.output_tokens) * output_usd_per_million
    ) / Decimal(1_000_000)
    return float(cost)


def assert_runtime_safe(value: Any) -> None:
    """Reject the two frozen hidden-truth identifiers from runtime logs/tool metadata."""
    serialized = str(value).lower()
    if any(token in serialized for token in _FORBIDDEN_RUNTIME_STRINGS):
        raise ValueError("hidden benchmark truth must not enter runtime telemetry")


def append_trace(path: Path, trace: InvestigationTraceV2) -> None:
    serialized = trace.model_dump_json() + "\n"
    assert_runtime_safe(serialized)
    with _TRACE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()


def append_trace_safely(path: Path, trace: InvestigationTraceV2) -> None:
    try:
        append_trace(path, trace)
    except Exception:
        LOGGER.warning("Trailsight V2 AI trace could not be written", exc_info=True)
