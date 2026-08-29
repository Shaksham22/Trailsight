"""Frozen V2 AI configuration and prompt provenance."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import os
from pathlib import Path


DEFAULT_PROMPT_VERSION = "investigation-v1"
DEFAULT_TRACE_PATH = Path("data/traces/investigations-v2.jsonl")
DEFAULT_RUN_TIMEOUT_SECONDS = 60.0
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROMPT_FILES = {
    "investigation-v1": _PROJECT_ROOT / "prompts" / "v2" / "investigation-v1.md",
}


class AIConfigurationError(RuntimeError):
    """Raised when the AI-only runtime configuration is invalid or incomplete."""


@dataclass(frozen=True, slots=True)
class AIConfig:
    model_identifier: str
    prompt_version: str
    prompt_path: Path
    prompt_sha256: str
    api_key: str
    trace_path: Path
    input_usd_per_million: Decimal | None
    output_usd_per_million: Decimal | None
    run_timeout_seconds: float = DEFAULT_RUN_TIMEOUT_SECONDS


def known_prompt_path(prompt_version: str) -> Path:
    prompt_path = _PROMPT_FILES.get(prompt_version)
    if prompt_path is None:
        raise AIConfigurationError(
            f"Unknown TRAILSIGHT_PROMPT_VERSION: {prompt_version!r}"
        )
    if not prompt_path.is_file():
        raise AIConfigurationError(
            f"Configured prompt file is missing for version {prompt_version!r}"
        )
    return prompt_path


def load_prompt(prompt_version: str) -> str:
    return known_prompt_path(prompt_version).read_text(encoding="utf-8")


def prompt_sha256(prompt_version: str) -> str:
    return sha256(known_prompt_path(prompt_version).read_bytes()).hexdigest()


def load_ai_config() -> AIConfig:
    model_identifier = _required("TRAILSIGHT_MODEL")
    api_key = _required("OPENAI_API_KEY")
    prompt_version = os.environ.get(
        "TRAILSIGHT_PROMPT_VERSION", DEFAULT_PROMPT_VERSION
    ).strip()
    prompt_path = known_prompt_path(prompt_version)
    trace_raw = os.environ.get("TRAILSIGHT_TRACE_PATH", "").strip()
    trace_path = Path(trace_raw).expanduser() if trace_raw else DEFAULT_TRACE_PATH
    return AIConfig(
        model_identifier=model_identifier,
        prompt_version=prompt_version,
        prompt_path=prompt_path,
        prompt_sha256=sha256(prompt_path.read_bytes()).hexdigest(),
        api_key=api_key,
        trace_path=trace_path,
        input_usd_per_million=_optional_rate(
            "TRAILSIGHT_MODEL_INPUT_USD_PER_MILLION"
        ),
        output_usd_per_million=_optional_rate(
            "TRAILSIGHT_MODEL_OUTPUT_USD_PER_MILLION"
        ),
    )


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise AIConfigurationError(f"{name} is required for AI investigations")
    return value


def _optional_rate(name: str) -> Decimal | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    try:
        rate = Decimal(value)
    except InvalidOperation as exc:
        raise AIConfigurationError(f"{name} must be a decimal number") from exc
    if not rate.is_finite() or rate < 0:
        raise AIConfigurationError(f"{name} must be a non-negative finite number")
    return rate
