from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from trailsight_v2.data.canonical import account_ref_for
from trailsight_v2.domain.models import HistoryQuality, SubjectType

from .conftest import SELECTED_TIME, TxSpec, selected_tx, txref


def _amount_history(n: int) -> list[TxSpec]:
    rows: list[TxSpec] = []
    for i in range(n):
        rows.append(
            TxSpec(
                txref(100 + i),
                SELECTED_TIME - timedelta(hours=5, minutes=i + 1),
                "B1",
                "ROOT",
                f"BS{i}",
                f"S{i}",
                amount_paid=str(i + 1),
                payment_currency="USD",
                amount_received=str(i + 1),
                receiving_currency="USD",
            )
        )
        rows.append(
            TxSpec(
                txref(500 + i),
                SELECTED_TIME - timedelta(hours=4, minutes=i + 1),
                f"BR{i}",
                f"R{i}",
                "B2",
                "PEER",
                amount_paid=str(i + 100),
                payment_currency="CAD",
                amount_received=str(i + 1),
                receiving_currency="EUR",
            )
        )
    return rows


@pytest.mark.parametrize(
    ("n", "quality", "has_median", "has_percentile"),
    [
        (0, HistoryQuality.INSUFFICIENT, False, False),
        (4, HistoryQuality.INSUFFICIENT, False, False),
        (5, HistoryQuality.LIMITED, True, False),
        (19, HistoryQuality.LIMITED, True, False),
        (20, HistoryQuality.SUFFICIENT, True, True),
    ],
)
def test_amount_quality_thresholds_two_sided(
    service_factory, n, quality, has_median, has_percentile
) -> None:
    selected = selected_tx()
    service = service_factory(_amount_history(n) + [selected])
    detail = service.get_transaction_detail(selected.ref)
    sender = detail.indicators.sender_amount_behavior
    receiver = detail.indicators.receiver_amount_behavior
    assert sender is not None and receiver is not None
    for facts in (sender, receiver):
        assert facts.sample_size == n
        assert facts.history_quality is quality
        assert (facts.historical_median is not None) is has_median
        assert (facts.empirical_percentile is not None) is has_percentile


def test_amount_median_percentile_and_currency_direction_isolation(service_factory) -> None:
    selected = selected_tx()
    rows = _amount_history(20)
    # Wrong currency outgoing and same-currency incoming to sender must not contaminate sender-paid population.
    rows += [
        TxSpec(txref(900), SELECTED_TIME - timedelta(minutes=10), "B1", "ROOT", "BX", "X", amount_paid="9999", payment_currency="JPY"),
        TxSpec(txref(901), SELECTED_TIME - timedelta(minutes=11), "BY", "Y", "B1", "ROOT", amount_received="9999", receiving_currency="USD"),
        TxSpec(txref(902), SELECTED_TIME - timedelta(minutes=12), "BZ", "Z", "B2", "PEER", amount_received="9999", receiving_currency="GBP"),
    ]
    service = service_factory(rows + [selected])
    detail = service.get_transaction_detail(selected.ref)
    sender = detail.indicators.sender_amount_behavior
    receiver = detail.indicators.receiver_amount_behavior
    assert sender and receiver
    assert sender.sample_size == 20
    assert sender.historical_median == "10.5"
    assert sender.empirical_percentile == 100.0
    assert receiver.sample_size == 20
    assert receiver.historical_median == "10.5"
    assert receiver.empirical_percentile == 100.0


def test_counterparty_relationship_both_directions_and_equal_time_exclusion(service_factory, root_ref, peer_ref) -> None:
    selected = selected_tx()
    rows = [
        TxSpec(txref(1), SELECTED_TIME - timedelta(days=2), "B1", "ROOT", "B2", "PEER", payment_currency="GBP", receiving_currency="GBP"),
        TxSpec(txref(2), SELECTED_TIME - timedelta(days=1), "B2", "PEER", "B1", "ROOT", payment_currency="GBP", receiving_currency="GBP"),
        TxSpec(txref(3), SELECTED_TIME, "B1", "ROOT", "B2", "PEER", payment_currency="GBP", receiving_currency="GBP"),
        selected,
    ]
    service = service_factory(rows)
    detail = service.get_transaction_detail(selected.ref)
    rel = detail.indicators.counterparty_relationship
    assert rel is not None
    assert rel.seen_before and not rel.new_counterparty
    assert rel.previous_interaction_count == 2
    assert rel.root_to_counterparty_count == 1
    assert rel.counterparty_to_root_count == 1
    assert rel.first_previous_timestamp == "2024-12-31T12:00:00"
    assert rel.most_recent_previous_timestamp == "2025-01-01T12:00:00"


def test_new_counterparty_semantics(service_factory) -> None:
    selected = selected_tx()
    service = service_factory([selected])
    rel = service.get_transaction_detail(selected.ref).indicators.counterparty_relationship
    assert rel is not None
    assert rel.new_counterparty is True
    assert rel.seen_before is False
    assert rel.previous_interaction_count == 0


def test_velocity_boundaries_and_selected_transaction_exclusion(service_factory, root_ref) -> None:
    selected = selected_tx()
    rows = [
        # Included exactly at 24h boundary, excluded from 1h.
        TxSpec(txref(10), SELECTED_TIME - timedelta(hours=24), "B8", "A", "B1", "ROOT", payment_currency="JPY", receiving_currency="JPY"),
        # Just outside 24h.
        TxSpec(txref(11), SELECTED_TIME - timedelta(hours=24, seconds=1), "B1", "ROOT", "B7", "B", payment_currency="JPY", receiving_currency="JPY"),
        # Included exactly at 1h boundary.
        TxSpec(txref(12), SELECTED_TIME - timedelta(hours=1), "B1", "ROOT", "B6", "C", payment_currency="JPY", receiving_currency="JPY"),
        # Inside 1h incoming.
        TxSpec(txref(13), SELECTED_TIME - timedelta(minutes=30), "B5", "D", "B1", "ROOT", payment_currency="JPY", receiving_currency="JPY"),
        # Equal timestamp should be excluded.
        TxSpec(txref(14), SELECTED_TIME, "B1", "ROOT", "B4", "E", payment_currency="JPY", receiving_currency="JPY"),
        selected,
    ]
    service = service_factory(rows)
    behavior = service.get_transaction_detail(selected.ref).indicators.account_network_behavior[root_ref]
    assert behavior.velocity_1h.incoming_count == 1
    assert behavior.velocity_1h.outgoing_count == 1
    assert behavior.velocity_1h.total_count == 2
    assert behavior.velocity_24h.incoming_count == 2
    assert behavior.velocity_24h.outgoing_count == 1
    assert behavior.velocity_24h.total_count == 3


def test_fan_in_out_use_canonical_accounts_not_account_id_alone(service_factory, root_ref) -> None:
    selected = selected_tx()
    rows = [
        TxSpec(txref(20), SELECTED_TIME - timedelta(hours=2), "B8", "SAMEID", "B1", "ROOT", payment_currency="JPY", receiving_currency="JPY"),
        TxSpec(txref(21), SELECTED_TIME - timedelta(hours=3), "B9", "SAMEID", "B1", "ROOT", payment_currency="JPY", receiving_currency="JPY"),
        TxSpec(txref(22), SELECTED_TIME - timedelta(hours=4), "B1", "ROOT", "B10", "SAMEID", payment_currency="JPY", receiving_currency="JPY"),
        TxSpec(txref(23), SELECTED_TIME - timedelta(hours=5), "B1", "ROOT", "B11", "SAMEID", payment_currency="JPY", receiving_currency="JPY"),
        selected,
    ]
    service = service_factory(rows)
    behavior = service.get_transaction_detail(selected.ref).indicators.account_network_behavior[root_ref]
    assert behavior.fan_in_24h == 2
    assert behavior.fan_out_24h == 2


def test_cross_currency_is_direct_inequality_no_fx_inference(service_factory) -> None:
    cross = selected_tx()
    same = TxSpec(txref(10000), SELECTED_TIME, "B1", "ROOT", "B2", "PEER", amount_paid="50", payment_currency="USD", amount_received="999999", receiving_currency="USD")
    service1 = service_factory([cross])
    assert service1.get_transaction_detail(cross.ref).indicators.cross_currency.cross_currency is True
    service2 = service_factory([same])
    currency = service2.get_transaction_detail(same.ref).indicators.cross_currency
    assert currency is not None
    assert currency.cross_currency is False
    assert currency.currency_pair == "USD -> USD"
