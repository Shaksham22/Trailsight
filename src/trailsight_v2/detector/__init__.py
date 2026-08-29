"""Public WP02 detector preparation contract.

The hidden-truth evaluator is intentionally excluded from this runtime-safe
surface and must be imported explicitly from ``detector.offline_evaluation``.
"""

from trailsight_v2.detector.alerts import creates_high_entry_alert
from trailsight_v2.detector.benchmark import FinalSnapshotBenchmark, benchmark_final_snapshot
from trailsight_v2.detector.constants import (
    ACTIVE_SCORER,
    ALGORITHM_NAME,
    ALGORITHM_VARIANT,
    ALGORITHM_VERSION,
    COMMUNITY_RESOLUTION,
    COMMUNITY_SEED,
    ELIGIBILITY_RULE_VERSION,
    REVIEW_BAND_POLICY_VERSION,
    UPSTREAM_CODE_PROVENANCE,
)
from trailsight_v2.detector.graph import (
    apply_louvain_community_filter,
    build_simple_undirected_graph,
    garg_undirected_reference_measures,
    preprocess_and_score,
)
from trailsight_v2.detector.pipeline import (
    derive_snapshot_cutoffs,
    materialize_transaction_review_states,
    run_detector_pipeline,
)
from trailsight_v2.detector.priority import derive_transaction_priority
from trailsight_v2.detector.provenance import (
    alert_ref_for,
    detector_config_hash,
    detector_configuration,
    snapshot_id_for,
)
from trailsight_v2.detector.ranking import assign_review_bands
from trailsight_v2.detector.schema import (
    WP02_RUNTIME_TABLES,
    WP02_TABLE_COLUMNS,
    assert_detector_schema,
    create_detector_schema,
)

__all__ = [
    "ACTIVE_SCORER",
    "ALGORITHM_NAME",
    "ALGORITHM_VARIANT",
    "ALGORITHM_VERSION",
    "COMMUNITY_RESOLUTION",
    "COMMUNITY_SEED",
    "ELIGIBILITY_RULE_VERSION",
    "FinalSnapshotBenchmark",
    "REVIEW_BAND_POLICY_VERSION",
    "UPSTREAM_CODE_PROVENANCE",
    "WP02_RUNTIME_TABLES",
    "WP02_TABLE_COLUMNS",
    "alert_ref_for",
    "apply_louvain_community_filter",
    "assert_detector_schema",
    "assign_review_bands",
    "benchmark_final_snapshot",
    "build_simple_undirected_graph",
    "create_detector_schema",
    "creates_high_entry_alert",
    "derive_snapshot_cutoffs",
    "derive_transaction_priority",
    "detector_config_hash",
    "detector_configuration",
    "garg_undirected_reference_measures",
    "materialize_transaction_review_states",
    "preprocess_and_score",
    "run_detector_pipeline",
    "snapshot_id_for",
]

