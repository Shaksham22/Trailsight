"""Read-only full-final-snapshot feasibility benchmark."""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as datetime_time, timedelta
from pathlib import Path

import duckdb
import networkx as nx

from trailsight_v2.data.schema import WP01_RUNTIME_TABLES, assert_ground_truth_firewall
from trailsight_v2.detector.constants import (
    ACTIVE_SCORER,
    MAX_FINAL_SNAPSHOT_SECONDS,
    MAX_PHYSICAL_RAM_FRACTION,
)
from trailsight_v2.detector.errors import DetectorContractError
from trailsight_v2.detector.graph import apply_louvain_community_filter, score_preprocessed_graph
from trailsight_v2.detector.provenance import detector_config_hash


@dataclass(frozen=True, slots=True)
class FinalSnapshotBenchmark:
    database_path: str
    snapshot_cutoff: str
    scorer: str
    workers: int
    config_hash: str
    graph_node_count: int
    graph_edge_count: int
    filtered_edge_count: int
    eligible_account_count: int
    graph_construction_seconds: float
    community_preprocessing_seconds: float
    scoring_seconds: float
    total_seconds: float
    peak_rss_bytes: int
    physical_ram_bytes: int
    peak_rss_fraction: float
    time_gate_pass: bool
    memory_gate_pass: bool
    gate_pass: bool

    def lines(self) -> tuple[str, ...]:
        return tuple(f"{key}={value}" for key, value in asdict(self).items())

    def json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, indent=2) + "\n"


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _physical_ram_bytes() -> int:
    try:
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        if pages > 0 and page_size > 0:
            return pages * page_size
    except (ValueError, OSError, AttributeError):
        pass
    if sys.platform == "darwin":
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            text=True,
        )
        return int(result.stdout.strip())
    raise DetectorContractError("cannot determine physical RAM for benchmark gate")


def benchmark_final_snapshot(database_path: str | Path) -> FinalSnapshotBenchmark:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise DetectorContractError(f"runtime DuckDB does not exist: {path}")
    total_started = time.perf_counter()
    connection = duckdb.connect(str(path), read_only=True)
    try:
        assert_ground_truth_firewall(connection, expected_tables=WP01_RUNTIME_TABLES)
        manifests = connection.execute(
            "SELECT source_dataset FROM source_manifest ORDER BY source_dataset"
        ).fetchall()
        if manifests != [("ibm-amlworld-hi-small",)]:
            raise DetectorContractError("benchmark requires the WP01 HI-Small source manifest")
        maximum = connection.execute(
            "SELECT MAX(transaction_timestamp) FROM transactions"
        ).fetchone()[0]
        if maximum is None:
            raise DetectorContractError("transactions must be non-empty for benchmark")
        cutoff = datetime.combine(maximum.date() + timedelta(days=1), datetime_time.min)

        graph_started = time.perf_counter()
        graph = nx.Graph()
        graph.add_nodes_from(
            row[0]
            for row in connection.execute(
                """
                SELECT account_ref
                FROM (
                    SELECT CAST(MIN(transaction_timestamp) AS DATE) AS first_day,
                           account_ref
                    FROM (
                        SELECT transaction_timestamp, from_account_ref AS account_ref
                        FROM transactions
                        UNION ALL
                        SELECT transaction_timestamp, to_account_ref AS account_ref
                        FROM transactions
                    )
                    GROUP BY account_ref
                )
                ORDER BY first_day, account_ref
                """
            ).fetchall()
        )
        cursor = connection.execute(
            """
            SELECT account_ref_a, account_ref_b
            FROM detector_edge_day_deltas
            WHERE edge_day < ?
            ORDER BY edge_day, account_ref_a, account_ref_b
            """,
            (cutoff.date(),),
        )
        while rows := cursor.fetchmany(50_000):
            graph.add_edges_from(rows)
        graph_seconds = time.perf_counter() - graph_started
    finally:
        connection.close()

    community_started = time.perf_counter()
    filtered, communities = apply_louvain_community_filter(graph)
    community_seconds = time.perf_counter() - community_started

    scoring_started = time.perf_counter()
    eligible_count = sum(
        result.scoring_eligible
        for result in score_preprocessed_graph(filtered, communities)
    )
    scoring_seconds = time.perf_counter() - scoring_started
    total_seconds = time.perf_counter() - total_started
    peak_rss = _peak_rss_bytes()
    physical_ram = _physical_ram_bytes()
    peak_fraction = peak_rss / physical_ram
    time_pass = total_seconds <= MAX_FINAL_SNAPSHOT_SECONDS
    memory_pass = peak_fraction < MAX_PHYSICAL_RAM_FRACTION
    return FinalSnapshotBenchmark(
        database_path=str(path),
        snapshot_cutoff=cutoff.isoformat(sep=" "),
        scorer=ACTIVE_SCORER,
        workers=1,
        config_hash=detector_config_hash(),
        graph_node_count=graph.number_of_nodes(),
        graph_edge_count=graph.number_of_edges(),
        filtered_edge_count=filtered.number_of_edges(),
        eligible_account_count=eligible_count,
        graph_construction_seconds=graph_seconds,
        community_preprocessing_seconds=community_seconds,
        scoring_seconds=scoring_seconds,
        total_seconds=total_seconds,
        peak_rss_bytes=peak_rss,
        physical_ram_bytes=physical_ram,
        peak_rss_fraction=peak_fraction,
        time_gate_pass=time_pass,
        memory_gate_pass=memory_pass,
        gate_pass=time_pass and memory_pass,
    )
