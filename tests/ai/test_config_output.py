from __future__ import annotations

import pytest
from pydantic import ValidationError

from trailsight_ai.config import AIConfigurationError, load_ai_config, load_prompt
from trailsight_ai.output import (
    Finding,
    InvestigationModelOutput,
    validate_output_for_mode,
)


def _configured_environment(monkeypatch) -> None:
    monkeypatch.setenv("TRAILSIGHT_MODEL", "model-from-environment")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("TRAILSIGHT_PROMPT_VERSION", "investigation-v1")


def test_missing_model_configuration_fails(monkeypatch) -> None:
    monkeypatch.delenv("TRAILSIGHT_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")

    with pytest.raises(AIConfigurationError, match="TRAILSIGHT_MODEL"):
        load_ai_config()


def test_known_prompt_and_exact_model_load(monkeypatch) -> None:
    _configured_environment(monkeypatch)

    config = load_ai_config()

    assert config.model_identifier == "model-from-environment"
    assert config.prompt_version == "investigation-v1"
    assert "smallest set of tools" in load_prompt(config.prompt_version)
    assert config.eval_judge_model == "model-from-environment"


def test_unknown_prompt_version_fails_without_path_loading(monkeypatch) -> None:
    _configured_environment(monkeypatch)
    monkeypatch.setenv("TRAILSIGHT_PROMPT_VERSION", "../../outside")

    with pytest.raises(AIConfigurationError, match="Unknown"):
        load_ai_config()


def test_optional_judge_and_pricing_configuration(monkeypatch) -> None:
    _configured_environment(monkeypatch)
    monkeypatch.setenv("TRAILSIGHT_EVAL_JUDGE_MODEL", "judge-exact")
    monkeypatch.setenv("TRAILSIGHT_MODEL_INPUT_USD_PER_MILLION", "1.25")
    monkeypatch.setenv("TRAILSIGHT_MODEL_OUTPUT_USD_PER_MILLION", "5")

    config = load_ai_config()

    assert config.eval_judge_model == "judge-exact"
    assert str(config.input_usd_per_million) == "1.25"
    assert str(config.output_usd_per_million) == "5"


def test_structured_output_accepts_valid_initial_and_unavailable() -> None:
    valid = InvestigationModelOutput(
        status="success",
        findings=[
            Finding(text="One fact.", evidence_ids=["ev:demo-01:selected"]),
            Finding(text="Another fact.", evidence_ids=["ev:demo-01:amount-history"]),
        ],
        limits=[],
    )
    unavailable = InvestigationModelOutput(
        status="unavailable",
        findings=[],
        limits=["Purpose information is unavailable."],
    )

    assert validate_output_for_mode(valid, mode="initial") is valid
    assert validate_output_for_mode(unavailable, mode="follow_up") is unavailable


def test_structured_output_rejects_over_four_and_display_labels() -> None:
    findings = [
        {"text": f"Fact {index}.", "evidence_ids": ["ev:demo-01:selected"]}
        for index in range(5)
    ]
    with pytest.raises(ValidationError):
        InvestigationModelOutput(status="success", findings=findings, limits=[])
    with pytest.raises(ValidationError, match="display evidence labels"):
        Finding(text="The fact [E1].", evidence_ids=["ev:demo-01:selected"])


def test_mode_specific_cardinality_has_no_free_text_fallback() -> None:
    one_finding = InvestigationModelOutput(
        status="success",
        findings=[Finding(text="Fact.", evidence_ids=["ev:demo-01:selected"])],
        limits=[],
    )
    with pytest.raises(ValueError, match="initial success"):
        validate_output_for_mode(one_finding, mode="initial")
    assert validate_output_for_mode(one_finding, mode="follow_up") is one_finding
    with pytest.raises(ValidationError):
        InvestigationModelOutput.model_validate("arbitrary prose")


def test_unavailable_requires_limit_and_zero_findings() -> None:
    missing_limit = InvestigationModelOutput(
        status="unavailable", findings=[], limits=[]
    )
    with pytest.raises(ValueError, match="at least one limit"):
        validate_output_for_mode(missing_limit, mode="follow_up")
    with pytest.raises(ValidationError):
        InvestigationModelOutput(
            status="unavailable",
            findings=[{"text": "Fact.", "evidence_ids": ["ev:demo-01:selected"]}],
            limits=["Unavailable."],
        )
