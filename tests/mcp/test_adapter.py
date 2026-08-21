from __future__ import annotations

from datetime import datetime, timedelta
import json
from types import SimpleNamespace

import pytest

from conftest import transaction
from trailsight.contracts import (
    AmountHistoryFacts,
    CounterpartyHistoryFacts,
    CurrencyHistoryFacts,
    RegionHistoryFacts,
    SenderHistoryFacts,
)
from trailsight_mcp.contracts import MAX_SERIALIZED_RESULT_BYTES, serialize_result
from trailsight_mcp.server import InvestigationToolAdapter


def amount_history(number: int) -> list[dict]:
    start = datetime(2025, 1, 1)
    return [
        transaction(
            index + 1,
            start + timedelta(hours=index),
            to_bank=f"History Bank {index}",
            to_account=f"A{index + 1:06d}",
            amount_paid=str(index + 1),
            payment_currency="CNY",
            receiving_currency="USD" if index % 2 == 0 else "EUR",
        )
        for index in range(number)
    ]


def _assert_bounded_and_has_no_history_payload(result) -> None:
    payload = result.model_dump(mode="json")
    encoded = serialize_result(result)
    assert len(encoded) < MAX_SERIALIZED_RESULT_BYTES
    forbidden_keys = {
        "supporting_transaction_refs",
        "transaction_refs",
        "historical_transactions",
        "rows",
        "raw_rows",
    }

    def walk(value):
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            pytest.fail("MCP model-facing results must not contain arrays")

    walk(payload)


def test_all_tools_are_exact_domain_projections(service_builder) -> None:
    history = amount_history(20)
    history[0].update(to_bank="Receiver Bank", to_account="A013644")
    service, _, _ = service_builder(history=history)
    adapter = InvestigationToolAdapter(service)

    sender_domain = service.get_sender_history_evidence("demo-01")
    sender = adapter.get_sender_history("demo-01")
    assert isinstance(sender_domain.facts, SenderHistoryFacts)
    assert sender.evidence_id == sender_domain.evidence_id
    assert sender.prior_outgoing_count == sender_domain.facts.prior_outgoing_count

    amount_domain = service.get_amount_history_evidence("demo-01")
    amount = adapter.compare_amount_history("demo-01")
    assert isinstance(amount_domain.facts, AmountHistoryFacts)
    assert amount.evidence_id == amount_domain.evidence_id
    assert amount.model_dump(exclude={"status", "evidence_id", "error_code"}) == {
        "payment_currency": amount_domain.facts.payment_currency,
        "selected_amount": amount_domain.facts.selected_amount,
        "sample_size": amount_domain.facts.sample_size,
        "history_quality": amount_domain.facts.history_quality,
        "historical_median": amount_domain.facts.historical_median,
        "empirical_percentile": amount_domain.facts.empirical_percentile,
    }

    counterparty_domain = service.get_counterparty_history_evidence("demo-01")
    counterparty = adapter.get_counterparty_history("demo-01")
    assert isinstance(counterparty_domain.facts, CounterpartyHistoryFacts)
    assert counterparty.evidence_id == counterparty_domain.evidence_id
    assert counterparty.model_dump(exclude={"status", "evidence_id", "error_code"}) == (
        counterparty_domain.facts.model_dump()
    )

    region_domain = service.get_region_history_evidence("demo-01")
    region = adapter.get_region_history("demo-01")
    assert isinstance(region_domain.facts, RegionHistoryFacts)
    assert region.evidence_id == region_domain.evidence_id
    assert region.model_dump(exclude={"status", "evidence_id", "error_code"}) == (
        region_domain.facts.model_dump()
    )

    currency_domain = service.get_currency_history_evidence(
        "demo-01", "receiving", "USD"
    )
    currency = adapter.get_currency_history("demo-01", "receiving", "USD")
    assert isinstance(currency_domain.facts, CurrencyHistoryFacts)
    assert currency.evidence_id == currency_domain.evidence_id
    assert currency.model_dump(exclude={"status", "evidence_id", "error_code"}) == (
        currency_domain.facts.model_dump()
    )

    for result in (sender, amount, counterparty, region, currency):
        _assert_bounded_and_has_no_history_payload(result)


@pytest.mark.parametrize(
    ("number", "status", "quality", "median", "has_percentile"),
    [
        (0, "insufficient_history", "insufficient", None, False),
        (4, "insufficient_history", "insufficient", None, False),
        (5, "ok", "limited", "3", False),
        (19, "ok", "limited", "10", False),
        (20, "ok", "sufficient", "10.5", True),
    ],
)
def test_amount_thresholds_are_preserved_from_domain(
    service_builder,
    number: int,
    status: str,
    quality: str,
    median: str | None,
    has_percentile: bool,
) -> None:
    service, _, _ = service_builder(history=amount_history(number))
    result = InvestigationToolAdapter(service).compare_amount_history("demo-01")

    assert result.status == status
    assert result.sample_size == number
    assert result.history_quality.value == quality
    assert result.historical_median == median
    assert (result.empirical_percentile is not None) is has_percentile


def test_missing_case_and_domain_failures_are_bounded(service_builder) -> None:
    service, _, _ = service_builder()
    adapter = InvestigationToolAdapter(service)

    missing_results = [
        adapter.get_sender_history("missing"),
        adapter.compare_amount_history("missing"),
        adapter.get_counterparty_history("missing"),
        adapter.get_region_history("missing"),
        adapter.get_currency_history("missing", "payment", "USD"),
    ]
    for result in missing_results:
        assert result.status == "not_found"
        assert result.evidence_id is None
        assert result.error_code is None
        _assert_bounded_and_has_no_history_payload(result)

    invalid = adapter.get_currency_history("demo-01", "incoming", "USD")
    assert invalid.status == "error"
    assert invalid.error_code == "invalid_input"

    invalid_history = transaction(1, datetime(2025, 2, 1, 12, 0, 0))
    broken_service, _, _ = service_builder(history=[invalid_history])
    domain_error = InvestigationToolAdapter(broken_service).get_sender_history("demo-01")
    assert domain_error.status == "error"
    assert domain_error.error_code == "domain_error"
    assert "timestamp" not in serialize_result(domain_error).decode()


def test_unexpected_exception_text_never_leaks() -> None:
    class BrokenService:
        def get_sender_history_evidence(self, _case_ref: str):
            raise RuntimeError("SELECT secret_value FROM hidden_table")

    result = InvestigationToolAdapter(BrokenService()).get_sender_history("demo-01")
    serialized = serialize_result(result).decode()
    assert result.status == "error"
    assert result.error_code == "domain_error"
    assert "secret_value" not in serialized
    assert "SELECT" not in serialized


def test_oversized_projection_fails_closed_without_truncation() -> None:
    class OversizedService:
        def get_sender_history_evidence(self, case_ref: str):
            return SimpleNamespace(
                evidence_id=f"ev:{case_ref}:sender-history:" + ("x" * 5000),
                facts=SenderHistoryFacts(prior_outgoing_count=1),
            )

    result = InvestigationToolAdapter(OversizedService()).get_sender_history("demo-01")
    assert result.status == "error"
    assert result.error_code == "result_too_large"
    assert result.evidence_id is None
    assert len(serialize_result(result)) < MAX_SERIALIZED_RESULT_BYTES


def test_currency_history_remains_sender_outgoing_only(service_builder) -> None:
    incoming_to_selected_sender = transaction(
        900,
        datetime(2025, 1, 15),
        from_bank="Incoming Bank",
        from_account="A000901",
        to_bank="Sender Bank",
        to_account="A016568",
        payment_currency="CAD",
        receiving_currency="GBP",
    )
    previous_outgoing = transaction(
        1,
        datetime(2025, 1, 10),
        payment_currency="CNY",
        receiving_currency="USD",
    )
    service, _, _ = service_builder(
        history=[previous_outgoing],
        other_transactions=[incoming_to_selected_sender],
    )
    adapter = InvestigationToolAdapter(service)

    payment = adapter.get_currency_history("demo-01", "payment", "CAD")
    receiving = adapter.get_currency_history("demo-01", "receiving", "GBP")

    assert payment.status == receiving.status == "ok"
    assert payment.seen_before is receiving.seen_before is False
    assert payment.previous_count == receiving.previous_count == 0


def test_success_and_error_results_exclude_hidden_or_detailed_data(service_builder) -> None:
    service, _, _ = service_builder(history=amount_history(5))
    adapter = InvestigationToolAdapter(service)
    results = [
        adapter.get_sender_history("demo-01"),
        adapter.compare_amount_history("demo-01"),
        adapter.get_counterparty_history("demo-01"),
        adapter.get_region_history("demo-01"),
        adapter.get_currency_history("demo-01", "payment", "CNY"),
        adapter.get_sender_history("missing"),
    ]
    serialized = json.dumps([result.model_dump(mode="json") for result in results])

    assert "Is Laundering" not in serialized
    assert "supporting_transaction_refs" not in serialized
    assert "transaction_refs" not in serialized
    assert "historical_transactions" not in serialized
    for result in results:
        _assert_bounded_and_has_no_history_payload(result)
