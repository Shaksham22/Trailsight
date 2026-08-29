"""Typed, deterministic WP02 detector values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SnapshotStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ReviewBand(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNSCORED = "UNSCORED"


class UnscoredReason(StrEnum):
    NOT_YET_OBSERVED = "NOT_YET_OBSERVED"
    NO_FIRST_ORDER_CONTEXT = "NO_FIRST_ORDER_CONTEXT"
    NO_SECOND_ORDER_CONTEXT = "NO_SECOND_ORDER_CONTEXT"
    NON_FINITE_SCORE = "NON_FINITE_SCORE"


@dataclass(frozen=True, slots=True)
class GargMeasures:
    first_order_neighbors: frozenset[str]
    second_order_neighbors: frozenset[str]
    block_measure_1: float
    block_measure_2: float
    block_measure_3: float
    block_size_1: int
    block_size_2: int
    block_size_3: int

    @property
    def score(self) -> float:
        return self.block_measure_2 - (
            self.block_measure_1 + self.block_measure_3
        ) / 2.0


@dataclass(frozen=True, slots=True)
class AccountScore:
    account_ref: str
    scoring_eligible: bool
    network_pattern_score: float | None
    unscored_reason: UnscoredReason | None
    first_order_neighbor_count: int
    second_order_neighbor_count: int
    community_index: int
    block_measure_1: float | None
    block_measure_2: float | None
    block_measure_3: float | None


@dataclass(frozen=True, slots=True)
class RankedScore:
    account_ref: str
    network_pattern_score: float
    rank: int
    percentile: float
    network_review_band: ReviewBand


@dataclass(frozen=True, slots=True)
class PriorityDerivation:
    priority: ReviewBand
    code: str
    text: str


@dataclass(frozen=True, slots=True)
class SnapshotRunResult:
    snapshot_id: str
    cutoff_timestamp: datetime
    status: SnapshotStatus
    account_count: int
    eligible_account_count: int
    scored_account_count: int
    alert_count_created: int
    skipped_existing_complete: bool


@dataclass(frozen=True, slots=True)
class DetectorRunSummary:
    database_path: str
    config_hash: str
    snapshot_results: tuple[SnapshotRunResult, ...]
    transaction_review_state_count: int

    def lines(self) -> tuple[str, ...]:
        complete = sum(result.status is SnapshotStatus.COMPLETE for result in self.snapshot_results)
        skipped = sum(result.skipped_existing_complete for result in self.snapshot_results)
        return (
            f"runtime_db_path={self.database_path}",
            f"detector_config_hash={self.config_hash}",
            f"snapshot_count={len(self.snapshot_results)}",
            f"complete_snapshot_count={complete}",
            f"restart_skipped_complete_count={skipped}",
            f"transaction_review_state_count={self.transaction_review_state_count}",
        )

