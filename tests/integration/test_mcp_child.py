from __future__ import annotations

import json
from pathlib import Path
import sys

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from integration_helpers import build_runtime_database


EXPECTED_TOOLS = {
    "get_sender_history",
    "compare_amount_history",
    "get_counterparty_history",
    "get_region_history",
    "get_currency_history",
}


def test_approved_mcp_module_starts_as_child_process(tmp_path: Path) -> None:
    runtime_database = build_runtime_database(tmp_path)
    project_root = Path(__file__).parents[2]
    stderr_path = runtime_database.parent / "mcp.stderr"
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "trailsight_mcp.server"],
        cwd=project_root,
        env={
            "TRAILSIGHT_DB_PATH": str(runtime_database),
            "PYTHONPATH": str(project_root / "src"),
        },
    )

    async def run_smoke() -> None:
        with stderr_path.open("w", encoding="utf-8") as errlog:
            async with stdio_client(parameters, errlog=errlog) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS

                    result = await session.call_tool(
                        "compare_amount_history", {"case_ref": "demo-01"}
                    )
                    assert result.isError is False
                    payload = result.structuredContent
                    assert payload is not None
                    assert payload["status"] == "ok"
                    assert payload["evidence_id"] == "ev:demo-01:amount-history"
                    assert payload["sample_size"] == 70
                    assert "supporting_transaction_refs" not in payload
                    assert "rows" not in payload
                    assert json.loads(result.content[0].text) == payload

    anyio.run(run_smoke)
    assert stderr_path.read_text(encoding="utf-8") == ""
