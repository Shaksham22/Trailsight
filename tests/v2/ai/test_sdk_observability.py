import inspect

from agents import RunHooks
from agents.mcp import MCPServerStdio
from mcp.server import Server

from trailsight_v2.ai.runner import MCP_CLIENT_SESSION_TIMEOUT_SECONDS


def test_locked_sdk_surface_exposes_real_tool_lifecycle_and_mcp_calls() -> None:
    assert inspect.iscoroutinefunction(RunHooks.on_tool_start)
    assert inspect.iscoroutinefunction(RunHooks.on_tool_end)
    start = inspect.signature(RunHooks.on_tool_start)
    end = inspect.signature(RunHooks.on_tool_end)
    assert "tool" in start.parameters
    assert "result" in end.parameters
    assert inspect.iscoroutinefunction(MCPServerStdio.list_tools)
    assert inspect.iscoroutinefunction(MCPServerStdio.call_tool)
    assert hasattr(Server, "list_tools")
    assert hasattr(Server, "call_tool")


def test_mcp_read_timeout_covers_measured_bounded_tool_runtime() -> None:
    sdk_default = inspect.signature(MCPServerStdio).parameters[
        "client_session_timeout_seconds"
    ].default
    assert sdk_default == 5
    assert MCP_CLIENT_SESSION_TIMEOUT_SECONDS == 10.0
