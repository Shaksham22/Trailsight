import pytest
from pydantic import ValidationError

from trailsight_v2.ai.models import InvestigationSummaryV2


def test_summary_contract_requires_no_evidence_ids() -> None:
    output = InvestigationSummaryV2(
        summary="The transaction priority is derived from the supplied endpoint bands.",
        observations=["The supplied transfer amount is 12,500 USD."],
        patterns=["Recent activity appears concentrated among newly observed counterparties."],
        limits=["The packet does not contain transaction purpose."],
    )

    assert output.observations == ["The supplied transfer amount is 12,500 USD."]
    assert output.patterns == [
        "Recent activity appears concentrated among newly observed counterparties."
    ]
    assert "evidence_ids" not in InvestigationSummaryV2.model_fields
    assert "findings" not in InvestigationSummaryV2.model_fields
    assert "attention_points" not in InvestigationSummaryV2.model_fields


def test_summary_contract_normalizes_direct_prose() -> None:
    output = InvestigationSummaryV2(
        summary="  Direct analyst summary.  ",
        observations=["  One observation.  "],
        patterns=[],
        limits=[],
    )

    assert output.summary == "Direct analyst summary."
    assert output.observations == ["One observation."]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "summary": "",
            "observations": [],
            "patterns": [],
            "limits": [],
        },
        {
            "summary": "A summary.",
            "observations": [""],
            "patterns": [],
            "limits": [],
        },
        {
            "summary": "A summary.",
            "observations": [],
            "patterns": [],
            "limits": [],
            "evidence_ids": ["ev2.forbidden"],
        },
        {
            "summary": "A summary.",
            "observations": [],
            "patterns": [],
            "limits": [],
            "attention_points": ["Review this."],
        },
    ],
)
def test_malformed_summary_schema_fails(payload) -> None:
    with pytest.raises(ValidationError):
        InvestigationSummaryV2.model_validate(payload)
