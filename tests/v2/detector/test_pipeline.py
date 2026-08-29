from __future__ import annotations

from datetime import datetime
import itertools
from pathlib import Path

import duckdb
import pytest

from trailsight_v2.data.constants import SOURCE_DATASET
from trailsight_v2.data.prepare import prepare_runtime_database
from trailsight_v2.data.schema import assert_ground_truth_firewall
from trailsight_v2.detector.errors import DetectorPreparationError
from trailsight_v2.detector.pipeline import (
    _alert_rows_for_snapshot,
    _persist_snapshot,
    _snapshot_metadata_values,
    derive_snapshot_cutoffs,
    materialize_transaction_review_states,
    run_detector_pipeline,
)
from trailsight_v2.detector.models import AccountScore, ReviewBand, UnscoredReason
from trailsight_v2.detector.provenance import (
    alert_ref_for,
    detector_config_hash,
    snapshot_id_for,
)
from trailsight_v2.detector.schema import (
    WP02_RUNTIME_TABLES,
    WP02_TABLE_COLUMNS,
    assert_detector_schema,
    create_detector_schema,
)

from .conftest import source_row


def test_pipeline_materializes_complete_explicit_point_in_time_state(
    prepared_detector_db: tuple[Path, Path],
) -> None:
    database, _ = prepared_detector_db
    summary = run_detector_pipeline(database)
    assert len(summary.snapshot_results) == 3
    assert all(result.status.value == "COMPLETE" for result in summary.snapshot_results)
    assert summary.transaction_review_state_count == 4

    connection = duckdb.connect(str(database), read_only=True)
    assert_detector_schema(connection)
    assert_ground_truth_firewall(connection)
    statuses = connection.execute(
        "SELECT cutoff_timestamp, status FROM detector_snapshots ORDER BY cutoff_timestamp"
    ).fetchall()
    assert statuses == [
        (datetime(2022, 9, 1), "COMPLETE"),
        (datetime(2022, 9, 2), "COMPLETE"),
        (datetime(2022, 9, 3), "COMPLETE"),
    ]
    account_count = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    state_counts = connection.execute(
        """
        SELECT snapshots.cutoff_timestamp, COUNT(states.account_ref)
        FROM detector_snapshots AS snapshots
        JOIN account_detector_states AS states USING (snapshot_id)
        GROUP BY snapshots.cutoff_timestamp
        ORDER BY snapshots.cutoff_timestamp
        """
    ).fetchall()
    assert state_counts == [(cutoff, account_count) for cutoff, _ in statuses]
    baseline_reasons = connection.execute(
        """
        SELECT DISTINCT states.unscored_reason
        FROM account_detector_states AS states
        JOIN detector_snapshots AS snapshots USING (snapshot_id)
        WHERE snapshots.cutoff_timestamp = TIMESTAMP '2022-09-01 00:00:00'
        """
    ).fetchall()
    assert baseline_reasons == [("NOT_YET_OBSERVED",)]

    review_rows = connection.execute(
        """
        SELECT transactions.transaction_timestamp, review.detector_cutoff,
               review.sender_band, review.receiver_band, review.aml_review_priority
        FROM transactions
        JOIN transaction_review_states AS review USING (transaction_ref)
        ORDER BY transactions.transaction_timestamp
        """
    ).fetchall()
    assert [row[1] for row in review_rows] == [
        datetime(2022, 9, 1),
        datetime(2022, 9, 1),
        datetime(2022, 9, 2),
        datetime(2022, 9, 2),
    ]
    assert all(row[2:] == ("UNSCORED", "UNSCORED", "UNSCORED") for row in review_rows)
    connection.close()


def test_snapshot_persistence_preserves_eligible_ineligible_and_not_observed_reasons(
    prepared_detector_db: tuple[Path, Path],
) -> None:
    database, _ = prepared_detector_db
    connection = duckdb.connect(str(database))
    create_detector_schema(connection)
    account_refs = [
        row[0]
        for row in connection.execute(
            "SELECT account_ref FROM accounts ORDER BY account_ref"
        ).fetchall()
    ]
    eligible_ref, ineligible_ref, not_observed_ref = account_refs[:3]
    cutoff = datetime(2022, 9, 2)
    config_hash = detector_config_hash()
    snapshot_id = snapshot_id_for(SOURCE_DATASET, cutoff, config_hash)
    metadata = list(
        _snapshot_metadata_values(snapshot_id, cutoff, config_hash, len(account_refs))
    )
    metadata[13] = "RUNNING"
    metadata[14] = cutoff
    connection.execute(
        "INSERT INTO detector_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        metadata,
    )

    scores = [
        AccountScore(
            account_ref=eligible_ref,
            scoring_eligible=True,
            network_pattern_score=0.8,
            unscored_reason=None,
            first_order_neighbor_count=2,
            second_order_neighbor_count=1,
            community_index=0,
            block_measure_1=0.0,
            block_measure_2=0.8,
            block_measure_3=0.0,
        ),
        AccountScore(
            account_ref=ineligible_ref,
            scoring_eligible=False,
            network_pattern_score=None,
            unscored_reason=UnscoredReason.NO_SECOND_ORDER_CONTEXT,
            first_order_neighbor_count=1,
            second_order_neighbor_count=0,
            community_index=0,
            block_measure_1=None,
            block_measure_2=None,
            block_measure_3=None,
        ),
    ]

    eligible_count, _ = _persist_snapshot(
        connection,
        snapshot_id,
        cutoff,
        scores,
        len(account_refs),
    )
    assert eligible_count == 1
    states = {
        row[0]: row[1:]
        for row in connection.execute(
            """
            SELECT account_ref, scoring_eligible, network_pattern_score,
                   rank, percentile, network_review_band, unscored_reason
            FROM account_detector_states
            WHERE snapshot_id = ?
            ORDER BY account_ref
            """,
            (snapshot_id,),
        ).fetchall()
    }
    connection.close()

    assert states[eligible_ref][0] is True
    assert states[eligible_ref][1] is not None
    assert states[eligible_ref][2] is not None
    assert states[eligible_ref][3] is not None
    assert states[eligible_ref][4] != "UNSCORED"
    assert states[eligible_ref][5] is None

    assert states[ineligible_ref] == (
        False,
        None,
        None,
        None,
        "UNSCORED",
        "NO_SECOND_ORDER_CONTEXT",
    )
    assert states[not_observed_ref] == (
        False,
        None,
        None,
        None,
        "UNSCORED",
        "NOT_YET_OBSERVED",
    )


def test_snapshot_graph_is_cumulative_and_strictly_before_cutoff(
    prepared_detector_db: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = prepared_detector_db
    observed_edges: list[set[frozenset[str]]] = []

    def capture(graph):
        observed_edges.append({frozenset(edge) for edge in graph.edges})
        return graph.copy(), []

    monkeypatch.setattr("trailsight_v2.detector.pipeline.preprocess_and_score", capture)
    run_detector_pipeline(database)
    assert len(observed_edges) == 2
    assert len(observed_edges[0]) == 2
    assert len(observed_edges[1]) == 4
    assert observed_edges[0] < observed_edges[1]


def test_restart_skips_and_does_not_mutate_complete_snapshots(
    prepared_detector_db: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = prepared_detector_db
    first = run_detector_pipeline(database)
    connection = duckdb.connect(str(database), read_only=True)
    before = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in WP02_RUNTIME_TABLES
    }
    completed_at = connection.execute(
        "SELECT snapshot_id, completed_at FROM detector_snapshots ORDER BY snapshot_id"
    ).fetchall()
    connection.close()

    def must_not_score(_graph):
        raise AssertionError("completed snapshots must never be rescored")

    monkeypatch.setattr("trailsight_v2.detector.pipeline.preprocess_and_score", must_not_score)
    second = run_detector_pipeline(database)
    assert all(result.skipped_existing_complete for result in second.snapshot_results)
    assert first.config_hash == second.config_hash
    connection = duckdb.connect(str(database), read_only=True)
    after = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in WP02_RUNTIME_TABLES
    }
    assert connection.execute(
        "SELECT snapshot_id, completed_at FROM detector_snapshots ORDER BY snapshot_id"
    ).fetchall() == completed_at
    connection.close()
    assert before == after


def test_failed_snapshot_exposes_no_partial_state(
    prepared_detector_db: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = prepared_detector_db

    def fail(_graph):
        raise MemoryError("fixture failure")

    monkeypatch.setattr("trailsight_v2.detector.pipeline.preprocess_and_score", fail)
    with pytest.raises(DetectorPreparationError, match="failed safely"):
        run_detector_pipeline(database)
    connection = duckdb.connect(str(database), read_only=True)
    rows = connection.execute(
        """
        SELECT snapshot_id, status, failure_message_safe
        FROM detector_snapshots
        ORDER BY cutoff_timestamp
        """
    ).fetchall()
    assert rows[0][1:] == ("COMPLETE", None)
    assert rows[1][1] == "FAILED"
    assert "fixture failure" not in rows[1][2]
    assert connection.execute(
        "SELECT COUNT(*) FROM account_detector_states WHERE snapshot_id = ?", (rows[1][0],)
    ).fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM transaction_review_states").fetchone()[0] == 0
    connection.close()


def test_failed_snapshot_can_restart_from_latest_complete(
    prepared_detector_db: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _ = prepared_detector_db
    original = __import__(
        "trailsight_v2.detector.pipeline", fromlist=["preprocess_and_score"]
    ).preprocess_and_score
    calls = 0

    def fail_once(graph):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("restart fixture")
        return original(graph)

    monkeypatch.setattr("trailsight_v2.detector.pipeline.preprocess_and_score", fail_once)
    with pytest.raises(DetectorPreparationError):
        run_detector_pipeline(database)
    monkeypatch.setattr("trailsight_v2.detector.pipeline.preprocess_and_score", original)
    summary = run_detector_pipeline(database)
    assert summary.snapshot_results[0].skipped_existing_complete is True
    assert all(result.status.value == "COMPLETE" for result in summary.snapshot_results)
    assert summary.transaction_review_state_count == 4


def test_future_snapshot_and_alert_do_not_leak_into_earlier_transaction(
    make_detector_source, tmp_path: Path
) -> None:
    source = make_detector_source(
        [
            source_row(**{"Timestamp": "2022/09/01 12:00"}),
            source_row(**{"Timestamp": "2022/09/02 12:00"}),
        ],
        filename="priority.csv",
    )
    database = tmp_path / "priority.duckdb"
    prepare_runtime_database(source_path=source, output_path=database)
    connection = duckdb.connect(str(database))
    create_detector_schema(connection)
    config_hash = detector_config_hash()
    account_count = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    sender_ref, receiver_ref = connection.execute(
        """
        SELECT from_account_ref, to_account_ref FROM transactions
        ORDER BY transaction_timestamp LIMIT 1
        """
    ).fetchone()
    cutoffs = (datetime(2022, 9, 1), datetime(2022, 9, 2))
    snapshots: list[str] = []
    for cutoff in cutoffs:
        snapshot_id = snapshot_id_for(SOURCE_DATASET, cutoff, config_hash)
        snapshots.append(snapshot_id)
        values = list(
            _snapshot_metadata_values(snapshot_id, cutoff, config_hash, account_count)
        )
        values[13] = "COMPLETE"
        values[15] = cutoff
        values[17] = 2
        values[18] = 2
        connection.execute(
            "INSERT INTO detector_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
        )

    for account_ref in (sender_ref, receiver_ref):
        connection.execute(
            "INSERT INTO account_detector_states VALUES (?, ?, TRUE, 0.1, 2, 50.0, 'LOW', NULL)",
            (snapshots[0], account_ref),
        )
    connection.execute(
        "INSERT INTO account_detector_states VALUES (?, ?, TRUE, 1.0, 1, 100.0, 'HIGH', NULL)",
        (snapshots[1], sender_ref),
    )
    connection.execute(
        "INSERT INTO account_detector_states VALUES (?, ?, TRUE, 0.1, 2, 50.0, 'LOW', NULL)",
        (snapshots[1], receiver_ref),
    )
    alert_ref = alert_ref_for(SOURCE_DATASET, sender_ref, snapshots[1])
    connection.execute(
        """
        INSERT INTO network_alerts VALUES (?, ?, ?, ?, 1.0, 1, 100.0, 'ENTERED_HIGH', 'NOT_REVIEWED')
        """,
        (alert_ref, sender_ref, snapshots[1], cutoffs[1]),
    )
    assert materialize_transaction_review_states(connection, config_hash, 2) == 2
    reviews = connection.execute(
        """
        SELECT transactions.transaction_timestamp, review.detector_cutoff,
               review.aml_review_priority, review.alert_involvement,
               review.sender_related_alert_ref
        FROM transactions
        JOIN transaction_review_states AS review USING (transaction_ref)
        ORDER BY transactions.transaction_timestamp
        """
    ).fetchall()
    connection.close()
    assert reviews[0] == (
        datetime(2022, 9, 1, 12),
        datetime(2022, 9, 1),
        "LOW",
        False,
        None,
    )
    assert reviews[1] == (
        datetime(2022, 9, 2, 12),
        datetime(2022, 9, 2),
        "HIGH",
        True,
        alert_ref,
    )


def test_materialized_transaction_priority_covers_every_endpoint_matrix_combination(
    make_detector_source, tmp_path: Path
) -> None:
    combinations = list(itertools.product(tuple(ReviewBand), repeat=2))
    rows = [
        source_row(
            **{
                "Timestamp": f"2022/09/01 12:{index:02d}",
                "From Bank": f"S{index:02d}",
                "Account": f"SA{index:02d}",
                "To Bank": f"R{index:02d}",
                "Account.1": f"RA{index:02d}",
            }
        )
        for index in range(len(combinations))
    ]
    source = make_detector_source(rows, filename="matrix.csv")
    database = tmp_path / "matrix.duckdb"
    prepare_runtime_database(source_path=source, output_path=database)
    connection = duckdb.connect(str(database))
    create_detector_schema(connection)
    config_hash = detector_config_hash()
    cutoff = datetime(2022, 9, 1)
    snapshot_id = snapshot_id_for(SOURCE_DATASET, cutoff, config_hash)
    account_count = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    values = list(_snapshot_metadata_values(snapshot_id, cutoff, config_hash, account_count))
    values[13] = "COMPLETE"
    values[15] = cutoff
    values[17] = sum(band is not ReviewBand.UNSCORED for pair in combinations for band in pair)
    values[18] = values[17]
    connection.execute(
        "INSERT INTO detector_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        values,
    )
    refs = connection.execute(
        """
        SELECT source_row_ordinal, from_account_ref, to_account_ref
        FROM transactions ORDER BY source_row_ordinal
        """
    ).fetchall()
    for (_, sender_ref, receiver_ref), (sender_band, receiver_band) in zip(
        refs, combinations, strict=True
    ):
        for account_ref, band in (
            (sender_ref, sender_band),
            (receiver_ref, receiver_band),
        ):
            if band is ReviewBand.UNSCORED:
                connection.execute(
                    "INSERT INTO account_detector_states VALUES (?, ?, FALSE, NULL, NULL, NULL, 'UNSCORED', 'NO_SECOND_ORDER_CONTEXT')",
                    (snapshot_id, account_ref),
                )
            else:
                connection.execute(
                    "INSERT INTO account_detector_states VALUES (?, ?, TRUE, 0.5, 1, 100.0, ?, NULL)",
                    (snapshot_id, account_ref, band.value),
                )
    assert materialize_transaction_review_states(connection, config_hash, 1) == len(rows)
    priorities = [
        row[0]
        for row in connection.execute(
            """
            SELECT review.aml_review_priority
            FROM transactions
            JOIN transaction_review_states AS review USING (transaction_ref)
            ORDER BY transactions.source_row_ordinal
            """
        ).fetchall()
    ]
    connection.close()
    expected = []
    for sender, receiver in combinations:
        if ReviewBand.HIGH in {sender, receiver}:
            expected.append("HIGH")
        elif ReviewBand.MEDIUM in {sender, receiver}:
            expected.append("MEDIUM")
        elif sender is receiver is ReviewBand.LOW:
            expected.append("LOW")
        else:
            expected.append("UNSCORED")
    assert priorities == expected


def test_database_alert_transition_path_first_entry_continuity_and_reentry() -> None:
    connection = duckdb.connect(":memory:")
    create_detector_schema(connection)
    account_ref = "acct_transition"
    config_hash = detector_config_hash()
    sequence = [
        ReviewBand.LOW,
        ReviewBand.HIGH,
        ReviewBand.HIGH,
        ReviewBand.LOW,
        ReviewBand.HIGH,
    ]
    alert_indexes: list[int] = []
    for index, band in enumerate(sequence):
        cutoff = datetime(2022, 9, 1 + index)
        snapshot_id = snapshot_id_for(SOURCE_DATASET, cutoff, config_hash)
        values = list(_snapshot_metadata_values(snapshot_id, cutoff, config_hash, 1))
        values[13] = "RUNNING"
        connection.execute(
            "INSERT INTO detector_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
        )
        connection.execute(
            "INSERT INTO account_detector_states VALUES (?, ?, TRUE, 1.0, 1, 100.0, ?, NULL)",
            (snapshot_id, account_ref, band.value),
        )
        alert_rows = _alert_rows_for_snapshot(connection, snapshot_id, cutoff)
        if alert_rows:
            alert_indexes.append(index)
            connection.executemany(
                "INSERT INTO network_alerts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                alert_rows,
            )
        connection.execute(
            "UPDATE detector_snapshots SET status = 'COMPLETE' WHERE snapshot_id = ?",
            (snapshot_id,),
        )
    persisted = connection.execute(
        "SELECT entry_cutoff FROM network_alerts ORDER BY entry_cutoff"
    ).fetchall()
    connection.close()
    assert alert_indexes == [1, 4]
    assert persisted == [(datetime(2022, 9, 2),), (datetime(2022, 9, 5),)]


def test_persisted_table_columns_are_exact(prepared_detector_db: tuple[Path, Path]) -> None:
    database, _ = prepared_detector_db
    run_detector_pipeline(database)
    connection = duckdb.connect(str(database), read_only=True)
    for table, expected_columns in WP02_TABLE_COLUMNS.items():
        actual = tuple(
            row[1]
            for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall()
        )
        assert actual == expected_columns
    assert derive_snapshot_cutoffs(connection) == (
        datetime(2022, 9, 1),
        datetime(2022, 9, 2),
        datetime(2022, 9, 3),
    )
    connection.close()
