from __future__ import annotations

from datetime import timedelta

from trailsight_v2.data.canonical import account_ref_for
from trailsight_v2.domain.models import SubjectType

from .conftest import AlertSpec, S1, SELECTED_TIME, TxSpec, selected_tx, txref


def test_alert_recent_transaction_count_boundaries_self_transfer_and_cross_bank_identity(service_factory, root_ref) -> None:
    alert = AlertSpec("alert_boundary", root_ref)
    rows = [
        # Left boundary included.
        TxSpec(txref(1), S1 - timedelta(hours=24), "B1", "ROOT", "B2", "P1"),
        # Self-transfer counts once.
        TxSpec(txref(2), S1 - timedelta(hours=12), "B1", "ROOT", "B1", "ROOT"),
        # Same Account ID at another bank is a different canonical account and must not count.
        TxSpec(txref(3), S1 - timedelta(hours=6), "B9", "ROOT", "B2", "P1"),
        # Entry cutoff excluded.
        TxSpec(txref(4), S1, "B1", "ROOT", "B2", "P1"),
        # Outside left boundary excluded.
        TxSpec(txref(5), S1 - timedelta(hours=24, seconds=1), "B1", "ROOT", "B2", "P1"),
        selected_tx(),
    ]
    service = service_factory(rows, alerts=[alert])
    facts = service.get_alert_context(alert.ref).alert
    assert facts.relevant_recent_transaction_count == 2


def test_network_is_one_hop_max24_selected_reserved_and_future_rows_excluded(service_factory, root_ref, peer_ref) -> None:
    selected = selected_tx()
    rows = []
    # 30 historical direct counterparties, deterministic counts/timestamps.
    for i in range(30):
        cp_bank = f"B{i+10}"
        cp_account = f"CP{i:02d}"
        rows.append(
            TxSpec(
                txref(100 + i),
                SELECTED_TIME - timedelta(hours=2, minutes=i),
                "B1",
                "ROOT",
                cp_bank,
                cp_account,
                payment_currency="GBP",
                receiving_currency="GBP",
            )
        )
        # A second hop from counterparty to another account must never appear as a root neighbor.
        rows.append(
            TxSpec(
                txref(500 + i),
                SELECTED_TIME - timedelta(hours=3, minutes=i),
                cp_bank,
                cp_account,
                f"BH{i}",
                f"HOP{i}",
                payment_currency="CAD",
                receiving_currency="CAD",
            )
        )
    # Future direct relation must not enter the historical network.
    rows.append(TxSpec(txref(900), SELECTED_TIME + timedelta(seconds=1), "B1", "ROOT", "BF", "FUTURE"))
    rows.append(selected)
    service = service_factory(rows)
    context = service.resolve_context(SubjectType.ACCOUNT, root_ref, selected.ref)
    network = service.get_account_network(root_ref, context=context)
    assert network.shown_counterparties == 24
    assert network.total_direct_counterparties == 31  # 30 historical + selected PEER
    assert network.truncated is True
    assert network.relationships[0].counterparty.account_ref == peer_ref
    assert network.relationships[0].selected_relationship is True
    refs = {item.counterparty.account_ref for item in network.relationships}
    assert account_ref_for("BF", "FUTURE") not in refs
    assert all(not item.counterparty.account_id.startswith("HOP") for item in network.relationships)


def test_network_ranking_is_deterministic_count_then_recency_then_ref(service_factory, root_ref) -> None:
    selected = selected_tx()
    rows = [
        # A and B both count 2; B is more recent and should rank first after reserved PEER.
        TxSpec(txref(1), SELECTED_TIME - timedelta(hours=4), "B1", "ROOT", "BA", "A", payment_currency="GBP", receiving_currency="GBP"),
        TxSpec(txref(2), SELECTED_TIME - timedelta(hours=3), "B1", "ROOT", "BA", "A", payment_currency="GBP", receiving_currency="GBP"),
        TxSpec(txref(3), SELECTED_TIME - timedelta(hours=2), "B1", "ROOT", "BB", "B", payment_currency="GBP", receiving_currency="GBP"),
        TxSpec(txref(4), SELECTED_TIME - timedelta(hours=1), "B1", "ROOT", "BB", "B", payment_currency="GBP", receiving_currency="GBP"),
        selected,
    ]
    service = service_factory(rows)
    network = service.get_account_network(root_ref, origin_ref=selected.ref)
    assert network.relationships[0].counterparty.account_ref == selected.to_ref
    assert network.relationships[1].counterparty.account_ref == account_ref_for("BB", "B")
    assert network.relationships[2].counterparty.account_ref == account_ref_for("BA", "A")


def test_network_relationship_query_returns_counterparty_identities_without_per_row_lookup(
    service_factory, root_ref, monkeypatch
) -> None:
    rows = [
        TxSpec(
            txref(index),
            SELECTED_TIME - timedelta(minutes=index),
            "B1",
            "ROOT",
            f"B{index + 20}",
            f"CP{index}",
        )
        for index in range(1, 6)
    ] + [selected_tx()]
    service = service_factory(rows)
    context = service.resolve_context(SubjectType.ACCOUNT, root_ref)
    identity_reads = 0
    original = service._repository.get_account_row

    def counted_identity(account_ref: str):
        nonlocal identity_reads
        identity_reads += 1
        return original(account_ref)

    monkeypatch.setattr(service._repository, "get_account_row", counted_identity)
    network = service.get_account_network(root_ref, context=context)
    assert network.shown_counterparties == 6
    assert identity_reads == 1  # root only; all counterparties came from the joined aggregate
