from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from trailsight_v2.api.models import ReviewStatus
from trailsight_v2.data.canonical import account_ref_for
from ..domain.conftest import selected_tx


def test_health_and_app_state_contract(api_client) -> None:
    client, app, _ = api_client
    assert app.state.investigation_service is not None
    assert app.state.runtime_state_store is not None
    response = client.get("/api/v2/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "runtime_db_ready": True,
        "latest_snapshot_id": "snap_2",
        "latest_snapshot_cutoff": "2025-01-03T00:00:00",
        "ai_configured": False,
        "product_version": "v2",
    }


def test_alert_list_status_patch_filter_restart_and_immutable_detector_state(
    api_client, api_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, state_path = api_client
    first = client.get("/api/v2/alerts", params={"limit": 1})
    assert first.status_code == 200
    body = first.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["review_status"] == "NOT_REVIEWED"
    assert body["has_more"] is True
    assert body["next_cursor"]

    assert client.patch(
        "/api/v2/alerts/alert_a/review-status", json={"review_status": "REVIEWED"}
    ).status_code == 409
    updated = client.patch(
        "/api/v2/alerts/alert_a/review-status", json={"review_status": "IN_REVIEW"}
    )
    assert updated.status_code == 200
    assert updated.json()["review_status"] == "IN_REVIEW"

    in_review = client.get("/api/v2/alerts", params={"review_status": "IN_REVIEW"})
    assert [item["alert_ref"] for item in in_review.json()["items"]] == ["alert_a"]
    not_reviewed = client.get("/api/v2/alerts", params={"review_status": "NOT_REVIEWED"})
    assert [item["alert_ref"] for item in not_reviewed.json()["items"]] == ["alert_b"]

    con = duckdb.connect(str(api_db), read_only=True)
    try:
        assert con.execute(
            "SELECT created_state FROM network_alerts WHERE alert_ref='alert_a'"
        ).fetchone()[0] == "NOT_REVIEWED"
    finally:
        con.close()

    # Re-open a fresh app against the retained state file.
    monkeypatch.setenv("TRAILSIGHT_V2_DB_PATH", str(api_db))
    monkeypatch.setenv("TRAILSIGHT_RUNTIME_STATE_PATH", str(state_path))
    from trailsight_v2.api.app import create_app

    app2 = create_app()
    with TestClient(app2) as client2:
        detail = client2.get("/api/v2/alerts/alert_a")
        assert detail.status_code == 200
        assert detail.json()["review_status"] == "IN_REVIEW"
        done = client2.patch(
            "/api/v2/alerts/alert_a/review-status", json={"review_status": "REVIEWED"}
        )
        assert done.status_code == 200


def test_alert_invalid_status_and_invalid_cursor_are_safe(api_client) -> None:
    client, _, _ = api_client
    invalid_status = client.patch(
        "/api/v2/alerts/alert_a/review-status", json={"review_status": "SUSPICIOUS"}
    )
    assert invalid_status.status_code == 422
    assert invalid_status.json()["error"]["code"] == "INVALID_INPUT"
    invalid_cursor = client.get("/api/v2/alerts", params={"cursor": "not-a-cursor"})
    assert invalid_cursor.status_code == 400
    assert invalid_cursor.json()["error"]["code"] == "INVALID_INPUT"


def test_alert_search_composes_with_review_filter_and_cursor(api_client) -> None:
    client, _, _ = api_client
    all_refs = [item["alert_ref"] for item in client.get("/api/v2/alerts").json()["items"]]
    blank_refs = [
        item["alert_ref"]
        for item in client.get("/api/v2/alerts", params={"q": "   "}).json()["items"]
    ]
    assert blank_refs == all_refs

    alert_match = client.get("/api/v2/alerts", params={"q": "alert_b"})
    assert [item["alert_ref"] for item in alert_match.json()["items"]] == ["alert_b"]
    root = alert_match.json()["items"][0]["account_ref"]
    for query in (root, "ROOT", "B1"):
        response = client.get("/api/v2/alerts", params={"q": query})
        assert [item["alert_ref"] for item in response.json()["items"]] == all_refs

    assert client.patch(
        "/api/v2/alerts/alert_a/review-status", json={"review_status": "IN_REVIEW"}
    ).status_code == 200
    composed = client.get(
        "/api/v2/alerts",
        params={"q": "alert_", "review_status": "NOT_REVIEWED"},
    )
    assert [item["alert_ref"] for item in composed.json()["items"]] == ["alert_b"]

    first = client.get("/api/v2/alerts", params={"q": "alert_", "limit": 1}).json()
    second = client.get(
        "/api/v2/alerts",
        params={"q": "alert_", "limit": 1, "cursor": first["next_cursor"]},
    ).json()
    assert [item["alert_ref"] for item in first["items"]] == ["alert_a"]
    assert [item["alert_ref"] for item in second["items"]] == ["alert_b"]


def test_alert_list_batches_runtime_status_read_once(api_client, monkeypatch) -> None:
    client, app, _ = api_client
    store = app.state.runtime_state_store
    reads = 0
    original = store._read_validated_unlocked

    def counted_read():
        nonlocal reads
        reads += 1
        return original()

    monkeypatch.setattr(store, "_read_validated_unlocked", counted_read)
    response = client.get("/api/v2/alerts", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert reads == 1


def test_transactions_list_filters_cursor_detail_and_bounds(api_client) -> None:
    client, _, _ = api_client
    all_rows = client.get("/api/v2/transactions", params={"limit": 2})
    assert all_rows.status_code == 200
    assert len(all_rows.json()["items"]) == 2
    assert all_rows.json()["next_cursor"]
    next_page = client.get(
        "/api/v2/transactions",
        params={"limit": 2, "cursor": all_rows.json()["next_cursor"]},
    )
    assert next_page.status_code == 200

    selected = selected_tx().ref
    q = client.get("/api/v2/transactions", params={"q": selected[:12]})
    assert any(item["transaction_ref"] == selected for item in q.json()["items"])
    detail = client.get(f"/api/v2/transactions/{selected}")
    assert detail.status_code == 200
    assert detail.json()["transaction_facts"]["transaction_ref"] == selected
    assert detail.json()["review_state"]["derivation_text"] == (
        "Persisted fixture derivation text; returned unchanged."
    )
    assert client.get("/api/v2/transactions", params={"limit": 101}).status_code == 422
    assert client.get(
        "/api/v2/transactions",
        params={"date_from": "2025-01-03T00:00:00", "date_to": "2025-01-02T00:00:00"},
    ).status_code == 400


def test_accounts_latest_alert_transaction_origins_and_network(api_client) -> None:
    client, _, _ = api_client
    root = account_ref_for("B1", "ROOT")
    selected = selected_tx().ref
    listing = client.get("/api/v2/accounts", params={"q": "ROOT"})
    assert listing.status_code == 200
    assert any(item["account_ref"] == root for item in listing.json()["items"])

    latest = client.get(f"/api/v2/accounts/{root}")
    assert latest.status_code == 200
    assert latest.json()["context"]["context_identity"]["context_kind"] == "SNAPSHOT"
    assert latest.json()["alert_history_total"] == 2
    assert latest.json()["alert_history_truncated"] is False
    assert all(item["review_status"] == "NOT_REVIEWED" for item in latest.json()["alert_history"])
    from_alert = client.get(
        f"/api/v2/accounts/{root}", params={"origin_alert_ref": "alert_a"}
    )
    assert from_alert.status_code == 200
    assert from_alert.json()["context"]["alert_ref"] == "alert_a"
    assert from_alert.json()["context"]["context_time"] == "2025-01-02T00:00:00"

    from_tx = client.get(
        f"/api/v2/accounts/{root}", params={"origin_transaction_ref": selected}
    )
    assert from_tx.status_code == 200
    assert from_tx.json()["context"]["selected_transaction_ref"] == selected

    dual = client.get(
        f"/api/v2/accounts/{root}",
        params={"origin_alert_ref": "alert_a", "origin_transaction_ref": selected},
    )
    assert dual.status_code == 400
    assert dual.json()["error"]["code"] == "INVALID_CONTEXT"

    txs = client.get(
        f"/api/v2/accounts/{root}/transactions",
        params={"origin_transaction_ref": selected, "direction": "BOTH"},
    )
    assert txs.status_code == 200
    assert all(item["timestamp"] < "2025-01-02T12:00:00" for item in txs.json()["items"])
    assert all(item["sender"]["account_id"] for item in txs.json()["items"])
    assert all(item["aml_review_priority"] in {"HIGH", "MEDIUM", "LOW", "UNSCORED"} for item in txs.json()["items"])
    network = client.get(
        f"/api/v2/accounts/{root}/network", params={"origin_transaction_ref": selected}
    )
    assert network.status_code == 200


def test_invalid_or_cross_context_account_origin_fails(api_client) -> None:
    client, _, _ = api_client
    other = account_ref_for("B4", "OTHER")
    response = client.get(
        f"/api/v2/accounts/{other}", params={"origin_alert_ref": "alert_a"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CONTEXT"


def test_evidence_valid_and_tampered_fail_closed(api_client) -> None:
    client, _, _ = api_client
    selected = selected_tx().ref
    detail = client.get(f"/api/v2/transactions/{selected}")
    evidence_id = detail.json()["evidence_ids"][0]
    valid = client.get(f"/api/v2/evidence/{evidence_id}")
    assert valid.status_code == 200
    assert valid.json()["evidence_id"] == evidence_id

    replacement = "A" if evidence_id[-1] != "A" else "B"
    tampered = evidence_id[:-1] + replacement
    invalid = client.get(f"/api/v2/evidence/{tampered}")
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_INPUT"
    serialized = json.dumps(invalid.json()).casefold()
    assert "select " not in serialized
    assert "/tmp/" not in serialized


def test_openapi_and_http_payloads_do_not_expose_hidden_truth(api_client) -> None:
    client, _, state_path = api_client
    client.get("/api/v2/alerts")
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    text = (openapi.text + state_path.read_text()).casefold()
    assert "is laundering" not in text
    assert "patterns.txt" not in text
    assert "laundering" not in openapi.text.casefold()


def test_unexpected_exception_is_redacted(api_client) -> None:
    client, app, _ = api_client

    class ExplodingService:
        def get_runtime_metadata(self):
            raise RuntimeError("SELECT secret FROM table at /tmp/private.duckdb")

    original = app.state.investigation_service
    app.state.investigation_service = ExplodingService()
    try:
        response = client.get("/api/v2/health")
    finally:
        app.state.investigation_service = original
    assert response.status_code == 500
    body = json.dumps(response.json()).casefold()
    assert "select secret" not in body
    assert "/tmp/private" not in body
    assert response.json()["error"]["code"] == "DATA_INTEGRITY_ERROR"


def test_ai_router_absent_does_not_break_deterministic_app(
    api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _ = api_client
    app_module = importlib.import_module("trailsight_v2.api.app")

    monkeypatch.setattr(
        app_module.importlib_util,
        "find_spec",
        lambda _name: None,
    )

    app = app_module.create_app()

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/v2/health").status_code == 200
        assert client.post("/api/v2/investigations").status_code == 404


def test_ai_router_present_seam_accepts_router(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module = importlib.import_module("trailsight_v2.api.app")
    ai_router = APIRouter()

    @ai_router.get("/api/v2/_ai-seam-test")
    def seam_test():
        return {"ok": True}

    monkeypatch.setattr(app_module.importlib_util, "find_spec", lambda _name: object())
    monkeypatch.setattr(app_module, "import_module", lambda _name: SimpleNamespace(router=ai_router))
    app = FastAPI()
    app_module._register_optional_ai_router(app)
    with TestClient(app) as client:
        assert client.get("/api/v2/_ai-seam-test").json() == {"ok": True}
