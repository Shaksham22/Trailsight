"""Fail-closed validation of model citations against WP03 Evidence V2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from trailsight_v2.domain.evidence import parse_canonical_timestamp
from trailsight_v2.domain.models import (
    DisplayEvidenceV2,
    EvidenceType,
    EvidenceV2,
    InvestigationContextV2,
    SubjectType,
)
from trailsight_v2.domain.service import InvestigationServiceV2

from .models import DisplayEvidenceItemV2, InvestigationOutputV2


class EvidenceValidationError(RuntimeError):
    """Any citation failure rejects the entire generated investigation output."""


_RUNTIME_SAFE_EVIDENCE_TYPES = frozenset(EvidenceType)
_OVERCLAIM_PATTERNS = (
    re.compile(
        r"\b(confirm(?:ed|s)?|prove(?:s|d)?|is|means?|indicates?|shows?|suggests?)\b"
        r".{0,36}\b(?:money\s+)?laundering\b",
        re.I,
    ),
    re.compile(
        r"\b(?:money\s+)?laundering\s+(?:probability|likelihood|chance)\b", re.I
    ),
    re.compile(
        r"\b(?:account|transaction|customer)\b.{0,36}"
        r"\b(?:launder(?:ed|ing)|criminal|fraudulent|guilty)\b",
        re.I,
    ),
    re.compile(
        r"\bhigh\b.{0,40}\b(?:laundering|criminal|guilty)\b"
        r"|\b(?:laundering|criminal|guilty)\b.{0,40}\bhigh\b",
        re.I,
    ),
)
_LOW_SAFE = re.compile(
    r"\blow\b.{0,40}\b(?:safe|cleared|benign|risk[- ]?free)\b"
    r"|\b(?:safe|cleared|benign|risk[- ]?free)\b.{0,40}\blow\b",
    re.I,
)
_CUSTOMER_GEO = re.compile(
    r"(?:\bcustomer\b.{0,50}\b(?:country|location|residence|lives|located|resides|nationality|geography)\b"
    r"|\bbank country\b.{0,50}\bcustomer\b)",
    re.I,
)
_UNAVAILABLE_FACT = re.compile(
    r"\b(?:source of funds|transaction purpose|purpose of (?:the )?(?:payment|transaction)|kyc|beneficial owner(?:ship)?)\b",
    re.I,
)
_HIDDEN_BENCHMARK = re.compile(
    r"\b(?:hidden benchmark|ground truth|pattern annotation|benchmark label)\b", re.I
)


@dataclass(frozen=True, slots=True)
class ValidatedOutputV2:
    output: InvestigationOutputV2
    display_evidence: tuple[DisplayEvidenceItemV2, ...]
    resolved_by_id: dict[str, EvidenceV2]


def validate_generated_output(
    *,
    output: InvestigationOutputV2,
    available_evidence_ids: set[str],
    authorized_transaction_refs: set[str],
    context: InvestigationContextV2,
    service: InvestigationServiceV2,
) -> ValidatedOutputV2:
    """Validate availability, integrity/recomputation, context, and safe finding language."""
    _validate_language(output)
    ordered_ids: list[str] = []
    for finding in output.findings:
        if not finding.evidence_ids:
            raise EvidenceValidationError("A finding did not cite evidence")
        for evidence_id in finding.evidence_ids:
            if evidence_id not in available_evidence_ids:
                raise EvidenceValidationError("A cited evidence ID was not issued in this run")
            if evidence_id not in ordered_ids:
                ordered_ids.append(evidence_id)

    resolved_by_id: dict[str, EvidenceV2] = {}
    display_items: list[DisplayEvidenceItemV2] = []
    for index, evidence_id in enumerate(ordered_ids, start=1):
        try:
            resolved = service.resolve_evidence(evidence_id)
        except Exception as exc:
            raise EvidenceValidationError(
                "A cited evidence ID failed Evidence V2 resolution"
            ) from exc
        if resolved.evidence_id != evidence_id:
            raise EvidenceValidationError("Resolved evidence identity did not match exactly")
        if resolved.evidence_type not in _RUNTIME_SAFE_EVIDENCE_TYPES:
            raise EvidenceValidationError("Evidence type is not runtime-safe")
        _validate_context_compatibility(
            resolved,
            context=context,
            authorized_transaction_refs=authorized_transaction_refs,
        )
        try:
            display = service.display_evidence(evidence_id)
        except Exception as exc:
            raise EvidenceValidationError("Display evidence could not be regenerated") from exc
        if display.evidence_id != evidence_id:
            raise EvidenceValidationError("Display evidence identity did not match exactly")
        resolved_by_id[evidence_id] = resolved
        display_items.append(DisplayEvidenceItemV2(label=f"E{index}", evidence=display))

    return ValidatedOutputV2(
        output=output,
        display_evidence=tuple(display_items),
        resolved_by_id=resolved_by_id,
    )


def _validate_context_compatibility(
    evidence: EvidenceV2,
    *,
    context: InvestigationContextV2,
    authorized_transaction_refs: set[str],
) -> None:
    if evidence.context_identity == context.context_identity:
        allowed_subjects: set[tuple[SubjectType, str]] = {
            (SubjectType.ACCOUNT, account_ref) for account_ref in context.root_account_refs
        }
        if context.selected_transaction_ref is not None:
            allowed_subjects.add((SubjectType.TRANSACTION, context.selected_transaction_ref))
        if context.alert_ref is not None:
            allowed_subjects.add((SubjectType.ALERT, context.alert_ref))
        # SUPPORTING_TRANSACTIONS preserves its source subject within the same context.
        if (evidence.subject_type, evidence.subject_ref) not in allowed_subjects:
            raise EvidenceValidationError("Evidence subject is outside the investigation context")
        return

    if (
        evidence.subject_type is SubjectType.TRANSACTION
        and evidence.subject_ref in authorized_transaction_refs
    ):
        evidence_time = parse_canonical_timestamp(evidence.context_time)
        current_time = parse_canonical_timestamp(context.context_time)
        if evidence_time > current_time:
            raise EvidenceValidationError("Supporting transaction evidence is from future context")
        if (
            context.detector_cutoff is not None
            and evidence.detector_cutoff is not None
            and parse_canonical_timestamp(evidence.detector_cutoff)
            > parse_canonical_timestamp(context.detector_cutoff)
        ):
            raise EvidenceValidationError("Supporting transaction detector state is from the future")
        return

    raise EvidenceValidationError("Evidence belongs to a different investigation context")


def _validate_language(output: InvestigationOutputV2) -> None:
    for finding in output.findings:
        text = finding.text
        if any(pattern.search(text) for pattern in _OVERCLAIM_PATTERNS):
            raise EvidenceValidationError("Finding makes an AML conclusion")
        if _LOW_SAFE.search(text):
            raise EvidenceValidationError("Finding incorrectly equates LOW with safety")
        if _CUSTOMER_GEO.search(text):
            raise EvidenceValidationError("Finding treats bank metadata as customer geography")
        if _UNAVAILABLE_FACT.search(text):
            raise EvidenceValidationError("Finding invents unavailable KYC or transaction-purpose facts")
        if _HIDDEN_BENCHMARK.search(text):
            raise EvidenceValidationError("Finding refers to hidden benchmark truth")
