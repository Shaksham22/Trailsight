"""Build small deterministic seed context for one V2 AI run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from trailsight_v2.domain.errors import InvalidContextError
from trailsight_v2.domain.models import InvestigationContextV2, SubjectType
from trailsight_v2.domain.service import InvestigationServiceV2


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
    origin_ref = _origin_ref(origin_alert_ref, origin_transaction_ref)
    context = service.resolve_context(subject_type, subject_ref, origin_ref)

    if subject_type is SubjectType.ALERT:
        detail = service.get_alert_context(subject_ref)
        _require_context(detail.context, context)
        review_status = runtime_state_store.get_alert_review_status(subject_ref)
        review_value = getattr(review_status, "value", str(review_status))
        summary = {
            "subject_type": subject_type.value,
            "subject_ref": subject_ref,
            "account": {
                "account_ref": detail.account_identity.account_ref,
                "bank_id": detail.account_identity.bank_id,
                "account_id": detail.account_identity.account_id,
                "bank_country": detail.account_identity.bank_country.country_name,
            },
            "alert": {
                "alert_ref": detail.alert.alert_ref,
                "entry_snapshot_id": detail.alert.entry_snapshot_id,
                "entry_cutoff": detail.alert.entry_cutoff,
                "reason": detail.alert.reason_code,
                "review_status": review_value,
            },
            "detector": {
                "network_review_band": detail.detector_state.network_review_band.value,
                "network_pattern_score": detail.detector_state.network_pattern_score,
                "rank": detail.detector_state.rank,
                "percentile": detail.detector_state.percentile,
                "detector_cutoff": detail.context.detector_cutoff,
            },
            "seed_evidence_ids": list(detail.evidence_ids),
        }
        return SeedContextV2(context, detail.evidence_ids, summary)

    if subject_type is SubjectType.TRANSACTION:
        detail = service.get_transaction_detail(subject_ref)
        _require_context(detail.context, context)
        facts = detail.transaction_facts
        review = detail.review_state
        route = detail.bank_country_route
        summary = {
            "subject_type": subject_type.value,
            "subject_ref": subject_ref,
            "transaction": {
                "timestamp": facts.transaction_timestamp,
                "sender": {
                    "account_ref": facts.sender.account_ref,
                    "bank_id": facts.sender.bank_id,
                    "account_id": facts.sender.account_id,
                },
                "receiver": {
                    "account_ref": facts.receiver.account_ref,
                    "bank_id": facts.receiver.bank_id,
                    "account_id": facts.receiver.account_id,
                },
                "amount_paid": facts.amount_paid,
                "payment_currency": facts.payment_currency,
                "amount_received": facts.amount_received,
                "receiving_currency": facts.receiving_currency,
                "payment_format": facts.payment_format,
                "cross_currency": facts.cross_currency,
            },
            "priority": {
                "aml_review_priority": review.aml_review_priority.value,
                "sender_band": review.sender_band.value,
                "receiver_band": review.receiver_band.value,
                "detector_cutoff": review.detector_cutoff,
                "derivation_text": review.derivation_text,
            },
            "bank_country_route": {
                "sending_bank_country": route.sending_bank.country_name,
                "receiving_bank_country": route.receiving_bank.country_name,
                "same_bank_country": route.same_bank_country,
                "mapping_version": route.mapping_version,
            },
            "seed_evidence_ids": list(detail.evidence_ids),
        }
        return SeedContextV2(context, detail.evidence_ids, summary)

    detail = service.get_account_detail(subject_ref, origin_ref=origin_ref)
    _require_context(detail.context, context)
    state = detail.network_review_state
    activity = detail.observed_activity
    summary = {
        "subject_type": subject_type.value,
        "subject_ref": subject_ref,
        "account": {
            "account_ref": detail.account_identity.account_ref,
            "bank_id": detail.account_identity.bank_id,
            "account_id": detail.account_identity.account_id,
            "bank_country": detail.account_identity.bank_country.country_name,
        },
        "detector": {
            "network_review_band": state.network_review_band.value,
            "network_pattern_score": state.network_pattern_score,
            "rank": state.rank,
            "percentile": state.percentile,
            "unscored_reason": state.unscored_reason,
            "snapshot_id": state.snapshot_id,
            "detector_cutoff": detail.context.detector_cutoff,
        },
        "observed_activity": {
            "incoming_count": activity.incoming_count,
            "outgoing_count": activity.outgoing_count,
            "distinct_counterparties": activity.distinct_counterparties,
            "first_observed": activity.first_observed_timestamp,
            "most_recent_observed": activity.most_recent_observed_timestamp,
        },
        "seed_evidence_ids": list(detail.evidence_ids),
    }
    return SeedContextV2(context, detail.evidence_ids, summary)


def _origin_ref(
    origin_alert_ref: str | None,
    origin_transaction_ref: str | None,
) -> str | None:
    if origin_alert_ref is not None and origin_transaction_ref is not None:
        raise InvalidContextError("At most one historical account origin may be supplied")
    return origin_alert_ref or origin_transaction_ref


def _require_context(actual: InvestigationContextV2, expected: InvestigationContextV2) -> None:
    if actual.context_identity != expected.context_identity:
        raise InvalidContextError("Seed facts do not match the resolved investigation context")
