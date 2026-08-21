"""Configuration boundary for the Trailsight AI package."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path


DEFAULT_PROMPT_VERSION = "investigation-v1"
DEFAULT_TRACE_PATH = Path("data/traces/investigations.jsonl")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROMPT_FILES = {
    "investigation-v1": _PROJECT_ROOT / "prompts" / "investigation-v1.md",
    "investigation-v2": _PROJECT_ROOT / "prompts" / "investigation-v2.md",
}


class AIConfigurationError(RuntimeError):
    """Raised when required AI-only runtime configuration is invalid."""


@dataclass(frozen=True, slots=True)
class AIConfig:
    model_identifier: str
    prompt_version: str
    prompt_path: Path
    api_key: str
    trace_path: Path
    input_usd_per_million: Decimal | None
    output_usd_per_million: Decimal | None
    eval_judge_model: str


def known_prompt_path(prompt_version: str) -> Path:
    """Resolve one checked-in prompt version without accepting arbitrary paths."""

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
    """Load one known, checked-in investigation prompt."""

    return known_prompt_path(prompt_version).read_text(encoding="utf-8")


def load_ai_config() -> AIConfig:
    """Load only the frozen AI/eval environment variables."""

    model_identifier = _required("TRAILSIGHT_MODEL")
    api_key = _required("OPENAI_API_KEY")
    prompt_version = os.environ.get(
        "TRAILSIGHT_PROMPT_VERSION", DEFAULT_PROMPT_VERSION
    ).strip()
    prompt_path = known_prompt_path(prompt_version)
    trace_value = os.environ.get("TRAILSIGHT_TRACE_PATH")
    trace_path = Path(trace_value) if trace_value else DEFAULT_TRACE_PATH
    input_rate = _optional_rate("TRAILSIGHT_MODEL_INPUT_USD_PER_MILLION")
    output_rate = _optional_rate("TRAILSIGHT_MODEL_OUTPUT_USD_PER_MILLION")
    judge_model = os.environ.get("TRAILSIGHT_EVAL_JUDGE_MODEL", "").strip()
    if not judge_model:
        judge_model = model_identifier

    return AIConfig(
        model_identifier=model_identifier,
        prompt_version=prompt_version,
        prompt_path=prompt_path,
        api_key=api_key,
        trace_path=trace_path,
        input_usd_per_million=input_rate,
        output_usd_per_million=output_rate,
        eval_judge_model=judge_model,
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
