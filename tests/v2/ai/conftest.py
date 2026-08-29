from __future__ import annotations

from pathlib import Path
import importlib.util
import sys

import pytest


def _domain_fixture_module():
    path = Path(__file__).resolve().parents[1] / "domain" / "conftest.py"
    spec = importlib.util.spec_from_file_location("trailsight_domain_test_fixtures_ai", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load WP03 domain test fixture helpers")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ai_service(tmp_path: Path):
    fx = _domain_fixture_module()
    transactions = [
        fx.TxSpec(fx.txref(11), __import__("datetime").datetime(2025, 1, 1, 9), "B3", "X", "B1", "ROOT"),
        fx.TxSpec(fx.txref(12), __import__("datetime").datetime(2025, 1, 1, 10), "B1", "ROOT", "B4", "Y"),
        fx.selected_tx(),
        fx.TxSpec(fx.txref(10000), __import__("datetime").datetime(2025, 1, 2, 13), "B1", "ROOT", "B5", "Z"),
    ]
    path = fx.build_runtime_db(tmp_path / "ai.duckdb", transactions)
    service = fx.create_investigation_service_v2(path)
    yield service, fx.selected_tx(), transactions[-1]
    service.close()


class ReviewState:
    def get_alert_review_status(self, _alert_ref: str):
        return "NOT_REVIEWED"
