from __future__ import annotations

import json

from trailsight_v2.ai.context import (
    MAX_ACTIVITY_BUCKETS,
    MAX_ALERT_HISTORY_ITEMS,
    MAX_BANK_COUNTRY_FLOWS,
    MAX_NETWORK_RELATIONSHIPS,
    MAX_SUPPORTING_TRANSACTIONS,
    resolve_seed_context,
)
from trailsight_v2.domain.models import EvidenceType, SubjectType

from .conftest import ReviewState


def _catalog_types(packet: dict) -> set[str]:
    return {item["evidence_type"] for item in packet["evidence_catalog"]}


def test_account_packet_contains_visible_detector_activity_network_and_support(ai_service) -> None:
    service, selected, _ = ai_service
    account_ref = service.get_transaction_detail(
        selected.ref
    ).transaction_facts.sender.account_ref
    seed = resolve_seed_context(
        service,
        ReviewState(),
        subject_type=SubjectType.ACCOUNT,
        subject_ref=account_ref,
    )
    packet = seed.model_summary
    investigation = packet["account_investigation"]
    detector = investigation["detector"]

    assert packet["packet_version"] == "investigation-packet-v1"
    assert detector["eligible_account_count"] > 0
    assert detector["network_pattern_score"] is not None
    assert detector["rank"] is not None
    assert detector["structural_support"] is not None
    assert investigation["activity"]["total_transaction_count"] >= 1
    assert investigation["network"]["total_direct_counterparties"] >= 1
    assert len(investigation["network"]["relationships"]) <= MAX_NETWORK_RELATIONSHIPS
    assert len(investigation["activity_over_time"]["items"]) <= MAX_ACTIVITY_BUCKETS
    assert len(investigation["bank_country_flows"]["items"]) <= MAX_BANK_COUNTRY_FLOWS
    assert len(investigation["alert_history"]["items"]) <= MAX_ALERT_HISTORY_ITEMS
    assert (
        len(packet["supporting_transactions"]["transactions"])
        <= MAX_SUPPORTING_TRANSACTIONS
    )
    assert {
        EvidenceType.DETECTOR_STATE.value,
        EvidenceType.ACCOUNT_ACTIVITY.value,
        EvidenceType.NETWORK_BEHAVIOR.value,
    } <= _catalog_types(packet)
    assert {item["evidence_id"] for item in packet["evidence_catalog"]} == set(
        seed.seed_evidence_ids
    )


def test_transaction_packet_contains_priority_history_endpoints_and_bounded_rows(ai_service) -> None:
    service, selected, _ = ai_service
    detail = service.get_transaction_detail(selected.ref)
    seed = resolve_seed_context(
        service,
        ReviewState(),
        subject_type=SubjectType.TRANSACTION,
        subject_ref=selected.ref,
    )
    packet = seed.model_summary

    assert packet["transaction"]["amount_paid"] == detail.transaction_facts.amount_paid
    assert packet["transaction_review_priority"]["aml_review_priority"] == (
        detail.review_state.aml_review_priority.value
    )
    assert packet["transaction_review_priority"]["sender_band"] == (
        detail.review_state.sender_band.value
    )
    assert packet["transaction_review_priority"]["receiver_band"] == (
        detail.review_state.receiver_band.value
    )
    assert len(packet["historical_context"]["amount_behavior"]) == 2
    assert packet["historical_context"]["relationship"] is not None
    assert (
        len(packet["historical_context"]["activity_window"]["items"])
        <= MAX_ACTIVITY_BUCKETS
    )
    assert len(packet["endpoint_accounts"]) == 2
    assert all(
        endpoint["detector"]["eligible_account_count"] > 0
        for endpoint in packet["endpoint_accounts"]
    )
    assert (
        len(packet["supporting_transactions"]["transactions"])
        <= MAX_SUPPORTING_TRANSACTIONS
    )
    assert {
        EvidenceType.TRANSACTION_FACTS.value,
        EvidenceType.TRANSACTION_PRIORITY.value,
        EvidenceType.BANK_COUNTRY_ROUTE.value,
        EvidenceType.AMOUNT_BEHAVIOR.value,
        EvidenceType.COUNTERPARTY_RELATIONSHIP.value,
        EvidenceType.CURRENCY_BEHAVIOR.value,
        EvidenceType.NETWORK_BEHAVIOR.value,
        EvidenceType.DETECTOR_STATE.value,
    } <= _catalog_types(packet)


def test_packet_is_compact_and_hidden_ground_truth_is_absent(ai_service) -> None:
    service, selected, _ = ai_service
    seed = resolve_seed_context(
        service,
        ReviewState(),
        subject_type=SubjectType.TRANSACTION,
        subject_ref=selected.ref,
    )
    serialized = json.dumps(seed.model_summary, sort_keys=True).lower()

    assert len(serialized.encode("utf-8")) < 200_000
    assert "is laundering" not in serialized
    assert "pattern_label" not in serialized
    assert "patterns.txt" not in serialized
    assert "customer residence" not in serialized
