from __future__ import annotations

import hashlib
from pathlib import Path

from trailsight_v2.detector.benchmark import benchmark_final_snapshot
from trailsight_v2.detector.constants import ACTIVE_SCORER


def test_fixture_final_snapshot_benchmark_is_read_only_and_reports_resources(
    prepared_detector_db: tuple[Path, Path],
) -> None:
    database, _ = prepared_detector_db
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    result = benchmark_final_snapshot(database)
    after = hashlib.sha256(database.read_bytes()).hexdigest()
    assert before == after
    assert result.scorer == ACTIVE_SCORER
    assert result.graph_node_count == 4
    assert result.graph_edge_count == 4
    assert result.total_seconds >= result.scoring_seconds
    assert result.peak_rss_bytes > 0
    assert result.physical_ram_bytes > result.peak_rss_bytes
    assert result.gate_pass is True

