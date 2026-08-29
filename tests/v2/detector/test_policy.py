from __future__ import annotations

import itertools

import pytest

from trailsight_v2.detector.alerts import creates_high_entry_alert
from trailsight_v2.detector.models import ReviewBand
from trailsight_v2.detector.priority import derive_transaction_priority
from trailsight_v2.detector.provenance import (
    alert_ref_for,
    detector_config_hash,
    snapshot_id_for,
)
from trailsight_v2.detector.ranking import assign_review_bands


def test_rank_band_boundaries_percentiles_and_label_blind_population() -> None:
    scores = [(f"acct_{index:03d}", float(index)) for index in range(100)]
    ranked = assign_review_bands(scores)
    ordered = sorted(ranked.values(), key=lambda value: value.rank)
    assert [value.network_review_band for value in ordered].count(ReviewBand.HIGH) == 1
    assert [value.network_review_band for value in ordered].count(ReviewBand.MEDIUM) == 4
    assert [value.network_review_band for value in ordered].count(ReviewBand.LOW) == 95
    assert ordered[0].percentile == 100.0
    assert ordered[-1].percentile == 1.0


def test_ties_use_account_ref_ascending_and_unscored_never_enters_population() -> None:
    ranked = assign_review_bands(
        [("acct_z", 1.0), ("acct_a", 1.0), ("acct_m", 0.5)]
    )
    assert ranked["acct_a"].rank == 1
    assert ranked["acct_z"].rank == 2
    assert ranked["acct_m"].rank == 3
    assert "acct_unscored" not in ranked


def expected_priority(sender: ReviewBand, receiver: ReviewBand) -> ReviewBand:
    if ReviewBand.HIGH in {sender, receiver}:
        return ReviewBand.HIGH
    if ReviewBand.MEDIUM in {sender, receiver}:
        return ReviewBand.MEDIUM
    if sender is receiver is ReviewBand.LOW:
        return ReviewBand.LOW
    return ReviewBand.UNSCORED


@pytest.mark.parametrize(
    ("sender", "receiver"),
    list(itertools.product(tuple(ReviewBand), repeat=2)),
)
def test_every_transaction_priority_matrix_combination(
    sender: ReviewBand,
    receiver: ReviewBand,
) -> None:
    result = derive_transaction_priority(sender, receiver)
    assert result.priority is expected_priority(sender, receiver)
    assert "risk" not in result.text.lower()
    assert "garg flagged" not in result.text.lower()


@pytest.mark.parametrize(
    ("sequence", "expected_alert_indexes"),
    [
        ([ReviewBand.UNSCORED, ReviewBand.HIGH], [1]),
        ([ReviewBand.LOW, ReviewBand.HIGH], [1]),
        ([ReviewBand.MEDIUM, ReviewBand.HIGH], [1]),
        ([ReviewBand.HIGH, ReviewBand.HIGH], [0]),
        ([ReviewBand.HIGH, ReviewBand.MEDIUM], [0]),
        ([ReviewBand.HIGH, ReviewBand.LOW, ReviewBand.HIGH], [0, 2]),
        ([ReviewBand.HIGH, ReviewBand.UNSCORED, ReviewBand.HIGH], [0, 2]),
        ([ReviewBand.LOW, ReviewBand.MEDIUM], []),
    ],
)
def test_high_first_entry_continuity_and_reentry(
    sequence: list[ReviewBand],
    expected_alert_indexes: list[int],
) -> None:
    previous = None
    actual: list[int] = []
    for index, current in enumerate(sequence):
        if creates_high_entry_alert(previous, current):
            actual.append(index)
        previous = current
    assert actual == expected_alert_indexes


def test_snapshot_config_and_alert_ids_are_deterministic_and_context_sensitive() -> None:
    from datetime import datetime

    cutoff = datetime(2022, 9, 2)
    config_hash = detector_config_hash()
    snapshot = snapshot_id_for("ibm-amlworld-hi-small", cutoff, config_hash)
    assert snapshot == snapshot_id_for("ibm-amlworld-hi-small", cutoff, config_hash)
    assert snapshot != snapshot_id_for(
        "ibm-amlworld-hi-small", datetime(2022, 9, 3), config_hash
    )
    alert = alert_ref_for("ibm-amlworld-hi-small", "acct_a", snapshot)
    assert alert == alert_ref_for("ibm-amlworld-hi-small", "acct_a", snapshot)
    assert alert != alert_ref_for("ibm-amlworld-hi-small", "acct_b", snapshot)
