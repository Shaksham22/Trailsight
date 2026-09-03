import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from trailsight_v2.ai import http as ai_http
from trailsight_v2.ai.models import InvestigationResponseV2, InvestigationStatus
from trailsight_v2.ai.runner import InvestigationRunV2
from trailsight_v2.ai.telemetry import TokenUsageV2
from trailsight_v2.api.runtime_state import FollowUpAlreadyUsedError, RuntimeStateStore


class FakeRunner:
    def __init__(self) -> None:
        self.initial_calls = 0
        self.follow_up_calls = 0
        self.fail_initial = False
        self.fail_follow_up = False

    async def run_initial(self, *, investigation_id, seed, **_kwargs):
        self.initial_calls += 1
        if self.fail_initial:
            return _failed_run("MODEL_ERROR")
        return _success_run(investigation_id, seed)

    async def run_follow_up(self, *, investigation_id, seed, **_kwargs):
        self.follow_up_calls += 1
        if self.fail_follow_up:
            return _failed_run("TOOL_ERROR")
        return _success_run(investigation_id, seed)


def _success_run(investigation_id, seed) -> InvestigationRunV2:
    response = InvestigationResponseV2(
        investigation_id=investigation_id,
        run_status=InvestigationStatus.SUCCESS,
        subject_type=seed.context.subject_type,
        subject_ref=seed.context.subject_ref,
        context=seed.context,
        summary="A bounded analyst summary.",
        observations=(),
        patterns=(),
        limits=(),
    )
    return InvestigationRunV2(
        response=response,
        structured_output=None,
        mcp_calls=(),
        token_usage=TokenUsageV2(),
        estimated_cost_usd=None,
        validation_status="NOT_RUN",
        failure_code=None,
    )


def _failed_run(code: str) -> InvestigationRunV2:
    return InvestigationRunV2(
        response=None,
        structured_output=None,
        mcp_calls=(),
        token_usage=TokenUsageV2(),
        estimated_cost_usd=None,
        validation_status="NOT_RUN",
        failure_code=code,
    )


def _app(service, state) -> FastAPI:
    app = FastAPI()
    app.state.investigation_service = service
    app.state.runtime_state_store = state

    @app.exception_handler(FollowUpAlreadyUsedError)
    async def used(_request: Request, exc: FollowUpAlreadyUsedError):
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": exc.safe_message}},
        )

    app.include_router(ai_http.router)
    return app


def test_http_uses_app_state_and_persists_exactly_one_follow_up(ai_service, tmp_path, monkeypatch) -> None:
    service, selected, _ = ai_service
    state = RuntimeStateStore(tmp_path / "state.json")
    fake_runner = FakeRunner()
    monkeypatch.setattr(ai_http, "_runner_from_environment", lambda: fake_runner)
    client = TestClient(_app(service, state), raise_server_exceptions=False)

    created = client.post(
        "/api/v2/investigations",
        json={"subject_type": "TRANSACTION", "subject_ref": selected.ref},
    )
    assert created.status_code == 200
    investigation_id = created.json()["investigation_id"]
    session = state.get_investigation_session(investigation_id)
    assert session.follow_up_used is False

    first = client.post(
        f"/api/v2/investigations/{investigation_id}/follow-up",
        json={"question": "What evidence should I examine?"},
    )
    assert first.status_code == 200
    assert state.get_investigation_session(investigation_id).follow_up_used is True

    second = client.post(
        f"/api/v2/investigations/{investigation_id}/follow-up",
        json={"question": "One more question"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "FOLLOW_UP_ALREADY_USED"
    assert fake_runner.initial_calls == 1
    assert fake_runner.follow_up_calls == 1


def test_failed_initial_creates_no_orphan_and_failed_follow_up_remains_available(
    ai_service, tmp_path, monkeypatch
) -> None:
    service, selected, _ = ai_service
    state = RuntimeStateStore(tmp_path / "state.json")
    fake_runner = FakeRunner()
    monkeypatch.setattr(ai_http, "_runner_from_environment", lambda: fake_runner)
    client = TestClient(_app(service, state), raise_server_exceptions=False)

    fake_runner.fail_initial = True
    failed_initial = client.post(
        "/api/v2/investigations",
        json={"subject_type": "TRANSACTION", "subject_ref": selected.ref},
    )
    assert failed_initial.status_code == 503
    assert not json.loads(state.path.read_text())["investigations"]

    fake_runner.fail_initial = False
    created = client.post(
        "/api/v2/investigations",
        json={"subject_type": "TRANSACTION", "subject_ref": selected.ref},
    )
    investigation_id = created.json()["investigation_id"]
    fake_runner.fail_follow_up = True
    failed_follow_up = client.post(
        f"/api/v2/investigations/{investigation_id}/follow-up",
        json={"question": "What evidence should I examine?"},
    )
    assert failed_follow_up.status_code == 503
    assert state.get_investigation_session(investigation_id).follow_up_used is False

    fake_runner.fail_follow_up = False
    retry = client.post(
        f"/api/v2/investigations/{investigation_id}/follow-up",
        json={"question": "What evidence should I examine?"},
    )
    assert retry.status_code == 200
    assert state.get_investigation_session(investigation_id).follow_up_used is True


def test_http_module_does_not_construct_domain_or_runtime_state_services() -> None:
    source = __import__("inspect").getsource(ai_http)
    assert "create_investigation_service_v2" not in source
    assert "RuntimeStateStore(" not in source
    assert "runtime_state.json" not in source
