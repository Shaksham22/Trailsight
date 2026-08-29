from __future__ import annotations

from pathlib import Path
import importlib.util
import sys

import pytest


def _domain_fixture_module():
    path = Path(__file__).resolve().parents[1] / "domain" / "conftest.py"
    spec = importlib.util.spec_from_file_location("trailsight_domain_test_fixtures_mcp", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load WP03 domain test fixture helpers")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def root_ref() -> str:
    from trailsight_v2.data.canonical import account_ref_for

    return account_ref_for("B1", "ROOT")


@pytest.fixture
def peer_ref() -> str:
    from trailsight_v2.data.canonical import account_ref_for

    return account_ref_for("B2", "PEER")


@pytest.fixture
def mcp_runtime(tmp_path: Path, root_ref: str):
    fx = _domain_fixture_module()
    transactions = [
        fx.TxSpec(
            fx.txref(1),
            __import__("datetime").datetime(2025, 1, 1, 9),
            "B3",
            "X",
            "B1",
            "ROOT",
        ),
        fx.TxSpec(
            fx.txref(2),
            __import__("datetime").datetime(2025, 1, 1, 10),
            "B1",
            "ROOT",
            "B4",
            "Y",
        ),
        fx.selected_tx(),
    ]
    alert = fx.AlertSpec("alert_fixture_high", root_ref)
    path = fx.build_runtime_db(tmp_path / "mcp.duckdb", transactions, alerts=[alert])
    return path, alert, fx.selected_tx(), fx


@pytest.fixture
def mcp_service(mcp_runtime):
    path, alert, selected, fx = mcp_runtime
    service = fx.create_investigation_service_v2(path)
    yield service, alert, selected
    service.close()
