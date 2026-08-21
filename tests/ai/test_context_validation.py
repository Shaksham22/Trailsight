from __future__ import annotations

import json

import pytest

from ai_helpers import FakeService, currency_evidence, selected_evidence
from trailsight.contracts import CurrencyDimension, CurrencyHistoryFacts
from trailsight_ai.output import Finding, InvestigationModelOutput
from trailsight_ai.runner import selected_transaction_summary
from trailsight_ai.validation import EvidenceValidationError, validate_and_render


def output_with(*evidence_ids: str) -> InvestigationModelOutput:
    return InvestigationModelOutput(
        status="success",
        findings=[
            Finding(text="Selected transaction fact.", evidence_ids=[evidence_ids[0]]),
            Finding(text="Historical fact.", evidence_ids=list(evidence_ids[1:])),
        ],
        limits=[],
    )


def test_selected_model_context_is_allowlisted() -> None:
    evidence = selected_evidence()

    payload = selected_transaction_summary(evidence).model_dump(mode="json")
    serialized = json.dumps(payload)

    assert payload == {
        "evidence_id": "ev:demo-01:selected",
        "timestamp": "2025-05-08T16:18:46.000000",
        "sender": {"bank": "Sender Bank", "account": "A016568"},
        "counterparty": {
            "bank": "Receiver Bank",
            "account": "A013644",
            "entity_type": "Merchant",
        },
        "amount_paid": "69.54",
        "payment_currency": "CNY",
        "amount_received": "9.4",
        "receiving_currency": "USD",
        "payment_format": "Cash",
        "sender_region": 8,
        "receiver_region": 4,
        "cross_currency": True,
        "currency_pair": "CNY → USD",
        "region_relationship": "cross_region",
    }
    for forbidden in (
        "supporting_transaction_refs",
        "historical_transactions",
        "Is Laundering",
        "demographics",
        "transaction_ref",
    ):
        assert forbidden not in serialized


def test_selected_and_called_tool_evidence_validate() -> None:
    fake_service = FakeService()
    output = output_with("ev:demo-01:selected", "ev:demo-01:amount-history")

    validated = validate_and_render(
        output=output,
        case_ref="demo-01",
        available_evidence_ids={
            "ev:demo-01:selected",
            "ev:demo-01:amount-history",
        },
        service=fake_service,
    )

    assert [item.label for item in validated.evidence] == ["E1", "E2"]
    assert fake_service.resolve_calls == [
        "ev:demo-01:selected",
        "ev:demo-01:amount-history",
    ]


@pytest.mark.parametrize(
    "invalid_id",
    [
        "ev:demo-01:invented",
        "ev:demo-01:sender-history",
        "ev:other-case:selected",
    ],
)
def test_invented_uncalled_and_other_case_evidence_fail_closed(
    invalid_id: str,
) -> None:
    fake_service = FakeService()
    if invalid_id == "ev:other-case:selected":
        fake_service.evidence[invalid_id] = selected_evidence("other-case")
    output = output_with("ev:demo-01:selected", invalid_id)
    available = {"ev:demo-01:selected", invalid_id}
    if invalid_id == "ev:demo-01:sender-history":
        available = {"ev:demo-01:selected"}

    with pytest.raises(EvidenceValidationError):
        validate_and_render(
            output=output,
            case_ref="demo-01",
            available_evidence_ids=available,
            service=fake_service,
        )


def test_currency_parameter_mismatch_fails_closed() -> None:
    fake_service = FakeService()
    requested = "ev:demo-01:currency:payment:CNY"
    mismatched = currency_evidence(dimension="payment", currency="CNY")
    facts = mismatched.facts
    assert isinstance(facts, CurrencyHistoryFacts)
    fake_service.evidence[requested] = mismatched.model_copy(
        update={
            "facts": facts.model_copy(
                update={"dimension": CurrencyDimension.RECEIVING}
            )
        }
    )
    output = output_with("ev:demo-01:selected", requested)

    with pytest.raises(EvidenceValidationError, match="parameterization"):
        validate_and_render(
            output=output,
            case_ref="demo-01",
            available_evidence_ids={"ev:demo-01:selected", requested},
            service=fake_service,
        )


def test_one_invalid_finding_rejects_entire_output() -> None:
    fake_service = FakeService()
    output = InvestigationModelOutput(
        status="success",
        findings=[
            Finding(
                text="Valid fact.",
                evidence_ids=["ev:demo-01:selected"],
            ),
            Finding(
                text="Invalid fact.",
                evidence_ids=["ev:demo-01:not-issued"],
            ),
        ],
        limits=[],
    )

    with pytest.raises(EvidenceValidationError):
        validate_and_render(
            output=output,
            case_ref="demo-01",
            available_evidence_ids={"ev:demo-01:selected"},
            service=fake_service,
        )


def test_display_mapping_reuses_labels_and_uses_internal_supporting_refs(
) -> None:
    fake_service = FakeService()
    output = InvestigationModelOutput(
        status="success",
        findings=[
            Finding(
                text="Amount and selected facts.",
                evidence_ids=[
                    "ev:demo-01:amount-history",
                    "ev:demo-01:selected",
                ],
            ),
            Finding(
                text="Amount repeated.",
                evidence_ids=["ev:demo-01:amount-history"],
            ),
        ],
        limits=[],
    )

    validated = validate_and_render(
        output=output,
        case_ref="demo-01",
        available_evidence_ids={
            "ev:demo-01:selected",
            "ev:demo-01:amount-history",
        },
        service=fake_service,
    )

    assert [citation.label for citation in validated.findings[0].citations] == [
        "E1",
        "E2",
    ]
    assert validated.findings[1].citations[0].label == "E1"
    assert validated.evidence[0].supporting_transaction_refs == (
        fake_service.evidence["ev:demo-01:amount-history"].supporting_transaction_refs
    )
