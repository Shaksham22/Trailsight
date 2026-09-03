"""One local stdio MCP server exposing exactly seven Trailsight V2 tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from trailsight_v2.api.runtime_state import RuntimeStateStore
from trailsight_v2.domain.service import create_investigation_service_v2

from .adapter import InvestigationToolAdapterV2
from .contracts import TOOL_SPECS, McpResult, serialize_result
from .scope import scope_from_environment


def registered_tool_definitions() -> list[types.Tool]:
    """Return the frozen seven closed-schema tool definitions."""
    return [
        types.Tool(
            name=spec.name,
            description=spec.description,
            inputSchema=spec.input_model.model_json_schema(),
            outputSchema=spec.output_model.model_json_schema(mode="serialization"),
        )
        for spec in TOOL_SPECS
    ]


def create_mcp_server(
    service,
    runtime_state_store,
    *,
    scope=None,
) -> Server:
    """Create the low-level server around already-created deterministic dependencies."""
    scope = scope or scope_from_environment()
    adapter = InvestigationToolAdapterV2(service, runtime_state_store, scope)
    specs = {spec.name: spec for spec in TOOL_SPECS}
    server = Server("trailsight-v2-mcp", version="2")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return registered_tool_definitions()

    @server.call_tool()
    async def call_tool(
        name: str,
        arguments: dict[str, Any],
    ) -> tuple[list[types.TextContent], dict[str, Any]]:
        spec = specs.get(name)
        if spec is None:
            raise ValueError("Unknown Trailsight V2 MCP tool")
        validated = spec.input_model.model_validate(arguments)
        method = getattr(adapter, spec.adapter_method)
        result: McpResult = method(**validated.model_dump())
        serialized = serialize_result(result)
        return (
            [types.TextContent(type="text", text=serialized.decode("utf-8"))],
            result.model_dump(mode="json"),
        )

    return server


async def _run_stdio(server: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Create one domain service and one state reader for the stdio child lifetime."""
    configured = os.environ.get("TRAILSIGHT_V2_DB_PATH")
    database_path = (
        Path(configured).expanduser()
        if configured
        else Path("data/v2/runtime/trailsight_v2.duckdb")
    )
    service = create_investigation_service_v2(database_path)
    runtime_state_store = RuntimeStateStore()
    try:
        anyio.run(_run_stdio, create_mcp_server(service, runtime_state_store))
    finally:
        runtime_state_store.close()
        service.close()


if __name__ == "__main__":
    main()
