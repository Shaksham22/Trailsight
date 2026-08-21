from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from conftest import build_runtime_database, transaction
from trailsight.api import app as app_module
from trailsight.api.app import create_app, create_investigation_service
from trailsight.domain.service import InvestigationService
from trailsight.errors import ConfigurationError


def _app_for_database(monkeypatch, database_path: Path, static_path: Path) -> TestClient:
    monkeypatch.setenv("TRAILSIGHT_DB_PATH", str(database_path))
    monkeypatch.setenv("TRAILSIGHT_STATIC_DIR", str(static_path))
    return TestClient(create_app())


def test_service_factory_uses_runtime_configuration(monkeypatch, tmp_path: Path) -> None:
    database_path = build_runtime_database(tmp_path / "factory.duckdb")
    monkeypatch.setenv("TRAILSIGHT_DB_PATH", str(database_path))

    service = create_investigation_service()

    assert isinstance(service, InvestigationService)
    assert service.get_workspace("demo-01").case_ref == "demo-01"
    service._repository.close()


def test_create_app_stores_exact_factory_instance(
    monkeypatch, service_builder, tmp_path: Path
) -> None:
    service, _, _ = service_builder()
    monkeypatch.setattr(app_module, "create_investigation_service", lambda: service)
    monkeypatch.setenv("TRAILSIGHT_STATIC_DIR", str(tmp_path / "absent"))

    application = app_module.create_app()

    assert application.state.investigation_service is service


def test_create_app_fails_clearly_without_database_configuration(
    monkeypatch,
) -> None:
    monkeypatch.delenv("TRAILSIGHT_DB_PATH", raising=False)

    with pytest.raises(ConfigurationError, match="TRAILSIGHT_DB_PATH"):
        create_app()


def test_health_contract(monkeypatch, tmp_path: Path) -> None:
    database_path = build_runtime_database(tmp_path / "health.duckdb")
    with _app_for_database(
        monkeypatch, database_path, tmp_path / "missing-static"
    ) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_case_list_contract(monkeypatch, tmp_path: Path) -> None:
    database_path = build_runtime_database(tmp_path / "cases.duckdb")
    with _app_for_database(
        monkeypatch, database_path, tmp_path / "missing-static"
    ) as client:
        response = client.get("/api/cases")

    assert response.status_code == 200
    assert response.json() == {
        "cases": [{"case_ref": "demo-01", "display_name": "Demo 01"}]
    }


def test_workspace_http_contract_and_decimal_strings(monkeypatch, tmp_path: Path) -> None:
    history = transaction(1, datetime(2025, 1, 1), amount_paid="15.095")
    database_path = build_runtime_database(
        tmp_path / "workspace.duckdb", history=[history]
    )
    with _app_for_database(
        monkeypatch, database_path, tmp_path / "missing-static"
    ) as client:
        response = client.get("/api/cases/demo-01")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "case_ref",
        "display_name",
        "selected_transaction",
        "sender_history",
        "amount_history",
        "counterparty_history",
        "region_history",
        "historical_transactions",
    }
    assert set(payload["selected_transaction"]) == {
        "transaction_ref",
        "timestamp",
        "sender",
        "counterparty",
        "amount_paid",
        "payment_currency",
        "amount_received",
        "receiving_currency",
        "payment_format",
        "cross_currency",
        "currency_pair",
        "region_relationship",
    }
    assert payload["selected_transaction"]["amount_paid"] == "69.54"
    assert payload["selected_transaction"]["amount_received"] == "9.4"
    assert payload["historical_transactions"][0]["amount_paid"] == "15.095"
    assert "Is Laundering" not in response.text


def test_missing_case_uses_exact_error_envelope(monkeypatch, tmp_path: Path) -> None:
    database_path = build_runtime_database(tmp_path / "missing-case.duckdb")
    with _app_for_database(
        monkeypatch, database_path, tmp_path / "missing-static"
    ) as client:
        response = client.get("/api/cases/not-present")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "case_not_found",
            "message": "The requested case was not found.",
        }
    }


def test_domain_integrity_error_does_not_leak_details(monkeypatch, tmp_path: Path) -> None:
    equal_timestamp = transaction(1, datetime(2025, 2, 1, 12, 0, 0))
    database_path = build_runtime_database(
        tmp_path / "invalid-history.duckdb", history=[equal_timestamp]
    )
    with _app_for_database(
        monkeypatch, database_path, tmp_path / "missing-static"
    ) as client:
        response = client.get("/api/cases/demo-01")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "deterministic_error",
            "message": "The deterministic workspace could not be loaded.",
        }
    }
    assert "timestamp" not in response.text
    assert "SELECT" not in response.text


def test_static_serving_boundary_preserves_api_precedence(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = build_runtime_database(tmp_path / "static.duckdb")
    static_directory = tmp_path / "dist"
    static_directory.mkdir()
    (static_directory / "index.html").write_text(
        "<html><body>Trailsight static boundary</body></html>", encoding="utf-8"
    )

    with _app_for_database(monkeypatch, database_path, static_directory) as client:
        api_response = client.get("/api/health")
        static_response = client.get("/")

    assert api_response.status_code == 200
    assert api_response.json()["status"] == "ok"
    assert static_response.status_code == 200
    assert "Trailsight static boundary" in static_response.text


def test_missing_static_directory_does_not_block_api(monkeypatch, tmp_path: Path) -> None:
    database_path = build_runtime_database(tmp_path / "no-static.duckdb")
    with _app_for_database(
        monkeypatch, database_path, tmp_path / "does-not-exist"
    ) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
