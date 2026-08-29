from trailsight_v2.mcp.contracts import TOOL_NAMES
from trailsight_v2.mcp.server import registered_tool_definitions


def test_server_exports_exactly_the_frozen_tool_schemas() -> None:
    definitions = registered_tool_definitions()
    assert tuple(item.name for item in definitions) == TOOL_NAMES
    for item in definitions:
        assert item.inputSchema.get("additionalProperties") is False
