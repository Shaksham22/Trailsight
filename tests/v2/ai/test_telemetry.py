import json

import pytest

from trailsight_v2.ai.telemetry import (
    InvestigationTraceV2,
    MCPCallTraceV2,
    TokenUsageV2,
    append_trace,
)


def _trace() -> InvestigationTraceV2:
    return InvestigationTraceV2(
        investigation_id="inv_test",
        parent_investigation_id=None,
        subject_type="ACCOUNT",
        subject_ref="acct_test",
        origin_alert_ref=None,
        origin_transaction_ref=None,
        snapshot_id="snap_1",
        detector_cutoff="2025-01-02T00:00:00Z",
        prompt_version="investigation-v1",
        prompt_sha256="0" * 64,
        model_identifier="test-model",
        started_at="2026-08-28T00:00:00.000Z",
        finished_at="2026-08-28T00:00:00.100Z",
        latency_ms=100,
        run_status="SUCCESS",
        mcp_calls=(
            MCPCallTraceV2(
                sequence=1,
                tool_name="get_network_context",
                safe_input_summary={"account_ref": "acct_test"},
                started_at="2026-08-28T00:00:00.010Z",
                latency_ms=20,
                result_status="OK",
                result_size_bytes=123,
                evidence_ids=("ev2.safe.checksum",),
            ),
        ),
        referenced_evidence_ids=("ev2.safe.checksum",),
        validation_status="PASSED",
        token_usage=TokenUsageV2(requests=1, input_tokens=10, output_tokens=5, total_tokens=15),
        estimated_cost_usd=None,
        failure_code=None,
    )


def test_jsonl_shape_is_one_deterministic_record_per_append(tmp_path) -> None:
    path = tmp_path / "trace.jsonl"
    append_trace(path, _trace())
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["trace_schema_version"] == "investigation-trace-v2"
    assert payload["mcp_calls"][0]["sequence"] == 1
    assert payload["mcp_calls"][0]["result_status"] == "OK"
    assert payload["validation_status"] == "PASSED"


def test_hidden_truth_cannot_enter_safe_input_summary() -> None:
    with pytest.raises(ValueError):
        MCPCallTraceV2(
            sequence=1,
            tool_name="get_account_context",
            safe_input_summary={"account_ref": "Patterns.txt"},
            started_at="2026-08-28T00:00:00.000Z",
            latency_ms=0,
            result_status="ERROR",
            result_size_bytes=0,
            evidence_ids=(),
        )
