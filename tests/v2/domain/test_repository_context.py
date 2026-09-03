from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from trailsight_v2.data.canonical import account_ref_for
from trailsight_v2.domain.errors import DataIntegrityError, InvalidContextError, InvalidInputError, NotFoundError
from trailsight_v2.domain.models import ContextKind, SubjectType
from trailsight_v2.domain.repository import DuckDBInvestigationRepositoryV2
from trailsight_v2.domain.service import create_investigation_service_v2

from .conftest import AlertSpec, S1, S2, SELECTED_TIME, TxSpec, build_runtime_db, selected_tx, txref


def test_missing_database_fails_safely(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError) as exc:
        DuckDBInvestigationRepositoryV2(tmp_path / "missing.duckdb")
    assert "SQL" not in str(exc.value)


def test_repository_is_read_only(tmp_path: Path) -> None:
    path = build_runtime_db(tmp_path / "runtime.duckdb", [selected_tx()])
    repo = DuckDBInvestigationRepositoryV2(path)
    try:
        assert not hasattr(repo, "connection")
        with pytest.raises(duckdb.Error):
            repo.execute_readonly_probe("CREATE TABLE should_fail(x INTEGER)")
    finally:
        repo.close()


def test_missing_detector_schema_is_rejected(tmp_path: Path) -> None:
    path = build_runtime_db(tmp_path / "runtime.duckdb", [selected_tx()])
    con = duckdb.connect(str(path))
    con.execute("DROP TABLE account_detector_support")
    con.close()
    with pytest.raises(DataIntegrityError):
        DuckDBInvestigationRepositoryV2(path)


def test_ground_truth_column_is_rejected(tmp_path: Path) -> None:
    path = build_runtime_db(tmp_path / "runtime.duckdb", [selected_tx()])
    con = duckdb.connect(str(path))
    con.execute('ALTER TABLE transactions ADD COLUMN "Is Laundering" INTEGER')
    con.close()
    with pytest.raises(DataIntegrityError):
        DuckDBInvestigationRepositoryV2(path)


def test_transaction_context_uses_latest_complete_snapshot_and_persisted_facts(service_factory, root_ref) -> None:
    service = service_factory([selected_tx()])
    context = service.resolve_context(SubjectType.TRANSACTION, selected_tx().ref)
    assert context.context_identity.context_kind is ContextKind.TRANSACTION
    assert context.context_time == "2025-01-02T12:00:00"
    assert context.detector_snapshot_id == "snap_1"
    detail = service.get_transaction_detail(selected_tx().ref)
    assert detail.review_state.derivation_text == "Persisted fixture derivation text; returned unchanged."
    root = service.get_account_detail(root_ref, origin_ref=selected_tx().ref)
    assert root.network_review_state.network_pattern_score == 0.987654321
    assert root.network_review_state.rank == 2
    assert root.network_review_state.percentile == 98.7654321
    assert root.network_review_state.network_review_band.value == "HIGH"


def test_direct_latest_and_historical_origins(service_factory, root_ref) -> None:
    alert = AlertSpec("alert_fixture", root_ref)
    service = service_factory([selected_tx()], alerts=[alert])
    latest = service.resolve_context(SubjectType.ACCOUNT, root_ref)
    assert latest.context_time == "2025-01-03T00:00:00"
    assert latest.detector_snapshot_id == "snap_2"
    from_alert = service.resolve_context(SubjectType.ACCOUNT, root_ref, "alert_fixture")
    assert from_alert.context_time == "2025-01-02T00:00:00"
    assert from_alert.alert_ref == "alert_fixture"
    from_tx = service.resolve_context(SubjectType.ACCOUNT, root_ref, selected_tx().ref)
    assert from_tx.context_time == "2025-01-02T12:00:00"
    assert from_tx.selected_transaction_ref == selected_tx().ref


def test_historical_origin_must_authorize_account(service_factory) -> None:
    unrelated_tx = TxSpec(txref(77), S1 + timedelta(hours=2), "B9", "NOPE", "B8", "OTHER")
    service = service_factory([selected_tx(), unrelated_tx])
    unrelated = account_ref_for("B9", "NOPE")
    with pytest.raises(InvalidContextError):
        service.resolve_context(SubjectType.ACCOUNT, unrelated, selected_tx().ref)


def test_equal_timestamp_and_future_rows_are_not_prior_history(service_factory, root_ref, peer_ref) -> None:
    prior = TxSpec(txref(1), SELECTED_TIME - timedelta(minutes=1), "B1", "ROOT", "B2", "PEER", payment_currency="GBP", receiving_currency="GBP")
    equal = TxSpec(txref(2), SELECTED_TIME, "B2", "PEER", "B1", "ROOT", payment_currency="GBP", receiving_currency="GBP")
    future = TxSpec(txref(3), SELECTED_TIME + timedelta(seconds=1), "B1", "ROOT", "B2", "PEER", payment_currency="GBP", receiving_currency="GBP")
    selected = selected_tx(4)
    service = service_factory([prior, equal, future, selected])
    context = service.resolve_context(SubjectType.TRANSACTION, selected.ref)
    rel = service._relationship(root_ref, peer_ref, context)
    assert rel.previous_interaction_count == 1
    account = service.get_account_detail(root_ref, origin_ref=selected.ref)
    assert account.observed_activity.outgoing_count + account.observed_activity.incoming_count == 1


def test_bounded_account_transaction_pagination(service_factory, root_ref) -> None:
    txs = [
        TxSpec(txref(i), SELECTED_TIME - timedelta(minutes=i + 1), "B1", "ROOT", f"B{i+10}", f"C{i}")
        for i in range(5)
    ] + [selected_tx()]
    service = service_factory(txs)
    first = service.list_account_transactions(root_ref, origin_ref=selected_tx().ref, limit=2)
    assert len(first.items) == 2 and first.has_more and first.next_cursor
    assert first.items[0].sender.account_id
    assert first.items[0].sender.bank_country.country_name
    assert first.items[0].aml_review_priority.value in {"HIGH", "MEDIUM", "LOW", "UNSCORED"}
    second = service.list_account_transactions(root_ref, origin_ref=selected_tx().ref, limit=2, cursor=first.next_cursor)
    assert len(second.items) == 2
    assert {item.transaction_ref for item in first.items}.isdisjoint(item.transaction_ref for item in second.items)
    with pytest.raises(InvalidInputError):
        service.list_account_transactions(root_ref, limit=101)



def test_account_transaction_sort_is_timestamp_desc_then_ref_desc(service_factory, root_ref) -> None:
    same_time = SELECTED_TIME - timedelta(minutes=5)
    rows = [
        TxSpec(txref(1), same_time, "B1", "ROOT", "B2", "A"),
        TxSpec(txref(2), same_time, "B1", "ROOT", "B3", "B"),
        TxSpec(txref(3), same_time - timedelta(seconds=1), "B1", "ROOT", "B4", "C"),
        selected_tx(),
    ]
    service = service_factory(rows)
    first = service.list_account_transactions(root_ref, origin_ref=selected_tx().ref, limit=1)
    assert [item.transaction_ref for item in first.items] == [txref(2)]
    assert first.has_more is True
    second = service.list_account_transactions(
        root_ref, origin_ref=selected_tx().ref, limit=1, cursor=first.next_cursor
    )
    assert [item.transaction_ref for item in second.items] == [txref(1)]
    third = service.list_account_transactions(
        root_ref, origin_ref=selected_tx().ref, limit=1, cursor=second.next_cursor
    )
    assert [item.transaction_ref for item in third.items] == [txref(3)]

def test_account_activity_counts_first_last_and_historical_vs_latest(service_factory, root_ref) -> None:
    selected = selected_tx()
    rows = [
        TxSpec(txref(301), S1 - timedelta(hours=5), "B8", "A", "B1", "ROOT", payment_currency="GBP", receiving_currency="GBP"),
        TxSpec(txref(302), S1 + timedelta(hours=1), "B1", "ROOT", "B7", "B", payment_currency="GBP", receiving_currency="GBP"),
        TxSpec(txref(303), S1 + timedelta(hours=2), "B6", "C", "B1", "ROOT", payment_currency="GBP", receiving_currency="GBP"),
        selected,
    ]
    service = service_factory(rows)
    historical = service.get_account_detail(root_ref, origin_ref=selected.ref).observed_activity
    assert historical.incoming_count == 2
    assert historical.outgoing_count == 1
    assert historical.distinct_counterparties == 3
    assert historical.incoming_distinct_counterparties == 2
    assert historical.outgoing_distinct_counterparties == 1
    assert historical.first_observed_timestamp == "2025-01-01T19:00:00"
    assert historical.most_recent_observed_timestamp == "2025-01-02T02:00:00"
    latest = service.get_account_detail(root_ref).observed_activity
    assert latest.outgoing_count == 2  # latest snapshot cutoff includes selected transaction
    assert latest.most_recent_observed_timestamp == "2025-01-02T12:00:00"


def test_future_detector_snapshot_in_transaction_state_is_rejected(tmp_path: Path) -> None:
    selected = selected_tx()
    path = build_runtime_db(tmp_path / "future_state.duckdb", [selected])
    con = duckdb.connect(str(path))
    con.execute(
        "UPDATE transaction_review_states SET snapshot_id='snap_2', detector_cutoff=? WHERE transaction_ref=?",
        [S2, selected.ref],
    )
    con.close()
    service = create_investigation_service_v2(path)
    try:
        with pytest.raises(InvalidContextError):
            service.resolve_context(SubjectType.TRANSACTION, selected.ref)
    finally:
        service.close()


def test_persisted_priority_and_bands_are_not_recomputed(tmp_path: Path) -> None:
    selected = selected_tx()
    path = build_runtime_db(tmp_path / "persisted_priority.duckdb", [selected])
    con = duckdb.connect(str(path))
    con.execute(
        """
        UPDATE transaction_review_states
        SET sender_band='LOW', receiver_band='UNSCORED', aml_review_priority='MEDIUM',
            derivation_code='persisted-test', derivation_text='Exact persisted priority fixture.'
        WHERE transaction_ref=?
        """,
        [selected.ref],
    )
    con.close()
    service = create_investigation_service_v2(path)
    try:
        review = service.get_transaction_detail(selected.ref).review_state
        assert review.sender_band.value == "LOW"
        assert review.receiver_band.value == "UNSCORED"
        assert review.aml_review_priority.value == "MEDIUM"
        assert review.derivation_code == "persisted-test"
        assert review.derivation_text == "Exact persisted priority fixture."
        assert review.snapshot_id == "snap_1"
    finally:
        service.close()
