from __future__ import annotations

import base64
import hashlib
import json
from datetime import timedelta

import pytest

from trailsight_v2.domain.evidence import decode_evidence_id, encode_evidence_id
from trailsight_v2.domain.errors import InvalidContextError, InvalidInputError
from trailsight_v2.domain.models import (
    ContextIdentityV2,
    ContextKind,
    EvidenceIdentityV2,
    EvidenceType,
    SubjectType,
)

from .conftest import AlertSpec, S1, SELECTED_TIME, TxSpec, selected_tx, txref


def _history(n: int) -> list[TxSpec]:
    return [
        TxSpec(
            txref(i + 1),
            SELECTED_TIME - timedelta(minutes=i + 1),
            "B1",
            "ROOT",
            f"B{i+10}",
            f"CP{i}",
            amount_paid=str(i + 1),
            payment_currency="USD",
            amount_received=str(i + 1),
            receiving_currency="USD",
        )
        for i in range(n)
    ]


def _all_evidence_ids(service, alert_ref: str, selected_ref: str, root_ref: str) -> dict[EvidenceType, str]:
    alert = service.get_alert_context(alert_ref)
    transaction = service.get_transaction_detail(selected_ref)
    account = service.get_account_detail(root_ref, origin_ref=selected_ref)
    ids = list(alert.evidence_ids) + list(transaction.evidence_ids) + list(transaction.indicators.evidence_ids) + list(account.evidence_ids)
    result: dict[EvidenceType, str] = {}
    for evidence_id in ids:
        decoded = decode_evidence_id(evidence_id)
        result.setdefault(decoded.evidence_type, evidence_id)
    source_id = result[EvidenceType.ACCOUNT_ACTIVITY]
    support = service.get_supporting_evidence(source_id)
    result[EvidenceType.SUPPORTING_TRANSACTIONS] = support.evidence_id
    return result


def test_all_frozen_evidence_types_resolve_recompute_and_regenerate(service_factory, root_ref) -> None:
    selected = selected_tx()
    alert = AlertSpec("alert_evidence", root_ref)
    service = service_factory(_history(20) + [selected], alerts=[alert])
    ids = _all_evidence_ids(service, alert.ref, selected.ref, root_ref)
    assert set(ids) == set(EvidenceType)
    for evidence_type, evidence_id in ids.items():
        identity = decode_evidence_id(evidence_id)
        assert identity.evidence_type is evidence_type
        assert encode_evidence_id(identity) == evidence_id
        evidence = service.resolve_evidence(evidence_id)
        assert evidence.evidence_id == evidence_id
        assert evidence.context_identity == identity.context_identity
        assert evidence.parameters == identity.parameters
        display = service.display_evidence(evidence_id)
        assert display.evidence_id == evidence_id
        assert len(display.supporting_transactions) <= 50
        serialized = evidence.model_dump_json()
        assert "Is Laundering" not in serialized
        assert "pattern_label" not in serialized.lower()


def test_evidence_id_is_stable_self_describing_url_safe_and_parameterized(service_factory, root_ref) -> None:
    selected = selected_tx()
    service = service_factory(_history(5) + [selected])
    detail1 = service.get_transaction_detail(selected.ref)
    detail2 = service.get_transaction_detail(selected.ref)
    assert detail1.indicators.evidence_ids == detail2.indicators.evidence_ids
    amount_ids = [
        eid
        for eid in detail1.indicators.evidence_ids
        if decode_evidence_id(eid).evidence_type is EvidenceType.AMOUNT_BEHAVIOR
    ]
    assert len(amount_ids) == 2
    sides = {decode_evidence_id(eid).parameters["side"] for eid in amount_ids}
    assert sides == {"SENDER_PAID", "RECEIVER_RECEIVED"}
    assert all(eid.startswith("ev2.") and "+" not in eid and "/" not in eid and "=" not in eid for eid in amount_ids)


def test_tamper_checksum_unknown_type_and_noncanonical_json_rejected(service_factory, root_ref) -> None:
    selected = selected_tx()
    service = service_factory([selected])
    evidence_id = service.get_transaction_detail(selected.ref).evidence_ids[0]
    prefix, payload, checksum = evidence_id.split(".")
    tampered = f"{prefix}.{payload[:-1]}{'A' if payload[-1] != 'A' else 'B'}.{checksum}"
    with pytest.raises(InvalidInputError):
        service.resolve_evidence(tampered)

    decoded_bytes = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    obj = json.loads(decoded_bytes)
    obj["evidence_type"] = "NOT_A_REAL_TYPE"
    unknown_bytes = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    unknown_payload = base64.urlsafe_b64encode(unknown_bytes).decode().rstrip("=")
    unknown_checksum = base64.urlsafe_b64encode(hashlib.sha256(unknown_bytes).digest()).decode().rstrip("=")
    with pytest.raises(InvalidInputError):
        service.resolve_evidence(f"ev2.{unknown_payload}.{unknown_checksum}")

    # Valid JSON/checksum but intentionally non-canonical whitespace.
    noncanonical_bytes = json.dumps(json.loads(decoded_bytes), sort_keys=True, indent=1).encode()
    noncanonical_payload = base64.urlsafe_b64encode(noncanonical_bytes).decode().rstrip("=")
    noncanonical_checksum = base64.urlsafe_b64encode(hashlib.sha256(noncanonical_bytes).digest()).decode().rstrip("=")
    with pytest.raises(InvalidInputError):
        service.resolve_evidence(f"ev2.{noncanonical_payload}.{noncanonical_checksum}")


def test_cross_context_and_future_context_evidence_rejected(service_factory, root_ref) -> None:
    selected = selected_tx()
    service = service_factory([selected])
    valid = service.get_account_detail(root_ref, origin_ref=selected.ref).evidence_ids[0]
    identity = decode_evidence_id(valid)
    wrong_context = ContextIdentityV2(
        context_kind=ContextKind.TRANSACTION,
        context_ref=selected.ref,
        context_time="2025-01-02T12:00:01",
        snapshot_id="snap_1",
    )
    forged = encode_evidence_id(
        EvidenceIdentityV2(
            evidence_type=identity.evidence_type,
            subject_type=identity.subject_type,
            subject_ref=identity.subject_ref,
            context_identity=wrong_context,
            parameters=identity.parameters,
        )
    )
    with pytest.raises(InvalidContextError):
        service.resolve_evidence(forged)


def test_support_count_exact_refs_max50_and_truncated(service_factory, root_ref) -> None:
    selected = selected_tx()
    service = service_factory(_history(60) + [selected])
    account = service.get_account_detail(root_ref, origin_ref=selected.ref)
    activity_id = next(
        eid for eid in account.evidence_ids if decode_evidence_id(eid).evidence_type is EvidenceType.ACCOUNT_ACTIVITY
    )
    evidence = service.resolve_evidence(activity_id)
    assert evidence.supporting_transaction_count == 60
    assert len(evidence.supporting_transaction_refs) == 50
    assert evidence.support_truncated is True
    display = service.get_supporting_evidence(activity_id)
    assert display.evidence_type is EvidenceType.SUPPORTING_TRANSACTIONS
    assert display.supporting_transaction_count == 60
    assert len(display.supporting_transactions) == 50
    assert display.support_truncated is True


def test_detector_evidence_reuses_persisted_values_without_transaction_support(service_factory, root_ref) -> None:
    selected = selected_tx()
    service = service_factory([selected])
    account = service.get_account_detail(root_ref, origin_ref=selected.ref)
    detector_id = next(
        eid
        for eid in account.evidence_ids
        if decode_evidence_id(eid).evidence_type is EvidenceType.DETECTOR_STATE
    )

    evidence = service.resolve_evidence(detector_id)

    assert account.detector_support is not None

    assert (
        evidence.facts.network_pattern_score
        == account.network_review_state.network_pattern_score
        == 0.987654321
    )
    assert evidence.facts.rank == 2
    assert evidence.facts.eligible_account_count > 0
    assert evidence.facts.percentile == 98.7654321
    assert evidence.facts.network_review_band.value == "HIGH"

    assert (
        evidence.facts.first_order_neighbor_count
        == account.detector_support.first_order_neighbor_count
        == 11
    )
    assert (
        evidence.facts.second_order_neighbor_count
        == account.detector_support.second_order_neighbor_count
        == 22
    )
    assert (
        evidence.facts.block_measure_1
        == account.detector_support.block_measure_1
        == 1.1
    )
    assert (
        evidence.facts.block_measure_2
        == account.detector_support.block_measure_2
        == 2.2
    )
    assert (
        evidence.facts.block_measure_3
        == account.detector_support.block_measure_3
        == 3.3
    )

    display = service.display_evidence(detector_id)

    assert display.facts["first_order_neighbor_count"] == 11
    assert display.facts["second_order_neighbor_count"] == 22
    assert display.facts["block_measure_1"] == 1.1
    assert display.facts["block_measure_2"] == 2.2
    assert display.facts["block_measure_3"] == 3.3
    assert display.facts["network_pattern_score"] == 0.987654321

    assert evidence.supporting_transaction_count == 0
    assert evidence.supporting_transaction_refs == ()
