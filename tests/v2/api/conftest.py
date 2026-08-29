from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ..domain.conftest import AlertSpec, S1, TxSpec, build_runtime_db, selected_tx, txref
from trailsight_v2.data.canonical import account_ref_for
from trailsight_v2.api.app import create_app


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    root = account_ref_for("B1", "ROOT")
    transactions = [
        TxSpec(
            ref=txref(1),
            timestamp=S1 - timedelta(hours=1),
            from_bank="B3",
            from_account="PRE",
            to_bank="B1",
            to_account="ROOT",
        ),
        selected_tx(),
        TxSpec(
            ref=txref(2),
            timestamp=S1 + timedelta(hours=2),
            from_bank="B1",
            from_account="ROOT",
            to_bank="B4",
            to_account="OTHER",
            payment_currency="CAD",
            receiving_currency="USD",
        ),
    ]
    alerts = [
        AlertSpec("alert_a", root),
        AlertSpec("alert_b", root),
    ]
    return build_runtime_db(tmp_path / "api.duckdb", transactions, alerts=alerts)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, api_db: Path, tmp_path: Path):
    state_path = tmp_path / "runtime_state.json"
    monkeypatch.setenv("TRAILSIGHT_V2_DB_PATH", str(api_db))
    monkeypatch.setenv("TRAILSIGHT_RUNTIME_STATE_PATH", str(state_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TRAILSIGHT_MODEL", raising=False)
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, app, state_path
