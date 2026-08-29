"""Network Pattern Alert entry/re-entry transition semantics."""

from __future__ import annotations

from trailsight_v2.detector.models import ReviewBand


def creates_high_entry_alert(
    previous_band: ReviewBand | str | None,
    current_band: ReviewBand | str,
) -> bool:
    previous = ReviewBand(previous_band) if previous_band is not None else None
    current = ReviewBand(current_band)
    return current is ReviewBand.HIGH and previous is not ReviewBand.HIGH

