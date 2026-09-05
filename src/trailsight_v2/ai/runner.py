"""OpenAI Agents SDK orchestration for one bounded Trailsight V2 investigation run."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from trailsight_v2.domain.models import InvestigationContextV2, SubjectType
from trailsight_v2.domain.service import InvestigationServiceV2
from trailsight_v2.mcp.contracts import TOOL_NAMES
from trailsight_v2.mcp.scope import InvestigationScopeV2, scope_to_json

from .config import AIConfig, load_ai_config, load_prompt
from .context import SeedContextV2
from .models import (
    InvestigationResponseV2,
    InvestigationSummaryV2,
    InvestigationStatus,
)
from .telemetry import (
    InvestigationTraceV2,
    MCPCallTraceV2,
    TokenUsageV2,
    append_trace_safely,
    estimate_cost_usd,
    utc_timestamp,
)


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SUCCESSFUL_TOOL_STATUSES = {"OK"}
MCP_CLIENT_SESSION_TIMEOUT_SECONDS = 10.0
_TOOL_INPUT_FIELDS: dict[str, tuple[str, ...]] = {
    "get_alert_context": ("alert_ref",),
    "get_transaction_context": ("transaction_ref",),
    "get_account_context": ("account_ref",),
    "get_behavioral_indicators": ("account_ref",),
    "get_relationship_context": ("account_ref", "counterparty_account_ref"),
    "get_network_context": ("account_ref",),
    "get_supporting_evidence": ("evidence_id",),
}


@dataclass(frozen=True, slots=True)
class ModelRunRequestV2:
    mode: Literal["initial", "follow_up"]
    model_identifier: str
    system_prompt: str
    task_input: str
    mcp_environment: dict[str, str]
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class SDKExecutionV2:
    output: InvestigationSummaryV2
    mcp_calls: tuple[MCPCallTraceV2, ...]
    token_usage: TokenUsageV2


class ModelExecutorV2(Protocol):
    async def execute(self, request: ModelRunRequestV2) -> SDKExecutionV2: ...


class _ExecutionError(RuntimeError):
    code = "AI_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.mcp_calls: tuple[MCPCallTraceV2, ...] = ()
        self.token_usage = TokenUsageV2()


class StructuredOutputError(_ExecutionError):
    code = "STRUCTURED_OUTPUT_INVALID"


class MCPInfrastructureError(_ExecutionError):
    code = "TOOL_ERROR"


class ModelExecutionError(_ExecutionError):
    code = "MODEL_ERROR"


class ModelTimeoutError(_ExecutionError):
    code = "MODEL_TIMEOUT"


@dataclass(frozen=True, slots=True)
class InvestigationRunV2:
    response: InvestigationResponseV2 | None
    structured_output: InvestigationSummaryV2 | None
    mcp_calls: tuple[MCPCallTraceV2, ...]
    token_usage: TokenUsageV2
    estimated_cost_usd: float | None
    validation_status: Literal["PASSED", "FAILED", "NOT_RUN"]
    failure_code: str | None

    @property
    def succeeded(self) -> bool:
        return self.response is not None and self.failure_code is None


@dataclass(slots=True)
class _PendingCall:
    sequence: int
    tool_name: str
    safe_input: dict[str, Any]
    started_at: datetime
    started_clock: float


class ToolCallRecorderV2:
    """State used by the real SDK RunHooks implementation and deterministic tests."""

    def __init__(self) -> None:
        self._pending: dict[str, _PendingCall] = {}
        self.calls: list[MCPCallTraceV2] = []

    @property
    def has_incomplete_calls(self) -> bool:
        return bool(self._pending)

    def start(self, *, call_id: str, tool_name: str, arguments: object) -> None:
        self._pending[call_id] = _PendingCall(
            sequence=len(self.calls) + len(self._pending) + 1,
            tool_name=tool_name,
            safe_input=_safe_tool_input(tool_name, arguments),
            started_at=datetime.now(timezone.utc),
            started_clock=perf_counter(),
        )

    def end(self, *, call_id: str, tool_name: str, arguments: object, result: object) -> None:
        pending = self._pending.pop(call_id, None)
        if pending is None:
            pending = _PendingCall(
                sequence=len(self.calls) + 1,
                tool_name=tool_name,
                safe_input=_safe_tool_input(tool_name, arguments),
                started_at=datetime.now(timezone.utc),
                started_clock=perf_counter(),
            )
        raw, payload = _tool_result_payload(result)
        status = str(payload.get("status", "ERROR")).upper()
        evidence_ids = _evidence_ids_from_payload(payload) if status in _SUCCESSFUL_TOOL_STATUSES else ()
        self.calls.append(
            MCPCallTraceV2(
                sequence=pending.sequence,
                tool_name=pending.tool_name,
                safe_input_summary=pending.safe_input,
                started_at=utc_timestamp(pending.started_at),
                latency_ms=max(0.0, (perf_counter() - pending.started_clock) * 1000),
                result_status=status,
                result_size_bytes=len(raw),
                evidence_ids=evidence_ids,
            )
        )
        self.calls.sort(key=lambda item: item.sequence)

    def finish_incomplete(self) -> None:
        for pending in sorted(self._pending.values(), key=lambda item: item.sequence):
            self.calls.append(
                MCPCallTraceV2(
                    sequence=pending.sequence,
                    tool_name=pending.tool_name,
                    safe_input_summary=pending.safe_input,
                    started_at=utc_timestamp(pending.started_at),
                    latency_ms=max(0.0, (perf_counter() - pending.started_clock) * 1000),
                    result_status="ERROR",
                    result_size_bytes=0,
                    evidence_ids=(),
                )
            )
        self._pending.clear()
        self.calls.sort(key=lambda item: item.sequence)


class AgentsSDKExecutorV2:
    """Production executor using real Agents SDK MCP calls and RunHooks."""

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def execute(self, request: ModelRunRequestV2) -> SDKExecutionV2:
        # Imports are intentionally local: the deterministic REST application can
        # boot without the optional AI provider being configured, while production
        # execution still uses the locked SDK directly.
        try:
            from agents import Agent, ModelBehaviorError, RunConfig, RunHooks, Runner
            from agents.mcp import MCPServerStdio
            from agents.models.openai_provider import OpenAIProvider
            from openai import AsyncOpenAI
        except Exception as exc:  # pragma: no cover - dependency/runtime integration
            raise MCPInfrastructureError("The locked Agents/MCP SDK could not be imported") from exc

        recorder = ToolCallRecorderV2()

        class _Hooks(RunHooks):
            async def on_tool_start(self, context, _agent, tool) -> None:
                name = str(getattr(tool, "name", "unknown"))
                call_id = str(
                    getattr(context, "tool_call_id", "")
                    or f"{name}:{len(recorder.calls) + len(recorder._pending) + 1}"
                )
                recorder.start(
                    call_id=call_id,
                    tool_name=name,
                    arguments=getattr(context, "tool_arguments", "{}"),
                )

            async def on_tool_end(self, context, _agent, tool, result) -> None:
                name = str(getattr(tool, "name", "unknown"))
                call_id = str(getattr(context, "tool_call_id", "") or "")
                recorder.end(
                    call_id=call_id,
                    tool_name=name,
                    arguments=getattr(context, "tool_arguments", "{}"),
                    result=result,
                )

        server = MCPServerStdio(
            name="trailsight-v2-mcp",
            params={
                "command": sys.executable,
                "args": ["-m", "trailsight_v2.mcp.server"],
                "cwd": str(_PROJECT_ROOT),
                "env": request.mcp_environment,
            },
            cache_tools_list=True,
            use_structured_content=True,
            client_session_timeout_seconds=MCP_CLIENT_SESSION_TIMEOUT_SECONDS,
            max_retry_attempts=0,
        )
        connected = False
        result: object | None = None
        try:
            async with asyncio.timeout(request.timeout_seconds):
                async with server:
                    connected = True
                    try:
                        listed = await server.list_tools()
                        if tuple(sorted(tool.name for tool in listed)) != tuple(sorted(TOOL_NAMES)):
                            raise MCPInfrastructureError(
                                "The local V2 MCP tool set did not match the frozen seven-tool contract"
                            )
                    except MCPInfrastructureError:
                        raise
                    except Exception as exc:
                        raise MCPInfrastructureError(
                            "The local V2 MCP tool list could not be loaded"
                        ) from exc

                    async with AsyncOpenAI(api_key=self._api_key, max_retries=0) as client:
                        agent = Agent(
                            name="Trailsight V2 investigation assistant",
                            instructions=request.system_prompt,
                            model=request.model_identifier,
                            mcp_servers=[server],
                            output_type=InvestigationSummaryV2,
                        )
                        try:
                            result = await Runner.run(
                                agent,
                                request.task_input,
                                hooks=_Hooks(),
                                max_turns=8,
                                run_config=RunConfig(
                                    model_provider=OpenAIProvider(openai_client=client),
                                    tracing_disabled=True,
                                    workflow_name="Trailsight V2 investigation",
                                ),
                            )
                        except ModelBehaviorError as exc:
                            raise StructuredOutputError(
                                "The model did not satisfy InvestigationSummaryV2"
                            ) from exc
        except asyncio.TimeoutError as exc:
            recorder.finish_incomplete()
            mapped = ModelTimeoutError("The bounded AI run timed out")
            _attach_execution(mapped, recorder)
            raise mapped from exc
        except StructuredOutputError as exc:
            recorder.finish_incomplete()
            _attach_execution(exc, recorder)
            raise
        except MCPInfrastructureError as exc:
            recorder.finish_incomplete()
            _attach_execution(exc, recorder)
            raise
        except Exception as exc:
            had_incomplete = recorder.has_incomplete_calls
            recorder.finish_incomplete()
            if not connected or had_incomplete:
                mapped: _ExecutionError = MCPInfrastructureError(
                    "The local V2 MCP connection or tool execution failed"
                )
            else:
                mapped = ModelExecutionError("The configured model request failed")
            _attach_execution(mapped, recorder)
            raise mapped from exc

        if result is None:  # pragma: no cover - defensive SDK boundary
            mapped = ModelExecutionError("The model run returned no result")
            _attach_execution(mapped, recorder)
            raise mapped
        try:
            final_output = getattr(result, "final_output", None)
            if not isinstance(final_output, InvestigationSummaryV2):
                final_output = InvestigationSummaryV2.model_validate(final_output)
        except Exception as exc:
            mapped = StructuredOutputError(
                "The model response violated the investigation summary contract"
            )
            _attach_execution(mapped, recorder)
            mapped.token_usage = _token_usage_from_result(result)
            raise mapped from exc
        return SDKExecutionV2(
            output=final_output,
            mcp_calls=tuple(recorder.calls),
            token_usage=_token_usage_from_result(result),
        )


class InvestigationRunnerV2:
    """Run an initial investigation or one stateless follow-up and write one trace."""

    def __init__(self, config: AIConfig, *, executor: ModelExecutorV2 | None = None) -> None:
        self.config = config
        self._executor = executor or AgentsSDKExecutorV2(api_key=config.api_key)

    @classmethod
    def from_environment(cls) -> "InvestigationRunnerV2":
        return cls(load_ai_config())

    async def run_initial(
        self,
        *,
        investigation_id: str,
        seed: SeedContextV2,
        service: InvestigationServiceV2,
        runtime_state_path: Path,
        origin_alert_ref: str | None,
        origin_transaction_ref: str | None,
    ) -> InvestigationRunV2:
        return await self._run(
            mode="initial",
            investigation_id=investigation_id,
            parent_investigation_id=None,
            question=None,
            seed=seed,
            service=service,
            runtime_state_path=runtime_state_path,
            origin_alert_ref=origin_alert_ref,
            origin_transaction_ref=origin_transaction_ref,
        )

    async def run_follow_up(
        self,
        *,
        investigation_id: str,
        parent_investigation_id: str,
        question: str,
        seed: SeedContextV2,
        service: InvestigationServiceV2,
        runtime_state_path: Path,
        origin_alert_ref: str | None,
        origin_transaction_ref: str | None,
    ) -> InvestigationRunV2:
        normalized = question.strip()
        if not 1 <= len(normalized) <= 500:
            raise ValueError("Follow-up question must contain 1 to 500 characters")
        return await self._run(
            mode="follow_up",
            investigation_id=investigation_id,
            parent_investigation_id=parent_investigation_id,
            question=normalized,
            seed=seed,
            service=service,
            runtime_state_path=runtime_state_path,
            origin_alert_ref=origin_alert_ref,
            origin_transaction_ref=origin_transaction_ref,
        )

    async def _run(
        self,
        *,
        mode: Literal["initial", "follow_up"],
        investigation_id: str,
        parent_investigation_id: str | None,
        question: str | None,
        seed: SeedContextV2,
        service: InvestigationServiceV2,
        runtime_state_path: Path,
        origin_alert_ref: str | None,
        origin_transaction_ref: str | None,
    ) -> InvestigationRunV2:
        started_at = datetime.now(timezone.utc)
        started_clock = perf_counter()
        output: InvestigationSummaryV2 | None = None
        calls: tuple[MCPCallTraceV2, ...] = ()
        usage = TokenUsageV2()
        validation_status: Literal["PASSED", "FAILED", "NOT_RUN"] = "NOT_RUN"
        failure_code: str | None = None
        response: InvestigationResponseV2 | None = None

        unsupported_limit = (
            _hidden_truth_follow_up_limit(question)
            if mode == "follow_up" and question is not None
            else None
        )
        if unsupported_limit is not None:
            output = InvestigationSummaryV2(
                summary="This follow-up cannot be answered from the bounded investigation packet.",
                observations=[],
                patterns=[],
                limits=[unsupported_limit],
            )
            response = InvestigationResponseV2(
                investigation_id=investigation_id,
                run_status=InvestigationStatus.UNAVAILABLE,
                subject_type=seed.context.subject_type,
                subject_ref=seed.context.subject_ref,
                context=seed.context,
                summary=output.summary,
                observations=(),
                patterns=(),
                limits=(unsupported_limit,),
            )
        else:
            request = self._request(
                mode=mode,
                seed=seed,
                question=question,
                runtime_state_path=runtime_state_path,
                origin_alert_ref=origin_alert_ref,
                origin_transaction_ref=origin_transaction_ref,
            )
            try:
                execution = await self._executor.execute(request)
                output = execution.output
                calls = execution.mcp_calls
                usage = execution.token_usage
                validation_status = "PASSED"
                run_status, final_output = _application_output(output, calls)
                response = InvestigationResponseV2(
                    investigation_id=investigation_id,
                    run_status=run_status,
                    subject_type=seed.context.subject_type,
                    subject_ref=seed.context.subject_ref,
                    context=seed.context,
                    summary=final_output.summary,
                    observations=tuple(final_output.observations),
                    patterns=tuple(final_output.patterns),
                    limits=tuple(final_output.limits),
                )
            except _ExecutionError as exc:
                calls = exc.mcp_calls
                usage = exc.token_usage
                failure_code = exc.code
            except Exception:
                failure_code = "AI_ERROR"

        cost = estimate_cost_usd(
            usage,
            input_usd_per_million=self.config.input_usd_per_million,
            output_usd_per_million=self.config.output_usd_per_million,
        )
        finished_at = datetime.now(timezone.utc)
        trace = InvestigationTraceV2(
            investigation_id=investigation_id,
            parent_investigation_id=parent_investigation_id,
            subject_type=seed.context.subject_type.value,
            subject_ref=seed.context.subject_ref,
            origin_alert_ref=origin_alert_ref,
            origin_transaction_ref=origin_transaction_ref,
            snapshot_id=seed.context.detector_snapshot_id,
            detector_cutoff=seed.context.detector_cutoff,
            prompt_version=self.config.prompt_version,
            prompt_sha256=self.config.prompt_sha256,
            model_identifier=self.config.model_identifier,
            started_at=utc_timestamp(started_at),
            finished_at=utc_timestamp(finished_at),
            latency_ms=max(0.0, (perf_counter() - started_clock) * 1000),
            run_status=(failure_code or (response.run_status.value if response else "UNAVAILABLE")),
            mcp_calls=calls,
            referenced_evidence_ids=(),
            validation_status=validation_status,
            token_usage=usage,
            estimated_cost_usd=cost,
            failure_code=failure_code,
        )
        append_trace_safely(self.config.trace_path, trace)
        return InvestigationRunV2(
            response=response,
            structured_output=output,
            mcp_calls=calls,
            token_usage=usage,
            estimated_cost_usd=cost,
            validation_status=validation_status,
            failure_code=failure_code,
        )

    def _request(
        self,
        *,
        mode: Literal["initial", "follow_up"],
        seed: SeedContextV2,
        question: str | None,
        runtime_state_path: Path,
        origin_alert_ref: str | None,
        origin_transaction_ref: str | None,
    ) -> ModelRunRequestV2:
        task = (
            "Write for a reader with no AML, graph-analysis, or data-science expertise. Explain "
            "the authoritative subject result using the subject-specific opening rules. For an "
            "account, explain the supplied GARG conclusion. For a transaction, state the supplied "
            "review priority and its sender/receiver band derivation without inventing a transaction "
            "GARG score. Keep scores, ranks, snapshots, raw measures, and unexplained product jargon "
            "out of routine prose. Describe supplied deterministic facts honestly. Never call the "
            "subject safe or the transactions genuine, and avoid product narration or advice."
            if mode == "initial"
            else (
                "Answer exactly this one bounded follow-up by reasoning across the same investigation "
                "packet and preserve its authoritative account band or transaction-priority derivation."
            )
        )
        payload: dict[str, Any] = {
            "investigation_packet": seed.model_summary,
            "task": task,
        }
        if question is not None:
            payload["current_question"] = question
        scope = InvestigationScopeV2(
            subject_type=seed.context.subject_type,
            subject_ref=seed.context.subject_ref,
            origin_alert_ref=origin_alert_ref,
            origin_transaction_ref=origin_transaction_ref,
            context_identity=seed.context.context_identity,
            seed_evidence_ids=seed.seed_evidence_ids,
        )
        database_path = Path(
            os.environ.get(
                "TRAILSIGHT_V2_DB_PATH", "data/v2/runtime/trailsight_v2.duckdb"
            )
        ).expanduser().resolve()
        mcp_environment = {
            "TRAILSIGHT_V2_DB_PATH": str(database_path),
            "TRAILSIGHT_RUNTIME_STATE_PATH": str(runtime_state_path),
            "TRAILSIGHT_MCP_SCOPE_JSON": scope_to_json(scope),
            "PYTHONPATH": str(_PROJECT_ROOT / "src"),
        }
        return ModelRunRequestV2(
            mode=mode,
            model_identifier=self.config.model_identifier,
            system_prompt=load_prompt(self.config.prompt_version),
            task_input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            mcp_environment=mcp_environment,
            timeout_seconds=self.config.run_timeout_seconds,
        )


def _attach_execution(error: _ExecutionError, recorder: ToolCallRecorderV2) -> None:
    error.mcp_calls = tuple(recorder.calls)


def _safe_tool_input(tool_name: str, arguments: object) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
    except (TypeError, ValueError):
        parsed = {}
    if not isinstance(parsed, dict):
        return {}
    return {
        field: parsed[field]
        for field in _TOOL_INPUT_FIELDS.get(tool_name, ())
        if field in parsed and (parsed[field] is None or isinstance(parsed[field], str))
    }


def _tool_result_payload(result: object) -> tuple[bytes, dict[str, Any]]:
    if isinstance(result, BaseModel):
        value: Any = result.model_dump(mode="json")
    else:
        value = result
    if isinstance(value, dict):
        for key in ("structuredContent", "structured_content"):
            nested = value.get(key)
            if isinstance(nested, dict):
                raw = json.dumps(nested, ensure_ascii=False, separators=(",", ":")).encode()
                return raw, nested
        if isinstance(value.get("text"), str):
            text = value["text"]
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                parsed = {}
            return text.encode(), parsed if isinstance(parsed, dict) else {}
        raw = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":")).encode()
        return raw, value
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = {}
    return text.encode(), parsed if isinstance(parsed, dict) else {}


def _evidence_ids_from_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    ordered: list[str] = []
    singular = payload.get("evidence_id")
    if isinstance(singular, str) and singular:
        ordered.append(singular)
    plural = payload.get("evidence_ids")
    if isinstance(plural, (list, tuple)):
        for evidence_id in plural:
            if isinstance(evidence_id, str) and evidence_id and evidence_id not in ordered:
                ordered.append(evidence_id)
    return tuple(ordered)


def _token_usage_from_result(result: object) -> TokenUsageV2:
    wrapper = getattr(result, "context_wrapper", None)
    usage = getattr(wrapper, "usage", None)
    if usage is None:
        return TokenUsageV2()
    return TokenUsageV2(
        requests=max(0, int(getattr(usage, "requests", 0) or 0)),
        input_tokens=max(0, int(getattr(usage, "input_tokens", 0) or 0)),
        output_tokens=max(0, int(getattr(usage, "output_tokens", 0) or 0)),
        total_tokens=max(0, int(getattr(usage, "total_tokens", 0) or 0)),
    )


def _application_output(
    output: InvestigationSummaryV2,
    calls: tuple[MCPCallTraceV2, ...],
) -> tuple[InvestigationStatus, InvestigationSummaryV2]:
    failed = [call for call in calls if call.result_status not in _SUCCESSFUL_TOOL_STATUSES]
    if not failed:
        return InvestigationStatus.SUCCESS, output
    mandatory_limit = "One or more bounded evidence tools were unavailable."
    limits = [mandatory_limit]
    limits.extend(limit for limit in output.limits if limit != mandatory_limit)
    return InvestigationStatus.PARTIAL, output.model_copy(
        update={"limits": limits[:6]},
    )


def _hidden_truth_follow_up_limit(question: str) -> str | None:
    normalized = " ".join(question.lower().split())
    hidden_identifiers = ("is laundering", "patterns.txt")
    if any(token in normalized for token in hidden_identifiers) or (
        "hidden" in normalized
        and ("benchmark" in normalized or "ground truth" in normalized or "pattern" in normalized)
    ):
        return "Hidden benchmark truth is not available to runtime investigations."
    return None
