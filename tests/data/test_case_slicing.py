from __future__ import annotations

from datetime import datetime, timedelta

import duckdb

from trailsight_data.canonical import canonicalize_transaction
from trailsight_data.cases import build_case_slices, select_required_cases
from trailsight_data.database import create_source_transactions_table, insert_staging_transactions
from trailsight_data.models import CaseDefinition, RuntimeTransaction


def make_transaction(
    timestamp: datetime,
    *,
    from_bank: str = "B1",
    from_account: str = "A000001",
    to_bank: str = "B2",
    to_account: str = "A000002",
    amount_paid: str = "10",
    payment_currency: str = "USD",
    amount_received: str = "10",
    receiving_currency: str = "USD",
    payment_format: str = "Card",
) -> RuntimeTransaction:
    canonical = canonicalize_transaction(
        {
            "Timestamp": timestamp.isoformat(sep=" "),
            "From Bank": from_bank,
            "From Account": from_account,
            "To Bank": to_bank,
            "To Account": to_account,
            "Amount Paid": amount_paid,
            "Payment Currency": payment_currency,
            "Amount Received": amount_received,
            "Receiving Currency": receiving_currency,
            "Payment Format": payment_format,
        }
    )
    return RuntimeTransaction(
        transaction_ref=canonical.transaction_ref,
        timestamp=canonical.timestamp,
        from_bank=canonical.from_bank,
        from_account=canonical.from_account,
        to_bank=canonical.to_bank,
        to_account=canonical.to_account,
        amount_paid=canonical.amount_paid,
        payment_currency=canonical.payment_currency,
        amount_received=canonical.amount_received,
        receiving_currency=canonical.receiving_currency,
        payment_format=canonical.payment_format,
    )


def case_for(case_ref: str, transaction: RuntimeTransaction) -> CaseDefinition:
    return CaseDefinition(case_ref, case_ref, transaction.transaction_ref, "test_fixture")


def staged_connection(transactions: list[RuntimeTransaction]):
    connection = duckdb.connect(":memory:")
    create_source_transactions_table(connection)
    insert_staging_transactions(connection, transactions)
    return connection


def test_history_includes_only_earlier_same_bank_and_account_sender() -> None:
    selected_time = datetime(2025, 1, 2, 12)
    earlier = make_transaction(selected_time - timedelta(seconds=1), to_account="A000003")
    selected = make_transaction(selected_time)
    same_timestamp = make_transaction(selected_time, to_account="A000004")
    later = make_transaction(selected_time + timedelta(seconds=1), to_account="A000005")
    same_account_other_bank = make_transaction(
        selected_time - timedelta(seconds=2),
        from_bank="B9",
        from_account=selected.from_account,
        to_account="A000006",
    )
    connection = staged_connection(
        [later, same_timestamp, selected, same_account_other_bank, earlier]
    )
    try:
        case_slice = build_case_slices(connection, (case_for("case-01", selected),))[0]
    finally:
        connection.close()
    assert [row.transaction_ref for row in case_slice.history] == [
        earlier.transaction_ref
    ]


def test_overlapping_cases_do_not_leak_future_rows() -> None:
    start = datetime(2025, 1, 1)
    first = make_transaction(start, to_account="A000010")
    second = make_transaction(start + timedelta(days=1), to_account="A000011")
    third = make_transaction(start + timedelta(days=2), to_account="A000012")
    connection = staged_connection([third, first, second])
    try:
        slices = build_case_slices(
            connection,
            (case_for("case-a", second), case_for("case-b", third)),
        )
    finally:
        connection.close()
    assert [row.transaction_ref for row in slices[0].history] == [first.transaction_ref]
    assert [row.transaction_ref for row in slices[1].history] == [
        first.transaction_ref,
        second.transaction_ref,
    ]


def test_required_eval_candidates_are_selected_deterministically() -> None:
    transactions: list[RuntimeTransaction] = []
    start = datetime(2025, 1, 1)
    for offset in range(6):
        transactions.append(
            make_transaction(
                start + timedelta(days=offset),
                to_account="A000020",
                amount_paid=str(offset + 1),
            )
        )
    demo = make_transaction(
        datetime(2025, 5, 8, 16, 18, 46),
        from_bank="B3",
        from_account="A016568",
        to_bank="B4",
        to_account="A013644",
        amount_paid="69.54",
        payment_currency="CNY",
        amount_received="9.40",
        receiving_currency="USD",
        payment_format="Cash",
    )
    transactions.append(demo)
    connection = staged_connection(list(reversed(transactions)))
    try:
        selected = {case.case_ref: case for case in select_required_cases(connection)}
    finally:
        connection.close()
    assert selected["demo-01"].selected_transaction_ref == demo.transaction_ref
    assert selected["eval-amount-insufficient-01"].selected_transaction_ref == (
        transactions[0].transaction_ref
    )
    assert selected["eval-amount-limited-01"].selected_transaction_ref == (
        transactions[5].transaction_ref
    )
    assert selected["eval-repeat-counterparty-01"].selected_transaction_ref == (
        transactions[1].transaction_ref
    )
