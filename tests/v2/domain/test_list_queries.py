from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from trailsight_v2.data.bank_country import bank_country_for
from trailsight_v2.data.canonical import account_ref_for
from trailsight_v2.domain.errors import DataIntegrityError, InvalidInputError
from trailsight_v2.domain.models import (
    AccountListRequestV2,
    AlertListRequestV2,
    NetworkReviewBand,
    TransactionListRequestV2,
)
from trailsight_v2.domain.service import create_investigation_service_v2

from .conftest import AlertSpec, S1, S2, TxSpec, build_runtime_db, txref


def _tx(
    index: int,
    when: datetime,
    *,
    from_bank: str = "B1",
    from_account: str = "ROOT",
    to_bank: str = "B2",
    to_account: str = "PEER",
    amount_paid: str = "10",
    payment_currency: str = "USD",
    amount_received: str = "10",
    receiving_currency: str = "USD",
    payment_format: str = "ACH",
) -> TxSpec:
    return TxSpec(
        ref=txref(index),
        timestamp=when,
        from_bank=from_bank,
        from_account=from_account,
        to_bank=to_bank,
        to_account=to_account,
        amount_paid=amount_paid,
        payment_currency=payment_currency,
        amount_received=amount_received,
        receiving_currency=receiving_currency,
        payment_format=payment_format,
    )


def _mutate(path: Path, statement: str, parameters: list[object] | None = None) -> None:
    connection = duckdb.connect(str(path))
    try:
        if parameters is None:
            connection.execute(statement)
        else:
            connection.execute(statement, parameters)
    finally:
        connection.close()


def _service(path: Path):
    return create_investigation_service_v2(path)


def _set_high(path: Path, snapshot_id: str, account_ref: str, score: float = 0.99) -> None:
    _mutate(
        path,
        """
        UPDATE account_detector_states
        SET scoring_eligible = TRUE,
            network_pattern_score = ?, rank = 1, percentile = 99.0,
            network_review_band = 'HIGH', unscored_reason = NULL
        WHERE snapshot_id = ? AND account_ref = ?
        """,
        [score, snapshot_id, account_ref],
    )


def test_alert_list_order_cursor_country_and_immutable_projection(tmp_path: Path) -> None:
    root = account_ref_for("B1", "ROOT")
    peer = account_ref_for("B2", "PEER")
    transactions = [_tx(1, S1 + timedelta(hours=1))]
    alerts = [
        AlertSpec("alert_b", root, "snap_1", S1),
        AlertSpec("alert_a", root, "snap_1", S1),
        AlertSpec("alert_c", peer, "snap_2", S2),
    ]
    path = build_runtime_db(tmp_path / "alerts.duckdb", transactions, alerts=alerts)
    _set_high(path, "snap_2", peer)
    service = _service(path)
    try:
        page1 = service.list_alerts(AlertListRequestV2(limit=2))
        assert [item.alert_ref for item in page1.items] == ["alert_c", "alert_a"]
        assert page1.has_more is True
        assert page1.next_cursor
        page2 = service.list_alerts(AlertListRequestV2(limit=2, cursor=page1.next_cursor))
        assert [item.alert_ref for item in page2.items] == ["alert_b"]
        assert page2.has_more is False

        country = bank_country_for("B1")
        filtered = service.list_alerts(AlertListRequestV2(bank_country=country.country_name))
        assert [item.alert_ref for item in filtered.items] == ["alert_a", "alert_b"]
        assert filtered.items[0].network_review_band is NetworkReviewBand.HIGH
        payload = filtered.items[0].model_dump()
        assert "review_status" not in payload
        assert "entry_score" not in payload
        assert "network_pattern_score" not in payload
    finally:
        service.close()


def test_alert_search_covers_identifiers_composes_filters_and_preserves_cursor(
    tmp_path: Path,
) -> None:
    root = account_ref_for("B1", "ROOT")
    peer = account_ref_for("B2", "PEER")
    path = build_runtime_db(
        tmp_path / "alert_search.duckdb",
        [_tx(1, S1 + timedelta(hours=1))],
        alerts=[
            AlertSpec("alert_b", root, "snap_1", S1),
            AlertSpec("alert_a", root, "snap_1", S1),
            AlertSpec("alert_c", peer, "snap_2", S2),
        ],
    )
    _set_high(path, "snap_2", peer)
    service = _service(path)
    try:
        assert [item.alert_ref for item in service.list_alerts(
            AlertListRequestV2(q="alert_c")
        ).items] == ["alert_c"]
        assert [item.alert_ref for item in service.list_alerts(
            AlertListRequestV2(q=peer)
        ).items] == ["alert_c"]
        assert [item.alert_ref for item in service.list_alerts(
            AlertListRequestV2(q="PEE")
        ).items] == ["alert_c"]
        assert [item.alert_ref for item in service.list_alerts(
            AlertListRequestV2(q="B2")
        ).items] == ["alert_c"]
        assert [item.alert_ref for item in service.list_alerts(
            AlertListRequestV2(q="alert_", bank_country=bank_country_for("B1").iso_alpha2)
        ).items] == ["alert_a", "alert_b"]

        first = service.list_alerts(AlertListRequestV2(q="alert_", limit=1))
        assert [item.alert_ref for item in first.items] == ["alert_c"]
        assert first.has_more is True
        second = service.list_alerts(
            AlertListRequestV2(q="alert_", limit=1, cursor=first.next_cursor)
        )
        assert [item.alert_ref for item in second.items] == ["alert_a"]

        absent = service.list_alerts(AlertListRequestV2())
        blank = service.list_alerts(AlertListRequestV2(q="   \t"))
        assert blank == absent
    finally:
        service.close()


def test_alert_membership_filters_apply_before_pagination(tmp_path: Path) -> None:
    root = account_ref_for("B1", "ROOT")
    path = build_runtime_db(
        tmp_path / "membership.duckdb",
        [_tx(1, S1 + timedelta(hours=1))],
        alerts=[
            AlertSpec("alert_a", root),
            AlertSpec("alert_b", root),
            AlertSpec("alert_c", root),
        ],
    )
    service = _service(path)
    try:
        first = service.list_alerts(
            AlertListRequestV2(limit=1, include_alert_refs=("alert_b", "alert_c"))
        )
        assert [item.alert_ref for item in first.items] == ["alert_b"]
        assert first.has_more is True
        second = service.list_alerts(
            AlertListRequestV2(
                limit=1,
                cursor=first.next_cursor,
                include_alert_refs=("alert_b", "alert_c"),
            )
        )
        assert [item.alert_ref for item in second.items] == ["alert_c"]

        excluded = service.list_alerts(
            AlertListRequestV2(limit=1, exclude_alert_refs=("alert_a",))
        )
        assert [item.alert_ref for item in excluded.items] == ["alert_b"]

        empty = service.list_alerts(AlertListRequestV2(include_alert_refs=()))
        assert empty.items == ()
        assert empty.has_more is False
    finally:
        service.close()


def test_alert_include_exclude_are_mutually_exclusive(tmp_path: Path) -> None:
    root = account_ref_for("B1", "ROOT")
    path = build_runtime_db(
        tmp_path / "membership_error.duckdb",
        [_tx(1, S1 + timedelta(hours=1))],
        alerts=[AlertSpec("alert_a", root)],
    )
    service = _service(path)
    try:
        with pytest.raises(InvalidInputError):
            service.list_alerts(
                AlertListRequestV2(
                    include_alert_refs=("alert_a",), exclude_alert_refs=("alert_b",)
                )
            )
    finally:
        service.close()


def test_alert_recent_count_has_exact_24h_boundaries_and_self_transfer_once(tmp_path: Path) -> None:
    root = account_ref_for("B1", "ROOT")
    transactions = [
        _tx(1, S1 - timedelta(hours=24), to_bank="B3", to_account="A"),
        _tx(
            2,
            S1 - timedelta(hours=1),
            from_bank="B1",
            from_account="ROOT",
            to_bank="B1",
            to_account="ROOT",
        ),
        _tx(3, S1, to_bank="B4", to_account="B"),
        _tx(4, S1 - timedelta(hours=24, seconds=1), to_bank="B5", to_account="C"),
    ]
    path = build_runtime_db(
        tmp_path / "alert_count.duckdb", transactions, alerts=[AlertSpec("alert_count", root)]
    )
    service = _service(path)
    try:
        page = service.list_alerts()
        assert page.items[0].relevant_recent_transaction_count == 2
    finally:
        service.close()


def test_transaction_list_stable_order_and_cursor_at_equal_timestamp(tmp_path: Path) -> None:
    when = S1 + timedelta(hours=2)
    path = build_runtime_db(
        tmp_path / "tx_order.duckdb", [_tx(1, when), _tx(3, when), _tx(2, when)]
    )
    service = _service(path)
    try:
        page1 = service.list_transactions(TransactionListRequestV2(limit=2))
        assert [item.transaction_ref for item in page1.items] == [txref(3), txref(2)]
        page2 = service.list_transactions(
            TransactionListRequestV2(limit=2, cursor=page1.next_cursor)
        )
        assert [item.transaction_ref for item in page2.items] == [txref(1)]
        assert service.list_transactions(TransactionListRequestV2(limit=2)).next_cursor == page1.next_cursor
    finally:
        service.close()


def test_transaction_queries_limit_candidates_before_display_enrichment(
    tmp_path: Path, monkeypatch
) -> None:
    transactions = [
        _tx(index, S1 + timedelta(minutes=index)) for index in range(1, 8)
    ]
    path = build_runtime_db(tmp_path / "candidate_first.duckdb", transactions)
    service = _service(path)
    repository = service._repository
    captured: list[tuple[str, list[object] | None]] = []
    original_fetchall = repository._fetchall

    def capture(statement: str, parameters: list[object] | None = None):
        captured.append((statement, parameters))
        return original_fetchall(statement, parameters)

    monkeypatch.setattr(repository, "_fetchall", capture)

    def plan_for_last_query() -> dict[str, object]:
        statement, parameters = captured[-1]
        connection = duckdb.connect(str(path), read_only=True)
        try:
            raw = connection.execute(
                "EXPLAIN (FORMAT JSON) " + statement, parameters or []
            ).fetchone()[1]
        finally:
            connection.close()
        return json.loads(raw)[0]

    def names(node: dict[str, object]) -> list[str]:
        result = [str(node.get("name"))]
        for child in node.get("children", []):
            result.extend(names(child))
        return result

    def tables(node: dict[str, object]) -> list[str]:
        table = node.get("extra_info", {}).get("Table")
        result = [str(table)] if table else []
        for child in node.get("children", []):
            result.extend(tables(child))
        return result

    def first_named(node: dict[str, object], name: str) -> dict[str, object]:
        if node.get("name") == name:
            return node
        for child in node.get("children", []):
            found = first_named(child, name)
            if found:
                return found
        return {}

    try:
        service.list_transactions(TransactionListRequestV2(limit=2))
        list_plan = plan_for_last_query()
        assert list_plan["name"] == "CTE"
        assert list_plan["extra_info"]["CTE Name"] == "page_candidates"
        list_candidate = list_plan["children"][0]
        list_top = first_named(list_candidate, "TOP_N")
        assert list_top["extra_info"]["Top"] == "3"
        assert tables(list_candidate)
        assert all(table.endswith(".transactions") for table in tables(list_candidate))
        assert "CTE_SCAN" in names(list_plan["children"][1])

        before_support = len(captured)
        support = repository.supporting_transaction_rows(
            [transactions[0].ref, transactions[1].ref]
        )
        assert [str(row[0]) for row in support] == [
            transactions[0].ref,
            transactions[1].ref,
        ]
        support_plans: list[dict[str, object]] = []
        connection = duckdb.connect(str(path), read_only=True)
        try:
            for statement, parameters in captured[before_support:]:
                raw = connection.execute(
                    "EXPLAIN (FORMAT JSON) " + statement, parameters or []
                ).fetchone()[1]
                support_plans.append(json.loads(raw)[0])
        finally:
            connection.close()
        queried_tables = [table for plan in support_plans for table in tables(plan)]
        assert len(support_plans) == 3
        assert all(len(tables(plan)) == 1 for plan in support_plans)
        assert {table.rsplit(".", 1)[-1] for table in queried_tables} == {
            "transactions",
            "transaction_review_states",
            "banks",
        }
    finally:
        service.close()


def test_transaction_list_q_searches_ref_account_and_bank_prefixes(tmp_path: Path) -> None:
    transactions = [
        _tx(10, S1 + timedelta(hours=1), from_account="ROOT-A", to_account="PEER-A"),
        _tx(
            20,
            S1 + timedelta(hours=2),
            from_bank="B4",
            from_account="OTHER",
            to_bank="B5",
            to_account="TARGET",
        ),
    ]
    path = build_runtime_db(tmp_path / "tx_q.duckdb", transactions)
    service = _service(path)
    try:
        assert [x.transaction_ref for x in service.list_transactions(
            TransactionListRequestV2(q=txref(10)[:67])
        ).items] == [txref(10)]

        shared_prefix = txref(10)[:20]
        assert [x.transaction_ref for x in service.list_transactions(
            TransactionListRequestV2(q=shared_prefix)
        ).items] == [txref(20), txref(10)]
        assert [x.transaction_ref for x in service.list_transactions(
            TransactionListRequestV2(q="ROOT")
        ).items] == [txref(10)]
        assert [x.transaction_ref for x in service.list_transactions(
            TransactionListRequestV2(q="B5")
        ).items] == [txref(20)]
    finally:
        service.close()


def test_transaction_list_filters_and_date_bounds(tmp_path: Path) -> None:
    t0 = S1 + timedelta(hours=1)
    t1 = S1 + timedelta(hours=2)
    t2 = S1 + timedelta(hours=3)
    root = account_ref_for("B1", "ROOT")
    alerts = [AlertSpec("alert_root", root)]
    transactions = [
        _tx(1, t0, payment_currency="USD", receiving_currency="EUR", payment_format="ACH"),
        _tx(2, t1, from_bank="B4", from_account="OTHER", payment_format="Cash"),
        _tx(3, t2, payment_currency="CAD", receiving_currency="USD", payment_format="Wire"),
    ]
    path = build_runtime_db(tmp_path / "tx_filters.duckdb", transactions, alerts=alerts)
    service = _service(path)
    try:
        high = service.list_transactions(TransactionListRequestV2(priority=NetworkReviewBand.HIGH))
        assert {item.transaction_ref for item in high.items} == {txref(1), txref(3)}

        involved = service.list_transactions(TransactionListRequestV2(alert_involvement=True))
        assert {item.transaction_ref for item in involved.items} == {txref(1), txref(3)}

        bounded = service.list_transactions(
            TransactionListRequestV2(date_from=t0, date_to=t2)
        )
        assert [item.transaction_ref for item in bounded.items] == [txref(2), txref(1)]

        eur = service.list_transactions(TransactionListRequestV2(currency="EUR"))
        assert [item.transaction_ref for item in eur.items] == [txref(1)]
        cash = service.list_transactions(TransactionListRequestV2(payment_format="Cash"))
        assert [item.transaction_ref for item in cash.items] == [txref(2)]

        sending = service.list_transactions(
            TransactionListRequestV2(sending_bank_country=bank_country_for("B4").country_name)
        )
        assert [item.transaction_ref for item in sending.items] == [txref(2)]
        receiving = service.list_transactions(
            TransactionListRequestV2(receiving_bank_country=bank_country_for("B2").iso_alpha2)
        )
        assert {item.transaction_ref for item in receiving.items} == {txref(1), txref(2), txref(3)}
    finally:
        service.close()


def test_transaction_list_returns_persisted_priority_and_decimal_safe_amounts(tmp_path: Path) -> None:
    transaction = _tx(
        8,
        S1 + timedelta(hours=1),
        from_bank="B4",
        from_account="OTHER",
        amount_paid="10.10",
        amount_received="7.2500",
    )
    path = build_runtime_db(tmp_path / "tx_persisted.duckdb", [transaction])
    _mutate(
        path,
        "UPDATE transaction_review_states SET aml_review_priority = 'MEDIUM' WHERE transaction_ref = ?",
        [transaction.ref],
    )
    service = _service(path)
    try:
        item = service.list_transactions().items[0]
        assert item.aml_review_priority is NetworkReviewBand.MEDIUM
        assert item.amount_paid == "10.1"
        assert item.amount_received == "7.25"
        assert not isinstance(item.amount_paid, float)
    finally:
        service.close()


def test_transaction_related_alert_uses_persisted_endpoint_refs(tmp_path: Path) -> None:
    root = account_ref_for("B1", "ROOT")
    peer = account_ref_for("B2", "PEER")
    tx = _tx(9, S2 + timedelta(hours=1))
    path = build_runtime_db(
        tmp_path / "tx_alert.duckdb",
        [tx],
        alerts=[
            AlertSpec("alert_sender", root, "snap_1", S1),
            AlertSpec("alert_receiver", peer, "snap_2", S2),
        ],
    )
    _set_high(path, "snap_2", peer)
    service = _service(path)
    try:
        item = service.list_transactions().items[0]
        assert item.related_alert == "alert_receiver"
    finally:
        service.close()


def _account_fixture(path: Path) -> tuple[Path, dict[str, str]]:
    transactions = [
        _tx(1, S1 + timedelta(hours=1), to_bank="B2", to_account="PEER"),
        _tx(2, S1 + timedelta(hours=2), to_bank="B4", to_account="UNS"),
        _tx(
            3,
            S1 + timedelta(hours=3),
            from_bank="B5",
            from_account="LOW-B",
            to_bank="B1",
            to_account="ROOT",
        ),
    ]
    refs = {
        "root": account_ref_for("B1", "ROOT"),
        "peer": account_ref_for("B2", "PEER"),
        "uns": account_ref_for("B4", "UNS"),
        "lowb": account_ref_for("B5", "LOW-B"),
    }
    db = build_runtime_db(path, transactions, alerts=[AlertSpec("alert_root", refs["root"])])
    updates = [
        (refs["root"], "HIGH", 0.90, True, None),
        (refs["peer"], "MEDIUM", 0.80, True, None),
        (refs["lowb"], "LOW", 0.70, True, None),
        (refs["uns"], "UNSCORED", None, False, "NO_SECOND_ORDER_CONTEXT"),
    ]
    for rank, (ref, band, score, eligible, reason) in enumerate(updates, 1):
        _mutate(
            db,
            """
            UPDATE account_detector_states
            SET network_review_band=?, network_pattern_score=?, rank=?, percentile=?,
                scoring_eligible=?, unscored_reason=?
            WHERE snapshot_id='snap_2' AND account_ref=?
            """,
            [band, score, None if not eligible else rank, None if not eligible else 99-rank,
             eligible, reason, ref],
        )
    return db, refs


def test_account_list_uses_latest_complete_snapshot_and_frozen_order(tmp_path: Path) -> None:
    path, refs = _account_fixture(tmp_path / "accounts.duckdb")
    service = _service(path)
    try:
        page = service.list_accounts()
        assert [item.account_ref for item in page.items] == [
            refs["root"], refs["peer"], refs["lowb"], refs["uns"]
        ]
        assert {item.latest_snapshot_id for item in page.items} == {"snap_2"}
        assert {item.latest_detector_cutoff for item in page.items} == {"2025-01-03T00:00:00"}
        uns = next(item for item in page.items if item.account_ref == refs["uns"])
        assert uns.network_pattern_score is None
    finally:
        service.close()


def test_account_order_score_desc_then_account_ref(tmp_path: Path) -> None:
    transactions = [
        _tx(1, S1 + timedelta(hours=1), to_bank="B4", to_account="LOW-A"),
        _tx(2, S1 + timedelta(hours=2), to_bank="B5", to_account="LOW-B"),
    ]
    path = build_runtime_db(tmp_path / "score_order.duckdb", transactions)
    a = account_ref_for("B4", "LOW-A")
    b = account_ref_for("B5", "LOW-B")
    _mutate(path, "UPDATE account_detector_states SET network_pattern_score=0.9 WHERE snapshot_id='snap_2' AND account_ref=?", [a])
    _mutate(path, "UPDATE account_detector_states SET network_pattern_score=0.8 WHERE snapshot_id='snap_2' AND account_ref=?", [b])
    service = _service(path)
    try:
        lows = service.list_accounts(AccountListRequestV2(band=NetworkReviewBand.LOW))
        low_refs = [item.account_ref for item in lows.items]
        assert low_refs.index(a) < low_refs.index(b)

    finally:
        service.close()


def test_account_list_uses_account_ref_as_final_tie_break(tmp_path: Path) -> None:
    transactions = [
        _tx(1, S1 + timedelta(hours=1), to_bank="B4", to_account="LOW-A"),
        _tx(2, S1 + timedelta(hours=2), to_bank="B5", to_account="LOW-B"),
    ]
    path = build_runtime_db(tmp_path / "tie_order.duckdb", transactions)
    refs = [account_ref_for("B4", "LOW-A"), account_ref_for("B5", "LOW-B")]
    for ref in refs:
        _mutate(
            path,
            "UPDATE account_detector_states SET network_pattern_score=0.75 "
            "WHERE snapshot_id='snap_2' AND account_ref=?",
            [ref],
        )
    service = _service(path)
    try:
        lows = service.list_accounts(AccountListRequestV2(band=NetworkReviewBand.LOW))
        shown = [item.account_ref for item in lows.items if item.account_ref in refs]
        assert shown == sorted(refs)
    finally:
        service.close()


def test_account_list_cursor_and_filters(tmp_path: Path) -> None:
    path, refs = _account_fixture(tmp_path / "account_filters.duckdb")
    service = _service(path)
    try:
        first = service.list_accounts(AccountListRequestV2(limit=2))
        second = service.list_accounts(AccountListRequestV2(limit=2, cursor=first.next_cursor))
        assert [x.account_ref for x in first.items + second.items] == [
            refs["root"], refs["peer"], refs["lowb"], refs["uns"]
        ]

        assert [x.account_ref for x in service.list_accounts(
            AccountListRequestV2(q="ROO")
        ).items] == [refs["root"]]
        assert [x.account_ref for x in service.list_accounts(
            AccountListRequestV2(q="B4")
        ).items] == [refs["uns"]]
        assert [x.account_ref for x in service.list_accounts(
            AccountListRequestV2(band=NetworkReviewBand.MEDIUM)
        ).items] == [refs["peer"]]
        assert [x.account_ref for x in service.list_accounts(
            AccountListRequestV2(bank_country=bank_country_for("B4").iso_alpha2)
        ).items] == [refs["uns"]]
        assert [x.account_ref for x in service.list_accounts(
            AccountListRequestV2(alert_involvement=True)
        ).items] == [refs["root"]]
    finally:
        service.close()


def test_account_list_activity_counts_are_strictly_before_latest_cutoff(tmp_path: Path) -> None:
    root = account_ref_for("B1", "ROOT")
    transactions = [
        _tx(1, S1 + timedelta(hours=1)),
        _tx(2, S1 + timedelta(hours=2)),
        _tx(3, S1 + timedelta(hours=3), from_bank="B4", from_account="IN", to_bank="B1", to_account="ROOT"),
        _tx(4, S2, to_bank="B5", to_account="FUTURE-AT-CUTOFF"),
    ]
    path = build_runtime_db(tmp_path / "account_counts.duckdb", transactions)
    service = _service(path)
    try:
        item = next(x for x in service.list_accounts().items if x.account_ref == root)
        assert item.incoming_count == 1
        assert item.outgoing_count == 2
    finally:
        service.close()


@pytest.mark.parametrize("status", ["FAILED", "PENDING"])
def test_latest_complete_snapshot_ignores_noncomplete_newer_snapshot(
    tmp_path: Path, status: str
) -> None:
    path = build_runtime_db(
        tmp_path / f"metadata_{status.lower()}.duckdb", [_tx(1, S1 + timedelta(hours=1))]
    )
    _mutate(path, "UPDATE detector_snapshots SET status=? WHERE snapshot_id='snap_2'", [status])
    service = _service(path)
    try:
        metadata = service.get_runtime_metadata()
        assert metadata.latest_snapshot_id == "snap_1"
        assert metadata.latest_snapshot_cutoff == "2025-01-02T00:00:00"
        accounts = service.list_accounts()
        assert {item.latest_snapshot_id for item in accounts.items} == {"snap_1"}
        assert set(metadata.model_dump()) == {"latest_snapshot_id", "latest_snapshot_cutoff"}
    finally:
        service.close()


def test_no_complete_snapshot_fails_safely(tmp_path: Path) -> None:
    path = build_runtime_db(tmp_path / "no_complete.duckdb", [_tx(1, S1 + timedelta(hours=1))])
    _mutate(path, "UPDATE detector_snapshots SET status='FAILED'")
    service = _service(path)
    try:
        with pytest.raises(DataIntegrityError):
            service.get_runtime_metadata()
        with pytest.raises(DataIntegrityError):
            service.list_accounts()
    finally:
        service.close()


def test_page_limits_default_50_limit_100_and_invalid_bounds(tmp_path: Path) -> None:
    transactions = [
        _tx(i, S1 + timedelta(minutes=i), from_bank="B4", from_account=f"A{i}")
        for i in range(1, 102)
    ]
    path = build_runtime_db(tmp_path / "limits.duckdb", transactions)
    service = _service(path)
    try:
        default = service.list_transactions()
        assert len(default.items) == 50
        assert default.has_more is True
        hundred = service.list_transactions(TransactionListRequestV2(limit=100))
        assert len(hundred.items) == 100
        assert hundred.has_more is True
        one = service.list_transactions(TransactionListRequestV2(limit=1))
        assert len(one.items) == 1
        with pytest.raises(InvalidInputError):
            service.list_transactions(TransactionListRequestV2(limit=0))
        with pytest.raises(InvalidInputError):
            service.list_accounts(AccountListRequestV2(limit=101))
    finally:
        service.close()


def test_malformed_and_cross_resource_cursors_are_rejected(tmp_path: Path) -> None:
    root = account_ref_for("B1", "ROOT")
    path = build_runtime_db(
        tmp_path / "cursor_errors.duckdb",
        [_tx(1, S1 + timedelta(hours=1)), _tx(2, S1 + timedelta(hours=2))],
        alerts=[AlertSpec("alert_a", root), AlertSpec("alert_b", root)],
    )
    service = _service(path)
    try:
        with pytest.raises(InvalidInputError):
            service.list_transactions(TransactionListRequestV2(cursor="not-a-cursor"))
        alert_cursor = service.list_alerts(AlertListRequestV2(limit=1)).next_cursor
        assert alert_cursor
        with pytest.raises(InvalidInputError):
            service.list_transactions(TransactionListRequestV2(cursor=alert_cursor))
    finally:
        service.close()


def test_q_is_bounded(tmp_path: Path) -> None:
    path = build_runtime_db(tmp_path / "q_bound.duckdb", [_tx(1, S1 + timedelta(hours=1))])
    service = _service(path)
    try:
        with pytest.raises(InvalidInputError):
            service.list_transactions(TransactionListRequestV2(q="x" * 257))
        with pytest.raises(InvalidInputError):
            service.list_accounts(AccountListRequestV2(q="x" * 257))
        with pytest.raises(InvalidInputError):
            service.list_alerts(AlertListRequestV2(q="x" * 257))
    finally:
        service.close()
