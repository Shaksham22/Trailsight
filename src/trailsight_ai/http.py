"""FastAPI router for the two frozen AI investigation endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from trailsight.contracts import (
    ApplicationError,
    ErrorDetail,
    FollowUpRequest,
    InvestigationResponse,
    InvestigationRunStatus,
)
from trailsight.domain.service import InvestigationService
from trailsight_ai.config import AIConfigurationError
from trailsight_ai.runner import InvestigationRunner


router = APIRouter()


class _EmptyInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post(
    "/api/cases/{case_ref}/investigations",
    response_model=InvestigationResponse,
)
async def initial_investigation(
    case_ref: str,
    request: Request,
    _body: _EmptyInvestigationRequest | None = Body(default=None),
) -> InvestigationResponse:
    service: InvestigationService = request.app.state.investigation_service
    selected_evidence = service.get_selected_transaction_evidence(case_ref)
    try:
        runner = _runner_for_request(request)
    except AIConfigurationError:
        return _configuration_failure(case_ref=case_ref, parent_id=None)
    run = await runner.run_initial(
        case_ref,
        service,
        selected_evidence=selected_evidence,
    )
    return run.response


@router.post(
    "/api/cases/{case_ref}/follow-up",
    response_model=InvestigationResponse,
    responses={400: {"model": ApplicationError}},
)
async def follow_up(
    case_ref: str,
    request: Request,
) -> InvestigationResponse | JSONResponse:
    follow_up_request = await _parse_follow_up(request)
    if isinstance(follow_up_request, JSONResponse):
        return follow_up_request

    service: InvestigationService = request.app.state.investigation_service
    selected_evidence = service.get_selected_transaction_evidence(case_ref)
    try:
        runner = _runner_for_request(request)
    except AIConfigurationError:
        return _configuration_failure(
            case_ref=case_ref,
            parent_id=follow_up_request.parent_investigation_id,
        )
    run = await runner.run_follow_up(
        case_ref,
        follow_up_request.question,
        follow_up_request.parent_investigation_id,
        service,
        selected_evidence=selected_evidence,
    )
    return run.response


def create_router() -> APIRouter:
    """Expose the narrow WP02 lazy-registration factory boundary."""

    return router


def _runner_for_request(request: Request) -> InvestigationRunner:
    injected = getattr(request.app.state, "investigation_runner", None)
    if injected is not None:
        return injected
    return InvestigationRunner.from_environment()


async def _parse_follow_up(request: Request) -> FollowUpRequest | JSONResponse:
    try:
        payload = await request.json()
        parsed = FollowUpRequest.model_validate(payload)
    except (ValidationError, ValueError, TypeError):
        error = ApplicationError(
            error=ErrorDetail(
                code="invalid_question",
                message="Question must contain 1 to 500 characters after trimming.",
            )
        )
        return JSONResponse(
            status_code=400,
            content=error.model_dump(mode="json"),
        )
    return parsed


def _configuration_failure(
    *,
    case_ref: str,
    parent_id: str | None,
) -> InvestigationResponse:
    return InvestigationResponse(
        investigation_id=f"inv_{uuid4().hex}",
        case_ref=case_ref,
        parent_investigation_id=parent_id,
        run_status=InvestigationRunStatus.MODEL_ERROR,
        findings=[],
        limits=[],
        evidence=[],
    )
