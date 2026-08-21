"""Fail-closed application evidence validation and display-label mapping."""

from __future__ import annotations

from dataclasses import dataclass
import re

from trailsight.contracts import (
    CurrencyHistoryFacts,
    DisplayEvidence,
    EvidenceType,
    InternalEvidence,
    RenderedCitation,
    RenderedFinding,
)
from trailsight.domain.service import InvestigationService
from trailsight_ai.output import InvestigationModelOutput


_CASE_REF = r"[a-z0-9][a-z0-9-]{0,63}"
_SIMPLE_ID = re.compile(
    rf"^ev:({_CASE_REF}):(selected|sender-history|amount-history|counterparty-history|region-history)$"
)
_CURRENCY_ID = re.compile(
    rf"^ev:({_CASE_REF}):currency:(payment|receiving):([A-Z]{{3}})$"
)
_SIMPLE_TYPES = {
    "selected": EvidenceType.SELECTED_TRANSACTION,
    "sender-history": EvidenceType.SENDER_HISTORY,
    "amount-history": EvidenceType.AMOUNT_HISTORY,
    "counterparty-history": EvidenceType.COUNTERPARTY_HISTORY,
    "region-history": EvidenceType.REGION_HISTORY,
}


class EvidenceValidationError(RuntimeError):
    """Raised when any generated evidence reference fails closed."""


@dataclass(frozen=True, slots=True)
class ValidatedInvestigation:
    findings: list[RenderedFinding]
    evidence: list[DisplayEvidence]
    resolved_by_id: dict[str, InternalEvidence]


def validate_and_render(
    *,
    output: InvestigationModelOutput,
    case_ref: str,
    available_evidence_ids: set[str],
    service: InvestigationService,
) -> ValidatedInvestigation:
    """Validate every citation, then create deterministic E1/E2 mappings."""

    ordered_ids: list[str] = []
    for finding in output.findings:
        if not finding.evidence_ids:
            raise EvidenceValidationError("A finding did not cite evidence")
        for evidence_id in finding.evidence_ids:
            if evidence_id not in available_evidence_ids:
                raise EvidenceValidationError(
                    "A cited evidence ID was not available in this run"
                )
            if evidence_id not in ordered_ids:
                ordered_ids.append(evidence_id)

    resolved_by_id: dict[str, InternalEvidence] = {}
    for evidence_id in ordered_ids:
        try:
            resolved = service.resolve_evidence(evidence_id)
        except Exception as exc:
            raise EvidenceValidationError(
                "A cited evidence ID could not be resolved"
            ) from exc
        _validate_resolved_identity(
            requested_id=evidence_id,
            requested_case_ref=case_ref,
            resolved=resolved,
        )
        resolved_by_id[evidence_id] = resolved

    labels = {
        evidence_id: f"E{index}"
        for index, evidence_id in enumerate(ordered_ids, start=1)
    }
    rendered_findings = [
        RenderedFinding(
            text=finding.text,
            citations=[
                RenderedCitation(
                    label=labels[evidence_id], evidence_id=evidence_id
                )
                for evidence_id in finding.evidence_ids
            ],
        )
        for finding in output.findings
    ]
    display_evidence = [
        DisplayEvidence(
            label=labels[evidence_id],
            evidence_id=evidence_id,
            evidence_type=resolved_by_id[evidence_id].evidence_type,
            ui_target=resolved_by_id[evidence_id].ui_target,
            supporting_transaction_refs=(
                resolved_by_id[evidence_id].supporting_transaction_refs
            ),
        )
        for evidence_id in ordered_ids
    ]
    return ValidatedInvestigation(
        findings=rendered_findings,
        evidence=display_evidence,
        resolved_by_id=resolved_by_id,
    )


def _validate_resolved_identity(
    *,
    requested_id: str,
    requested_case_ref: str,
    resolved: InternalEvidence,
) -> None:
    if resolved.evidence_id != requested_id:
        raise EvidenceValidationError("Resolved evidence ID did not match")
    if resolved.case_ref != requested_case_ref:
        raise EvidenceValidationError("Resolved evidence belongs to another case")

    simple_match = _SIMPLE_ID.fullmatch(requested_id)
    if simple_match is not None:
        encoded_case_ref, encoded_kind = simple_match.groups()
        if encoded_case_ref != requested_case_ref:
            raise EvidenceValidationError("Evidence ID encodes another case")
        if resolved.evidence_type is not _SIMPLE_TYPES[encoded_kind]:
            raise EvidenceValidationError("Evidence type did not match its ID")
        return

    currency_match = _CURRENCY_ID.fullmatch(requested_id)
    if currency_match is None:
        raise EvidenceValidationError("Evidence ID format is unsupported")
    encoded_case_ref, dimension, currency = currency_match.groups()
    if encoded_case_ref != requested_case_ref:
        raise EvidenceValidationError("Currency evidence ID encodes another case")
    if resolved.evidence_type is not EvidenceType.CURRENCY_HISTORY:
        raise EvidenceValidationError("Currency evidence resolved to the wrong type")
    facts = resolved.facts
    if not isinstance(facts, CurrencyHistoryFacts):
        raise EvidenceValidationError("Currency evidence facts have the wrong type")
    if facts.dimension.value != dimension or facts.currency != currency:
        raise EvidenceValidationError(
            "Currency evidence parameterization did not match its ID"
        )
