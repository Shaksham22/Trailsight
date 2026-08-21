from __future__ import annotations

import asyncio
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace

from ai_helpers import FakeService, make_ai_config
from trailsight_ai.output import Finding, InvestigationModelOutput
from trailsight_ai.runner import (
    MCPInfrastructureError,
    SDKExecution,
    StructuredOutputError,
    InvestigationRunner,
    _ToolRecorder,
)
from trailsight_ai.telemetry import TokenUsage, ToolCallTrace


def tool_call(
    sequence: int,
    tool_name: str,
    *,
    status: str = "ok",
    evidence_id: str | None = None,
    safe_input: dict | None = None,
) -> ToolCallTrace:
    return ToolCallTrace(
        sequence=sequence,
        tool_name=tool_name,
        safe_input=safe_input or {"case_ref": "demo-01"},
        started_at="2026-08-20T12:00:00.000Z",
        status=status,
        latency_ms=2.5,
        result_size_bytes=128,
        evidence_id=evidence_id,
    )


def initial_output(
    second_id: str = "ev:demo-01:amount-history",
) -> InvestigationModelOutput:
    return InvestigationModelOutput(
        status="success",
        findings=[
            Finding(
                text="The selected transaction is cross-currency.",
                evidence_ids=["ev:demo-01:selected"],
            ),
            Finding(
                text="The amount has sufficient same-currency history.",
                evidence_ids=[second_id],
            ),
        ],
        limits=[],
    )


class FakeExecutor:
    def __init__(self, execution: SDKExecution | None = None, error=None) -> None:
        self.execution = execution
        self.error = error
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.execution is not None
        return self.execution


def execution_for(output: InvestigationModelOutput, calls=None) -> SDKExecution:
    calls = calls or []
    summaries = {}
    for call in calls:
        if call.evidence_id == "ev:demo-01:amount-history":
            summaries[call.evidence_id] = {
                "status": "ok",
                "evidence_id": call.evidence_id,
                "payment_currency": "CNY",
                "selected_amount": "69.54",
                "sample_size": 70,
                "history_quality": "sufficient",
                "historical_median": "15.095",
                "empirical_percentile": 95.7142857,
                "error_code": None,
            }
    return SDKExecution(
        output=output,
        tool_calls=calls,
        evidence_summaries=summaries,
        token_usage=TokenUsage(
            requests=2,
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
        ),
    )


def test_sdk_tool_hooks_capture_actual_order_inputs_results_and_evidence() -> None:
    recorder = _ToolRecorder()
    tool_a = SimpleNamespace(name="get_currency_history")
    tool_b = SimpleNamespace(name="get_sender_history")
    context_a = SimpleNamespace(
        tool_call_id="call-a",
        tool_arguments=json.dumps(
            {
                "case_ref": "demo-01",
                "dimension": "receiving",
                "currency": "USD",
                "unapproved": "drop-me",
            }
        ),
    )
    context_b = SimpleNamespace(
        tool_call_id="call-b",
        tool_arguments='{"case_ref":"demo-01"}',
    )

    async def record() -> None:
        await recorder.on_tool_start(context_a, None, tool_a)
        await recorder.on_tool_start(context_b, None, tool_b)
        await recorder.on_tool_end(
            context_b,
            None,
            tool_b,
            '{"status":"ok","evidence_id":"ev:demo-01:sender-history","prior_outgoing_count":74}',
        )
        await recorder.on_tool_end(
            context_a,
            None,
            tool_a,
            '{"status":"ok","evidence_id":"ev:demo-01:currency:receiving:USD","dimension":"receiving","currency":"USD"}',
        )

    asyncio.run(record())

    assert [call.sequence for call in recorder.tool_calls] == [1, 2]
    assert [call.tool_name for call in recorder.tool_calls] == [
        "get_currency_history",
        "get_sender_history",
    ]
    assert recorder.tool_calls[0].safe_input == {
        "case_ref": "demo-01",
        "dimension": "receiving",
        "currency": "USD",
    }
    assert recorder.tool_calls[0].result_size_bytes > 0
    assert set(recorder.evidence_summaries) == {
        "ev:demo-01:currency:receiving:USD",
        "ev:demo-01:sender-history",
    }


def test_success_records_trace_and_renders_evidence(
    tmp_path, monkeypatch
) -> None:
    ai_config = make_ai_config(tmp_path)
    fake_service = FakeService()
    monkeypatch.setenv("TRAILSIGHT_DB_PATH", "/approved/runtime.duckdb")
    call = tool_call(
        1,
        "compare_amount_history",
        evidence_id="ev:demo-01:amount-history",
    )
    executor = FakeExecutor(execution_for(initial_output(), [call]))
    runner = InvestigationRunner(ai_config, executor=executor)

    run = asyncio.run(runner.run_initial("demo-01", fake_service))

    assert run.response.run_status.value == "success"
    assert [item.label for item in run.response.evidence] == ["E1", "E2"]
    trace = json.loads(ai_config.trace_path.read_text(encoding="utf-8"))
    assert trace["trace_schema_version"] == 1
    assert trace["model_identifier"] == "configured-test-model"
    assert trace["prompt_version"] == "investigation-v1"
    assert trace["tool_calls"][0]["tool_name"] == "compare_amount_history"
    assert trace["token_usage"] == {
        "requests": 2,
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
    }
    assert trace["estimated_cost_usd"] is None
    assert "test-key-not-for-network" not in json.dumps(trace)
    assert "supporting_transaction_refs" not in json.dumps(trace)
    assert executor.requests[0].model_identifier == "configured-test-model"
    assert set(executor.requests[0].mcp_environment) == {
        "TRAILSIGHT_DB_PATH",
        "PYTHONPATH",
    }
    assert "OPENAI_API_KEY" not in executor.requests[0].mcp_environment


def test_follow_up_contains_only_current_question_and_selected_summary(
    tmp_path,
) -> None:
    ai_config = make_ai_config(tmp_path)
    fake_service = FakeService()
    output = InvestigationModelOutput(
        status="success",
        findings=[
            Finding(
                text="The selected payment currency is CNY.",
                evidence_ids=["ev:demo-01:selected"],
            )
        ],
        limits=[],
    )
    executor = FakeExecutor(execution_for(output))
    runner = InvestigationRunner(ai_config, executor=executor)

    run = asyncio.run(
        runner.run_follow_up(
            "demo-01",
            "  What is the payment currency?  ",
            "inv_parentopaque",
            fake_service,
        )
    )

    payload = json.loads(executor.requests[0].task_input)
    assert payload["current_question"] == "What is the payment currency?"
    assert set(payload) == {"selected_transaction", "task", "current_question"}
    assert "inv_parentopaque" not in executor.requests[0].task_input
    assert "previous" not in executor.requests[0].task_input.casefold()
    assert run.response.parent_investigation_id == "inv_parentopaque"


def test_failure_status_mapping_is_fail_closed(tmp_path) -> None:
    ai_config = make_ai_config(tmp_path)
    fake_service = FakeService()
    failures = [
        (RuntimeError("model"), "model_error"),
        (MCPInfrastructureError("mcp"), "tool_error"),
        (StructuredOutputError("schema"), "structured_output_invalid"),
    ]
    for error, expected in failures:
        config = replace(
            ai_config,
            trace_path=ai_config.trace_path.with_name(f"{expected}.jsonl"),
        )
        run = asyncio.run(
            InvestigationRunner(config, executor=FakeExecutor(error=error)).run_initial(
                "demo-01", fake_service
            )
        )
        assert run.response.run_status.value == expected
        assert run.response.findings == []
        assert run.response.evidence == []
        trace = json.loads(config.trace_path.read_text(encoding="utf-8"))
        assert trace["run_status"] == expected
        assert trace["failure_code"] == expected


def test_evidence_failure_rejects_entire_generated_answer(
    tmp_path,
) -> None:
    ai_config = make_ai_config(tmp_path)
    fake_service = FakeService()
    executor = FakeExecutor(execution_for(initial_output("ev:demo-01:invented")))
    run = asyncio.run(
        InvestigationRunner(ai_config, executor=executor).run_initial(
            "demo-01", fake_service
        )
    )

    assert run.response.run_status.value == "evidence_validation_failed"
    assert run.response.findings == []
    assert run.response.evidence == []
    assert run.validation_status == "failed"
    assert run.structured_output is not None
    trace = json.loads(ai_config.trace_path.read_text(encoding="utf-8"))
    assert trace["run_status"] == "evidence_validation_failed"
    assert trace["validation_status"] == "failed"
    assert trace["referenced_evidence_ids"] == [
        "ev:demo-01:selected",
        "ev:demo-01:invented",
    ]


def test_valid_unavailable_and_partial_with_failed_unrelated_tool(
    tmp_path,
) -> None:
    ai_config = make_ai_config(tmp_path)
    fake_service = FakeService()
    unavailable = InvestigationModelOutput(
        status="unavailable",
        findings=[],
        limits=["Transaction purpose is unavailable."],
    )
    unavailable_run = asyncio.run(
        InvestigationRunner(
            replace(ai_config, trace_path=ai_config.trace_path.with_name("unavailable.jsonl")),
            executor=FakeExecutor(execution_for(unavailable)),
        ).run_follow_up("demo-01", "Why?", None, fake_service)
    )
    assert unavailable_run.response.run_status.value == "unavailable"
    assert unavailable_run.response.findings == []

    partial = InvestigationModelOutput(
        status="partial",
        findings=[
            Finding(
                text="The amount history is sufficient.",
                evidence_ids=["ev:demo-01:amount-history"],
            )
        ],
        limits=["Region history was unavailable."],
    )
    calls = [
        tool_call(
            1,
            "compare_amount_history",
            evidence_id="ev:demo-01:amount-history",
        ),
        tool_call(2, "get_region_history", status="error"),
    ]
    partial_run = asyncio.run(
        InvestigationRunner(
            replace(ai_config, trace_path=ai_config.trace_path.with_name("partial.jsonl")),
            executor=FakeExecutor(execution_for(partial, calls)),
        ).run_follow_up("demo-01", "Amount and region?", None, fake_service)
    )
    assert partial_run.response.run_status.value == "partial"
    assert len(partial_run.response.findings) == 1


def test_all_failed_tools_map_to_empty_tool_error(tmp_path) -> None:
    ai_config = make_ai_config(tmp_path)
    fake_service = FakeService()
    output = InvestigationModelOutput(
        status="success",
        findings=[
            Finding(
                text="The transaction is cross-currency.",
                evidence_ids=["ev:demo-01:selected"],
            )
        ],
        limits=[],
    )
    calls = [tool_call(1, "compare_amount_history", status="error")]
    run = asyncio.run(
        InvestigationRunner(
            ai_config, executor=FakeExecutor(execution_for(output, calls))
        ).run_follow_up("demo-01", "Compare the amount.", None, fake_service)
    )

    assert run.response.run_status.value == "tool_error"
    assert run.response.findings == []
    assert run.response.evidence == []

    unavailable = InvestigationModelOutput(
        status="unavailable",
        findings=[],
        limits=["The required tool result was unavailable."],
    )
    unavailable_run = asyncio.run(
        InvestigationRunner(
            replace(ai_config, trace_path=tmp_path / "tool-unavailable.jsonl"),
            executor=FakeExecutor(execution_for(unavailable, calls)),
        ).run_follow_up("demo-01", "Compare the amount.", None, fake_service)
    )
    assert unavailable_run.response.run_status.value == "tool_error"
    assert unavailable_run.response.limits == []


def test_cost_calculation_and_trace_write_failure_do_not_change_response(
    tmp_path, monkeypatch
) -> None:
    ai_config = make_ai_config(tmp_path)
    fake_service = FakeService()
    priced_config = replace(
        ai_config,
        input_usd_per_million=Decimal("2"),
        output_usd_per_million=Decimal("10"),
    )
    call = tool_call(
        1,
        "compare_amount_history",
        evidence_id="ev:demo-01:amount-history",
    )
    runner = InvestigationRunner(
        priced_config,
        executor=FakeExecutor(execution_for(initial_output(), [call])),
    )

    run = asyncio.run(runner.run_initial("demo-01", fake_service))
    assert run.estimated_cost_usd == 0.0004

    import trailsight_ai.telemetry as telemetry

    monkeypatch.setattr(
        telemetry,
        "append_trace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("read only")),
    )
    safe_runner = InvestigationRunner(
        replace(ai_config, trace_path=Path("/not-written/trace.jsonl")),
        executor=FakeExecutor(execution_for(initial_output(), [call])),
    )
    safe_run = asyncio.run(safe_runner.run_initial("demo-01", fake_service))
    assert safe_run.response.run_status.value == "success"
