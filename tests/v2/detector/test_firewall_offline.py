from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import pytest

import trailsight_v2.detector as runtime_detector
from trailsight_v2.data.prepare import prepare_runtime_database
from trailsight_v2.data.schema import assert_ground_truth_firewall, runtime_schema_columns
from trailsight_v2.detector.errors import DetectorContractError
from trailsight_v2.detector.offline_evaluation import (
    evaluate_labelled_transaction_priorities,
)
from trailsight_v2.detector.pipeline import run_detector_pipeline
from trailsight_v2.detector.schema import create_detector_schema

from .conftest import multi_day_rows


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def detector_outputs(database: Path) -> dict[str, list[tuple[object, ...]]]:
    connection = duckdb.connect(str(database), read_only=True)
    outputs = {
        "snapshots": connection.execute(
            """
            SELECT snapshot_id, source_dataset, cutoff_timestamp, algorithm_name,
                   algorithm_variant, algorithm_version, upstream_code_provenance,
                   identity_rule_version, eligibility_rule_version,
                   community_algorithm, community_resolution, community_seed,
                   config_hash, status, account_count, eligible_account_count,
                   scored_account_count, failure_message_safe
            FROM detector_snapshots ORDER BY snapshot_id
            """
        ).fetchall(),
        "states": connection.execute(
            "SELECT * FROM account_detector_states ORDER BY snapshot_id, account_ref"
        ).fetchall(),
        "support": connection.execute(
            "SELECT * FROM account_detector_support ORDER BY snapshot_id, account_ref"
        ).fetchall(),
        "reviews": connection.execute(
            "SELECT * FROM transaction_review_states ORDER BY transaction_ref"
        ).fetchall(),
        "alerts": connection.execute(
            "SELECT * FROM network_alerts ORDER BY alert_ref"
        ).fetchall(),
    }
    connection.close()
    return outputs


def test_runtime_detector_surface_does_not_import_offline_truth_path() -> None:
    assert not hasattr(runtime_detector, "evaluate_labelled_transaction_priorities")
    assert "evaluate_labelled_transaction_priorities" not in runtime_detector.__all__


def test_offline_evaluator_refuses_hidden_source_before_outputs_exist(
    prepared_detector_db: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    database, source = prepared_detector_db
    connection = duckdb.connect(str(database))
    create_detector_schema(connection)
    connection.close()
    hidden_source_opened = False

    def forbidden(_path):
        nonlocal hidden_source_opened
        hidden_source_opened = True
        raise AssertionError("hidden source must not be opened")

    monkeypatch.setattr(
        "trailsight_v2.detector.offline_evaluation._iter_positive_transaction_refs",
        forbidden,
    )
    with pytest.raises(DetectorContractError, match="already-materialized"):
        evaluate_labelled_transaction_priorities(
            database_path=database,
            hidden_source_path=source,
        )
    assert hidden_source_opened is False


def test_label_changes_cannot_change_detector_scores_bands_priorities_or_alerts(
    make_detector_source, tmp_path: Path
) -> None:
    first_rows = multi_day_rows()
    second_rows = [dict(row, **{"Is Laundering": "1" if index % 2 == 0 else "0"}) for index, row in enumerate(first_rows)]
    source_a = make_detector_source(first_rows, filename="labels-a.csv")
    source_b = make_detector_source(second_rows, filename="labels-b.csv")
    database_a = tmp_path / "labels-a.duckdb"
    database_b = tmp_path / "labels-b.duckdb"
    prepare_runtime_database(source_path=source_a, output_path=database_a)
    prepare_runtime_database(source_path=source_b, output_path=database_b)
    run_detector_pipeline(database_a)
    run_detector_pipeline(database_b)
    assert detector_outputs(database_a) == detector_outputs(database_b)


def test_offline_evaluation_is_aggregate_only_and_cannot_modify_runtime_db(
    prepared_detector_db: tuple[Path, Path],
) -> None:
    database, source = prepared_detector_db
    run_detector_pipeline(database)
    before = file_sha256(database)
    report = evaluate_labelled_transaction_priorities(
        database_path=database,
        hidden_source_path=source,
    )
    after = file_sha256(database)
    assert before == after
    assert report.labelled_transaction_count == 1
    assert sum(report.priority_counts.values()) == 1
    assert set(report.priority_counts) == {"HIGH", "MEDIUM", "LOW", "UNSCORED"}
    assert "txn_" not in report.json()

    connection = duckdb.connect(str(database), read_only=True)
    assert_ground_truth_firewall(connection)
    schema = runtime_schema_columns(connection)
    assert all(
        column.lower() not in {"is_laundering", "pattern", "pattern_label", "aml_pattern"}
        for columns in schema.values()
        for column in columns
    )
    connection.close()
