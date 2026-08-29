from dataclasses import replace

from trailsight_v2.ai.evals import (
    APPROVED_TOOL_NAMES,
    EXPECTED_SCENARIO_COUNT,
    DeterministicMockModelExecutorV2,
    execute_non_live_scenario,
    load_eval_suite,
    observe_mock_execution,
    validate_eval_observation,
)
from trailsight_v2.domain.models import SubjectType


def _mock_execution_for(scenario):
    return DeterministicMockModelExecutorV2().execute(
        subject_type=scenario.subject_type,
        subject_ref_fixture=scenario.subject_ref_fixture,
        origin_context_fixture=scenario.origin_context_fixture,
        question=scenario.question,
    )


def test_frozen_eval_suite_has_exactly_fifteen_authoritative_scenarios() -> None:
    suite = load_eval_suite()
    assert len(suite.scenarios) == EXPECTED_SCENARIO_COUNT == 15
    assert all(item.subject_type is not SubjectType.TRANSACTION for item in suite.scenarios[:5])
    assert all(item.subject_type is SubjectType.TRANSACTION for item in suite.scenarios[5:10])
    assert all(item.id.startswith("safety_") for item in suite.scenarios[10:])
    assert all(set(item.required_tools) <= set(item.allowed_tools) for item in suite.scenarios)
    assert all(set(item.allowed_tools).isdisjoint(item.forbidden_tools) for item in suite.scenarios)
    assert set(APPROVED_TOOL_NAMES) == {
        "get_alert_context",
        "get_transaction_context",
        "get_account_context",
        "get_behavioral_indicators",
        "get_relationship_context",
        "get_network_context",
        "get_supporting_evidence",
    }
    fields = set(type(suite.scenarios[0]).model_fields)
    assert fields == {
        "id",
        "subject_type",
        "subject_ref_fixture",
        "origin_context_fixture",
        "question",
        "required_tools",
        "allowed_tools",
        "forbidden_tools",
        "expected_evidence_types",
        "expected_output_categories",
        "expected_priority_explanation",
        "forbidden_claims",
        "required_wording_constraints",
        "max_tool_calls",
        "expected_status",
    }


def test_all_fifteen_scenarios_pass_independent_deterministic_mock_execution() -> None:
    suite = load_eval_suite()
    results = []
    for scenario in suite.scenarios:
        observation = execute_non_live_scenario(scenario)
        results.append(validate_eval_observation(scenario, observation))
    assert len(results) == 15
    assert all(result.passed for result in results), results


def test_observed_missing_required_tool_fails_unchanged_scenario() -> None:
    scenario = load_eval_suite().scenarios[0]
    observation = execute_non_live_scenario(scenario)
    changed = observation.model_copy(update={"tool_names": ("get_alert_context",)})

    result = validate_eval_observation(scenario, changed)

    assert result.passed is False
    assert "required_tools" in result.failures


def test_unapproved_tool_does_not_short_circuit_independent_tool_failures() -> None:
    scenario = load_eval_suite().scenarios[0]
    observation = execute_non_live_scenario(scenario)
    changed = observation.model_copy(
        update={
            "tool_names": (
                "run_sql",
                "get_transaction_context",
                "get_transaction_context",
                "get_transaction_context",
                "get_transaction_context",
            )
        }
    )

    result = validate_eval_observation(scenario, changed)

    assert result.passed is False
    assert {
        "mcp_tool_restriction",
        "required_tools",
        "allowed_tools",
        "forbidden_tools",
        "max_tool_calls",
    } <= set(result.failures)


def test_wrong_priority_explanation_from_observed_output_fails() -> None:
    scenario = load_eval_suite().scenarios[0]
    execution = _mock_execution_for(scenario)
    findings = list(execution.output.findings)
    findings[0] = findings[0].model_copy(
        update={"text": "The review priority has an unrelated explanation."}
    )
    changed = replace(
        execution,
        output=execution.output.model_copy(update={"findings": findings}),
    )
    observation = observe_mock_execution(changed)

    result = validate_eval_observation(scenario, observation)

    assert result.passed is False
    assert "expected_priority_explanation" in result.failures


def test_forbidden_claim_detected_from_observed_output_fails() -> None:
    scenario = load_eval_suite().scenarios[1]
    execution = _mock_execution_for(scenario)
    findings = list(execution.output.findings)
    findings[0] = findings[0].model_copy(
        update={"text": findings[0].text + " This is money laundering."}
    )
    changed = replace(
        execution,
        output=execution.output.model_copy(update={"findings": findings}),
    )
    observation = observe_mock_execution(changed)

    assert "aml_guilt" in observation.detected_forbidden_claims
    result = validate_eval_observation(scenario, observation)
    assert result.passed is False
    assert "forbidden_claims" in result.failures


def test_missing_required_wording_from_observed_output_fails() -> None:
    scenario = load_eval_suite().scenarios[1]
    execution = _mock_execution_for(scenario)
    findings = list(execution.output.findings)
    findings[0] = findings[0].model_copy(
        update={
            "text": (
                "The HIGH account detector state explains review prioritization; "
                "it is not a laundering determination."
            )
        }
    )
    changed = replace(
        execution,
        output=execution.output.model_copy(update={"findings": findings}),
    )
    observation = observe_mock_execution(changed)

    assert "high_is_not_laundering" not in observation.satisfied_wording_constraints
    result = validate_eval_observation(scenario, observation)
    assert result.passed is False
    assert "required_wording_constraints" in result.failures
