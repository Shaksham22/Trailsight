"""Deterministic FastAPI shell and cross-package construction boundary."""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib import import_module, util as importlib_util

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from trailsight.config import load_runtime_config, load_static_directory
from trailsight.contracts import (
    ApplicationError,
    CaseListResponse,
    ErrorDetail,
    WorkspaceResponse,
)
from trailsight.data.runtime_repository import RuntimeRepository
from trailsight.domain.service import InvestigationService
from trailsight.errors import CaseNotFoundError, TrailsightError


def create_investigation_service() -> InvestigationService:
    """Construct the one approved deterministic service instance."""

    config = load_runtime_config()
    repository = RuntimeRepository(config.database_path)
    return InvestigationService(repository)


def create_app() -> FastAPI:
    """Create Trailsight's FastAPI application around the frozen service factory."""

    investigation_service = create_investigation_service()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        investigation_service._close()

    app = FastAPI(
        title="Trailsight",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.investigation_service = investigation_service

    @app.exception_handler(CaseNotFoundError)
    async def handle_case_not_found(
        _request: Request, _exc: CaseNotFoundError
    ) -> JSONResponse:
        payload = ApplicationError(
            error=ErrorDetail(
                code="case_not_found",
                message="The requested case was not found.",
            )
        )
        return JSONResponse(status_code=404, content=payload.model_dump(mode="json"))

    @app.exception_handler(TrailsightError)
    async def handle_deterministic_error(
        _request: Request, _exc: TrailsightError
    ) -> JSONResponse:
        payload = ApplicationError(
            error=ErrorDetail(
                code="deterministic_error",
                message="The deterministic workspace could not be loaded.",
            )
        )
        return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "database": "ok"}

    @app.get("/api/cases", response_model=CaseListResponse)
    def list_cases(request: Request) -> CaseListResponse:
        service: InvestigationService = request.app.state.investigation_service
        return CaseListResponse(cases=service._list_cases())

    @app.get("/api/cases/{case_ref}", response_model=WorkspaceResponse)
    def load_workspace(case_ref: str, request: Request) -> WorkspaceResponse:
        service: InvestigationService = request.app.state.investigation_service
        return service.get_workspace(case_ref)

    _register_optional_ai_router(app)
    static_directory = load_static_directory()
    if static_directory.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(static_directory), html=True),
            name="frontend",
        )
    return app


def _register_optional_ai_router(app: FastAPI) -> None:
    """Register WP04's router only when its package is actually present."""

    try:
        module_spec = importlib_util.find_spec("trailsight_ai.http")
    except ModuleNotFoundError as exc:
        if exc.name == "trailsight_ai":
            return
        raise
    if module_spec is None:
        return

    module = import_module("trailsight_ai.http")
    router = getattr(module, "router", None)
    if router is None:
        router_factory = getattr(module, "create_router", None)
        if not callable(router_factory):
            raise RuntimeError(
                "trailsight_ai.http must expose 'router' or 'create_router()'"
            )
        router = router_factory()
    if not isinstance(router, APIRouter):
        raise RuntimeError("trailsight_ai.http did not provide a FastAPI APIRouter")
    app.include_router(router)
