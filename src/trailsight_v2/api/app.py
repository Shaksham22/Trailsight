"""FastAPI application factory for the integrated Trailsight V2 runtime."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from importlib import import_module, util as importlib_util
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from trailsight_v2.domain.errors import DomainErrorCode, InvestigationDomainError
from trailsight_v2.domain.service import (
    InvestigationServiceV2,
    create_investigation_service_v2,
)

from .models import ErrorDetailV2, ErrorEnvelopeV2
from .routes import router
from .runtime_state import (
    FollowUpAlreadyUsedError,
    InvestigationStateNotFoundError,
    ReviewStateConflictError,
    RuntimeStateCorruptError,
    RuntimeStateError,
    RuntimeStateStore,
)

DEFAULT_RUNTIME_DB_PATH = Path("data/v2/runtime/trailsight_v2.duckdb")


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ErrorEnvelopeV2(error=ErrorDetailV2(code=code, message=message, request_id=None))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _domain_status(exc: InvestigationDomainError) -> int:
    if exc.code in {DomainErrorCode.INVALID_INPUT, DomainErrorCode.INVALID_CONTEXT}:
        return 400
    if exc.code is DomainErrorCode.NOT_FOUND:
        return 404
    if exc.code in {
        DomainErrorCode.INSUFFICIENT_HISTORY,
        DomainErrorCode.INSUFFICIENT_NETWORK_CONTEXT,
        DomainErrorCode.RESULT_TOO_LARGE,
    }:
        return 400
    return 500


def _database_path() -> Path:
    configured = os.getenv("TRAILSIGHT_V2_DB_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_RUNTIME_DB_PATH


def create_app() -> FastAPI:
    """Create the deterministic V2 application exactly once per lifecycle."""
    investigation_service = create_investigation_service_v2(_database_path())
    try:
        runtime_state_store = RuntimeStateStore()
    except Exception:
        investigation_service.close()
        raise

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            runtime_state_store.close()
            investigation_service.close()

    app = FastAPI(
        title="Trailsight V2",
        version="2",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.investigation_service = investigation_service
    app.state.runtime_state_store = runtime_state_store

    @app.exception_handler(InvestigationDomainError)
    async def handle_domain_error(
        _request: Request, exc: InvestigationDomainError
    ) -> JSONResponse:
        return _error_response(_domain_status(exc), exc.code.value, exc.safe_message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(422, "INVALID_INPUT", "The request schema is invalid")

    @app.exception_handler(ReviewStateConflictError)
    async def handle_review_conflict(
        _request: Request, exc: ReviewStateConflictError
    ) -> JSONResponse:
        return _error_response(409, exc.code, exc.safe_message)

    @app.exception_handler(FollowUpAlreadyUsedError)
    async def handle_followup_conflict(
        _request: Request, exc: FollowUpAlreadyUsedError
    ) -> JSONResponse:
        return _error_response(409, exc.code, exc.safe_message)

    @app.exception_handler(InvestigationStateNotFoundError)
    async def handle_investigation_not_found(
        _request: Request, exc: InvestigationStateNotFoundError
    ) -> JSONResponse:
        return _error_response(404, exc.code, exc.safe_message)

    @app.exception_handler(RuntimeStateCorruptError)
    async def handle_runtime_state_integrity(
        _request: Request, exc: RuntimeStateCorruptError
    ) -> JSONResponse:
        return _error_response(500, exc.code, exc.safe_message)

    @app.exception_handler(RuntimeStateError)
    async def handle_runtime_state_error(
        _request: Request, exc: RuntimeStateError
    ) -> JSONResponse:
        return _error_response(500, exc.code, exc.safe_message)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
        return _error_response(
            500,
            "DATA_INTEGRITY_ERROR",
            "The deterministic runtime could not complete the request safely",
        )

    app.include_router(router)
    _register_optional_ai_router(app)
    return app


def _register_optional_ai_router(app: FastAPI) -> None:
    """Register the optional AI route package when it is installed/present."""
    module_name = "trailsight_v2.ai.http"
    try:
        module_spec = importlib_util.find_spec(module_name)
    except ModuleNotFoundError as exc:
        if exc.name in {"trailsight_v2.ai", module_name}:
            return
        raise
    if module_spec is None:
        return

    module = import_module(module_name)
    ai_router = getattr(module, "router", None)
    if ai_router is None:
        router_factory = getattr(module, "create_router", None)
        if not callable(router_factory):
            raise RuntimeError(
                "trailsight_v2.ai.http must expose 'router' or 'create_router()'"
            )
        ai_router = router_factory()
    if not isinstance(ai_router, APIRouter):
        raise RuntimeError("trailsight_v2.ai.http did not provide a FastAPI APIRouter")
    app.include_router(ai_router)
