from __future__ import annotations

import json
from pathlib import Path
import sys

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from conftest import build_runtime_database


EXPECTED_TOOLS = {
    "get_sender_history",
    "compare_amount_history",
    "get_counterparty_history",
    "get_region_history",
    "get_currency_history",
}


def test_real_stdio_client_lists_and_calls_server(tmp_path: Path) -> None:
    database_path = build_runtime_database(tmp_path / "stdio.duckdb")
    stderr_path = tmp_path / "stdio-server.stderr"
    project_root = Path(__file__).parents[2]
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "trailsight_mcp.server"],
        cwd=project_root,
        env={
            "TRAILSIGHT_DB_PATH": str(database_path),
            "PYTHONPATH": str(project_root / "src"),
        },
    )

    async def run_smoke() -> None:
        with stderr_path.open("w", encoding="utf-8") as errlog:
            async with stdio_client(server_parameters, errlog=errlog) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS

                    result = await session.call_tool(
                        "get_sender_history", {"case_ref": "demo-01"}
                    )
                    assert result.isError is False
                    assert result.structuredContent == {
                        "status": "ok",
                        "evidence_id": "ev:demo-01:sender-history",
                        "prior_outgoing_count": 0,
                        "error_code": None,
                    }
                    assert json.loads(result.content[0].text) == result.structuredContent

                    rejected = await session.call_tool(
                        "get_sender_history",
                        {"case_ref": "demo-01", "limit": 100},
                    )
                    assert rejected.isError is True

    anyio.run(run_smoke)
    assert stderr_path.read_text(encoding="utf-8") == ""
