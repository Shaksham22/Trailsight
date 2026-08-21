from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from trailsight_mcp.contracts import CaseRefInput, CurrencyHistoryInput
from trailsight_mcp.server import registered_tool_definitions


EXPECTED_INPUTS = {
    "get_sender_history": {"case_ref"},
    "compare_amount_history": {"case_ref"},
    "get_counterparty_history": {"case_ref"},
    "get_region_history": {"case_ref"},
    "get_currency_history": {"case_ref", "dimension", "currency"},
}


def test_exact_five_tools_and_closed_input_schemas() -> None:
    tools = registered_tool_definitions()

    assert [tool.name for tool in tools] == list(EXPECTED_INPUTS)
    for tool in tools:
        expected = EXPECTED_INPUTS[tool.name]
        assert set(tool.inputSchema["properties"]) == expected
        assert set(tool.inputSchema["required"]) == expected
        assert tool.inputSchema["additionalProperties"] is False
        assert set(tool.outputSchema["required"]) == set(
            tool.outputSchema["properties"]
        )


def test_input_models_accept_only_frozen_fields_and_values() -> None:
    assert CaseRefInput.model_validate({"case_ref": "demo-01"}).case_ref == "demo-01"
    valid_currency = CurrencyHistoryInput.model_validate(
        {"case_ref": "demo-01", "dimension": "receiving", "currency": "USD"}
    )
    assert valid_currency.dimension.value == "receiving"
    assert valid_currency.currency == "USD"

    invalid_inputs = [
        (CaseRefInput, {"case_ref": "demo-01", "limit": 10}),
        (CaseRefInput, {"case_ref": "demo-01", "include_details": True}),
        (CaseRefInput, {"case_ref": "Demo-01"}),
        (
            CurrencyHistoryInput,
            {"case_ref": "demo-01", "dimension": "incoming", "currency": "USD"},
        ),
        (
            CurrencyHistoryInput,
            {"case_ref": "demo-01", "dimension": "payment", "currency": "usd"},
        ),
        (
            CurrencyHistoryInput,
            {
                "case_ref": "demo-01",
                "dimension": "payment",
                "currency": "USD",
                "page_size": 5,
            },
        ),
    ]
    for model, payload in invalid_inputs:
        with pytest.raises(ValidationError):
            model.model_validate(payload)


def test_mcp_source_does_not_open_data_or_define_unapproved_capabilities() -> None:
    package_root = Path(__file__).parents[2] / "src" / "trailsight_mcp"
    source = "\n".join(path.read_text() for path in package_root.glob("*.py"))

    forbidden_terms = (
        "duckdb",
        "RuntimeRepository",
        "TransXion",
        "SELECT ",
        "account_search",
        "incoming_account_history",
        "streamable-http",
        "transport=\"sse\"",
    )
    for term in forbidden_terms:
        assert term not in source
    assert "service = create_investigation_service()" in source
