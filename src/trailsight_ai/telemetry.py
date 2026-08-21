"""Sanitized JSONL telemetry for completed and failed AI runs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import logging
from pathlib import Path
import threading
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


LOGGER = logging.getLogger(__name__)
TRACE_SCHEMA_VERSION = 1
_TRACE_LOCK = threading.Lock()


class TelemetryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TokenUsage(TelemetryModel):
    requests: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ToolCallTrace(TelemetryModel):
    sequence: int = Field(ge=1)
    tool_name: str
    safe_input: dict[str, Any]
    started_at: str
    status: str
    latency_ms: float = Field(ge=0)
    result_size_bytes: int = Field(ge=0)
    evidence_id: str | None


class InvestigationTrace(TelemetryModel):
    trace_schema_version: Literal[1] = TRACE_SCHEMA_VERSION
    investigation_id: str
    parent_investigation_id: str | None
    case_ref: str
    prompt_version: str
    model_identifier: str
    started_at: str
    finished_at: str
    latency_ms: float = Field(ge=0)
    run_status: str
    tool_calls: list[ToolCallTrace]
    token_usage: TokenUsage
    estimated_cost_usd: float | None
    referenced_evidence_ids: list[str]
    validation_status: Literal["passed", "failed", "not_run"]
    failure_code: str | None


def utc_timestamp(value: datetime) -> str:
    """Serialize aware UTC timestamps with a stable trailing Z."""

    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def estimate_cost_usd(
    usage: TokenUsage,
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


def append_trace(path: Path, trace: InvestigationTrace) -> None:
    """Append exactly one compact JSON object to the configured JSONL path."""

    serialized = trace.model_dump_json() + "\n"
    with _TRACE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(serialized)


def append_trace_safely(path: Path, trace: InvestigationTrace) -> None:
    """Keep trace filesystem failures from replacing the product response."""

    try:
        append_trace(path, trace)
    except Exception:
        LOGGER.warning("Trailsight AI trace could not be written", exc_info=True)
