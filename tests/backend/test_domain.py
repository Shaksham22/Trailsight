from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import json

import pytest

from conftest import selected_transaction, transaction, txref
from trailsight.contracts import (
    AmountHistoryFacts,
    CounterpartyHistoryFacts,
    CurrencyDimension,
    CurrencyHistoryFacts,
    HistoryQuality,
    RegionHistoryFacts,
    SelectedTransaction,
    SenderHistoryFacts,
)
from trailsight.domain.service import InvestigationService
from trailsight.domain.synthetic_region import derive_synthetic_region
from trailsight.errors import DataIntegrityError, DomainInputError, EvidenceResolutionError


def test_investigation_service_exposes_exact_frozen_public_methods() -> None:
    public_methods = {
        name
        for name, value in InvestigationService.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    assert public_methods == {
        "get_workspace",
        "get_selected_transaction_evidence",
        "get_sender_history_evidence",
        "get_amount_history_evidence",
        "get_counterparty_history_evidence",
        "get_region_history_evidence",
        "get_currency_history_evidence",
        "resolve_evidence",
    }


@pytest.mark.parametrize(
    ("account", "expected"),
    [("A016568", 8), ("A013644", 4), ("prefix000", 0)],
)
def test_synthetic_region_examples(account: str, expected: int) -> None:
    assert derive_synthetic_region(account) == expected


@pytest.mark.parametrize("account", ["A", "", "123-no-suffix"])
def test_synthetic_region_rejects_malformed_accounts(account: str) -> None:
    with pytest.raises(DomainInputError):
        derive_synthetic_region(account)


def test_selected_transaction_construction(service_builder) -> None:
    service, _, _ = service_builder()

    evidence = service.get_selected_transaction_evidence("demo-01")
    selected = evidence.facts

    assert isinstance(selected, SelectedTransaction)
    assert selected.timestamp == "2025-02-01T12:00:00.000000"
    assert selected.sender.bank == "Sender Bank"
    assert selected.sender.account == "A016568"
    assert selected.sender.entity_type.value == "Person"
    assert selected.sender.synthetic_region == 8
    assert selected.counterparty.account == "A013644"
    assert selected.counterparty.synthetic_region == 4
    assert selected.amount_paid == "69.54"
    assert selected.amount_received == "9.4"
    assert selected.cross_currency is True
    assert selected.currency_pair == "CNY → USD"
    assert selected.region_relationship.value == "cross_region"
    assert evidence.supporting_transaction_refs == [txref(10_000)]


def test_missing_entity_mapping_fails_deterministically(service_builder) -> None:
    service, repository, _ = service_builder()
    repository._connection.close()
    # The database must be reopened writable only after the read-only fixture connection closes.
    import duckdb

    connection = duckdb.connect(str(repository.database_path))
    connection.execute(
        "DELETE FROM entities WHERE bank = 'Receiver Bank' AND account = 'A013644'"
    )
    connection.close()
    repository._connection = duckdb.connect(str(repository.database_path), read_only=True)

    with pytest.raises(DataIntegrityError, match="cannot be resolved"):
        service.get_selected_transaction_evidence("demo-01")


@pytest.mark.parametrize(
    "invalid_timestamp",
    [datetime(2025, 2, 1, 12, 0, 0), datetime(2025, 2, 2, 12, 0, 0)],
    ids=["equal", "later"],
)
@pytest.mark.parametrize(
    "operation",
    [
        lambda service: service.get_sender_history_evidence("demo-01"),
        lambda service: service.get_amount_history_evidence("demo-01"),
        lambda service: service.get_counterparty_history_evidence("demo-01"),
        lambda service: service.get_region_history_evidence("demo-01"),
        lambda service: service.get_currency_history_evidence(
            "demo-01", "payment", "CNY"
        ),
        lambda service: service.get_workspace("demo-01"),
    ],
)
def test_every_history_calculation_rejects_equal_or_later_rows(
    service_builder, invalid_timestamp: datetime, operation
) -> None:
    invalid = transaction(1, invalid_timestamp)
    service, _, _ = service_builder(history=[invalid])

    with pytest.raises(DataIntegrityError, match="strictly earlier"):
        operation(service)


def _amount_history(number: int) -> list[dict]:
    start = datetime(2025, 1, 1)
    return [
        transaction(
            index + 1,
            start + timedelta(hours=index),
            to_bank=f"History Bank {index}",
            to_account=f"A{index + 1:06d}",
            amount_paid=str(index + 1),
            payment_currency="CNY",
        )
        for index in range(number)
    ]


@pytest.mark.parametrize(
    ("number", "quality", "median", "percentile"),
    [
        (0, HistoryQuality.INSUFFICIENT, None, None),
        (4, HistoryQuality.INSUFFICIENT, None, None),
        (5, HistoryQuality.LIMITED, "3", None),
        (19, HistoryQuality.LIMITED, "10", None),
        (20, HistoryQuality.SUFFICIENT, "10.5", 50.0),
    ],
)
def test_amount_history_thresholds(
    service_builder,
    number: int,
    quality: HistoryQuality,
    median: str | None,
    percentile: float | None,
) -> None:
    selected = selected_transaction(amount_paid=Decimal("10.005"))
    different_currency = transaction(
        900,
        datetime(2025, 1, 31),
        to_bank="USD Bank",
        to_account="A000900",
        amount_paid="999999.99",
        payment_currency="USD",
    )
    service, _, _ = service_builder(
        selected=selected,
        history=[*_amount_history(number), different_currency],
    )

    evidence = service.get_amount_history_evidence("demo-01")
    facts = evidence.facts

    assert isinstance(facts, AmountHistoryFacts)
    assert facts.sample_size == number
    assert facts.history_quality is quality
    assert facts.historical_median == median
    assert facts.empirical_percentile == percentile
    assert facts.selected_amount == "10.005"
    assert different_currency["transaction_ref"] not in evidence.supporting_transaction_refs
    assert len(evidence.supporting_transaction_refs) == number


def test_amount_median_uses_decimal_semantics(service_builder) -> None:
    history = [
        transaction(
            index,
            datetime(2025, 1, index),
            to_bank=f"Bank {index}",
            to_account=f"A{index:06d}",
            amount_paid=amount,
        )
        for index, amount in enumerate(
            ["0.1", "0.2", "0.3", "0.4", "0.5"], start=1
        )
    ]
    service, _, _ = service_builder(history=history)

    facts = service.get_amount_history_evidence("demo-01").facts

    assert isinstance(facts, AmountHistoryFacts)
    assert facts.historical_median == "0.3"


def test_counterparty_history_uses_bank_and_account(service_builder) -> None:
    exact_early = transaction(1, datetime(2025, 1, 1))
    exact_late = transaction(2, datetime(2025, 1, 20))
    same_account_other_bank = transaction(
        3,
        datetime(2025, 1, 10),
        to_bank="Different Receiver Bank",
        to_account="A013644",
    )
    service, _, _ = service_builder(
        history=[exact_late, same_account_other_bank, exact_early]
    )

    evidence = service.get_counterparty_history_evidence("demo-01")
    facts = evidence.facts

    assert isinstance(facts, CounterpartyHistoryFacts)
    assert facts.seen_before is True
    assert facts.previous_interaction_count == 2
    assert facts.first_previous_timestamp == "2025-01-01T00:00:00.000000"
    assert facts.most_recent_previous_timestamp == "2025-01-20T00:00:00.000000"
    assert evidence.supporting_transaction_refs == [
        exact_early["transaction_ref"],
        exact_late["transaction_ref"],
    ]


def test_counterparty_history_zero_is_valid_evidence(service_builder) -> None:
    other = transaction(
        1,
        datetime(2025, 1, 1),
        to_bank="Other Bank",
        to_account="A000001",
    )
    service, _, _ = service_builder(history=[other])

    facts = service.get_counterparty_history_evidence("demo-01").facts

    assert isinstance(facts, CounterpartyHistoryFacts)
    assert facts.seen_before is False
    assert facts.previous_interaction_count == 0
    assert facts.first_previous_timestamp is None
    assert facts.most_recent_previous_timestamp is None


def test_currency_history_dimensions_use_prior_sender_outgoing_only(service_builder) -> None:
    cny_usd = transaction(1, datetime(2025, 1, 1))
    usd_eur = transaction(
        2,
        datetime(2025, 1, 2),
        to_bank="EUR Bank",
        to_account="A000002",
        payment_currency="USD",
        receiving_currency="EUR",
    )
    incoming = transaction(
        3,
        datetime(2025, 1, 3),
        from_bank="Incoming Bank",
        from_account="A000003",
        to_bank="Sender Bank",
        to_account="A016568",
        payment_currency="CNY",
        receiving_currency="USD",
    )
    service, _, _ = service_builder(
        history=[cny_usd, usd_eur], other_transactions=[incoming]
    )

    payment = service.get_currency_history_evidence(
        "demo-01", CurrencyDimension.PAYMENT, "CNY"
    )
    receiving = service.get_currency_history_evidence(
        "demo-01", CurrencyDimension.RECEIVING, "EUR"
    )

    assert isinstance(payment.facts, CurrencyHistoryFacts)
    assert payment.facts.previous_count == 1
    assert payment.supporting_transaction_refs == [cny_usd["transaction_ref"]]
    assert isinstance(receiving.facts, CurrencyHistoryFacts)
    assert receiving.facts.previous_count == 1
    assert receiving.supporting_transaction_refs == [usd_eur["transaction_ref"]]
    assert incoming["transaction_ref"] not in payment.supporting_transaction_refs


@pytest.mark.parametrize(
    ("dimension", "currency"),
    [("incoming", "CNY"), ("payment", "cny"), ("payment", "USDD"), ("payment", "U1D")],
)
def test_currency_history_rejects_invalid_parameters(
    service_builder, dimension: str, currency: str
) -> None:
    service, _, _ = service_builder()

    with pytest.raises(DomainInputError):
        service.get_currency_history_evidence("demo-01", dimension, currency)


def test_region_history_seen_supports_only_matching_region(service_builder) -> None:
    matching_region = transaction(
        1,
        datetime(2025, 1, 1),
        to_bank="Region Four Bank",
        to_account="A000024",
    )
    other_region = transaction(
        2,
        datetime(2025, 1, 2),
        to_bank="Region Five Bank",
        to_account="A000025",
    )
    service, _, _ = service_builder(history=[matching_region, other_region])

    evidence = service.get_region_history_evidence("demo-01")
    facts = evidence.facts

    assert isinstance(facts, RegionHistoryFacts)
    assert facts.sender_region == 8
    assert facts.receiver_region == 4
    assert facts.region_relationship.value == "cross_region"
    assert facts.receiver_region_seen_before is True
    assert facts.previous_receiver_region_count == 1
    assert evidence.supporting_transaction_refs == [matching_region["transaction_ref"]]


def test_region_history_unseen_and_same_region_selected(service_builder) -> None:
    selected = selected_transaction(to_account="A000008")
    history = transaction(
        1,
        datetime(2025, 1, 1),
        to_bank="Region Five Bank",
        to_account="A000005",
    )
    service, _, _ = service_builder(selected=selected, history=[history])

    facts = service.get_region_history_evidence("demo-01").facts

    assert isinstance(facts, RegionHistoryFacts)
    assert facts.region_relationship.value == "same_region"
    assert facts.receiver_region_seen_before is False
    assert facts.previous_receiver_region_count == 0


def test_all_evidence_ids_resolve_with_complete_support(service_builder) -> None:
    history = [
        transaction(1, datetime(2025, 1, 1)),
        transaction(
            2,
            datetime(2025, 1, 2),
            to_bank="Other Bank",
            to_account="A000002",
            receiving_currency="EUR",
        ),
    ]
    service, _, _ = service_builder(history=history)
    evidence_items = [
        service.get_selected_transaction_evidence("demo-01"),
        service.get_sender_history_evidence("demo-01"),
        service.get_amount_history_evidence("demo-01"),
        service.get_counterparty_history_evidence("demo-01"),
        service.get_region_history_evidence("demo-01"),
        service.get_currency_history_evidence("demo-01", "payment", "CNY"),
        service.get_currency_history_evidence("demo-01", "receiving", "EUR"),
    ]

    for evidence in evidence_items:
        assert service.resolve_evidence(evidence.evidence_id) == evidence
    sender_facts = evidence_items[1].facts
    assert isinstance(sender_facts, SenderHistoryFacts)
    assert sender_facts.prior_outgoing_count == 2
    assert evidence_items[1].supporting_transaction_refs == [txref(1), txref(2)]


@pytest.mark.parametrize(
    "evidence_id",
    [
        "ev:demo-01:unknown",
        "ev:demo-01:currency:incoming:CNY",
        "ev:demo-01:currency:payment:cny",
        "ev:DEMO:sender-history",
        "database-row-1",
    ],
)
def test_unknown_or_wrong_evidence_id_is_rejected(
    service_builder, evidence_id: str
) -> None:
    service, _, _ = service_builder()

    with pytest.raises(EvidenceResolutionError):
        service.resolve_evidence(evidence_id)


def test_currency_evidence_resolution_verifies_exact_parameterization(
    service_builder, monkeypatch
) -> None:
    service, _, _ = service_builder()
    usd_evidence = service.get_currency_history_evidence(
        "demo-01", "payment", "USD"
    )

    def return_wrong_currency(_case_ref, _dimension, _currency):
        return usd_evidence

    monkeypatch.setattr(
        service, "get_currency_history_evidence", return_wrong_currency
    )
    with pytest.raises(EvidenceResolutionError, match="does not match"):
        service.resolve_evidence("ev:demo-01:currency:payment:CNY")


def test_workspace_is_evidence_backed_sorted_and_json_safe(service_builder) -> None:
    same_time_2 = transaction(2, datetime(2025, 1, 10), amount_paid="2.00")
    newest = transaction(3, datetime(2025, 1, 20), amount_paid="3.00")
    same_time_1 = transaction(1, datetime(2025, 1, 10), amount_paid="1.00")
    service, _, _ = service_builder(history=[same_time_2, newest, same_time_1])

    workspace = service.get_workspace("demo-01")
    sender_evidence = service.get_sender_history_evidence("demo-01")
    amount_evidence = service.get_amount_history_evidence("demo-01")
    counterparty_evidence = service.get_counterparty_history_evidence("demo-01")
    region_evidence = service.get_region_history_evidence("demo-01")
    payload = workspace.model_dump(mode="json")
    encoded = json.dumps(payload)

    assert [row.transaction_ref for row in workspace.historical_transactions] == [
        txref(3),
        txref(1),
        txref(2),
    ]
    assert workspace.sender_history.evidence_id == sender_evidence.evidence_id
    assert workspace.amount_history.evidence_id == amount_evidence.evidence_id
    assert workspace.counterparty_history.evidence_id == counterparty_evidence.evidence_id
    assert workspace.region_history is not None
    assert workspace.region_history.evidence_id == region_evidence.evidence_id
    assert isinstance(payload["selected_transaction"]["amount_paid"], str)
    assert all(
        isinstance(row["amount_paid"], str)
        for row in payload["historical_transactions"]
    )
    assert "Is Laundering" not in encoded
    assert "age" not in encoded
    assert "risk" not in encoded
    assert "suspicious" not in encoded
