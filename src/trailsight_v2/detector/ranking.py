"""Label-blind deterministic Network Review Band policy."""

from __future__ import annotations

import math
from collections.abc import Iterable

from trailsight_v2.detector.models import RankedScore, ReviewBand


def assign_review_bands(scores: Iterable[tuple[str, float]]) -> dict[str, RankedScore]:
    ordered = sorted(scores, key=lambda item: (-item[1], item[0]))
    population = len(ordered)
    if population == 0:
        return {}
    high_count = math.ceil(0.01 * population)
    medium_count = math.ceil(0.04 * population)
    ranked: dict[str, RankedScore] = {}
    for rank, (account_ref, score) in enumerate(ordered, start=1):
        if rank <= high_count:
            band = ReviewBand.HIGH
        elif rank <= high_count + medium_count:
            band = ReviewBand.MEDIUM
        else:
            band = ReviewBand.LOW
        ranked[account_ref] = RankedScore(
            account_ref=account_ref,
            network_pattern_score=score,
            rank=rank,
            percentile=100.0 * (population - rank + 1) / population,
            network_review_band=band,
        )
    return ranked

