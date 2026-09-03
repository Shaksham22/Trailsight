"""Atomic mutable operational state for Trailsight V2.

The analytical DuckDB is immutable at runtime. This store owns only human alert
review progress and minimal investigation-session metadata needed by AI follow-up.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from trailsight_v2.domain.evidence import parse_canonical_timestamp
from trailsight_v2.domain.models import ContextIdentityV2, ContextKind, SubjectType

from .models import ReviewStatus

RUNTIME_STATE_VERSION = "runtime-state-v1"
DEFAULT_RUNTIME_STATE_PATH = Path("data/state/runtime_state.json")
_RUNTIME_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FORBIDDEN_TEXT = ("is laundering", "patterns.txt")
MAX_ALERT_STATUS_BATCH = 100


class RuntimeStateError(RuntimeError):
    """Base display-safe runtime-state error."""

    code = "RUNTIME_STATE_ERROR"
    safe_message = "Runtime state could not be processed safely"


class RuntimeStateCorruptError(RuntimeStateError):
    code = "DATA_INTEGRITY_ERROR"
    safe_message = "Runtime state failed the Trailsight integrity contract"


class ReviewStateConflictError(RuntimeStateError):
    code = "REVIEW_STATE_CONFLICT"
    safe_message = "The requested review-status transition is not allowed"


class FollowUpAlreadyUsedError(RuntimeStateError):
    code = "FOLLOW_UP_ALREADY_USED"
    safe_message = "The single follow-up for this investigation has already been used"


class InvestigationStateNotFoundError(RuntimeStateError):
    code = "NOT_FOUND"
    safe_message = "The requested investigation state was not found"


@dataclass(frozen=True)
class AlertReviewState:
    alert_ref: str
    review_status: ReviewStatus
    updated_at: str


@dataclass(frozen=True)
class RuntimeContextIdentity:
    kind: ContextKind
    ref: str
    time: str
    snapshot_id: str | None

    @classmethod
    def from_domain(cls, value: ContextIdentityV2) -> "RuntimeContextIdentity":
        return cls(
            kind=value.context_kind,
            ref=value.context_ref,
            time=value.context_time,
            snapshot_id=value.snapshot_id,
        )

    def as_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "ref": self.ref,
            "time": self.time,
            "snapshot_id": self.snapshot_id,
        }


@dataclass(frozen=True)
class InvestigationSessionState:
    investigation_id: str
    subject_type: SubjectType
    subject_ref: str
    origin_alert_ref: str | None
    origin_transaction_ref: str | None
    context_identity: RuntimeContextIdentity
    follow_up_used: bool
    created_at: str


class RuntimeStateStore:
    """Single-process, restart-safe JSON runtime-state store.

    Public integration methods intentionally provide the complete state boundary;
    callers must never read ``runtime_state.json`` directly.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path if path is not None else os.getenv("TRAILSIGHT_RUNTIME_STATE_PATH")
        self.path = Path(configured) if configured else DEFAULT_RUNTIME_STATE_PATH
        self.path = self.path.expanduser().resolve()
        self._lock = RLock()
        self._follow_ups_in_progress: set[str] = set()
        with self._lock:
            if self.path.exists():
                self._read_validated_unlocked()
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._write_unlocked(self._empty_state())

    def close(self) -> None:
        """Symmetric lifecycle hook; the file store has no persistent handle."""

    def get_alert_review_status(self, alert_ref: str) -> ReviewStatus:
        """Return mutable review progress; absent alert state is NOT_REVIEWED."""
        return self.get_alert_review_statuses((alert_ref,))[alert_ref]

    def get_alert_review_statuses(
        self, alert_refs: Iterable[str]
    ) -> dict[str, ReviewStatus]:
        """Read and validate runtime state once for a bounded set of alert refs."""
        refs: list[str] = []
        seen: set[str] = set()
        for alert_ref in alert_refs:
            self._require_ref(alert_ref, "alert_ref")
            if alert_ref not in seen:
                refs.append(alert_ref)
                seen.add(alert_ref)
        if len(refs) > MAX_ALERT_STATUS_BATCH:
            raise RuntimeStateCorruptError()
        if not refs:
            return {}
        with self._lock:
            state = self._read_validated_unlocked()
            return {
                alert_ref: (
                    ReviewStatus.NOT_REVIEWED
                    if state["alerts"].get(alert_ref) is None
                    else ReviewStatus(state["alerts"][alert_ref]["review_status"])
                )
                for alert_ref in refs
            }

    def set_alert_review_status(
        self, alert_ref: str, review_status: ReviewStatus | str
    ) -> AlertReviewState:
        self._require_ref(alert_ref, "alert_ref")
        try:
            requested = ReviewStatus(review_status)
        except ValueError as exc:
            raise RuntimeStateCorruptError() from exc
        with self._lock:
            state = self._read_validated_unlocked()
            current_raw = state["alerts"].get(alert_ref)
            current = (
                ReviewStatus.NOT_REVIEWED
                if current_raw is None
                else ReviewStatus(current_raw["review_status"])
            )
            allowed = {
                ReviewStatus.NOT_REVIEWED: {
                    ReviewStatus.NOT_REVIEWED,
                    ReviewStatus.IN_REVIEW,
                },
                ReviewStatus.IN_REVIEW: {
                    ReviewStatus.IN_REVIEW,
                    ReviewStatus.REVIEWED,
                },
                ReviewStatus.REVIEWED: {ReviewStatus.REVIEWED},
            }
            if requested not in allowed[current]:
                raise ReviewStateConflictError()
            updated_at = self._now_utc()
            state["alerts"][alert_ref] = {
                "review_status": requested.value,
                "updated_at": updated_at,
            }
            self._write_unlocked(state)
            return AlertReviewState(alert_ref, requested, updated_at)

    def alert_filter_membership(
        self, review_status: ReviewStatus | str
    ) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
        """Return (include_refs, exclude_refs) for server-side alert-list membership.

        Explicit IN_REVIEW/REVIEWED filters become include sets. NOT_REVIEWED is
        represented as exclusion of all persisted non-NOT_REVIEWED refs so
        pagination/filtering stays inside the bounded DuckDB query.
        """
        try:
            requested = ReviewStatus(review_status)
        except ValueError as exc:
            raise RuntimeStateCorruptError() from exc
        with self._lock:
            state = self._read_validated_unlocked()
            if requested is ReviewStatus.NOT_REVIEWED:
                excluded = tuple(
                    sorted(
                        ref
                        for ref, item in state["alerts"].items()
                        if ReviewStatus(item["review_status"]) is not ReviewStatus.NOT_REVIEWED
                    )
                )
                return None, excluded
            included = tuple(
                sorted(
                    ref
                    for ref, item in state["alerts"].items()
                    if ReviewStatus(item["review_status"]) is requested
                )
            )
            return included, None

    def create_investigation_session(
        self,
        investigation_id: str,
        *,
        subject_type: SubjectType | str,
        subject_ref: str,
        context_identity: ContextIdentityV2 | RuntimeContextIdentity,
        origin_alert_ref: str | None = None,
        origin_transaction_ref: str | None = None,
    ) -> InvestigationSessionState:
        self._require_ref(investigation_id, "investigation_id")
        self._require_ref(subject_ref, "subject_ref")
        if origin_alert_ref is not None:
            self._require_ref(origin_alert_ref, "origin_alert_ref")
        if origin_transaction_ref is not None:
            self._require_ref(origin_transaction_ref, "origin_transaction_ref")
        if origin_alert_ref is not None and origin_transaction_ref is not None:
            raise RuntimeStateCorruptError()
        try:
            subject = SubjectType(subject_type)
        except ValueError as exc:
            raise RuntimeStateCorruptError() from exc
        context = (
            RuntimeContextIdentity.from_domain(context_identity)
            if isinstance(context_identity, ContextIdentityV2)
            else context_identity
        )
        self._validate_context_identity(context)
        expected_identity = {
            "subject_type": subject.value,
            "subject_ref": subject_ref,
            "origin_alert_ref": origin_alert_ref,
            "origin_transaction_ref": origin_transaction_ref,
            "context_identity": context.as_json(),
            "follow_up_used": False,
        }
        self._assert_no_forbidden(expected_identity)
        with self._lock:
            state = self._read_validated_unlocked()
            existing = state["investigations"].get(investigation_id)
            if existing is not None:
                # Allocation is one-shot. An exact duplicate before follow-up use is idempotent.
                if any(existing[key] != value for key, value in expected_identity.items()):
                    raise RuntimeStateCorruptError()
                return self._session_from_json(investigation_id, existing)
            entry = {**expected_identity, "created_at": self._now_utc()}
            state["investigations"][investigation_id] = entry
            self._write_unlocked(state)
        return self._session_from_json(investigation_id, entry)

    def get_investigation_session(self, investigation_id: str) -> InvestigationSessionState:
        self._require_ref(investigation_id, "investigation_id")
        with self._lock:
            state = self._read_validated_unlocked()
            entry = state["investigations"].get(investigation_id)
            if entry is None:
                raise InvestigationStateNotFoundError()
            return self._session_from_json(investigation_id, entry)

    def consume_follow_up(self, investigation_id: str) -> InvestigationSessionState:
        """Compatibility helper that reserves and immediately consumes a follow-up."""
        self.begin_follow_up(investigation_id)
        return self.complete_follow_up(investigation_id)

    def begin_follow_up(self, investigation_id: str) -> InvestigationSessionState:
        """Atomically reserve the one follow-up slot without consuming it."""
        self._require_ref(investigation_id, "investigation_id")
        with self._lock:
            state = self._read_validated_unlocked()
            entry = state["investigations"].get(investigation_id)
            if entry is None:
                raise InvestigationStateNotFoundError()
            if entry["follow_up_used"] is True or investigation_id in self._follow_ups_in_progress:
                raise FollowUpAlreadyUsedError()
            self._follow_ups_in_progress.add(investigation_id)
            return self._session_from_json(investigation_id, entry)

    def complete_follow_up(self, investigation_id: str) -> InvestigationSessionState:
        """Persist consumption only after a valid terminal follow-up result exists."""
        self._require_ref(investigation_id, "investigation_id")
        with self._lock:
            state = self._read_validated_unlocked()
            entry = state["investigations"].get(investigation_id)
            if entry is None:
                raise InvestigationStateNotFoundError()
            if entry["follow_up_used"] is True:
                self._follow_ups_in_progress.discard(investigation_id)
                raise FollowUpAlreadyUsedError()
            if investigation_id not in self._follow_ups_in_progress:
                raise RuntimeStateCorruptError()
            entry["follow_up_used"] = True
            self._write_unlocked(state)
            self._follow_ups_in_progress.remove(investigation_id)
            return self._session_from_json(investigation_id, entry)

    def release_follow_up(self, investigation_id: str) -> None:
        """Release an unsuccessful in-process follow-up reservation for retry."""
        self._require_ref(investigation_id, "investigation_id")
        with self._lock:
            self._follow_ups_in_progress.discard(investigation_id)

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {"version": RUNTIME_STATE_VERSION, "alerts": {}, "investigations": {}}

    def _read_validated_unlocked(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeStateCorruptError() from exc
        self._validate_state(state)
        return state

    def _write_unlocked(self, state: Mapping[str, Any]) -> None:
        self._validate_state(dict(state))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
            )
            temp_path = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, sort_keys=True, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            temp_path = None
            # Persist the rename where the platform supports directory fsync.
            try:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except OSError as exc:
            raise RuntimeStateError() from exc
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _validate_state(self, state: Any) -> None:
        if not isinstance(state, dict) or set(state) != {"version", "alerts", "investigations"}:
            raise RuntimeStateCorruptError()
        if state.get("version") != RUNTIME_STATE_VERSION:
            raise RuntimeStateCorruptError()
        alerts = state.get("alerts")
        investigations = state.get("investigations")
        if not isinstance(alerts, dict) or not isinstance(investigations, dict):
            raise RuntimeStateCorruptError()
        for alert_ref, entry in alerts.items():
            self._require_ref(alert_ref, "alert_ref")
            if not isinstance(entry, dict) or set(entry) != {"review_status", "updated_at"}:
                raise RuntimeStateCorruptError()
            try:
                ReviewStatus(entry["review_status"])
            except (ValueError, TypeError) as exc:
                raise RuntimeStateCorruptError() from exc
            self._validate_runtime_timestamp(entry["updated_at"])
        for investigation_id, entry in investigations.items():
            self._require_ref(investigation_id, "investigation_id")
            self._validate_investigation_json(entry)
        self._assert_no_forbidden(state)

    def _validate_investigation_json(self, entry: Any) -> None:
        required = {
            "subject_type",
            "subject_ref",
            "origin_alert_ref",
            "origin_transaction_ref",
            "context_identity",
            "follow_up_used",
            "created_at",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise RuntimeStateCorruptError()
        try:
            SubjectType(entry["subject_type"])
        except (ValueError, TypeError) as exc:
            raise RuntimeStateCorruptError() from exc
        self._require_ref(entry["subject_ref"], "subject_ref")
        for key in ("origin_alert_ref", "origin_transaction_ref"):
            if entry[key] is not None:
                self._require_ref(entry[key], key)
        if entry["origin_alert_ref"] is not None and entry["origin_transaction_ref"] is not None:
            raise RuntimeStateCorruptError()
        if not isinstance(entry["follow_up_used"], bool):
            raise RuntimeStateCorruptError()
        self._validate_runtime_timestamp(entry["created_at"])
        context = entry["context_identity"]
        if not isinstance(context, dict) or set(context) != {"kind", "ref", "time", "snapshot_id"}:
            raise RuntimeStateCorruptError()
        try:
            runtime_context = RuntimeContextIdentity(
                kind=ContextKind(context["kind"]),
                ref=context["ref"],
                time=context["time"],
                snapshot_id=context["snapshot_id"],
            )
        except (ValueError, TypeError) as exc:
            raise RuntimeStateCorruptError() from exc
        self._validate_context_identity(runtime_context)

    def _session_from_json(
        self, investigation_id: str, entry: Mapping[str, Any]
    ) -> InvestigationSessionState:
        context = entry["context_identity"]
        return InvestigationSessionState(
            investigation_id=investigation_id,
            subject_type=SubjectType(entry["subject_type"]),
            subject_ref=str(entry["subject_ref"]),
            origin_alert_ref=entry["origin_alert_ref"],
            origin_transaction_ref=entry["origin_transaction_ref"],
            context_identity=RuntimeContextIdentity(
                kind=ContextKind(context["kind"]),
                ref=str(context["ref"]),
                time=str(context["time"]),
                snapshot_id=context["snapshot_id"],
            ),
            follow_up_used=bool(entry["follow_up_used"]),
            created_at=str(entry["created_at"]),
        )

    def _validate_context_identity(self, context: RuntimeContextIdentity) -> None:
        if not isinstance(context, RuntimeContextIdentity):
            raise RuntimeStateCorruptError()
        self._require_ref(context.ref, "context_identity.ref")
        if context.snapshot_id is not None:
            self._require_ref(context.snapshot_id, "context_identity.snapshot_id")
        try:
            parse_canonical_timestamp(context.time)
        except Exception as exc:
            raise RuntimeStateCorruptError() from exc

    @staticmethod
    def _require_ref(value: Any, _field: str) -> None:
        if not isinstance(value, str) or not value or len(value) > 2048:
            raise RuntimeStateCorruptError()
        lowered = value.casefold()
        if any(token in lowered for token in _FORBIDDEN_TEXT):
            raise RuntimeStateCorruptError()

    @staticmethod
    def _now_utc() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _validate_runtime_timestamp(value: Any) -> None:
        if not isinstance(value, str) or not _RUNTIME_TIMESTAMP_RE.fullmatch(value):
            raise RuntimeStateCorruptError()
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise RuntimeStateCorruptError() from exc

    @classmethod
    def _assert_no_forbidden(cls, value: Any) -> None:
        if isinstance(value, str):
            lowered = value.casefold()
            if any(token in lowered for token in _FORBIDDEN_TEXT):
                raise RuntimeStateCorruptError()
            return
        if isinstance(value, dict):
            for key, item in value.items():
                cls._assert_no_forbidden(str(key))
                cls._assert_no_forbidden(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                cls._assert_no_forbidden(item)
