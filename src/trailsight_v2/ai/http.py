"""WP04B-owned FastAPI routes composed through WP04A app.state services."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from trailsight_v2.domain.errors import InvalidContextError
from trailsight_v2.domain.models import ContextIdentityV2, SubjectType

from .config import AIConfigurationError
from .context import resolve_seed_context
from .models import (
    CreateInvestigationRequestV2,
    FollowUpRequestV2,
    InvestigationResponseV2,
)
from .runner import InvestigationRunnerV2


router = APIRouter(prefix="/api/v2", tags=["ai-investigation-v2"])


def create_router() -> APIRouter:
    """Frozen WP04A dynamic-registration export."""
    return router


@router.post("/investigations", response_model=InvestigationResponseV2)
async def create_investigation(
    payload: CreateInvestigationRequestV2,
    request: Request,
):
    service, state = _app_services(request)
    seed = resolve_seed_context(
        service,
        state,
        subject_type=payload.subject_type,
        subject_ref=payload.subject_ref,
        origin_alert_ref=payload.origin_alert_ref,
        origin_transaction_ref=payload.origin_transaction_ref,
    )
    investigation_id = _new_investigation_id()
    state.create_investigation_session(
        investigation_id,
        subject_type=payload.subject_type,
        subject_ref=payload.subject_ref,
        context_identity=seed.context.context_identity,
        origin_alert_ref=payload.origin_alert_ref,
        origin_transaction_ref=payload.origin_transaction_ref,
    )
    try:
        runner = _runner_from_environment()
    except AIConfigurationError:
        return _ai_error("AI_UNAVAILABLE", "AI investigation is not configured", 503)
    result = await runner.run_initial(
        investigation_id=investigation_id,
        seed=seed,
        service=service,
        runtime_state_path=_runtime_state_path(state),
        origin_alert_ref=payload.origin_alert_ref,
        origin_transaction_ref=payload.origin_transaction_ref,
    )
    if result.response is None:
        return _run_error(result.failure_code)
    return result.response


@router.post(
    "/investigations/{investigation_id}/follow-up",
    response_model=InvestigationResponseV2,
)
async def create_follow_up(
    investigation_id: str,
    payload: FollowUpRequestV2,
    request: Request,
):
    service, state = _app_services(request)
    session = state.get_investigation_session(investigation_id)
    seed = resolve_seed_context(
        service,
        state,
        subject_type=SubjectType(session.subject_type),
        subject_ref=session.subject_ref,
        origin_alert_ref=session.origin_alert_ref,
        origin_transaction_ref=session.origin_transaction_ref,
    )
    _require_persisted_context(seed.context.context_identity, session.context_identity)
    # This is deliberately before the model run. The accepted follow-up is consumed
    # atomically and restart-safely even if the downstream provider later fails.
    state.consume_follow_up(investigation_id)
    follow_up_run_id = _new_investigation_id()
    try:
        runner = _runner_from_environment()
    except AIConfigurationError:
        return _ai_error("AI_UNAVAILABLE", "AI investigation is not configured", 503)
    result = await runner.run_follow_up(
        investigation_id=follow_up_run_id,
        parent_investigation_id=investigation_id,
        question=payload.question,
        seed=seed,
        service=service,
        runtime_state_path=_runtime_state_path(state),
        origin_alert_ref=session.origin_alert_ref,
        origin_transaction_ref=session.origin_transaction_ref,
    )
    if result.response is None:
        return _run_error(result.failure_code)
    return result.response


def _app_services(request: Request) -> tuple[Any, Any]:
    service = getattr(request.app.state, "investigation_service", None)
    state = getattr(request.app.state, "runtime_state_store", None)
    if service is None or state is None:
        raise RuntimeError("WP04A app.state integration services are missing")
    return service, state


def _runner_from_environment() -> InvestigationRunnerV2:
    """Small patch point for deterministic HTTP tests; production uses real SDK config."""
    return InvestigationRunnerV2.from_environment()


def _runtime_state_path(state: Any) -> Path:
    value = getattr(state, "path", None)
    if value is None:
        raise RuntimeError("WP04A runtime_state_store.path is required for MCP composition")
    return Path(value)


def _require_persisted_context(actual: ContextIdentityV2, persisted: Any) -> None:
    values = (
        (actual.context_kind, getattr(persisted, "kind", None)),
        (actual.context_ref, getattr(persisted, "ref", None)),
        (actual.context_time, getattr(persisted, "time", None)),
        (actual.snapshot_id, getattr(persisted, "snapshot_id", None)),
    )
    for left, right in values:
        left_value = getattr(left, "value", left)
        right_value = getattr(right, "value", right)
        if left_value != right_value:
            raise InvalidContextError("Persisted investigation context no longer matches")


def _new_investigation_id() -> str:
    return f"inv_{uuid4().hex}"


def _run_error(failure_code: str | None) -> JSONResponse:
    code = failure_code or "AI_UNAVAILABLE"
    messages = {
        "EVIDENCE_VALIDATION_FAILED": "Generated findings failed Evidence V2 validation",
        "STRUCTURED_OUTPUT_INVALID": "The model response did not satisfy the investigation contract",
        "TOOL_ERROR": "The bounded investigation tools were unavailable",
        "MODEL_TIMEOUT": "The AI investigation timed out",
        "MODEL_ERROR": "The AI model request was unavailable",
    }
    return _ai_error(code, messages.get(code, "The AI investigation was unavailable"), 503)


def _ai_error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": None}},
    )
