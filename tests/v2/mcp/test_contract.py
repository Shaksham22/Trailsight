from trailsight_v2.mcp.contracts import TOOL_NAMES, TOOL_SPECS


def test_exactly_seven_frozen_tools_with_closed_inputs() -> None:
    assert TOOL_NAMES == (
        "get_alert_context",
        "get_transaction_context",
        "get_account_context",
        "get_behavioral_indicators",
        "get_relationship_context",
        "get_network_context",
        "get_supporting_evidence",
    )
    assert len(TOOL_SPECS) == 7
    for spec in TOOL_SPECS:
        schema = spec.input_model.model_json_schema()
        assert schema.get("additionalProperties") is False
        assert not {"limit", "offset", "hops", "sql", "table", "query"} & set(
            schema.get("properties", {})
        )


def test_no_general_purpose_tool_is_registered() -> None:
    joined = " ".join(TOOL_NAMES).lower()
    for forbidden in ("sql", "duckdb", "filesystem", "shell", "web", "graph_traversal"):
        assert forbidden not in joined
