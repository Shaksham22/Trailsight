"""One local stdio MCP server over the deterministic InvestigationService."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel

from trailsight.api.app import create_investigation_service
from trailsight.contracts import (
    AmountHistoryFacts,
    CounterpartyHistoryFacts,
    CurrencyDimension,
    CurrencyHistoryFacts,
    InternalEvidence,
    RegionHistoryFacts,
    SenderHistoryFacts,
)
from trailsight.domain.service import InvestigationService
from trailsight.errors import CaseNotFoundError, DomainInputError, TrailsightError
from trailsight_mcp.contracts import (
    MAX_SERIALIZED_RESULT_BYTES,
    AmountHistoryResult,
    CaseRefInput,
    CounterpartyHistoryResult,
    CurrencyHistoryInput,
    CurrencyHistoryResult,
    McpResult,
    RegionHistoryResult,
    SenderHistoryResult,
    serialize_result,
)


_ResultT = TypeVar(
    "_ResultT",
    SenderHistoryResult,
    AmountHistoryResult,
    CounterpartyHistoryResult,
    RegionHistoryResult,
    CurrencyHistoryResult,
)


@dataclass(frozen=True, slots=True)
class _ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    adapter_method: str


_TOOL_SPECS = (
    _ToolSpec(
        name="get_sender_history",
        description="Return the selected sender's prior outgoing transaction count.",
        input_model=CaseRefInput,
        output_model=SenderHistoryResult,
        adapter_method="get_sender_history",
    ),
    _ToolSpec(
        name="compare_amount_history",
        description=(
            "Compare the selected amount with the sender's earlier outgoing payments "
            "in the selected payment currency."
        ),
        input_model=CaseRefInput,
        output_model=AmountHistoryResult,
        adapter_method="compare_amount_history",
    ),
    _ToolSpec(
        name="get_counterparty_history",
        description=(
            "Return whether the selected sender previously sent to the selected "
            "Bank + Account counterparty."
        ),
        input_model=CaseRefInput,
        output_model=CounterpartyHistoryResult,
        adapter_method="get_counterparty_history",
    ),
    _ToolSpec(
        name="get_region_history",
        description=(
            "Return the selected Synthetic Region relationship and prior outgoing "
            "destination-region aggregate."
        ),
        input_model=CaseRefInput,
        output_model=RegionHistoryResult,
        adapter_method="get_region_history",
    ),
    _ToolSpec(
        name="get_currency_history",
        description=(
            "Return whether a currency appeared on the requested side of the "
            "selected sender's previous outgoing transactions."
        ),
        input_model=CurrencyHistoryInput,
        output_model=CurrencyHistoryResult,
        adapter_method="get_currency_history",
    ),
)


class InvestigationToolAdapter:
    """Project domain-owned evidence into the five bounded MCP results."""

    def __init__(self, service: InvestigationService) -> None:
        self._service = service

    def get_sender_history(self, case_ref: str) -> SenderHistoryResult:
        return self._execute(
            SenderHistoryResult,
            lambda: self._service.get_sender_history_evidence(case_ref),
            self._project_sender_history,
        )

    def compare_amount_history(self, case_ref: str) -> AmountHistoryResult:
        return self._execute(
            AmountHistoryResult,
            lambda: self._service.get_amount_history_evidence(case_ref),
            self._project_amount_history,
        )

    def get_counterparty_history(self, case_ref: str) -> CounterpartyHistoryResult:
        return self._execute(
            CounterpartyHistoryResult,
            lambda: self._service.get_counterparty_history_evidence(case_ref),
            self._project_counterparty_history,
        )

    def get_region_history(self, case_ref: str) -> RegionHistoryResult:
        return self._execute(
            RegionHistoryResult,
            lambda: self._service.get_region_history_evidence(case_ref),
            self._project_region_history,
        )

    def get_currency_history(
        self,
        case_ref: str,
        dimension: CurrencyDimension | str,
        currency: str,
    ) -> CurrencyHistoryResult:
        return self._execute(
            CurrencyHistoryResult,
            lambda: self._service.get_currency_history_evidence(
                case_ref,
                dimension,
                currency,
            ),
            self._project_currency_history,
        )

    def _execute(
        self,
        result_model: type[_ResultT],
        evidence_call: Callable[[], InternalEvidence],
        projector: Callable[[InternalEvidence], _ResultT],
    ) -> _ResultT:
        try:
            result = projector(evidence_call())
        except CaseNotFoundError:
            return result_model(status="not_found")
        except DomainInputError:
            return result_model(status="error", error_code="invalid_input")
        except TrailsightError:
            return result_model(status="error", error_code="domain_error")
        except Exception:
            return result_model(status="error", error_code="domain_error")
        return self._enforce_size(result)

    @staticmethod
    def _enforce_size(result: _ResultT) -> _ResultT:
        if len(serialize_result(result)) <= MAX_SERIALIZED_RESULT_BYTES:
            return result
        result_model = type(result)
        return cast(
            _ResultT,
            result_model(status="error", error_code="result_too_large"),
        )

    @staticmethod
    def _project_sender_history(evidence: InternalEvidence) -> SenderHistoryResult:
        facts = evidence.facts
        if not isinstance(facts, SenderHistoryFacts):
            raise TypeError("Unexpected sender-history evidence facts")
        return SenderHistoryResult(
            status="ok",
            evidence_id=evidence.evidence_id,
            prior_outgoing_count=facts.prior_outgoing_count,
        )

    @staticmethod
    def _project_amount_history(evidence: InternalEvidence) -> AmountHistoryResult:
        facts = evidence.facts
        if not isinstance(facts, AmountHistoryFacts):
            raise TypeError("Unexpected amount-history evidence facts")
        status = (
            "insufficient_history"
            if facts.history_quality.value == "insufficient"
            else "ok"
        )
        return AmountHistoryResult(
            status=status,
            evidence_id=evidence.evidence_id,
            payment_currency=facts.payment_currency,
            selected_amount=facts.selected_amount,
            sample_size=facts.sample_size,
            history_quality=facts.history_quality,
            historical_median=facts.historical_median,
            empirical_percentile=facts.empirical_percentile,
        )

    @staticmethod
    def _project_counterparty_history(
        evidence: InternalEvidence,
    ) -> CounterpartyHistoryResult:
        facts = evidence.facts
        if not isinstance(facts, CounterpartyHistoryFacts):
            raise TypeError("Unexpected counterparty-history evidence facts")
        return CounterpartyHistoryResult(
            status="ok",
            evidence_id=evidence.evidence_id,
            seen_before=facts.seen_before,
            previous_interaction_count=facts.previous_interaction_count,
            first_previous_timestamp=facts.first_previous_timestamp,
            most_recent_previous_timestamp=facts.most_recent_previous_timestamp,
        )

    @staticmethod
    def _project_region_history(evidence: InternalEvidence) -> RegionHistoryResult:
        facts = evidence.facts
        if not isinstance(facts, RegionHistoryFacts):
            raise TypeError("Unexpected region-history evidence facts")
        return RegionHistoryResult(
            status="ok",
            evidence_id=evidence.evidence_id,
            sender_region=facts.sender_region,
            receiver_region=facts.receiver_region,
            region_relationship=facts.region_relationship,
            receiver_region_seen_before=facts.receiver_region_seen_before,
            previous_receiver_region_count=facts.previous_receiver_region_count,
        )

    @staticmethod
    def _project_currency_history(evidence: InternalEvidence) -> CurrencyHistoryResult:
        facts = evidence.facts
        if not isinstance(facts, CurrencyHistoryFacts):
            raise TypeError("Unexpected currency-history evidence facts")
        return CurrencyHistoryResult(
            status="ok",
            evidence_id=evidence.evidence_id,
            dimension=facts.dimension,
            currency=facts.currency,
            seen_before=facts.seen_before,
            previous_count=facts.previous_count,
            first_previous_timestamp=facts.first_previous_timestamp,
            most_recent_previous_timestamp=facts.most_recent_previous_timestamp,
        )


def registered_tool_definitions() -> list[types.Tool]:
    """Build the frozen five tool definitions with closed input schemas."""

    return [
        types.Tool(
            name=spec.name,
            description=spec.description,
            inputSchema=spec.input_model.model_json_schema(),
            outputSchema=spec.output_model.model_json_schema(mode="serialization"),
        )
        for spec in _TOOL_SPECS
    ]


def create_mcp_server(service: InvestigationService) -> Server:
    """Register exactly the approved tools against one WP02 service instance."""

    server = Server("trailsight-mcp", version="0.1.0")
    adapter = InvestigationToolAdapter(service)
    specs_by_name = {spec.name: spec for spec in _TOOL_SPECS}

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return registered_tool_definitions()

    @server.call_tool()
    async def call_tool(
        name: str,
        arguments: dict[str, Any],
    ) -> tuple[list[types.TextContent], dict[str, Any]]:
        spec = specs_by_name.get(name)
        if spec is None:
            raise ValueError("Unknown Trailsight MCP tool")
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
    """Construct WP02's service once and run only the stdio MCP transport."""

    service = create_investigation_service()
    try:
        server = create_mcp_server(service)
        anyio.run(_run_stdio, server)
    finally:
        service._close()


if __name__ == "__main__":
    main()
