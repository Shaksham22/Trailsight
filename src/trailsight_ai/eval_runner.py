"""Repeatable live evaluator for Trailsight's 15 required AI scenarios."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any, Literal, Protocol

from agents import Agent, RunConfig, Runner
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from trailsight.api.app import create_investigation_service
from trailsight.contracts import InvestigationRunStatus
from trailsight_ai.config import AIConfig, load_ai_config
from trailsight_ai.output import SupportJudgeOutput
from trailsight_ai.runner import InvestigationRun, InvestigationRunner
from trailsight_ai.telemetry import TokenUsage, estimate_cost_usd


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCENARIOS_PATH = _PROJECT_ROOT / "evals" / "scenarios.yaml"
_CASES_PATH = _PROJECT_ROOT / "data" / "cases" / "cases.yaml"
_RESULTS_ROOT = _PROJECT_ROOT / "eval_results"
_REQUIRED_TOOL_NAMES = {
    "get_sender_history",
    "compare_amount_history",
    "get_counterparty_history",
    "get_region_history",
    "get_currency_history",
}
_GLOBAL_FORBIDDEN_CLAIMS = (
    "money laundering",
    "laundering",
    "fraud",
    "suspicious",
    "block the transaction",
)
_TIMESTAMP_PATTERN = re.compile(
    r"\b(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    r"(?:(?:T| at )(?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?))?\b"
)
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(-?[0-9]+(?:\.[0-9]+)?)(%?)")
_CURRENCY_PATTERN = re.compile(r"\b[A-Z]{3}\b")


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvalScenario(EvalModel):
    id: str
    case_ref: str
    mode: Literal["initial", "follow_up"]
    question: str | None
    required_tools: list[str]
    allowed_tools: list[str]
    forbidden_tools: list[str]
    expected_evidence_types: list[str]
    expected_status: str
    max_total_tool_calls: int = Field(ge=0)
    forbidden_claims: list[str]
    notes: str | None

    @model_validator(mode="after")
    def validate_tool_sets(self) -> EvalScenario:
        required = set(self.required_tools)
        allowed = set(self.allowed_tools)
        forbidden = set(self.forbidden_tools)
        if not required <= allowed:
            raise ValueError("required_tools must be a subset of allowed_tools")
        if allowed & forbidden:
            raise ValueError("allowed_tools and forbidden_tools must not overlap")
        if not (required | allowed | forbidden) <= _REQUIRED_TOOL_NAMES:
            raise ValueError("scenario names an unknown Trailsight tool")
        if self.mode == "initial" and self.question is not None:
            raise ValueError("initial scenarios must not include a question")
        if self.mode == "follow_up" and not (self.question or "").strip():
            raise ValueError("follow-up scenarios require a question")
        if self.expected_status == "unavailable" and self.allowed_tools:
            raise ValueError("unsupported scenarios must allow no tools")
        return self


class ScenarioFile(EvalModel):
    scenarios: list[EvalScenario]


@dataclass(frozen=True, slots=True)
class JudgeResult:
    output: SupportJudgeOutput
    token_usage: TokenUsage


class FindingJudge(Protocol):
    async def judge(
        self,
        *,
        finding_text: str,
        evidence_summaries: list[dict[str, Any]],
    ) -> JudgeResult: ...


class AgentsSDKSupportJudge:
    """Eval-only structured semantic support judge with no tools or memory."""

    def __init__(self, config: AIConfig) -> None:
        self._config = config
        self._prompt = (_PROJECT_ROOT / "prompts" / "support-judge-v1.md").read_text(
            encoding="utf-8"
        )

    async def judge(
        self,
        *,
        finding_text: str,
        evidence_summaries: list[dict[str, Any]],
    ) -> JudgeResult:
        payload = json.dumps(
            {
                "finding": finding_text,
                "cited_model_facing_evidence": evidence_summaries,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        async with AsyncOpenAI(
            api_key=self._config.api_key,
            max_retries=0,
        ) as openai_client:
            agent = Agent(
                name="Trailsight eval support judge",
                instructions=self._prompt,
                model=self._config.eval_judge_model,
                output_type=SupportJudgeOutput,
            )
            result = await Runner.run(
                agent,
                payload,
                max_turns=2,
                run_config=RunConfig(
                    model_provider=OpenAIProvider(openai_client=openai_client),
                    tracing_disabled=True,
                    workflow_name="Trailsight factual support eval",
                ),
            )
        output = result.final_output
        if not isinstance(output, SupportJudgeOutput):
            output = SupportJudgeOutput.model_validate(output)
        usage = result.context_wrapper.usage
        return JudgeResult(
            output=output,
            token_usage=TokenUsage(
                requests=usage.requests,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
            ),
        )


def load_required_scenarios(
    scenarios_path: Path = _SCENARIOS_PATH,
    cases_path: Path = _CASES_PATH,
) -> list[EvalScenario]:
    """Load and validate exactly the frozen 15 required scenarios."""

    scenario_data = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    scenario_file = ScenarioFile.model_validate(scenario_data)
    scenarios = scenario_file.scenarios
    if len(scenarios) != 15:
        raise ValueError("evals/scenarios.yaml must contain exactly 15 required scenarios")
    ids = [scenario.id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("eval scenario IDs must be unique")

    case_data = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    known_cases = {entry["case_ref"] for entry in case_data.get("cases", [])}
    unknown_cases = sorted({scenario.case_ref for scenario in scenarios} - known_cases)
    if unknown_cases:
        raise ValueError(f"eval scenarios use unknown cases: {unknown_cases}")

    required_categories = {
        "initial": sum(scenario.mode == "initial" for scenario in scenarios),
        "follow_up": sum(scenario.mode == "follow_up" for scenario in scenarios),
        "unsupported": sum(
            scenario.expected_status == "unavailable" for scenario in scenarios
        ),
    }
    if required_categories != {"initial": 4, "follow_up": 11, "unsupported": 3}:
        raise ValueError("required eval category counts do not match the WP04 contract")
    return scenarios


async def evaluate_scenario(
    scenario: EvalScenario,
    run: InvestigationRun,
    judge: FindingJudge,
    *,
    config: AIConfig,
) -> dict[str, Any]:
    """Apply deterministic checks and the bounded semantic support judge."""

    called_tools = [call.tool_name for call in run.tool_calls]
    called_set = set(called_tools)
    tool_selection = (
        "PASS"
        if set(scenario.required_tools) <= called_set
        and called_set <= set(scenario.allowed_tools)
        else "FAIL"
    )
    signatures = [
        (call.tool_name, json.dumps(call.safe_input, sort_keys=True))
        for call in run.tool_calls
    ]
    has_duplicate = any(count > 1 for count in Counter(signatures).values())
    tool_efficiency = (
        "PASS"
        if not has_duplicate
        and len(run.tool_calls) <= scenario.max_total_tool_calls
        and not (called_set & set(scenario.forbidden_tools))
        and _currency_input_matches_scenario(scenario, run)
        else "FAIL"
    )

    actual_evidence_types = {
        evidence.evidence_type.value for evidence in run.response.evidence
    }
    evidence_validity = (
        "PASS"
        if run.validation_status == "passed"
        and set(scenario.expected_evidence_types) <= actual_evidence_types
        else "FAIL"
    )
    forbidden_claims = (
        "PASS" if _forbidden_claims_pass(scenario, run) else "FAIL"
    )
    abstention: Literal["PASS", "FAIL", "N/A"]
    if scenario.expected_status == "unavailable":
        abstention = (
            "PASS"
            if run.response.run_status is InvestigationRunStatus.UNAVAILABLE
            and not run.response.findings
            and bool(run.response.limits)
            else "FAIL"
        )
    else:
        abstention = "N/A"

    factual_support: Literal["PASS", "FAIL", "N/A"]
    judge_results: list[dict[str, Any]] = []
    judge_usage = TokenUsage()
    if scenario.expected_status == "unavailable":
        factual_support = "N/A"
    elif run.validation_status != "passed" or not run.structured_output:
        factual_support = "FAIL"
    else:
        support_passed = bool(run.structured_output.findings)
        for finding in run.structured_output.findings:
            summaries = [
                run.evidence_summaries[evidence_id]
                for evidence_id in finding.evidence_ids
                if evidence_id in run.evidence_summaries
            ]
            deterministic_pass, deterministic_reason = _deterministic_value_check(
                finding.text, summaries
            )
            try:
                judged = await judge.judge(
                    finding_text=finding.text,
                    evidence_summaries=summaries,
                )
                judge_usage = _add_usage(judge_usage, judged.token_usage)
                semantic_verdict = judged.output.verdict
                semantic_reason = judged.output.reason
            except Exception:
                semantic_verdict = "judge_error"
                semantic_reason = "The structured eval support judge failed."
            finding_passed = deterministic_pass and semantic_verdict == "supported"
            support_passed = support_passed and finding_passed
            judge_results.append(
                {
                    "finding": finding.text,
                    "deterministic_value_check": (
                        "PASS" if deterministic_pass else "FAIL"
                    ),
                    "deterministic_reason": deterministic_reason,
                    "semantic_verdict": semantic_verdict,
                    "semantic_reason": semantic_reason,
                    "overall": "PASS" if finding_passed else "FAIL",
                }
            )
        factual_support = "PASS" if support_passed else "FAIL"

    subchecks: dict[str, Literal["PASS", "FAIL", "N/A"]] = {
        "tool_selection": tool_selection,
        "tool_efficiency": tool_efficiency,
        "evidence_validity": evidence_validity,
        "factual_support": factual_support,
        "abstention": abstention,
        "forbidden_claims": forbidden_claims,
        "overall": "FAIL",
    }
    status_matches = run.response.run_status.value == scenario.expected_status
    required_checks_pass = all(
        value in {"PASS", "N/A"}
        for key, value in subchecks.items()
        if key != "overall"
    )
    subchecks["overall"] = "PASS" if status_matches and required_checks_pass else "FAIL"
    returned_evidence_ids = [
        call.evidence_id for call in run.tool_calls if call.evidence_id is not None
    ]
    judge_cost = (
        estimate_cost_usd(
            judge_usage,
            input_usd_per_million=config.input_usd_per_million,
            output_usd_per_million=config.output_usd_per_million,
        )
        if config.eval_judge_model == config.model_identifier
        else None
    )
    return {
        "scenario_id": scenario.id,
        "case_ref": scenario.case_ref,
        "mode": scenario.mode,
        "question": scenario.question,
        "prompt_version": config.prompt_version,
        "model_identifier": config.model_identifier,
        "judge_model_identifier": config.eval_judge_model,
        "structured_output": (
            run.structured_output.model_dump(mode="json")
            if run.structured_output is not None
            else None
        ),
        "ordered_tool_calls": [
            call.model_dump(mode="json") for call in run.tool_calls
        ],
        "returned_evidence_ids": returned_evidence_ids,
        "run_status": run.response.run_status.value,
        "expected_status": scenario.expected_status,
        "status_matches": status_matches,
        "subchecks": subchecks,
        "overall": subchecks["overall"],
        "factual_support_details": judge_results,
        "token_usage": run.token_usage.model_dump(mode="json"),
        "estimated_cost_usd": run.estimated_cost_usd,
        "judge_token_usage": judge_usage.model_dump(mode="json"),
        "judge_estimated_cost_usd": judge_cost,
    }


async def run_evals(selected_id: str | None) -> tuple[Path, Path, dict[str, Any]]:
    config = load_ai_config()
    scenarios = load_required_scenarios()
    if selected_id is not None:
        scenarios = [scenario for scenario in scenarios if scenario.id == selected_id]
        if not scenarios:
            raise ValueError(f"Unknown eval scenario: {selected_id}")

    service = create_investigation_service()
    investigation_runner = InvestigationRunner(config)
    judge = AgentsSDKSupportJudge(config)
    results: list[dict[str, Any]] = []
    try:
        for scenario in scenarios:
            if scenario.mode == "initial":
                run = await investigation_runner.run_initial(
                    scenario.case_ref, service
                )
            else:
                assert scenario.question is not None
                run = await investigation_runner.run_follow_up(
                    scenario.case_ref,
                    scenario.question,
                    None,
                    service,
                )
            results.append(
                await evaluate_scenario(
                    scenario,
                    run,
                    judge,
                    config=config,
                )
            )
    finally:
        service._close()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_directory = (
        _RESULTS_ROOT
        / config.prompt_version
        / _sanitize_model_identifier(config.model_identifier)
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    run_path = output_directory / f"run-{timestamp}.json"
    summary_path = output_directory / f"summary-{timestamp}.json"
    run_payload = {
        "prompt_version": config.prompt_version,
        "model_identifier": config.model_identifier,
        "judge_model_identifier": config.eval_judge_model,
        "generated_at": timestamp,
        "scenarios": results,
    }
    summary = _build_summary(run_payload)
    run_path.write_text(
        json.dumps(run_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return run_path, summary_path, summary


def _build_summary(run_payload: dict[str, Any]) -> dict[str, Any]:
    results = run_payload["scenarios"]
    passed = sum(result["overall"] == "PASS" for result in results)
    total_tool_calls = sum(len(result["ordered_tool_calls"]) for result in results)
    total_usage = TokenUsage()
    total_judge_usage = TokenUsage()
    evaluated_costs: list[float | None] = []
    judge_costs: list[float | None] = []
    for result in results:
        total_usage = _add_usage(
            total_usage, TokenUsage.model_validate(result["token_usage"])
        )
        total_judge_usage = _add_usage(
            total_judge_usage,
            TokenUsage.model_validate(result["judge_token_usage"]),
        )
        evaluated_costs.append(result["estimated_cost_usd"])
        judge_costs.append(result["judge_estimated_cost_usd"])
    return {
        "prompt_version": run_payload["prompt_version"],
        "model_identifier": run_payload["model_identifier"],
        "judge_model_identifier": run_payload["judge_model_identifier"],
        "generated_at": run_payload["generated_at"],
        "scenario_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "scenario_outcomes": {
            result["scenario_id"]: {
                "overall": result["overall"],
                "subchecks": result["subchecks"],
            }
            for result in results
        },
        "tool_efficiency": {
            "total_tool_calls": total_tool_calls,
            "scenarios_passing": sum(
                result["subchecks"]["tool_efficiency"] == "PASS"
                for result in results
            ),
            "scenarios_failing": sum(
                result["subchecks"]["tool_efficiency"] == "FAIL"
                for result in results
            ),
        },
        "token_usage": total_usage.model_dump(mode="json"),
        "judge_token_usage": total_judge_usage.model_dump(mode="json"),
        "estimated_cost_usd": _sum_optional_costs(evaluated_costs),
        "judge_estimated_cost_usd": _sum_optional_costs(judge_costs),
    }


def _currency_input_matches_scenario(
    scenario: EvalScenario, run: InvestigationRun
) -> bool:
    currency_calls = [
        call for call in run.tool_calls if call.tool_name == "get_currency_history"
    ]
    if scenario.id == "followup-payment-currency":
        return len(currency_calls) == 1 and currency_calls[0].safe_input == {
            "case_ref": scenario.case_ref,
            "dimension": "payment",
            "currency": "CNY",
        }
    if scenario.id == "followup-receiving-currency":
        return len(currency_calls) == 1 and currency_calls[0].safe_input == {
            "case_ref": scenario.case_ref,
            "dimension": "receiving",
            "currency": "USD",
        }
    return True


def _forbidden_claims_pass(
    scenario: EvalScenario, run: InvestigationRun
) -> bool:
    terms = {
        term.casefold()
        for term in (*_GLOBAL_FORBIDDEN_CLAIMS, *scenario.forbidden_claims)
    }
    for finding in run.response.findings:
        lowered = finding.text.casefold()
        if any(term in lowered for term in terms):
            return False
    for limit in run.response.limits:
        lowered = limit.casefold()
        for term in terms:
            if term in lowered and not _is_limit_disclaimer(lowered, term):
                return False
    return True


def _is_limit_disclaimer(text: str, term: str) -> bool:
    index = text.find(term)
    context = text[max(0, index - 80) : index + len(term) + 80]
    return any(
        marker in context
        for marker in (
            "cannot",
            "can't",
            "does not",
            "do not",
            "not available",
            "unavailable",
            "no information",
            "out of scope",
            "is unavailable",
            "are unavailable",
        )
    )


def _deterministic_value_check(
    finding_text: str,
    evidence_summaries: list[dict[str, Any]],
) -> tuple[bool, str]:
    serialized = json.dumps(evidence_summaries, ensure_ascii=False)
    evidence_strings = _all_scalar_strings(evidence_summaries)
    evidence_numbers = _all_decimal_values(evidence_summaries)

    timestamp_matches = list(_TIMESTAMP_PATTERN.finditer(finding_text))
    for timestamp_match in timestamp_matches:
        date_value = timestamp_match.group("date")
        time_value = timestamp_match.group("time")
        timestamp_value = (
            f"{date_value}T{time_value}" if time_value is not None else date_value
        )
        if not any(value.startswith(timestamp_value) for value in evidence_strings):
            return False, (
                f"Timestamp {timestamp_match.group(0)} is absent from cited evidence."
            )
    for currency in _CURRENCY_PATTERN.findall(finding_text):
        if currency not in serialized:
            return False, f"Currency {currency} is absent from cited evidence."
    for number_match in _NUMBER_PATTERN.finditer(finding_text):
        if any(
            timestamp_match.start() <= number_match.start() < timestamp_match.end()
            for timestamp_match in timestamp_matches
        ):
            continue
        number_text, percent_marker = number_match.groups()
        try:
            number = Decimal(number_text)
        except InvalidOperation:
            continue
        if any(abs(number - evidence) <= Decimal("0.011") for evidence in evidence_numbers):
            continue
        if percent_marker and any(
            abs(number - evidence) <= Decimal("0.011") for evidence in evidence_numbers
        ):
            continue
        return False, f"Numeric value {number_text}{percent_marker} is absent from cited evidence."
    return True, "All directly comparable values occur in the cited evidence summaries."


def _all_scalar_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            strings.extend(_all_scalar_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(_all_scalar_strings(child))
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        strings.append(str(value))
    return strings


def _all_decimal_values(value: Any) -> list[Decimal]:
    decimals: list[Decimal] = []
    if isinstance(value, dict):
        for child in value.values():
            decimals.extend(_all_decimal_values(child))
    elif isinstance(value, list):
        for child in value:
            decimals.extend(_all_decimal_values(child))
    elif isinstance(value, (int, float, str)) and not isinstance(value, bool):
        try:
            decimals.append(Decimal(str(value)))
        except InvalidOperation:
            pass
    return decimals


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        requests=left.requests + right.requests,
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        total_tokens=left.total_tokens + right.total_tokens,
    )


def _sum_optional_costs(costs: list[float | None]) -> float | None:
    if any(cost is None for cost in costs):
        return None
    return sum(cost for cost in costs if cost is not None)


def _sanitize_model_identifier(model_identifier: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", model_identifier).strip("._-")
    return sanitized or "model"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--scenario", help="Run one required scenario by ID")
    selection.add_argument(
        "--required",
        action="store_true",
        help="Run all 15 required scenarios",
    )
    arguments = parser.parse_args()
    run_path, summary_path, summary = asyncio.run(
        run_evals(arguments.scenario if not arguments.required else None)
    )
    print(
        json.dumps(
            {
                "run_path": str(run_path),
                "summary_path": str(summary_path),
                "summary": summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
