"""Canonical detector provenance, config hash, and stable output identities."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from importlib.metadata import version

from trailsight_v2.detector.constants import (
    ACTIVE_SCORER,
    ALERT_REF_VERSION,
    ALGORITHM_NAME,
    ALGORITHM_VARIANT,
    ALGORITHM_VERSION,
    COMMUNITY_ALGORITHM,
    COMMUNITY_RESOLUTION,
    COMMUNITY_SEED,
    ELIGIBILITY_RULE_VERSION,
    IDENTITY_RULE_VERSION,
    NETWORKX_VERSION,
    NUMPY_VERSION,
    REVIEW_BAND_POLICY_VERSION,
    SNAPSHOT_ID_VERSION,
    UPSTREAM_CODE_PROVENANCE,
    UPSTREAM_COMMIT,
    UPSTREAM_REPOSITORY,
)
from trailsight_v2.detector.errors import DetectorContractError


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def assert_supported_networkx() -> None:
    installed_networkx = version("networkx")
    if installed_networkx != NETWORKX_VERSION:
        raise DetectorContractError(
            f"WP02 requires networkx=={NETWORKX_VERSION}; found {installed_networkx}"
        )
    installed_numpy = version("numpy")
    if installed_numpy != NUMPY_VERSION:
        raise DetectorContractError(
            f"WP02 requires numpy=={NUMPY_VERSION}; found {installed_numpy}"
        )


def detector_configuration() -> dict[str, object]:
    """Return every value that can affect preprocessing, scoring, or policy."""
    assert_supported_networkx()
    return {
        "active_scorer": ACTIVE_SCORER,
        "algorithm_name": ALGORITHM_NAME,
        "algorithm_variant": ALGORITHM_VARIANT,
        "algorithm_version": ALGORITHM_VERSION,
        "community_algorithm": COMMUNITY_ALGORITHM,
        "community_resolution": COMMUNITY_RESOLUTION,
        "community_seed": COMMUNITY_SEED,
        "eligibility_rule_version": ELIGIBILITY_RULE_VERSION,
        "identity_rule_version": IDENTITY_RULE_VERSION,
        "networkx_version": NETWORKX_VERSION,
        "numpy_version": NUMPY_VERSION,
        "node_insertion_order": "first-observed-day-then-account-ref",
        "edge_insertion_order": "edge-day-then-canonical-endpoints",
        "review_band_policy_version": REVIEW_BAND_POLICY_VERSION,
        "simple_graph": True,
        "unweighted": True,
        "undirected": True,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_repository": UPSTREAM_REPOSITORY,
    }


def detector_config_hash() -> str:
    return hashlib.sha256(_canonical_json(detector_configuration())).hexdigest()


def canonical_cutoff(cutoff: datetime) -> str:
    if cutoff.tzinfo is not None:
        raise DetectorContractError("detector cutoffs must be timezone-unspecified")
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S")


def snapshot_id_for(source_dataset: str, cutoff: datetime, config_hash: str | None = None) -> str:
    payload = [
        SNAPSHOT_ID_VERSION,
        source_dataset,
        canonical_cutoff(cutoff),
        config_hash or detector_config_hash(),
    ]
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    return f"snap_{digest[:24]}"


def alert_ref_for(source_dataset: str, account_ref: str, entry_snapshot_id: str) -> str:
    payload = [ALERT_REF_VERSION, source_dataset, account_ref, entry_snapshot_id]
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    return f"alert_{digest[:24]}"


def persisted_provenance() -> dict[str, object]:
    return {
        **detector_configuration(),
        "config_hash": detector_config_hash(),
        "upstream_code_provenance": UPSTREAM_CODE_PROVENANCE,
    }
