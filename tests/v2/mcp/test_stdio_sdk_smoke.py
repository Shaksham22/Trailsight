import asyncio
from pathlib import Path
import os
import sys

from agents.mcp import MCPServerStdio

from trailsight_v2.ai.context import resolve_seed_context
from trailsight_v2.domain.models import SubjectType
from trailsight_v2.mcp.contracts import TOOL_NAMES
from trailsight_v2.mcp.scope import InvestigationScopeV2, scope_to_json


class State:
    def get_alert_review_status(self, _alert_ref: str):
        return "NOT_REVIEWED"


async def _smoke(database_path: Path, runtime_state_path: Path, service, transaction_ref: str):
    seed = resolve_seed_context(
        service,
        State(),
        subject_type=SubjectType.TRANSACTION,
        subject_ref=transaction_ref,
    )
    scope = InvestigationScopeV2(
        subject_type=SubjectType.TRANSACTION,
        subject_ref=transaction_ref,
        context_identity=seed.context.context_identity,
        seed_evidence_ids=seed.seed_evidence_ids,
    )
    root = Path(__file__).resolve().parents[3]
    server = MCPServerStdio(
        name="trailsight-v2-test",
        params={
            "command": sys.executable,
            "args": ["-m", "trailsight_v2.mcp.server"],
            "cwd": str(root),
            "env": {
                "TRAILSIGHT_V2_DB_PATH": str(database_path),
                "TRAILSIGHT_RUNTIME_STATE_PATH": str(runtime_state_path),
                "TRAILSIGHT_MCP_SCOPE_JSON": scope_to_json(scope),
                "PYTHONPATH": str(root / "src"),
            },
        },
        cache_tools_list=True,
        use_structured_content=True,
        max_retry_attempts=0,
    )
    async with server:
        tools = await server.list_tools()
        assert tuple(sorted(tool.name for tool in tools)) == tuple(sorted(TOOL_NAMES))
        result = await server.call_tool(
            "get_transaction_context", {"transaction_ref": transaction_ref}
        )
        assert result.isError is False
        structured = result.structuredContent
        assert isinstance(structured, dict)
        assert structured["status"] == "OK"
        assert structured["transaction_ref"] == transaction_ref


def test_real_agents_sdk_stdio_mcp_invocation(mcp_runtime, tmp_path) -> None:
    database_path, _alert, selected, fx = mcp_runtime
    service = fx.create_investigation_service_v2(database_path)
    try:
        asyncio.run(
            _smoke(
                database_path,
                tmp_path / "runtime_state.json",
                service,
                selected.ref,
            )
        )
    finally:
        service.close()
