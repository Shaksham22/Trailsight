from types import SimpleNamespace

from trailsight_v2.ai.context import resolve_seed_context
from trailsight_v2.domain.models import EvidenceType, SubjectType
from trailsight_v2.mcp.adapter import InvestigationToolAdapterV2
from trailsight_v2.mcp.scope import InvestigationScopeV2


class State:
    def __init__(self, status: str = "IN_REVIEW") -> None:
        self.status = status

    def get_alert_review_status(self, _alert_ref: str):
        return SimpleNamespace(value=self.status)


def _adapter(service, state, *, subject_type, subject_ref, origin_alert_ref=None, origin_transaction_ref=None):
    seed = resolve_seed_context(
        service,
        state,
        subject_type=subject_type,
        subject_ref=subject_ref,
        origin_alert_ref=origin_alert_ref,
        origin_transaction_ref=origin_transaction_ref,
    )
    scope = InvestigationScopeV2(
        subject_type=subject_type,
        subject_ref=subject_ref,
        origin_alert_ref=origin_alert_ref,
        origin_transaction_ref=origin_transaction_ref,
        context_identity=seed.context.context_identity,
        seed_evidence_ids=seed.seed_evidence_ids,
    )
    return InvestigationToolAdapterV2(service, state, scope), seed


def test_alert_review_status_comes_from_runtime_store(mcp_service) -> None:
    service, alert, _ = mcp_service
    adapter, _ = _adapter(service, State("REVIEWED"), subject_type=SubjectType.ALERT, subject_ref=alert.ref)
    result = adapter.get_alert_context(alert.ref)
    assert result.status == "OK"
    assert result.review_status == "REVIEWED"


def test_network_context_grounds_persisted_detector_support(mcp_service, root_ref) -> None:
    service, alert, _ = mcp_service
    adapter, _ = _adapter(service, State(), subject_type=SubjectType.ALERT, subject_ref=alert.ref)
    result = adapter.get_network_context(root_ref)
    assert result.status == "OK"
    assert result.first_order_neighbor_count == 11
    assert result.second_order_neighbor_count == 22
    assert result.block_measure_support is not None
    assert result.block_measure_support.block_measure_1 == 1.1
    resolved = [service.resolve_evidence(evidence_id) for evidence_id in result.evidence_ids]
    detector = next(item for item in resolved if item.evidence_type is EvidenceType.DETECTOR_STATE)
    assert detector.facts.first_order_neighbor_count == 11
    assert detector.facts.block_measure_3 == 3.3


def test_transaction_account_context_stays_at_selected_transaction_context(mcp_service, root_ref) -> None:
    service, _, selected = mcp_service
    adapter, seed = _adapter(
        service, State(), subject_type=SubjectType.TRANSACTION, subject_ref=selected.ref
    )
    result = adapter.get_account_context(root_ref)
    assert result.status == "OK"
    for evidence_id in result.evidence_ids:
        assert service.resolve_evidence(evidence_id).context_identity == seed.context.context_identity


def test_relationship_requires_bounded_network_authorization(mcp_service, root_ref) -> None:
    service, alert, _ = mcp_service
    adapter, _ = _adapter(service, State(), subject_type=SubjectType.ALERT, subject_ref=alert.ref)
    denied = adapter.get_relationship_context(root_ref, "acct_not_returned")
    assert denied.status == "ERROR"
    assert denied.error_code == "INVALID_CONTEXT"
    network = adapter.get_network_context(root_ref)
    assert network.status == "OK"
    assert network.relationships
    allowed_ref = network.relationships[0].counterparty_account_ref
    allowed = adapter.get_relationship_context(root_ref, allowed_ref)
    assert allowed.status == "OK"
    assert allowed.evidence_id


def test_supporting_evidence_is_issued_only_from_available_evidence_and_bounded(mcp_service, root_ref) -> None:
    service, alert, _ = mcp_service
    adapter, _ = _adapter(service, State(), subject_type=SubjectType.ALERT, subject_ref=alert.ref)
    account = adapter.get_account_context(root_ref)
    assert account.status == "OK"
    activity_id = next(
        evidence_id
        for evidence_id in account.evidence_ids
        if service.resolve_evidence(evidence_id).evidence_type is EvidenceType.ACCOUNT_ACTIVITY
    )
    support = adapter.get_supporting_evidence(activity_id)
    assert support.status == "OK"
    assert len(support.transactions) <= 8
    denied = adapter.get_supporting_evidence("ev2.not-issued.bad")
    assert denied.status == "ERROR"
    assert denied.error_code == "INVALID_CONTEXT"


def test_transaction_tool_rejects_arbitrary_enumeration(mcp_service) -> None:
    service, alert, _ = mcp_service
    adapter, _ = _adapter(service, State(), subject_type=SubjectType.ALERT, subject_ref=alert.ref)
    result = adapter.get_transaction_context("txn_arbitrary")
    assert result.status == "ERROR"
    assert result.error_code == "INVALID_CONTEXT"

def test_alert_behavioral_indicators_default_to_alert_root_account(mcp_service) -> None:
    service, alert, _ = mcp_service
    adapter, _ = _adapter(service, State(), subject_type=SubjectType.ALERT, subject_ref=alert.ref)
    result = adapter.get_behavioral_indicators()
    assert result.status == "OK"
    assert result.network_behavior
