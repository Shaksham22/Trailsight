from __future__ import annotations

from decimal import Decimal
import json
import os
from pathlib import Path

import pytest

from trailsight.data.runtime_repository import RuntimeRepository
from trailsight.domain.service import InvestigationService


def test_primary_demo_against_real_wp01_runtime() -> None:
    raw_path = os.environ.get("TRAILSIGHT_DB_PATH")
    if not raw_path:
        pytest.skip("TRAILSIGHT_DB_PATH is not set for the opt-in WP01 integration")
    database_path = Path(raw_path)
    assert database_path.is_file(), "Configured WP01 runtime database is unavailable"

    repository = RuntimeRepository(database_path)
    try:
        workspace = InvestigationService(repository).get_workspace("demo-01")
    finally:
        repository.close()

    selected = workspace.selected_transaction
    assert selected.timestamp == "2025-05-08T16:18:46.000000"
    assert selected.sender.account == "A016568"
    assert selected.counterparty.account == "A013644"
    assert selected.amount_paid == "69.54"
    assert selected.payment_currency == "CNY"
    assert Decimal(selected.amount_received) == Decimal("9.40")
    assert selected.receiving_currency == "USD"
    assert selected.payment_format == "Cash"
    assert selected.sender.synthetic_region == 8
    assert selected.counterparty.synthetic_region == 4
    assert selected.cross_currency is True
    assert selected.region_relationship.value == "cross_region"
    assert workspace.sender_history.prior_outgoing_count == 74
    assert len(workspace.historical_transactions) == 74
    assert workspace.amount_history.sample_size == 70
    assert workspace.amount_history.historical_median == "15.095"
    assert workspace.amount_history.empirical_percentile == pytest.approx(95.71, abs=0.01)
    assert workspace.counterparty_history.previous_interaction_count == 0
    assert workspace.region_history is not None
    assert workspace.region_history.receiver_region_seen_before is False
    assert "Is Laundering" not in json.dumps(workspace.model_dump(mode="json"))
