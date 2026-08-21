from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from ai_helpers import FakeService
from trailsight.api.app import _register_optional_ai_router
from trailsight.contracts import (
    ApplicationError,
    ErrorDetail,
    InvestigationResponse,
    InvestigationRunStatus,
)
from trailsight.errors import CaseNotFoundError
from trailsight_ai.http import router
from trailsight_ai.runner import InvestigationRun
from trailsight_ai.telemetry import TokenUsage


def result(
    *,
    case_ref: str,
    parent_id: str | None,
) -> InvestigationRun:
    return InvestigationRun(
        response=InvestigationResponse(
            investigation_id="inv_0123456789abcdef0123456789abcdef",
            case_ref=case_ref,
            parent_investigation_id=parent_id,
            run_status=InvestigationRunStatus.UNAVAILABLE,
            findings=[],
            limits=["Requested information is unavailable."],
            evidence=[],
        ),
        structured_output=None,
        tool_calls=[],
        evidence_summaries={},
        token_usage=TokenUsage(),
        estimated_cost_usd=None,
        validation_status="passed",
        failure_code=None,
    )


class FakeRunner:
    def __init__(self) -> None:
        self.initial_calls = []
        self.follow_up_calls = []

    async def run_initial(self, case_ref, service, *, selected_evidence):
        self.initial_calls.append((case_ref, service, selected_evidence))
        return result(case_ref=case_ref, parent_id=None)

    async def run_follow_up(
        self,
        case_ref,
        question,
        parent_id,
        service,
        *,
        selected_evidence,
    ):
        self.follow_up_calls.append(
            (case_ref, question, parent_id, service, selected_evidence)
        )
        return result(case_ref=case_ref, parent_id=parent_id)


def app_with(service, fake_runner: FakeRunner) -> FastAPI:
    app = FastAPI()
    app.state.investigation_service = service
    app.state.investigation_runner = fake_runner

    @app.exception_handler(CaseNotFoundError)
    async def missing(_request: Request, _exc: CaseNotFoundError) -> JSONResponse:
        error = ApplicationError(
            error=ErrorDetail(
                code="case_not_found",
                message="The requested case was not found.",
            )
        )
        return JSONResponse(status_code=404, content=error.model_dump(mode="json"))

    app.include_router(router)
    return app


def test_initial_and_follow_up_exact_http_contract() -> None:
    fake_service = FakeService()
    fake_runner = FakeRunner()
    with TestClient(app_with(fake_service, fake_runner)) as client:
        initial = client.post("/api/cases/demo-01/investigations")
        follow_up = client.post(
            "/api/cases/demo-01/follow-up",
            json={
                "question": "  Why was it made?  ",
                "parent_investigation_id": "inv_parent",
            },
        )

    assert initial.status_code == 200
    assert initial.json() == {
        "investigation_id": "inv_0123456789abcdef0123456789abcdef",
        "case_ref": "demo-01",
        "parent_investigation_id": None,
        "run_status": "unavailable",
        "findings": [],
        "limits": ["Requested information is unavailable."],
        "evidence": [],
    }
    assert follow_up.status_code == 200
    assert follow_up.json()["parent_investigation_id"] == "inv_parent"
    assert fake_runner.follow_up_calls[0][1] == "Why was it made?"


def test_initial_rejects_unapproved_request_controls() -> None:
    fake_service = FakeService()
    fake_runner = FakeRunner()
    with TestClient(app_with(fake_service, fake_runner)) as client:
        response = client.post(
            "/api/cases/demo-01/investigations",
            json={"limit": 100, "include_details": True},
        )

    assert response.status_code == 422
    assert fake_runner.initial_calls == []


def test_invalid_follow_up_uses_shared_400_envelope() -> None:
    fake_service = FakeService()
    fake_runner = FakeRunner()
    with TestClient(app_with(fake_service, fake_runner)) as client:
        empty = client.post(
            "/api/cases/demo-01/follow-up", json={"question": "   "}
        )
        too_long = client.post(
            "/api/cases/demo-01/follow-up", json={"question": "x" * 501}
        )

    for response in (empty, too_long):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_question"
    assert fake_runner.follow_up_calls == []


def test_missing_case_is_checked_before_model_call() -> None:
    fake_service = FakeService()
    fake_runner = FakeRunner()
    with TestClient(app_with(fake_service, fake_runner)) as client:
        response = client.post("/api/cases/not-present/investigations")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "case_not_found"
    assert fake_runner.initial_calls == []


def test_valid_case_without_ai_configuration_fails_in_200_envelope(
    monkeypatch,
) -> None:
    monkeypatch.delenv("TRAILSIGHT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = FastAPI()
    app.state.investigation_service = FakeService()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.post("/api/cases/demo-01/investigations")

    assert response.status_code == 200
    assert response.json()["run_status"] == "model_error"
    assert response.json()["findings"] == []


def test_wp02_lazy_registration_finds_exact_ai_routes() -> None:
    app = FastAPI()

    _register_optional_ai_router(app)

    paths = app.openapi()["paths"]
    assert "post" in paths["/api/cases/{case_ref}/investigations"]
    assert "post" in paths["/api/cases/{case_ref}/follow-up"]
