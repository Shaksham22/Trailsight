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
        "required_output_sections",
        "expected_priority_explanation",
        "forbidden_claims",
        "required_wording_constraints",
        "required_fact_tokens",
        "forbidden_fact_tokens",
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
    changed = replace(
        execution,
        output=execution.output.model_copy(
            update={"summary": "The review priority has an unrelated explanation."}
        ),
    )
    observation = observe_mock_execution(changed)

    result = validate_eval_observation(scenario, observation)

    assert result.passed is False
    assert "expected_priority_explanation" in result.failures


def test_forbidden_claim_detected_from_observed_output_fails() -> None:
    scenario = load_eval_suite().scenarios[1]
    execution = _mock_execution_for(scenario)
    changed = replace(
        execution,
        output=execution.output.model_copy(
            update={"summary": execution.output.summary + " This is money laundering."}
        ),
    )
    observation = observe_mock_execution(changed)

    assert "aml_guilt" in observation.detected_forbidden_claims
    result = validate_eval_observation(scenario, observation)
    assert result.passed is False
    assert "forbidden_claims" in result.failures


def test_past_confirmed_laundering_similarity_claim_is_rejected() -> None:
    scenario = load_eval_suite().scenarios[1]
    execution = _mock_execution_for(scenario)
    changed = replace(
        execution,
        output=execution.output.model_copy(
            update={
                "summary": (
                    "These transactions are similar to past money laundering transactions."
                )
            }
        ),
    )

    observation = observe_mock_execution(changed)

    assert "supervised_correlation" in observation.detected_forbidden_claims
    assert validate_eval_observation(scenario, observation).passed is False


def test_detector_result_is_not_presented_as_statistical_confidence() -> None:
    scenario = load_eval_suite().scenarios[1]
    execution = _mock_execution_for(scenario)
    changed = replace(
        execution,
        output=execution.output.model_copy(
            update={"summary": "This conclusion is stated with 95% confidence."}
        ),
    )

    observation = observe_mock_execution(changed)

    assert "detector_as_confidence" in observation.detected_forbidden_claims
    assert validate_eval_observation(scenario, observation).passed is False


def test_missing_qualitative_detector_interpretation_fails() -> None:
    scenario = load_eval_suite().scenarios[1]
    execution = _mock_execution_for(scenario)
    changed = replace(
        execution,
        output=execution.output.model_copy(
            update={
                "summary": (
                    "This account has elevated priority."
                )
            }
        ),
    )
    observation = observe_mock_execution(changed)

    assert "qualitative_detector_interpretation" not in observation.satisfied_wording_constraints
    assert "smurfing_specialization" not in observation.satisfied_wording_constraints
    result = validate_eval_observation(scenario, observation)
    assert result.passed is False
    assert "required_wording_constraints" in result.failures


def test_account_copy_translates_result_without_exposing_detector_telemetry() -> None:
    scenario = load_eval_suite().scenarios[1]
    execution = _mock_execution_for(scenario)
    summary = execution.output.summary.lower()
    assert summary.startswith("garg found strong evidence")
    assert "this account’s wider connections resemble smurfing" in summary
    assert "transfers are spread across several accounts" in summary
    assert "six new accounts appeared" in summary
    assert "three outgoing transfers were for similar amounts" in summary
    assert "together, these facts strengthen the concern" in summary
    assert not any(
        token in summary
        for token in (
            "network pattern score",
            "1,647",
            "384,995",
            "99.57",
            "historical snapshot",
            "2022-09-19",
            "block measure",
            "first-order",
            "second-order",
        )
    )
    assert "trailsight marked" not in summary
    assert "known laundering" not in summary
    assert "confirmed laundering" not in summary
    assert "95% confidence" not in summary
    assert not any(term in summary for term in ("counterparty", "structural network concern", "supplied activity", "bounded"))


def test_medium_account_copy_balances_concern_with_specific_countervailing_context() -> None:
    scenario = load_eval_suite().scenarios[2]
    execution = _mock_execution_for(scenario)
    summary = execution.output.summary.lower()

    assert "some similarities to smurfing" in summary
    assert "but not a strong match" in summary
    assert "four new accounts" in summary
    assert "two similar-size outgoing transfers increase concern" in summary
    assert "18 of the 22 other accounts have an established history" in summary
    assert "total activity stayed within its recent range" in summary
    assert "the evidence is mixed" in summary
    assert "consistent with ordinary account use" in summary
    assert "genuine" not in summary
    assert "probability" not in summary
    assert "countervailing" not in summary
    assert "counterparty" not in summary


def test_low_account_copy_uses_data_only_to_support_the_low_garg_result() -> None:
    execution = DeterministicMockModelExecutorV2().execute(
        subject_type=SubjectType.ACCOUNT,
        subject_ref_fixture="LOW_ACCOUNT",
        origin_context_fixture=None,
        question=None,
    )
    observation = observe_mock_execution(execution)
    summary = execution.output.summary.lower()

    assert "garg found little evidence" in summary
    assert "transfers are spread across many accounts" in summary
    assert "six yen transfers occurred over september 1–3" in summary
    assert "two incoming payments totaling 194,289.78" in summary
    assert "two outgoing payments totaling 537,682.06" in summary
    assert "one bangladesh-bank relationship" in summary
    assert "focused on one relationship rather than spread across many accounts" in summary
    assert "consistent with the low result" in summary
    assert "low_contextual_support" in observation.satisfied_wording_constraints
    assert observation.priority_explanation == "LOW_ACCOUNT_STATE"
    assert not any(
        word in summary
        for word in (
            "safe",
            "cleared",
            "benign",
            "genuine",
            "however",
            "instead",
            "regardless",
            "notable",
            "concerning",
        )
    )


def test_medium_counterargument_never_becomes_a_genuine_transaction_probability() -> None:
    scenario = load_eval_suite().scenarios[2]
    execution = _mock_execution_for(scenario)
    changed = replace(
        execution,
        output=execution.output.model_copy(
            update={"summary": "There is an 80% chance that the transactions are genuine."}
        ),
    )

    observation = observe_mock_execution(changed)

    assert "genuine_probability" in observation.detected_forbidden_claims
    assert validate_eval_observation(scenario, observation).passed is False


def test_transaction_copy_is_endpoint_derived_and_not_directly_scored() -> None:
    scenario = load_eval_suite().scenarios[5]
    execution = _mock_execution_for(scenario)
    summary = execution.output.summary.lower()
    opening = summary.split(".", 1)[0]

    assert "linked to a sender" in opening
    assert "wider account connections strongly resemble smurfing" in opening
    assert "smurfing is a pattern where transfers are spread across several accounts" in summary
    assert "this transfer sent 12500 usd by wire" in summary
    assert all(token not in summary for token in ("network pattern score", "240th", "40,000", "top 1%"))
    assert "garg scored the transaction" not in summary
    assert "garg classified" not in summary


def test_bounded_relationship_sample_is_not_misrepresented_as_total() -> None:
    execution = _mock_execution_for(load_eval_suite().scenarios[1])
    text = "\n".join(execution.output.observations).lower()

    assert "money with 31 other accounts" in text
    assert "details for 12 of them are included here" in text
    assert "only 12 other accounts" not in text


def test_pattern_synthesis_is_descriptive_and_needs_no_evidence_verbatim() -> None:
    execution = _mock_execution_for(load_eval_suite().scenarios[1])
    pattern = execution.output.patterns[0].lower()

    assert "six new relationships" in pattern
    assert "three outgoing transfers occurred for similar amounts" in pattern
    assert "may indicate" in pattern
    assert not hasattr(execution.output, "evidence_ids")
    assert not any(word in pattern for word in ("review whether", "examine whether", "investigate"))


def test_bank_country_copy_stays_bank_metadata() -> None:
    execution = _mock_execution_for(load_eval_suite().scenarios[9])
    text = "\n".join(execution.output.observations).lower()

    assert "bank country" in text
    assert "both banks map to canada" in text
    assert "do not describe where either customer lives" in text
    assert "customer in canada" not in text
    assert "canadian customer" not in text


def test_missing_concrete_supplied_value_fails_semantic_eval() -> None:
    scenario = load_eval_suite().scenarios[1]
    observation = execute_non_live_scenario(scenario)
    changed = observation.model_copy(
        update={
            "output_text": observation.output_text.replace(
                "31 other accounts", "many other accounts"
            )
        }
    )

    result = validate_eval_observation(scenario, changed)

    assert result.passed is False
    assert "required_fact_tokens" in result.failures


def test_invented_transaction_counterparty_or_value_fails_semantic_eval() -> None:
    scenario = load_eval_suite().scenarios[-1]
    observation = execute_non_live_scenario(scenario)
    changed = observation.model_copy(
        update={
            "output_text": (
                observation.output_text
                + " Transaction tx_not_supplied sent 999999 to acct_not_supplied."
            )
        }
    )

    result = validate_eval_observation(scenario, changed)

    assert result.passed is False
    assert "forbidden_fact_tokens" in result.failures
