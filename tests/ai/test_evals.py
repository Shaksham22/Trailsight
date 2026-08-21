from __future__ import annotations

from trailsight_ai.eval_runner import (
    _deterministic_value_check,
    _forbidden_claims_pass,
    load_required_scenarios,
)
from trailsight_ai.runner import InvestigationRun
from trailsight_ai.telemetry import TokenUsage
from trailsight.contracts import InvestigationResponse, InvestigationRunStatus


def test_exactly_15_unique_known_required_scenarios() -> None:
    scenarios = load_required_scenarios()

    assert len(scenarios) == 15
    assert len({scenario.id for scenario in scenarios}) == 15
    assert {scenario.case_ref for scenario in scenarios} == {
        "demo-01",
        "eval-repeat-counterparty-01",
        "eval-amount-limited-01",
        "eval-amount-insufficient-01",
    }
    assert sum(scenario.mode == "initial" for scenario in scenarios) == 4
    assert sum(scenario.mode == "follow_up" for scenario in scenarios) == 11
    assert sum(scenario.expected_status == "unavailable" for scenario in scenarios) == 3


def test_all_scenario_tool_sets_and_call_bounds_are_valid() -> None:
    for scenario in load_required_scenarios():
        assert set(scenario.required_tools) <= set(scenario.allowed_tools)
        assert not set(scenario.allowed_tools) & set(scenario.forbidden_tools)
        assert scenario.max_total_tool_calls >= len(scenario.required_tools)
        if scenario.expected_status == "unavailable":
            assert scenario.allowed_tools == []
            assert scenario.max_total_tool_calls == 0


def test_focused_scenarios_forbid_unrelated_tools() -> None:
    scenarios = {scenario.id: scenario for scenario in load_required_scenarios()}

    assert scenarios["followup-counterparty-only"].allowed_tools == [
        "get_counterparty_history"
    ]
    assert scenarios["followup-amount-only"].allowed_tools == [
        "compare_amount_history"
    ]
    assert scenarios["focused-tool-efficiency"].allowed_tools == [
        "get_sender_history"
    ]
    assert "get_currency_history" in scenarios[
        "unsupported-incoming-history"
    ].forbidden_tools


def test_deterministic_value_check_compares_only_cited_summaries() -> None:
    summaries = [
        {
            "evidence_id": "ev:demo-01:amount-history",
            "payment_currency": "CNY",
            "sample_size": 70,
            "historical_median": "15.095",
            "empirical_percentile": 95.7142857,
        }
    ]

    passed, _ = _deterministic_value_check(
        "Across 70 earlier CNY payments, the median was 15.095 and the percentile was 95.71%.",
        summaries,
    )
    failed, reason = _deterministic_value_check(
        "Across 71 earlier CNY payments, the median was 15.095.", summaries
    )

    assert passed is True
    assert failed is False
    assert "71" in reason

    date_passed, _ = _deterministic_value_check(
        "The most recent earlier use was 2025-05-01T00:00:00.000000.",
        [{"most_recent_previous_timestamp": "2025-05-01T00:00:00.000000"}],
    )
    assert date_passed is True


def test_deterministic_value_check_treats_supported_timestamps_as_one_value() -> None:
    summaries = [{"timestamp": "2025-01-01T12:08:30.000000"}]

    for timestamp in (
        "2025-01-01T12:08:30",
        "2025-01-01T12:08:30.000000",
        "2025-01-01 at 12:08:30",
    ):
        passed, reason = _deterministic_value_check(
            f"The earlier interaction was {timestamp}.",
            summaries,
        )

        assert passed is True, reason

    unsupported, reason = _deterministic_value_check(
        "The earlier interaction was 2025-01-01T12:08:31.",
        summaries,
    )
    assert unsupported is False
    assert "2025-01-01T12:08:31" in reason


def test_timestamp_components_are_not_independent_numeric_claims() -> None:
    passed, reason = _deterministic_value_check(
        "The earlier interaction was 2025-01-01 at 12:08:30.",
        [{"timestamp": "2025-01-01T12:08:30.000000"}],
    )

    assert passed is True, reason


def test_ordinary_independent_numbers_are_still_checked() -> None:
    summaries = [
        {
            "prior_outgoing_count": 74,
            "selected_amount": "69.54",
            "historical_median": "15.095",
            "empirical_percentile": 95.71,
        }
    ]
    supported, reason = _deterministic_value_check(
        "The count was 74, amount 69.54, median 15.095, and percentile 95.71%.",
        summaries,
    )

    assert supported is True, reason
    for unsupported_number in ("75", "70.54", "16.095", "96.71%"):
        passed, failure_reason = _deterministic_value_check(
            f"The independent value was {unsupported_number}.",
            summaries,
        )

        assert passed is False
        assert unsupported_number.rstrip("%") in failure_reason


def test_genuinely_unsupported_number_still_fails() -> None:
    passed, reason = _deterministic_value_check(
        "The sender had 999 earlier transactions.",
        [{"prior_outgoing_count": 74}],
    )

    assert passed is False
    assert "999" in reason


def test_forbidden_claim_check_allows_explicit_limit_but_not_positive_claim() -> None:
    scenario = next(
        item for item in load_required_scenarios() if item.id == "unsupported-purpose"
    )
    unavailable = InvestigationRun(
        response=InvestigationResponse(
            investigation_id="inv_0123456789abcdef0123456789abcdef",
            case_ref="demo-01",
            parent_investigation_id=None,
            run_status=InvestigationRunStatus.UNAVAILABLE,
            findings=[],
            limits=["Transaction purpose is unavailable in Trailsight evidence."],
            evidence=[],
        ),
        structured_output=None,
        tool_calls=[],
        evidence_summaries={},
        token_usage=TokenUsage(),
        estimated_cost_usd=None,
        validation_status="passed",
        failure_code=None,
    )

    assert _forbidden_claims_pass(scenario, unavailable) is True
