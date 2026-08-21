"""Single-agent Trailsight orchestration over the approved local stdio MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Literal, Protocol
from uuid import uuid4

from agents import Agent, ModelBehaviorError, RunConfig, RunHooks, Runner
from agents.mcp import MCPServerStdio
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict

from trailsight.contracts import (
    InternalEvidence,
    InvestigationResponse,
    InvestigationRunStatus,
    SelectedTransaction,
)
from trailsight.domain.service import InvestigationService
from trailsight_ai.config import AIConfig, load_ai_config, load_prompt
from trailsight_ai.output import (
    InvestigationModelOutput,
    validate_output_for_mode,
)
from trailsight_ai.telemetry import (
    InvestigationTrace,
    TokenUsage,
    ToolCallTrace,
    append_trace_safely,
    estimate_cost_usd,
    utc_timestamp,
)
from trailsight_ai.validation import EvidenceValidationError, validate_and_render


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TOOL_INPUT_FIELDS = {
    "get_sender_history": ("case_ref",),
    "compare_amount_history": ("case_ref",),
    "get_counterparty_history": ("case_ref",),
    "get_region_history": ("case_ref",),
    "get_currency_history": ("case_ref", "dimension", "currency"),
}
_SUCCESSFUL_TOOL_STATUSES = {"ok", "insufficient_history"}


class ContextModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SenderModelSummary(ContextModel):
    bank: str
    account: str


class CounterpartyModelSummary(ContextModel):
    bank: str
    account: str
    entity_type: str


class SelectedTransactionModelSummary(ContextModel):
    evidence_id: str
    timestamp: str
    sender: SenderModelSummary
    counterparty: CounterpartyModelSummary
    amount_paid: str
    payment_currency: str
    amount_received: str
    receiving_currency: str
    payment_format: str
    sender_region: int
    receiver_region: int
    cross_currency: bool
    currency_pair: str
    region_relationship: str


def selected_transaction_summary(
    selected_evidence: InternalEvidence,
) -> SelectedTransactionModelSummary:
    """Project only the approved selected-transaction facts for model context."""

    facts = selected_evidence.facts
    if not isinstance(facts, SelectedTransaction):
        raise TypeError("Selected evidence did not contain selected transaction facts")
    return SelectedTransactionModelSummary(
        evidence_id=selected_evidence.evidence_id,
        timestamp=facts.timestamp,
        sender=SenderModelSummary(
            bank=facts.sender.bank,
            account=facts.sender.account,
        ),
        counterparty=CounterpartyModelSummary(
            bank=facts.counterparty.bank,
            account=facts.counterparty.account,
            entity_type=facts.counterparty.entity_type.value,
        ),
        amount_paid=facts.amount_paid,
        payment_currency=facts.payment_currency,
        amount_received=facts.amount_received,
        receiving_currency=facts.receiving_currency,
        payment_format=facts.payment_format,
        sender_region=facts.sender.synthetic_region,
        receiver_region=facts.counterparty.synthetic_region,
        cross_currency=facts.cross_currency,
        currency_pair=facts.currency_pair,
        region_relationship=facts.region_relationship.value,
    )


@dataclass(frozen=True, slots=True)
class ModelRunRequest:
    mode: Literal["initial", "follow_up"]
    model_identifier: str
    system_prompt: str
    task_input: str
    mcp_environment: dict[str, str]


@dataclass(frozen=True, slots=True)
class SDKExecution:
    output: InvestigationModelOutput
    tool_calls: list[ToolCallTrace]
    evidence_summaries: dict[str, dict[str, Any]]
    token_usage: TokenUsage


class ModelExecutor(Protocol):
    async def execute(self, request: ModelRunRequest) -> SDKExecution: ...


class StructuredOutputError(RuntimeError):
    """The model did not return the frozen structured-output schema."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.tool_calls: list[ToolCallTrace] = []
        self.evidence_summaries: dict[str, dict[str, Any]] = {}
        self.token_usage = TokenUsage()


class MCPInfrastructureError(RuntimeError):
    """The approved local MCP boundary could not provide usable tool execution."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.tool_calls: list[ToolCallTrace] = []
        self.evidence_summaries: dict[str, dict[str, Any]] = {}
        self.token_usage = TokenUsage()


class ModelExecutionError(RuntimeError):
    """A model/API failure occurred before a valid structured output."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.tool_calls: list[ToolCallTrace] = []
        self.evidence_summaries: dict[str, dict[str, Any]] = {}
        self.token_usage = TokenUsage()


@dataclass(frozen=True, slots=True)
class InvestigationRun:
    response: InvestigationResponse
    structured_output: InvestigationModelOutput | None
    tool_calls: list[ToolCallTrace]
    evidence_summaries: dict[str, dict[str, Any]]
    token_usage: TokenUsage
    estimated_cost_usd: float | None
    validation_status: Literal["passed", "failed", "not_run"]
    failure_code: str | None


@dataclass(slots=True)
class _PendingToolCall:
    sequence: int
    tool_name: str
    safe_input: dict[str, Any]
    started_at: datetime
    started_clock: float


class _ToolRecorder(RunHooks):
    """Capture actual SDK/MCP tool lifecycle events in execution order."""

    def __init__(self) -> None:
        self._pending: dict[str, _PendingToolCall] = {}
        self.tool_calls: list[ToolCallTrace] = []
        self.evidence_summaries: dict[str, dict[str, Any]] = {}

    @property
    def has_incomplete_calls(self) -> bool:
        return bool(self._pending)

    async def on_tool_start(self, context, _agent, tool) -> None:
        tool_name = str(getattr(tool, "name", "unknown"))
        call_id = str(
            getattr(context, "tool_call_id", "")
            or f"{tool_name}:{len(self.tool_calls) + len(self._pending) + 1}"
        )
        arguments = getattr(context, "tool_arguments", "{}")
        self._pending[call_id] = _PendingToolCall(
            sequence=len(self.tool_calls) + len(self._pending) + 1,
            tool_name=tool_name,
            safe_input=_safe_tool_input(tool_name, arguments),
            started_at=datetime.now(timezone.utc),
            started_clock=perf_counter(),
        )

    async def on_tool_end(self, context, _agent, tool, result) -> None:
        tool_name = str(getattr(tool, "name", "unknown"))
        call_id = str(getattr(context, "tool_call_id", "") or "")
        pending = self._pending.pop(call_id, None)
        if pending is None:
            pending = _PendingToolCall(
                sequence=len(self.tool_calls) + 1,
                tool_name=tool_name,
                safe_input=_safe_tool_input(
                    tool_name, getattr(context, "tool_arguments", "{}")
                ),
                started_at=datetime.now(timezone.utc),
                started_clock=perf_counter(),
            )
        result_bytes, payload = _tool_result_payload(result)
        status = str(payload.get("status", "error"))
        evidence_id_value = payload.get("evidence_id")
        evidence_id = (
            evidence_id_value if isinstance(evidence_id_value, str) else None
        )
        if status not in _SUCCESSFUL_TOOL_STATUSES:
            evidence_id = None
        elif evidence_id is not None:
            self.evidence_summaries[evidence_id] = payload
        self.tool_calls.append(
            ToolCallTrace(
                sequence=pending.sequence,
                tool_name=pending.tool_name,
                safe_input=pending.safe_input,
                started_at=utc_timestamp(pending.started_at),
                status=status,
                latency_ms=max(0.0, (perf_counter() - pending.started_clock) * 1000),
                result_size_bytes=len(result_bytes),
                evidence_id=evidence_id,
            )
        )
        self.tool_calls.sort(key=lambda call: call.sequence)

    def finish_incomplete_calls(self) -> None:
        for pending in sorted(self._pending.values(), key=lambda item: item.sequence):
            self.tool_calls.append(
                ToolCallTrace(
                    sequence=pending.sequence,
                    tool_name=pending.tool_name,
                    safe_input=pending.safe_input,
                    started_at=utc_timestamp(pending.started_at),
                    status="error",
                    latency_ms=max(
                        0.0, (perf_counter() - pending.started_clock) * 1000
                    ),
                    result_size_bytes=0,
                    evidence_id=None,
                )
            )
        self._pending.clear()
        self.tool_calls.sort(key=lambda call: call.sequence)


class AgentsSDKExecutor:
    """Production OpenAI Agents SDK execution with one local stdio MCP child."""

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def execute(self, request: ModelRunRequest) -> SDKExecution:
        recorder = _ToolRecorder()
        server = MCPServerStdio(
            name="trailsight-mcp",
            params={
                "command": sys.executable,
                "args": ["-m", "trailsight_mcp.server"],
                "cwd": str(_PROJECT_ROOT),
                "env": request.mcp_environment,
            },
            cache_tools_list=True,
            use_structured_content=True,
            max_retry_attempts=0,
        )
        connected = False
        try:
            async with server:
                connected = True
                try:
                    listed_tools = await server.list_tools()
                    if {tool.name for tool in listed_tools} != set(_TOOL_INPUT_FIELDS):
                        raise MCPInfrastructureError(
                            "The local Trailsight MCP tool set did not match the contract"
                        )
                except MCPInfrastructureError:
                    raise
                except Exception as exc:
                    raise MCPInfrastructureError(
                        "The local Trailsight MCP tool list could not be loaded"
                    ) from exc

                async with AsyncOpenAI(
                    api_key=self._api_key,
                    max_retries=0,
                ) as openai_client:
                    agent = Agent(
                        name="Trailsight investigation assistant",
                        instructions=request.system_prompt,
                        model=request.model_identifier,
                        mcp_servers=[server],
                        output_type=InvestigationModelOutput,
                    )
                    try:
                        result = await Runner.run(
                            agent,
                            request.task_input,
                            hooks=recorder,
                            max_turns=8,
                            run_config=RunConfig(
                                model_provider=OpenAIProvider(
                                    openai_client=openai_client
                                ),
                                tracing_disabled=True,
                                workflow_name="Trailsight investigation",
                            ),
                        )
                    except ModelBehaviorError as exc:
                        raise StructuredOutputError(
                            "The model response did not satisfy the structured contract"
                        ) from exc
        except StructuredOutputError as exc:
            recorder.finish_incomplete_calls()
            exc.tool_calls = list(recorder.tool_calls)
            exc.evidence_summaries = dict(recorder.evidence_summaries)
            raise
        except MCPInfrastructureError as exc:
            recorder.finish_incomplete_calls()
            exc.tool_calls = list(recorder.tool_calls)
            exc.evidence_summaries = dict(recorder.evidence_summaries)
            raise
        except Exception as exc:
            had_incomplete_calls = recorder.has_incomplete_calls
            recorder.finish_incomplete_calls()
            if not connected or had_incomplete_calls:
                mapped = MCPInfrastructureError(
                    "The local Trailsight MCP connection failed"
                )
            else:
                mapped = ModelExecutionError(
                    "The configured model request failed"
                )
            mapped.tool_calls = list(recorder.tool_calls)
            mapped.evidence_summaries = dict(recorder.evidence_summaries)
            raise mapped from exc

        final_output = result.final_output
        try:
            if not isinstance(final_output, InvestigationModelOutput):
                final_output = InvestigationModelOutput.model_validate(final_output)
            validated_output = validate_output_for_mode(
                final_output, mode=request.mode
            )
        except Exception as exc:
            mapped = StructuredOutputError(
                "The model response did not satisfy run-mode output constraints"
            )
            mapped.tool_calls = list(recorder.tool_calls)
            mapped.evidence_summaries = dict(recorder.evidence_summaries)
            mapped.token_usage = _token_usage_from_result(result)
            raise mapped from exc
        token_usage = _token_usage_from_result(result)
        return SDKExecution(
            output=validated_output,
            tool_calls=recorder.tool_calls,
            evidence_summaries=recorder.evidence_summaries,
            token_usage=token_usage,
        )


class InvestigationRunner:
    """Run one bounded initial investigation or one stateless follow-up."""

    def __init__(
        self,
        config: AIConfig,
        *,
        executor: ModelExecutor | None = None,
    ) -> None:
        self.config = config
        self._executor = executor or AgentsSDKExecutor(api_key=config.api_key)

    @classmethod
    def from_environment(cls) -> InvestigationRunner:
        return cls(load_ai_config())

    async def run_initial(
        self,
        case_ref: str,
        service: InvestigationService,
        *,
        selected_evidence: InternalEvidence | None = None,
    ) -> InvestigationRun:
        return await self._run(
            mode="initial",
            case_ref=case_ref,
            question=None,
            parent_investigation_id=None,
            service=service,
            selected_evidence=selected_evidence,
        )

    async def run_follow_up(
        self,
        case_ref: str,
        question: str,
        parent_investigation_id: str | None,
        service: InvestigationService,
        *,
        selected_evidence: InternalEvidence | None = None,
    ) -> InvestigationRun:
        normalized_question = question.strip()
        if not 1 <= len(normalized_question) <= 500:
            raise ValueError("Follow-up question must contain 1 to 500 characters")
        return await self._run(
            mode="follow_up",
            case_ref=case_ref,
            question=normalized_question,
            parent_investigation_id=parent_investigation_id,
            service=service,
            selected_evidence=selected_evidence,
        )

    async def _run(
        self,
        *,
        mode: Literal["initial", "follow_up"],
        case_ref: str,
        question: str | None,
        parent_investigation_id: str | None,
        service: InvestigationService,
        selected_evidence: InternalEvidence | None,
    ) -> InvestigationRun:
        investigation_id = f"inv_{uuid4().hex}"
        started_at = datetime.now(timezone.utc)
        started_clock = perf_counter()
        selected = selected_evidence or service.get_selected_transaction_evidence(
            case_ref
        )
        summary = selected_transaction_summary(selected)
        request = self._model_request(mode=mode, summary=summary, question=question)
        structured_output: InvestigationModelOutput | None = None
        tool_calls: list[ToolCallTrace] = []
        token_usage = TokenUsage()
        evidence_summaries: dict[str, dict[str, Any]] = {
            summary.evidence_id: summary.model_dump(mode="json")
        }
        validation_status: Literal["passed", "failed", "not_run"] = "not_run"
        failure_code: str | None = None
        estimated_cost: float | None = None

        try:
            execution = await self._executor.execute(request)
            structured_output = execution.output
            tool_calls = execution.tool_calls
            token_usage = execution.token_usage
            evidence_summaries.update(execution.evidence_summaries)
            available_evidence_ids = {summary.evidence_id}
            available_evidence_ids.update(
                call.evidence_id
                for call in tool_calls
                if call.evidence_id is not None
                and call.status in _SUCCESSFUL_TOOL_STATUSES
            )
            validated = validate_and_render(
                output=structured_output,
                case_ref=case_ref,
                available_evidence_ids=available_evidence_ids,
                service=service,
            )
            validation_status = "passed"
            run_status = _application_status(structured_output, tool_calls)
            if run_status is InvestigationRunStatus.TOOL_ERROR:
                failure_code = InvestigationRunStatus.TOOL_ERROR.value
                response = _failed_response(
                    investigation_id=investigation_id,
                    case_ref=case_ref,
                    parent_investigation_id=parent_investigation_id,
                    status=InvestigationRunStatus.TOOL_ERROR,
                )
            else:
                response = InvestigationResponse(
                    investigation_id=investigation_id,
                    case_ref=case_ref,
                    parent_investigation_id=parent_investigation_id,
                    run_status=run_status,
                    findings=validated.findings,
                    limits=structured_output.limits,
                    evidence=validated.evidence,
                )
        except MCPInfrastructureError as exc:
            tool_calls = list(exc.tool_calls)
            evidence_summaries.update(exc.evidence_summaries)
            token_usage = exc.token_usage
            failure_code = InvestigationRunStatus.TOOL_ERROR.value
            response = _failed_response(
                investigation_id=investigation_id,
                case_ref=case_ref,
                parent_investigation_id=parent_investigation_id,
                status=InvestigationRunStatus.TOOL_ERROR,
            )
        except StructuredOutputError as exc:
            tool_calls = list(exc.tool_calls)
            evidence_summaries.update(exc.evidence_summaries)
            token_usage = exc.token_usage
            failure_code = InvestigationRunStatus.STRUCTURED_OUTPUT_INVALID.value
            response = _failed_response(
                investigation_id=investigation_id,
                case_ref=case_ref,
                parent_investigation_id=parent_investigation_id,
                status=InvestigationRunStatus.STRUCTURED_OUTPUT_INVALID,
            )
        except EvidenceValidationError:
            validation_status = "failed"
            failure_code = InvestigationRunStatus.EVIDENCE_VALIDATION_FAILED.value
            response = _failed_response(
                investigation_id=investigation_id,
                case_ref=case_ref,
                parent_investigation_id=parent_investigation_id,
                status=InvestigationRunStatus.EVIDENCE_VALIDATION_FAILED,
                limits=[
                    "Generated findings could not be verified against Trailsight evidence."
                ],
            )
        except ModelExecutionError as exc:
            tool_calls = list(exc.tool_calls)
            evidence_summaries.update(exc.evidence_summaries)
            token_usage = exc.token_usage
            failure_code = InvestigationRunStatus.MODEL_ERROR.value
            response = _failed_response(
                investigation_id=investigation_id,
                case_ref=case_ref,
                parent_investigation_id=parent_investigation_id,
                status=InvestigationRunStatus.MODEL_ERROR,
            )
        except Exception:
            failure_code = InvestigationRunStatus.MODEL_ERROR.value
            response = _failed_response(
                investigation_id=investigation_id,
                case_ref=case_ref,
                parent_investigation_id=parent_investigation_id,
                status=InvestigationRunStatus.MODEL_ERROR,
            )

        estimated_cost = estimate_cost_usd(
            token_usage,
            input_usd_per_million=self.config.input_usd_per_million,
            output_usd_per_million=self.config.output_usd_per_million,
        )
        finished_at = datetime.now(timezone.utc)
        referenced_ids = _referenced_ids(structured_output)
        trace = InvestigationTrace(
            investigation_id=investigation_id,
            parent_investigation_id=parent_investigation_id,
            case_ref=case_ref,
            prompt_version=self.config.prompt_version,
            model_identifier=self.config.model_identifier,
            started_at=utc_timestamp(started_at),
            finished_at=utc_timestamp(finished_at),
            latency_ms=max(0.0, (perf_counter() - started_clock) * 1000),
            run_status=response.run_status.value,
            tool_calls=tool_calls,
            token_usage=token_usage,
            estimated_cost_usd=estimated_cost,
            referenced_evidence_ids=referenced_ids,
            validation_status=validation_status,
            failure_code=failure_code,
        )
        append_trace_safely(self.config.trace_path, trace)
        return InvestigationRun(
            response=response,
            structured_output=structured_output,
            tool_calls=tool_calls,
            evidence_summaries=evidence_summaries,
            token_usage=token_usage,
            estimated_cost_usd=estimated_cost,
            validation_status=validation_status,
            failure_code=failure_code,
        )

    def _model_request(
        self,
        *,
        mode: Literal["initial", "follow_up"],
        summary: SelectedTransactionModelSummary,
        question: str | None,
    ) -> ModelRunRequest:
        if mode == "initial":
            task = (
                "Identify the 2–4 most relevant historical context findings for this "
                "selected transaction using only the available Trailsight evidence tools. "
                "Do not make a fraud, laundering, or suspiciousness judgment."
            )
        else:
            task = (
                "Answer the current follow-up about this selected transaction using only "
                "the smallest relevant set of Trailsight evidence tools."
            )
        payload: dict[str, Any] = {
            "selected_transaction": summary.model_dump(mode="json"),
            "task": task,
        }
        if question is not None:
            payload["current_question"] = question
        database_path = os.environ.get("TRAILSIGHT_DB_PATH", "")
        mcp_environment = {
            "TRAILSIGHT_DB_PATH": database_path,
            "PYTHONPATH": str(_PROJECT_ROOT / "src"),
        }
        return ModelRunRequest(
            mode=mode,
            model_identifier=self.config.model_identifier,
            system_prompt=load_prompt(self.config.prompt_version),
            task_input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            mcp_environment=mcp_environment,
        )


def _safe_tool_input(tool_name: str, arguments: object) -> dict[str, Any]:
    try:
        if isinstance(arguments, str):
            parsed = json.loads(arguments) if arguments else {}
        elif isinstance(arguments, dict):
            parsed = arguments
        else:
            parsed = {}
    except (TypeError, ValueError):
        parsed = {}
    if not isinstance(parsed, dict):
        return {}
    approved_fields = _TOOL_INPUT_FIELDS.get(tool_name, ())
    return {
        field_name: parsed[field_name]
        for field_name in approved_fields
        if field_name in parsed and isinstance(parsed[field_name], str)
    }


def _tool_result_payload(result: object) -> tuple[bytes, dict[str, Any]]:
    if isinstance(result, str):
        text = result
    elif isinstance(result, dict) and isinstance(result.get("text"), str):
        text = result["text"]
    elif isinstance(result, BaseModel):
        dumped = result.model_dump(mode="json")
        text_value = dumped.get("text") if isinstance(dumped, dict) else None
        text = text_value if isinstance(text_value, str) else json.dumps(dumped)
    else:
        text = json.dumps(result, default=str, ensure_ascii=False)
    encoded = text.encode("utf-8")
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        payload = {}
    return encoded, payload if isinstance(payload, dict) else {}


def _application_status(
    output: InvestigationModelOutput,
    tool_calls: list[ToolCallTrace],
) -> InvestigationRunStatus:
    failed_calls = [
        call for call in tool_calls if call.status not in _SUCCESSFUL_TOOL_STATUSES
    ]
    successful_calls = [
        call for call in tool_calls if call.status in _SUCCESSFUL_TOOL_STATUSES
    ]
    if failed_calls and not successful_calls:
        return InvestigationRunStatus.TOOL_ERROR
    if failed_calls and output.findings:
        return InvestigationRunStatus.PARTIAL
    return InvestigationRunStatus(output.status)


def _failed_response(
    *,
    investigation_id: str,
    case_ref: str,
    parent_investigation_id: str | None,
    status: InvestigationRunStatus,
    limits: list[str] | None = None,
) -> InvestigationResponse:
    return InvestigationResponse(
        investigation_id=investigation_id,
        case_ref=case_ref,
        parent_investigation_id=parent_investigation_id,
        run_status=status,
        findings=[],
        limits=limits or [],
        evidence=[],
    )


def _referenced_ids(
    output: InvestigationModelOutput | None,
) -> list[str]:
    if output is None:
        return []
    ordered: list[str] = []
    for finding in output.findings:
        for evidence_id in finding.evidence_ids:
            if evidence_id not in ordered:
                ordered.append(evidence_id)
    return ordered


def _token_usage_from_result(result: object) -> TokenUsage:
    context_wrapper = getattr(result, "context_wrapper", None)
    usage = getattr(context_wrapper, "usage", None)
    if usage is None:
        return TokenUsage()
    return TokenUsage(
        requests=getattr(usage, "requests", 0),
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        total_tokens=getattr(usage, "total_tokens", 0),
    )
