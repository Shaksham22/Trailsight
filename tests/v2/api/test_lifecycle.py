from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient


class FakeService:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_app_lifecycle_closes_single_service_and_exposes_state(monkeypatch, tmp_path: Path) -> None:
    app_module = importlib.import_module("trailsight_v2.api.app")
    fake = FakeService()
    monkeypatch.setattr(app_module, "create_investigation_service_v2", lambda _path: fake)
    monkeypatch.setenv("TRAILSIGHT_RUNTIME_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(app_module.importlib_util, "find_spec", lambda _name: None)
    app = app_module.create_app()
    assert app.state.investigation_service is fake
    assert app.state.runtime_state_store is not None
    with TestClient(app):
        assert fake.closed is False
    assert fake.closed is True
