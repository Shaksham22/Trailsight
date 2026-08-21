from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trailsight.api.app import create_app
from trailsight.contracts import InvestigationResponse, InvestigationRunStatus
from trailsight_ai.runner import InvestigationRun
from trailsight_ai.telemetry import TokenUsage

from integration_helpers import build_runtime_database, build_static_directory


@pytest.fixture
def runtime_database(tmp_path: Path) -> Path:
    return build_runtime_database(tmp_path)


@pytest.fixture
def static_directory(tmp_path: Path) -> Path:
    return build_static_directory(tmp_path)


@pytest.fixture
def client(monkeypatch, runtime_database: Path, static_directory: Path):
    monkeypatch.setenv("TRAILSIGHT_DB_PATH", str(runtime_database))
    monkeypatch.setenv("TRAILSIGHT_STATIC_DIR", str(static_directory))
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_application_startup_health_and_static_frontend(client: TestClient) -> None:
    health = client.get("/api/health")
    root = client.get("/")
    asset = client.get("/assets/app.js")

    assert health.status_code == 200
    assert health.headers["content-type"].startswith("application/json")
    assert health.json() == {"status": "ok", "database": "ok"}
    assert root.status_code == 200
    assert "Trailsight integration build" in root.text
    assert asset.status_code == 200


def test_primary_demo_workspace_matches_approved_facts(client: TestClient) -> None:
    response = client.get("/api/cases/demo-01")

    assert response.status_code == 200
    workspace = response.json()
    selected = workspace["selected_transaction"]
    assert selected["timestamp"] == "2025-05-08T16:18:46.000000"
    assert selected["sender"]["account"] == "A016568"
    assert selected["counterparty"]["account"] == "A013644"
    assert selected["amount_paid"] == "69.54"
    assert selected["payment_currency"] == "CNY"
    assert selected["amount_received"] == "9.4"
    assert selected["receiving_currency"] == "USD"
    assert selected["payment_format"] == "Cash"
    assert selected["sender"]["synthetic_region"] == 8
    assert selected["counterparty"]["synthetic_region"] == 4
    assert selected["cross_currency"] is True
    assert selected["region_relationship"] == "cross_region"
    assert workspace["sender_history"]["prior_outgoing_count"] == 74
    assert workspace["amount_history"]["sample_size"] == 70
    assert workspace["amount_history"]["historical_median"] == "15.095"
    assert workspace["amount_history"]["empirical_percentile"] == pytest.approx(
        95.71, abs=0.01
    )
    assert workspace["counterparty_history"]["previous_interaction_count"] == 0
    assert workspace["region_history"]["receiver_region_seen_before"] is False


def test_runtime_responses_do_not_leak_hidden_label(client: TestClient) -> None:
    responses = [
        client.get("/api/cases"),
        client.get("/api/cases/demo-01"),
        client.get("/api/cases/does-not-exist"),
        client.post("/api/cases/demo-01/follow-up", json={"question": "   "}),
    ]

    assert [response.status_code for response in responses] == [200, 200, 404, 400]
    serialized = json.dumps([response.json() for response in responses])
    assert "Is Laundering" not in serialized


def _result(case_ref: str, parent_id: str | None) -> InvestigationRun:
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


class _FakeRunner:
    def __init__(self) -> None:
        self.initial_calls = 0
        self.follow_up_calls = 0

    async def run_initial(self, case_ref, service, *, selected_evidence):
        self.initial_calls += 1
        return _result(case_ref, None)

    async def run_follow_up(
        self, case_ref, question, parent_id, service, *, selected_evidence
    ):
        self.follow_up_calls += 1
        return _result(case_ref, parent_id)


def test_ai_routes_register_and_dispatch_without_live_model(
    monkeypatch, runtime_database: Path, static_directory: Path
) -> None:
    monkeypatch.setenv("TRAILSIGHT_DB_PATH", str(runtime_database))
    monkeypatch.setenv("TRAILSIGHT_STATIC_DIR", str(static_directory))
    app = create_app()
    runner = _FakeRunner()
    app.state.investigation_runner = runner

    openapi_paths = app.openapi()["paths"]
    assert "post" in openapi_paths["/api/cases/{case_ref}/investigations"]
    assert "post" in openapi_paths["/api/cases/{case_ref}/follow-up"]

    with TestClient(app) as test_client:
        initial = test_client.post("/api/cases/demo-01/investigations")
        follow_up = test_client.post(
            "/api/cases/demo-01/follow-up",
            json={
                "question": "Has this sender used this counterparty before?",
                "parent_investigation_id": "inv_parent",
            },
        )

    assert initial.status_code == 200
    assert initial.json()["run_status"] == "unavailable"
    assert follow_up.status_code == 200
    assert follow_up.json()["parent_investigation_id"] == "inv_parent"
    assert runner.initial_calls == 1
    assert runner.follow_up_calls == 1
