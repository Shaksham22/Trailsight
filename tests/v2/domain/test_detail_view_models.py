from __future__ import annotations

from datetime import datetime, timedelta

from trailsight_v2.data.bank_country import bank_country_for
from trailsight_v2.domain.models import EvidenceType, NetworkReviewBand, UITargetV2

from .conftest import AlertSpec, SELECTED_TIME, TxSpec, selected_tx, txref


def _prior(
    index: int,
    *,
    minutes: int,
    from_bank: str = "B1",
    from_account: str = "ROOT",
    to_bank: str | None = None,
    to_account: str | None = None,
    amount_paid: str = "10",
    payment_currency: str = "USD",
    amount_received: str | None = None,
    receiving_currency: str | None = None,
) -> TxSpec:
    return TxSpec(
        ref=txref(index),
        timestamp=SELECTED_TIME - timedelta(minutes=minutes),
        from_bank=from_bank,
        from_account=from_account,
        to_bank=to_bank or f"B{index + 20}",
        to_account=to_account or f"CP{index}",
        amount_paid=amount_paid,
        payment_currency=payment_currency,
        amount_received=amount_received or amount_paid,
        receiving_currency=receiving_currency or payment_currency,
    )


def test_transaction_detail_contains_complete_frozen_sections_and_historical_cards(
    service_factory, root_ref, peer_ref
) -> None:
    selected = selected_tx()
    service = service_factory([_prior(1, minutes=30), selected])

    detail = service.get_transaction_detail(selected.ref)
    dumped = detail.model_dump()

    assert {
        "review_state",
        "transaction_facts",
        "bank_country_route",
        "sender_account_card",
        "receiver_account_card",
        "investigation_indicators",
        "activity_context",
        "local_network_summary",
        "supporting_evidence_summary",
    }.issubset(dumped)

    assert detail.context.detector_snapshot_id == "snap_1"
    assert detail.sender_account_card.account.account_ref == root_ref
    assert detail.receiver_account_card.account.account_ref == peer_ref
    assert detail.sender_account_card.network_review_band is NetworkReviewBand.HIGH
    assert detail.receiver_account_card.network_review_band is NetworkReviewBand.MEDIUM
    assert detail.sender_account_card.detector_cutoff == "2025-01-02T00:00:00"
    assert detail.receiver_account_card.detector_cutoff == "2025-01-02T00:00:00"

    # Direct-latest browsing would use snap_2, proving the transaction cards did not leak latest state.
    latest_sender = service.get_account_detail(root_ref)
    assert latest_sender.context.detector_snapshot_id == "snap_2"
    assert latest_sender.network_review_state.network_review_band is NetworkReviewBand.LOW


def test_transaction_detail_indicators_use_resolvable_application_evidence(service_factory) -> None:
    selected = selected_tx()
    rows = [_prior(i, minutes=i + 1) for i in range(1, 22)] + [selected]
    service = service_factory(rows)

    detail = service.get_transaction_detail(selected.ref)
    keys = {item.key for item in detail.investigation_indicators}

    assert {
        "sender-amount-history",
        "receiver-amount-history",
        "counterparty-relationship",
        "sender-recent-network",
        "receiver-recent-network",
        "currency-route",
    } <= keys

    for indicator in detail.investigation_indicators:
        assert indicator.ui_target is UITargetV2.INVESTIGATION_INDICATORS
        resolved = service.resolve_evidence(indicator.evidence_id)
        assert resolved.evidence_id == indicator.evidence_id
        assert indicator.supporting_transaction_refs == resolved.supporting_transaction_refs

    evidence_types = {
        service.resolve_evidence(item.evidence_id).evidence_type
        for item in detail.investigation_indicators
    }
    assert {
        EvidenceType.AMOUNT_BEHAVIOR,
        EvidenceType.COUNTERPARTY_RELATIONSHIP,
        EvidenceType.NETWORK_BEHAVIOR,
        EvidenceType.CURRENCY_BEHAVIOR,
    } <= evidence_types


def test_transaction_detail_trusted_evidence_display_matches_public_resolution(
    service_factory,
) -> None:
    selected = selected_tx()
    rows = [_prior(i, minutes=i + 1) for i in range(1, 22)] + [selected]
    service = service_factory(rows)

    detail = service.get_transaction_detail(selected.ref)

    for summary in detail.supporting_evidence_summary:
        public_display = service.display_evidence(summary.evidence_id)
        assert summary.model_dump(exclude={"label"}) == public_display.model_dump()


def test_transaction_detail_query_count_stays_well_below_previous_hundreds(
    service_factory, monkeypatch
) -> None:
    selected = selected_tx()
    rows = [_prior(i, minutes=i + 1) for i in range(1, 22)] + [selected]
    service = service_factory(rows)
    repository = service._repository
    query_count = 0
    original_fetchone = repository._fetchone
    original_fetchall = repository._fetchall

    def count_fetchone(statement, parameters=None):
        nonlocal query_count
        query_count += 1
        return original_fetchone(statement, parameters)

    def count_fetchall(statement, parameters=None):
        nonlocal query_count
        query_count += 1
        return original_fetchall(statement, parameters)

    monkeypatch.setattr(repository, "_fetchone", count_fetchone)
    monkeypatch.setattr(repository, "_fetchall", count_fetchall)

    detail = service.get_transaction_detail(selected.ref)

    assert detail.supporting_evidence_summary
    assert query_count <= 50


def test_transaction_activity_context_is_prior_30_days_currency_separated_and_marks_selected(
    service_factory
) -> None:
    selected_time = datetime(2025, 2, 15, 12, 0, 0)
    selected = TxSpec(
        txref(9000),
        selected_time,
        "B1",
        "ROOT",
        "B2",
        "PEER",
        amount_paid="50",
        payment_currency="USD",
        amount_received="60",
        receiving_currency="EUR",
    )
    old = TxSpec(
        txref(1),
        datetime(2025, 1, 5, 9, 0, 0),
        "B1",
        "ROOT",
        "B3",
        "OLD",
        amount_paid="999",
        payment_currency="USD",
        amount_received="999",
        receiving_currency="USD",
    )
    recent_usd = TxSpec(
        txref(2),
        datetime(2025, 2, 1, 9, 0, 0),
        "B1",
        "ROOT",
        "B4",
        "USD_CP",
        amount_paid="25",
        payment_currency="USD",
        amount_received="25",
        receiving_currency="USD",
    )
    recent_eur = TxSpec(
        txref(3),
        datetime(2025, 2, 1, 10, 0, 0),
        "B5",
        "EUR_CP",
        "B1",
        "ROOT",
        amount_paid="30",
        payment_currency="EUR",
        amount_received="31",
        receiving_currency="EUR",
    )
    service = service_factory([old, recent_usd, recent_eur, selected])

    activity = service.get_transaction_detail(selected.ref).activity_context

    assert activity.range_start == "2025-01-16T12:00:00"
    assert activity.range_end == "2025-02-15T12:00:00"
    assert activity.selected_transaction is not None
    assert activity.selected_transaction.transaction_ref == selected.ref
    assert activity.selected_transaction.currency == "USD"
    assert activity.selected_transaction.amount == "50"

    by_currency = {bucket.currency: bucket for bucket in activity.buckets}
    assert set(by_currency) == {"EUR", "USD"}
    assert by_currency["USD"].incoming_amount == "0"
    assert by_currency["USD"].outgoing_amount == "25"
    assert by_currency["EUR"].incoming_amount == "31"
    assert by_currency["EUR"].outgoing_amount == "0"
    assert all("999" not in (bucket.incoming_amount, bucket.outgoing_amount) for bucket in activity.buckets)


def test_transaction_detail_networks_are_one_hop_bounded_and_evidence_support_is_bounded(
    service_factory
) -> None:
    selected = selected_tx()
    rows = [
        _prior(i, minutes=i + 1, to_bank=f"B{i + 10}", to_account=f"CP{i}")
        for i in range(60)
    ] + [selected]
    service = service_factory(rows)

    detail = service.get_transaction_detail(selected.ref)
    sender_network = detail.local_network_summary.sender
    receiver_network = detail.local_network_summary.receiver

    assert sender_network is not None
    assert receiver_network is not None
    assert sender_network.shown_counterparties <= 24
    assert receiver_network.shown_counterparties <= 24
    assert len(sender_network.relationships) == sender_network.shown_counterparties
    assert all(
        item.counterparty.account_ref != sender_network.root.account_ref
        for item in sender_network.relationships
    )

    assert detail.supporting_evidence_summary
    for item in detail.supporting_evidence_summary:
        assert item.label.startswith("E")
        assert len(item.supporting_transactions) <= 50
        assert service.resolve_evidence(item.evidence_id).evidence_id == item.evidence_id
    assert any(
        item.supporting_transaction_count > 50 and item.support_truncated
        for item in detail.supporting_evidence_summary
    )
    supporting = next(
        row
        for item in detail.supporting_evidence_summary
        for row in item.supporting_transactions
    )
    assert supporting.from_account_id
    assert supporting.from_bank_country.country_name
    assert supporting.to_account_id
    assert supporting.to_bank_country.country_name
    assert isinstance(supporting.aml_review_priority, NetworkReviewBand)


def test_account_bank_country_flows_return_complete_aggregate_without_top_12_limit(
    service_factory, root_ref
) -> None:
    banks_by_country: dict[str, str] = {}
    candidate = 0
    while len(banks_by_country) < 13:
        bank_id = f"COUNTRY_BANK_{candidate}"
        country = bank_country_for(bank_id).country_name
        banks_by_country.setdefault(country, bank_id)
        candidate += 1
    rows = [
        TxSpec(
            txref(index),
            SELECTED_TIME - timedelta(minutes=index + 1),
            "B1",
            "ROOT",
            bank_id,
            f"CP{index}",
        )
        for index, bank_id in enumerate(banks_by_country.values(), 1)
    ]
    service = service_factory([*rows, selected_tx()])
    detail = service.get_account_detail(root_ref, origin_ref=selected_tx().ref)
    assert len(detail.bank_country_flows) == 13
    assert {flow.counterparty_country for flow in detail.bank_country_flows} == set(
        banks_by_country
    )


def test_account_alert_history_exposes_honest_total_and_truncation(
    service_factory, root_ref
) -> None:
    alerts = [AlertSpec(f"alert_{index:03d}", root_ref) for index in range(137)]
    service = service_factory([selected_tx()], alerts=alerts)
    detail = service.get_account_detail(root_ref)
    assert len(detail.alert_history) == 100
    assert detail.alert_history_total == 137
    assert detail.alert_history_truncated is True


def test_account_currency_activity_groups_currency_and_direction_without_cross_currency_aggregation(
    service_factory, root_ref
) -> None:
    selected = selected_tx()
    rows = [
        TxSpec(
            txref(1),
            SELECTED_TIME - timedelta(hours=4),
            "B3",
            "IN_USD",
            "B1",
            "ROOT",
            amount_paid="90",
            payment_currency="USD",
            amount_received="100",
            receiving_currency="USD",
        ),
        TxSpec(
            txref(2),
            SELECTED_TIME - timedelta(hours=3),
            "B1",
            "ROOT",
            "B4",
            "OUT_USD",
            amount_paid="50",
            payment_currency="USD",
            amount_received="50",
            receiving_currency="USD",
        ),
        TxSpec(
            txref(3),
            SELECTED_TIME - timedelta(hours=2),
            "B5",
            "IN_EUR",
            "B1",
            "ROOT",
            amount_paid="65",
            payment_currency="EUR",
            amount_received="70",
            receiving_currency="EUR",
        ),
        TxSpec(
            txref(4),
            SELECTED_TIME - timedelta(hours=1),
            "B1",
            "ROOT",
            "B6",
            "OUT_EUR",
            amount_paid="20",
            payment_currency="EUR",
            amount_received="20",
            receiving_currency="EUR",
        ),
        selected,
    ]
    service = service_factory(rows)

    detail = service.get_account_detail(root_ref, origin_ref=selected.ref)
    by_currency = {row.currency: row for row in detail.currency_activity}

    assert set(by_currency) == {"EUR", "USD"}
    assert by_currency["USD"].incoming_count == 1
    assert by_currency["USD"].outgoing_count == 1
    assert by_currency["USD"].incoming_amount == "100"
    assert by_currency["USD"].outgoing_amount == "50"
    assert by_currency["EUR"].incoming_count == 1
    assert by_currency["EUR"].outgoing_count == 1
    assert by_currency["EUR"].incoming_amount == "70"
    assert by_currency["EUR"].outgoing_amount == "20"


def test_historical_account_currency_activity_excludes_selected_and_future_transactions(
    service_factory, root_ref
) -> None:
    selected = selected_tx()
    prior = TxSpec(
        txref(1),
        SELECTED_TIME - timedelta(hours=1),
        "B1",
        "ROOT",
        "B3",
        "PRIOR",
        amount_paid="10",
        payment_currency="USD",
        amount_received="10",
        receiving_currency="USD",
    )
    future = TxSpec(
        txref(2),
        SELECTED_TIME + timedelta(hours=1),
        "B1",
        "ROOT",
        "B4",
        "FUTURE",
        amount_paid="999",
        payment_currency="USD",
        amount_received="999",
        receiving_currency="USD",
    )
    service = service_factory([prior, selected, future])

    detail = service.get_account_detail(root_ref, origin_ref=selected.ref)
    usd = next(row for row in detail.currency_activity if row.currency == "USD")

    assert usd.outgoing_count == 1
    assert usd.outgoing_amount == "10"
    assert all(bucket.total_amount not in {"50", "999"} for bucket in detail.activity_over_time)
