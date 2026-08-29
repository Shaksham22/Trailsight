import pytest

from trailsight_v2.ai.context import resolve_seed_context
from trailsight_v2.ai.models import (
    FindingCategory,
    FindingV2,
    InvestigationOutputV2,
    InvestigationStatus,
)
from trailsight_v2.ai.validation import EvidenceValidationError, validate_generated_output
from trailsight_v2.domain.models import SubjectType

from .conftest import ReviewState


def _output(evidence_id: str, text: str = "The selected transaction is deterministically prioritized for review."):
    return InvestigationOutputV2(
        status=InvestigationStatus.SUCCESS,
        findings=[
            FindingV2(
                category=FindingCategory.DETECTOR_OUTPUT,
                text=text,
                evidence_ids=[evidence_id],
            )
        ],
        limits=[],
    )


def test_exact_finding_category_vocabulary() -> None:
    assert {item.value for item in FindingCategory} == {
        "DETECTOR_OUTPUT",
        "OBSERVED_FACT",
        "INTERPRETATION",
    }


def test_valid_application_issued_evidence_is_accepted(ai_service) -> None:
    service, selected, _ = ai_service
    seed = resolve_seed_context(
        service,
        ReviewState(),
        subject_type=SubjectType.TRANSACTION,
        subject_ref=selected.ref,
    )
    evidence_id = seed.seed_evidence_ids[0]
    validated = validate_generated_output(
        output=_output(evidence_id),
        available_evidence_ids={evidence_id},
        authorized_transaction_refs=set(),
        context=seed.context,
        service=service,
    )
    assert validated.display_evidence[0].label == "E1"
    assert validated.display_evidence[0].evidence.evidence_id == evidence_id


def test_fabricated_or_malformed_evidence_fails_closed(ai_service) -> None:
    service, selected, _ = ai_service
    seed = resolve_seed_context(
        service, ReviewState(), subject_type=SubjectType.TRANSACTION, subject_ref=selected.ref
    )
    invented = "ev2.fabricated.invalid"
    with pytest.raises(EvidenceValidationError):
        validate_generated_output(
            output=_output(invented),
            available_evidence_ids={invented},
            authorized_transaction_refs=set(),
            context=seed.context,
            service=service,
        )


def test_unissued_evidence_fails_before_trust(ai_service) -> None:
    service, selected, _ = ai_service
    seed = resolve_seed_context(
        service, ReviewState(), subject_type=SubjectType.TRANSACTION, subject_ref=selected.ref
    )
    valid_but_unissued = seed.seed_evidence_ids[0]
    with pytest.raises(EvidenceValidationError):
        validate_generated_output(
            output=_output(valid_but_unissued),
            available_evidence_ids=set(),
            authorized_transaction_refs=set(),
            context=seed.context,
            service=service,
        )


def test_cross_context_evidence_is_rejected(ai_service) -> None:
    service, selected, other = ai_service
    current = resolve_seed_context(
        service, ReviewState(), subject_type=SubjectType.TRANSACTION, subject_ref=selected.ref
    )
    other_evidence = service.get_transaction_detail(other.ref).evidence_ids[0]
    with pytest.raises(EvidenceValidationError):
        validate_generated_output(
            output=_output(other_evidence),
            available_evidence_ids={other_evidence},
            authorized_transaction_refs=set(),
            context=current.context,
            service=service,
        )


@pytest.mark.parametrize(
    "text",
    [
        "This confirms money laundering.",
        "The HIGH band means money laundering.",
        "The LOW band means this account is safe.",
        "Bank Country shows where the customer lives.",
        "The source of funds was salary income.",
        "A hidden benchmark label proves this result.",
    ],
)
def test_unsafe_material_wording_is_rejected(ai_service, text: str) -> None:
    service, selected, _ = ai_service
    seed = resolve_seed_context(
        service, ReviewState(), subject_type=SubjectType.TRANSACTION, subject_ref=selected.ref
    )
    evidence_id = seed.seed_evidence_ids[0]
    with pytest.raises(EvidenceValidationError):
        validate_generated_output(
            output=_output(evidence_id, text),
            available_evidence_ids={evidence_id},
            authorized_transaction_refs=set(),
            context=seed.context,
            service=service,
        )

def test_initial_and_follow_up_finding_bounds_are_frozen(ai_service) -> None:
    from trailsight_v2.ai.models import validate_output_for_mode

    service, selected, _ = ai_service
    seed = resolve_seed_context(
        service, ReviewState(), subject_type=SubjectType.TRANSACTION, subject_ref=selected.ref
    )
    one = _output(seed.seed_evidence_ids[0])
    with pytest.raises(ValueError):
        validate_output_for_mode(one, mode="initial")
    assert validate_output_for_mode(one, mode="follow_up") is one
