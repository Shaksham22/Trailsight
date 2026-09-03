"""Build a compact deterministic investigation packet for one V2 AI run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from pydantic import BaseModel

from trailsight_v2.domain.errors import InvalidContextError
from trailsight_v2.domain.models import (
    AccountDetailV2,
    AccountNetworkV2,
    EvidenceType,
    InvestigationContextV2,
    SubjectType,
    SupportingTransactionV2,
    TransactionDetailV2,
)
from trailsight_v2.domain.service import InvestigationServiceV2


MAX_ACTIVITY_BUCKETS = 60
MAX_NETWORK_RELATIONSHIPS = 12
MAX_BANK_COUNTRY_FLOWS = 24
MAX_SUPPORTING_TRANSACTIONS = 12
MAX_ALERT_HISTORY_ITEMS = 20


class AlertReviewStateReader(Protocol):
    def get_alert_review_status(self, alert_ref: str): ...


@dataclass(frozen=True, slots=True)
class SeedContextV2:
    context: InvestigationContextV2
    seed_evidence_ids: tuple[str, ...]
    model_summary: dict[str, Any]


def resolve_seed_context(
    service: InvestigationServiceV2,
    runtime_state_store: AlertReviewStateReader,
    *,
    subject_type: SubjectType,
    subject_ref: str,
    origin_alert_ref: str | None = None,
    origin_transaction_ref: str | None = None,
) -> SeedContextV2:
    """Resolve one point-in-time context and project its existing bounded detail data."""
    origin_ref = _origin_ref(origin_alert_ref, origin_transaction_ref)
    context = service.resolve_context(subject_type, subject_ref, origin_ref)

    if subject_type is SubjectType.TRANSACTION:
        packet, evidence_ids = _transaction_packet(service, subject_ref, context)
    else:
        packet, evidence_ids = _account_or_alert_packet(
            service,
            runtime_state_store,
            subject_type=subject_type,
            subject_ref=subject_ref,
            origin_ref=origin_ref,
            context=context,
        )

    ordered_ids = tuple(dict.fromkeys(evidence_ids))
    packet["evidence_catalog"] = _evidence_catalog(service, ordered_ids)
    packet["packet_bounds"] = {
        "activity_buckets": MAX_ACTIVITY_BUCKETS,
        "network_relationships_per_account": MAX_NETWORK_RELATIONSHIPS,
        "bank_country_flows": MAX_BANK_COUNTRY_FLOWS,
        "supporting_transactions": MAX_SUPPORTING_TRANSACTIONS,
        "alert_history_items": MAX_ALERT_HISTORY_ITEMS,
    }
    return SeedContextV2(context, ordered_ids, packet)


def _account_or_alert_packet(
    service: InvestigationServiceV2,
    runtime_state_store: AlertReviewStateReader,
    *,
    subject_type: SubjectType,
    subject_ref: str,
    origin_ref: str | None,
    context: InvestigationContextV2,
) -> tuple[dict[str, Any], list[str]]:
    alert_packet: dict[str, Any] | None = None
    if subject_type is SubjectType.ALERT:
        alert = service.get_alert_context(subject_ref)
        _require_context(alert.context, context)
        account_ref = alert.account_identity.account_ref
        review_status = runtime_state_store.get_alert_review_status(subject_ref)
        alert_packet = {
            **_json(alert.alert),
            "review_status": getattr(review_status, "value", str(review_status)),
        }
        evidence_ids = list(alert.evidence_ids)
        account_origin = subject_ref
    else:
        account_ref = subject_ref
        evidence_ids = []
        account_origin = origin_ref

    detail = service.get_account_detail(account_ref, origin_ref=account_origin)
    _require_context(detail.context, context)
    network = service.get_account_network(account_ref, context=context)
    behavior = service.get_behavioral_indicators(
        subject_type,
        subject_ref,
        context=context,
        account_ref=account_ref,
    )
    evidence_ids.extend(detail.evidence_ids)
    evidence_ids.extend(behavior.evidence_ids)
    detector_facts = _detector_facts(service, detail.evidence_ids)
    supporting = _supporting_packet(service, evidence_ids)

    packet: dict[str, Any] = {
        "packet_version": "investigation-packet-v1",
        "subject_type": subject_type.value,
        "subject_ref": subject_ref,
        "context": _json(context),
        "detector_semantics": _detector_semantics(),
        "account_investigation": _account_projection(
            detail,
            network=network,
            detector_facts=detector_facts,
            include_timeline=True,
        ),
        "behavioral_context": _json(behavior),
        "supporting_transactions": supporting,
    }
    if alert_packet is not None:
        packet["alert"] = alert_packet
    return packet, evidence_ids


def _transaction_packet(
    service: InvestigationServiceV2,
    transaction_ref: str,
    context: InvestigationContextV2,
) -> tuple[dict[str, Any], list[str]]:
    detail = service.get_transaction_detail(transaction_ref)
    _require_context(detail.context, context)
    facts = detail.transaction_facts
    endpoint_details = [
        service.get_account_detail(facts.sender.account_ref, origin_ref=transaction_ref),
        service.get_account_detail(facts.receiver.account_ref, origin_ref=transaction_ref),
    ]
    for endpoint in endpoint_details:
        _require_context(endpoint.context, context)

    evidence_ids = [*detail.evidence_ids, *detail.indicators.evidence_ids]
    evidence_ids.extend(item.evidence_id for item in detail.supporting_evidence_summary)
    evidence_ids.extend(
        evidence_id
        for endpoint in endpoint_details
        for evidence_id in endpoint.evidence_ids
    )
    network_by_ref = {
        item.root.account_ref: item
        for item in (
            detail.local_network_summary.sender,
            detail.local_network_summary.receiver,
        )
        if item is not None
    }
    endpoints = [
        _account_projection(
            endpoint,
            network=network_by_ref.get(endpoint.account_identity.account_ref),
            detector_facts=_detector_facts(service, endpoint.evidence_ids),
            include_timeline=False,
        )
        for endpoint in endpoint_details
    ]

    return (
        {
            "packet_version": "investigation-packet-v1",
            "subject_type": SubjectType.TRANSACTION.value,
            "subject_ref": transaction_ref,
            "context": _json(context),
            "detector_semantics": _detector_semantics(),
            "transaction": _json(facts),
            "transaction_review_priority": _json(detail.review_state),
            "bank_country_route": _json(detail.bank_country_route),
            "historical_context": {
                "amount_behavior": [
                    _json(item)
                    for item in (
                        detail.indicators.sender_amount_behavior,
                        detail.indicators.receiver_amount_behavior,
                    )
                    if item is not None
                ],
                "relationship": _json(detail.indicators.counterparty_relationship),
                "account_network_behavior": _json(
                    detail.indicators.account_network_behavior
                ),
                "cross_currency": _json(detail.indicators.cross_currency),
                "activity_window": _activity_context_projection(detail),
            },
            "endpoint_accounts": endpoints,
            "visible_investigation_indicators": [
                _json(item) for item in detail.investigation_indicators
            ],
            "supporting_transactions": _transaction_detail_supporting_packet(detail),
        },
        evidence_ids,
    )


def _account_projection(
    detail: AccountDetailV2,
    *,
    network: AccountNetworkV2 | None,
    detector_facts: dict[str, Any],
    include_timeline: bool,
) -> dict[str, Any]:
    activity = detail.observed_activity
    timeline = list(detail.activity_over_time)
    shown_timeline = timeline[-MAX_ACTIVITY_BUCKETS:]
    flows = list(detail.bank_country_flows)
    result: dict[str, Any] = {
        "account": {
            "account_ref": detail.account_identity.account_ref,
            "bank_id": detail.account_identity.bank_id,
            "account_id": detail.account_identity.account_id,
            "bank_country": detail.account_identity.bank_country.country_name,
            "bank_country_note": "Bank metadata only; not customer geography.",
        },
        "detector": {
            **_json(detail.network_review_state),
            "detector_cutoff": detail.context.detector_cutoff,
            "eligible_account_count": detector_facts.get("eligible_account_count"),
            "structural_support": _json(detail.detector_support),
        },
        "activity": {
            **_json(activity),
            "total_transaction_count": activity.incoming_count + activity.outgoing_count,
            "currency_activity": [_json(item) for item in detail.currency_activity],
        },
        "network": _network_projection(network),
        "bank_country_flows": {
            "total": len(flows),
            "shown": min(len(flows), MAX_BANK_COUNTRY_FLOWS),
            "truncated": len(flows) > MAX_BANK_COUNTRY_FLOWS,
            "items": [_json(item) for item in flows[:MAX_BANK_COUNTRY_FLOWS]],
            "metadata_note": "Countries identify banks, not customers.",
        },
        "alert_history": {
            "total": detail.alert_history_total,
            "shown": min(len(detail.alert_history), MAX_ALERT_HISTORY_ITEMS),
            "truncated": (
                detail.alert_history_truncated
                or len(detail.alert_history) > MAX_ALERT_HISTORY_ITEMS
            ),
            "items": [
                _json(item) for item in detail.alert_history[:MAX_ALERT_HISTORY_ITEMS]
            ],
        },
    }
    if include_timeline:
        result["activity_over_time"] = {
            "total_buckets": len(timeline),
            "shown_buckets": len(shown_timeline),
            "truncated": len(timeline) > len(shown_timeline),
            "items": [_json(item) for item in shown_timeline],
        }
    return result


def _network_projection(network: AccountNetworkV2 | None) -> dict[str, Any] | None:
    if network is None:
        return None
    relationships = list(network.relationships)
    shown = relationships[:MAX_NETWORK_RELATIONSHIPS]
    return {
        "total_direct_counterparties": network.total_direct_counterparties,
        "shown_counterparties": len(shown),
        "truncated": network.total_direct_counterparties > len(shown),
        "selection_rule_version": network.selection_rule_version,
        "relationships": [
            {
                "counterparty": {
                    "account_ref": item.counterparty.account_ref,
                    "bank_id": item.counterparty.bank_id,
                    "account_id": item.counterparty.account_id,
                    "bank_country": item.counterparty.bank_country.country_name,
                },
                "incoming_count": item.incoming_count,
                "outgoing_count": item.outgoing_count,
                "total_count": item.total_count,
                "first_historical_timestamp": item.first_historical_timestamp,
                "last_historical_timestamp": item.last_historical_timestamp,
                "selected_relationship": item.selected_relationship,
            }
            for item in shown
        ],
    }


def _supporting_packet(
    service: InvestigationServiceV2,
    evidence_ids: Iterable[str],
) -> dict[str, Any]:
    source_summaries: list[dict[str, Any]] = []
    transactions: list[SupportingTransactionV2] = []
    seen_transactions: set[str] = set()
    for evidence_id in dict.fromkeys(evidence_ids):
        display = service.display_evidence(evidence_id)
        source_summaries.append(
            {
                "evidence_id": evidence_id,
                "evidence_type": display.evidence_type.value,
                "supporting_transaction_count": display.supporting_transaction_count,
                "support_truncated": display.support_truncated,
            }
        )
        for transaction in display.supporting_transactions:
            if transaction.transaction_ref in seen_transactions:
                continue
            seen_transactions.add(transaction.transaction_ref)
            transactions.append(transaction)
            if len(transactions) >= MAX_SUPPORTING_TRANSACTIONS:
                break
        if len(transactions) >= MAX_SUPPORTING_TRANSACTIONS:
            break
    return {
        "sources": source_summaries,
        "shown_transactions": len(transactions),
        "truncated": any(
            item["supporting_transaction_count"] > len(transactions)
            or item["support_truncated"]
            for item in source_summaries
        ),
        "transactions": [_supporting_transaction_projection(item) for item in transactions],
    }


def _transaction_detail_supporting_packet(detail: TransactionDetailV2) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    transactions: list[SupportingTransactionV2] = []
    seen: set[str] = set()
    for item in detail.supporting_evidence_summary:
        sources.append(
            {
                "evidence_id": item.evidence_id,
                "evidence_type": item.evidence_type.value,
                "supporting_transaction_count": item.supporting_transaction_count,
                "support_truncated": item.support_truncated,
            }
        )
        for transaction in item.supporting_transactions:
            if transaction.transaction_ref in seen:
                continue
            seen.add(transaction.transaction_ref)
            transactions.append(transaction)
            if len(transactions) >= MAX_SUPPORTING_TRANSACTIONS:
                break
        if len(transactions) >= MAX_SUPPORTING_TRANSACTIONS:
            break
    return {
        "sources": sources,
        "shown_transactions": len(transactions),
        "truncated": any(item["support_truncated"] for item in sources)
        or sum(item["supporting_transaction_count"] for item in sources)
        > len(transactions),
        "transactions": [_supporting_transaction_projection(item) for item in transactions],
    }


def _activity_context_projection(detail: TransactionDetailV2) -> dict[str, Any]:
    buckets = list(detail.activity_context.buckets)
    shown = buckets[-MAX_ACTIVITY_BUCKETS:]
    return {
        "range_start": detail.activity_context.range_start,
        "range_end": detail.activity_context.range_end,
        "total_buckets": len(buckets),
        "shown_buckets": len(shown),
        "truncated": len(buckets) > len(shown),
        "items": [_json(item) for item in shown],
        "selected_transaction": _json(detail.activity_context.selected_transaction),
    }


def _supporting_transaction_projection(item: SupportingTransactionV2) -> dict[str, Any]:
    return {
        "transaction_ref": item.transaction_ref,
        "transaction_timestamp": item.transaction_timestamp,
        "sender": {
            "account_ref": item.from_account_ref,
            "bank_id": item.from_bank_id,
            "account_id": item.from_account_id,
            "bank_country": item.from_bank_country.country_name,
        },
        "receiver": {
            "account_ref": item.to_account_ref,
            "bank_id": item.to_bank_id,
            "account_id": item.to_account_id,
            "bank_country": item.to_bank_country.country_name,
        },
        "amount_paid": item.amount_paid,
        "payment_currency": item.payment_currency,
        "amount_received": item.amount_received,
        "receiving_currency": item.receiving_currency,
        "payment_format": item.payment_format,
        "cross_currency": item.cross_currency,
    }


def _detector_facts(
    service: InvestigationServiceV2,
    evidence_ids: Iterable[str],
) -> dict[str, Any]:
    for evidence_id in evidence_ids:
        evidence = service.resolve_evidence(evidence_id)
        if evidence.evidence_type is EvidenceType.DETECTOR_STATE:
            return _json(evidence.facts)
    raise InvalidContextError("Detector evidence is missing from the investigation packet")


def _evidence_catalog(
    service: InvestigationServiceV2,
    evidence_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": evidence.evidence_id,
            "evidence_type": evidence.evidence_type.value,
            "subject_type": evidence.subject_type.value,
            "subject_ref": evidence.subject_ref,
        }
        for evidence_id in evidence_ids
        for evidence in (service.resolve_evidence(evidence_id),)
    ]


def _detector_semantics() -> dict[str, Any]:
    return {
        "account_review_bands": {
            "HIGH": "Top 1% of eligible accounts in the applicable historical GARG snapshot by Network Pattern Score ranking.",
            "MEDIUM": "Next 4% of eligible accounts in that snapshot.",
            "LOW": "Remaining eligible scored accounts in that snapshot; LOW does not mean safe or cleared.",
            "UNSCORED": "Insufficient valid network context for a score; UNSCORED does not mean safe.",
        },
        "account_signal": "A structural network-pattern review signal, not a laundering probability, verdict, or proof of suspicious activity.",
        "transaction_priority": "GARG does not directly score transactions. Transaction review priority is derived deterministically from the historical GARG review bands of its sender and receiver accounts.",
        "causality": "Only supplied GARG structural inputs/measures may be described as explaining the detector signal. Other transaction, currency, relationship, route, or activity facts are separate investigation context.",
    }


def _json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _origin_ref(
    origin_alert_ref: str | None,
    origin_transaction_ref: str | None,
) -> str | None:
    if origin_alert_ref is not None and origin_transaction_ref is not None:
        raise InvalidContextError("At most one historical account origin may be supplied")
    return origin_alert_ref or origin_transaction_ref


def _require_context(actual: InvestigationContextV2, expected: InvestigationContextV2) -> None:
    if actual.context_identity != expected.context_identity:
        raise InvalidContextError("Investigation packet facts do not match the resolved context")
