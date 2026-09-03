from __future__ import annotations

import json
from pathlib import Path

import pytest

from trailsight_v2.api.models import ReviewStatus
from trailsight_v2.api.runtime_state import (
    FollowUpAlreadyUsedError,
    ReviewStateConflictError,
    RuntimeStateCorruptError,
    RuntimeStateError,
    RuntimeStateStore,
)
from trailsight_v2.domain.models import ContextIdentityV2, ContextKind, SubjectType


def context() -> ContextIdentityV2:
    return ContextIdentityV2(
        context_kind=ContextKind.SNAPSHOT,
        context_ref="snap_2",
        context_time="2025-01-03T00:00:00",
        snapshot_id="snap_2",
    )


def test_missing_state_initializes_and_absent_alert_defaults(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "runtime_state.json"
    store = RuntimeStateStore(path)
    assert path.is_file()
    assert store.get_alert_review_status("alert_missing") is ReviewStatus.NOT_REVIEWED
    payload = json.loads(path.read_text())
    assert payload == {"alerts": {}, "investigations": {}, "version": "runtime-state-v1"}


def test_reviewed_is_terminal_v2_policy_and_forward_transitions_persist(tmp_path: Path) -> None:
    path = tmp_path / "runtime_state.json"
    store = RuntimeStateStore(path)
    first = store.set_alert_review_status("alert_1", ReviewStatus.IN_REVIEW)
    assert first.review_status is ReviewStatus.IN_REVIEW
    assert store.get_alert_review_status("alert_1") is ReviewStatus.IN_REVIEW
    store.set_alert_review_status("alert_1", ReviewStatus.REVIEWED)
    reopened = RuntimeStateStore(path)
    assert reopened.get_alert_review_status("alert_1") is ReviewStatus.REVIEWED
    with pytest.raises(ReviewStateConflictError):
        reopened.set_alert_review_status("alert_1", ReviewStatus.IN_REVIEW)


def test_batched_review_statuses_read_and_validate_state_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime_state.json")
    store.set_alert_review_status("alert_a", ReviewStatus.IN_REVIEW)
    reads = 0
    original = store._read_validated_unlocked

    def counted_read():
        nonlocal reads
        reads += 1
        return original()

    monkeypatch.setattr(store, "_read_validated_unlocked", counted_read)
    statuses = store.get_alert_review_statuses(("alert_a", "alert_b", "alert_a"))
    assert statuses == {
        "alert_a": ReviewStatus.IN_REVIEW,
        "alert_b": ReviewStatus.NOT_REVIEWED,
    }
    assert reads == 1


def test_skipping_review_state_is_rejected_and_same_state_is_idempotent(tmp_path: Path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime_state.json")
    with pytest.raises(ReviewStateConflictError):
        store.set_alert_review_status("alert_1", ReviewStatus.REVIEWED)
    store.set_alert_review_status("alert_1", ReviewStatus.NOT_REVIEWED)
    store.set_alert_review_status("alert_1", ReviewStatus.IN_REVIEW)
    store.set_alert_review_status("alert_1", ReviewStatus.IN_REVIEW)


def test_filter_membership_keeps_runtime_state_small_and_server_queryable(tmp_path: Path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime_state.json")
    store.set_alert_review_status("alert_a", ReviewStatus.IN_REVIEW)
    store.set_alert_review_status("alert_b", ReviewStatus.NOT_REVIEWED)
    include, exclude = store.alert_filter_membership(ReviewStatus.IN_REVIEW)
    assert include == ("alert_a",)
    assert exclude is None
    include, exclude = store.alert_filter_membership(ReviewStatus.NOT_REVIEWED)
    assert include is None
    assert exclude == ("alert_a",)


def test_follow_up_reservation_releases_on_failure_and_only_success_persists_consumption(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime_state.json"
    store = RuntimeStateStore(path)
    created = store.create_investigation_session(
        "inv_1",
        subject_type=SubjectType.ACCOUNT,
        subject_ref="acct_1",
        origin_alert_ref="alert_1",
        context_identity=context(),
    )
    assert created.follow_up_used is False
    assert created.context_identity.ref == "snap_2"
    # exact re-creation before follow-up is safe/idempotent
    duplicate = store.create_investigation_session(
        "inv_1",
        subject_type=SubjectType.ACCOUNT,
        subject_ref="acct_1",
        origin_alert_ref="alert_1",
        context_identity=context(),
    )
    assert duplicate.created_at == created.created_at
    reserved = store.begin_follow_up("inv_1")
    assert reserved.follow_up_used is False
    with pytest.raises(FollowUpAlreadyUsedError):
        store.begin_follow_up("inv_1")
    store.release_follow_up("inv_1")
    store.begin_follow_up("inv_1")
    consumed = store.complete_follow_up("inv_1")
    assert consumed.follow_up_used is True
    reopened = RuntimeStateStore(path)
    assert reopened.get_investigation_session("inv_1").follow_up_used is True
    with pytest.raises(FollowUpAlreadyUsedError):
        reopened.begin_follow_up("inv_1")


def test_runtime_state_has_only_frozen_minimal_session_fields(tmp_path: Path) -> None:
    path = tmp_path / "runtime_state.json"
    store = RuntimeStateStore(path)
    store.create_investigation_session(
        "inv_1",
        subject_type="TRANSACTION",
        subject_ref="txn_1",
        origin_transaction_ref="txn_1",
        context_identity=ContextIdentityV2(
            context_kind=ContextKind.TRANSACTION,
            context_ref="txn_1",
            context_time="2025-01-02T12:00:00",
            snapshot_id="snap_1",
        ),
    )
    raw = path.read_text().casefold()
    for forbidden in (
        "transcript",
        "chain_of_thought",
        "model_reasoning",
        "findings",
        "aml_disposition",
        "evidence_cache",
        "is laundering",
        "patterns.txt",
    ):
        assert forbidden not in raw


def test_corrupt_state_is_not_silently_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "runtime_state.json"
    path.write_text('{"version":"wrong","alerts":{},"investigations":{}}')
    before = path.read_text()
    with pytest.raises(RuntimeStateCorruptError):
        RuntimeStateStore(path)
    assert path.read_text() == before


def test_atomic_replace_failure_leaves_previous_state_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "runtime_state.json"
    store = RuntimeStateStore(path)
    before = path.read_text()

    def fail_replace(_src, _dst):
        raise OSError("fixture replace failure")

    monkeypatch.setattr("trailsight_v2.api.runtime_state.os.replace", fail_replace)
    with pytest.raises(RuntimeStateError):
        store.set_alert_review_status("alert_a", ReviewStatus.IN_REVIEW)
    assert path.read_text() == before
