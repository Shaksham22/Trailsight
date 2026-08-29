import inspect

from agents import RunHooks
from agents.mcp import MCPServerStdio
from mcp.server import Server


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
