"""Restart-safe offline snapshot, band, priority, and alert materialization."""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import duckdb
import networkx as nx

from trailsight_v2.data.constants import SOURCE_DATASET
from trailsight_v2.data.schema import WP01_RUNTIME_TABLES, assert_ground_truth_firewall
from trailsight_v2.detector.alerts import creates_high_entry_alert
from trailsight_v2.detector.constants import (
    ACTIVE_SCORER,
    ALERT_CREATED_STATE,
    ALERT_REASON_CODE,
    ALGORITHM_NAME,
    ALGORITHM_VARIANT,
    ALGORITHM_VERSION,
    COMMUNITY_ALGORITHM,
    COMMUNITY_RESOLUTION,
    COMMUNITY_SEED,
    DEFAULT_WORKERS,
    ELIGIBILITY_RULE_VERSION,
    IDENTITY_RULE_VERSION,
    UPSTREAM_CODE_PROVENANCE,
)
from trailsight_v2.detector.errors import DetectorContractError, DetectorPreparationError
from trailsight_v2.detector.graph import add_canonical_edges, preprocess_and_score
from trailsight_v2.detector.models import (
    AccountScore,
    DetectorRunSummary,
    ReviewBand,
    SnapshotRunResult,
    SnapshotStatus,
)
from trailsight_v2.detector.provenance import (
    alert_ref_for,
    detector_config_hash,
    snapshot_id_for,
)
from trailsight_v2.detector.ranking import assign_review_bands
from trailsight_v2.detector.schema import (
    WP02_RUNTIME_TABLES,
    assert_detector_schema,
    create_detector_schema,
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def configured_workers() -> int:
    raw = os.environ.get("GARG_WORKERS", str(DEFAULT_WORKERS))
    try:
        workers = int(raw)
    except ValueError as exc:
        raise DetectorPreparationError("GARG_WORKERS must be an integer") from exc
    if workers != 1:
        raise DetectorPreparationError(
            "reference-dense-v1 is frozen to GARG_WORKERS=1 until a target-Mac parity/resource benchmark approves another value"
        )
    return workers


def derive_snapshot_cutoffs(connection: duckdb.DuckDBPyConnection) -> tuple[datetime, ...]:
    minimum, maximum = connection.execute(
        "SELECT MIN(transaction_timestamp), MAX(transaction_timestamp) FROM transactions"
    ).fetchone()
    if minimum is None or maximum is None:
        raise DetectorContractError("transactions must be non-empty before detector preparation")
    first = datetime.combine(minimum.date(), time.min)
    final = datetime.combine(maximum.date() + timedelta(days=1), time.min)
    count = (final.date() - first.date()).days + 1
    return tuple(first + timedelta(days=offset) for offset in range(count))


def _first_observed_nodes_by_day(
    connection: duckdb.DuckDBPyConnection,
) -> dict[object, list[str]]:
    rows = connection.execute(
        """
        SELECT CAST(MIN(transaction_timestamp) AS DATE) AS first_day, account_ref
        FROM (
            SELECT transaction_timestamp, from_account_ref AS account_ref FROM transactions
            UNION ALL
            SELECT transaction_timestamp, to_account_ref AS account_ref FROM transactions
        )
        GROUP BY account_ref
        ORDER BY first_day, account_ref
        """
    ).fetchall()
    result: dict[object, list[str]] = {}
    for first_day, account_ref in rows:
        result.setdefault(first_day, []).append(account_ref)
    return result


def _validate_wp01_contract(connection: duckdb.DuckDBPyConnection) -> int:
    assert_ground_truth_firewall(connection, expected_tables=WP01_RUNTIME_TABLES)
    manifests = connection.execute(
        "SELECT source_dataset FROM source_manifest ORDER BY source_dataset"
    ).fetchall()
    if manifests != [(SOURCE_DATASET,)]:
        raise DetectorContractError(
            f"WP02 requires exactly source_dataset={SOURCE_DATASET!r}; found {manifests!r}"
        )
    account_count = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if account_count < 1:
        raise DetectorContractError("accounts must be non-empty before detector preparation")
    return account_count


def _snapshot_metadata_values(
    snapshot_id: str,
    cutoff: datetime,
    config_hash: str,
    account_count: int,
) -> tuple[object, ...]:
    return (
        snapshot_id,
        SOURCE_DATASET,
        cutoff,
        ALGORITHM_NAME,
        ALGORITHM_VARIANT,
        ALGORITHM_VERSION,
        UPSTREAM_CODE_PROVENANCE,
        IDENTITY_RULE_VERSION,
        ELIGIBILITY_RULE_VERSION,
        COMMUNITY_ALGORITHM,
        COMMUNITY_RESOLUTION,
        COMMUNITY_SEED,
        config_hash,
        SnapshotStatus.PENDING.value,
        None,
        None,
        account_count,
        0,
        0,
        None,
    )


def _ensure_snapshot_metadata(
    connection: duckdb.DuckDBPyConnection,
    cutoffs: tuple[datetime, ...],
    config_hash: str,
    account_count: int,
) -> None:
    other_configs = connection.execute(
        """
        SELECT DISTINCT config_hash
        FROM detector_snapshots
        WHERE source_dataset = ? AND config_hash <> ?
        """,
        (SOURCE_DATASET, config_hash),
    ).fetchall()
    if other_configs:
        raise DetectorContractError(
            "detector database contains snapshots from a different config; completed detector state is immutable"
        )

    expected_by_id = {
        snapshot_id_for(SOURCE_DATASET, cutoff, config_hash): cutoff for cutoff in cutoffs
    }
    actual_ids = {
        row[0]
        for row in connection.execute(
            "SELECT snapshot_id FROM detector_snapshots WHERE source_dataset = ?",
            (SOURCE_DATASET,),
        ).fetchall()
    }
    unexpected = actual_ids - set(expected_by_id)
    if unexpected:
        raise DetectorContractError(
            "detector database contains snapshots outside the derived timestamp range"
        )

    for snapshot_id, cutoff in expected_by_id.items():
        row = connection.execute(
            """
            SELECT source_dataset, cutoff_timestamp, algorithm_name, algorithm_variant,
                   algorithm_version, upstream_code_provenance, identity_rule_version,
                   eligibility_rule_version, community_algorithm, community_resolution,
                   community_seed, config_hash, account_count
            FROM detector_snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchone()
        expected = (
            SOURCE_DATASET,
            cutoff,
            ALGORITHM_NAME,
            ALGORITHM_VARIANT,
            ALGORITHM_VERSION,
            UPSTREAM_CODE_PROVENANCE,
            IDENTITY_RULE_VERSION,
            ELIGIBILITY_RULE_VERSION,
            COMMUNITY_ALGORITHM,
            COMMUNITY_RESOLUTION,
            COMMUNITY_SEED,
            config_hash,
            account_count,
        )
        if row is None:
            connection.execute(
                "INSERT INTO detector_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _snapshot_metadata_values(snapshot_id, cutoff, config_hash, account_count),
            )
        elif row != expected:
            raise DetectorContractError(
                f"snapshot metadata does not match frozen config for {snapshot_id}"
            )


def _verify_complete_snapshot(
    connection: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    account_count: int,
) -> tuple[int, int]:
    metadata = connection.execute(
        """
        SELECT eligible_account_count, scored_account_count
        FROM detector_snapshots
        WHERE snapshot_id = ? AND status = 'COMPLETE'
        """,
        (snapshot_id,),
    ).fetchone()
    if metadata is None:
        raise DetectorContractError(f"snapshot {snapshot_id} is not COMPLETE")
    state_count, eligible_count = connection.execute(
        """
        SELECT COUNT(*), COUNT(*) FILTER (WHERE scoring_eligible)
        FROM account_detector_states
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchone()
    support_count = connection.execute(
        "SELECT COUNT(*) FROM account_detector_support WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()[0]
    if state_count != account_count:
        raise DetectorContractError(
            f"COMPLETE snapshot {snapshot_id} has {state_count} account states; expected {account_count}"
        )
    if eligible_count != metadata[0] or support_count != metadata[0]:
        raise DetectorContractError(
            f"COMPLETE snapshot {snapshot_id} has inconsistent eligible/support counts"
        )
    if metadata[0] != metadata[1]:
        raise DetectorContractError(
            f"COMPLETE snapshot {snapshot_id} has inconsistent scored count"
        )
    return metadata


def _prepare_stage_rows(scores: Iterable[AccountScore]) -> list[tuple[object, ...]]:
    score_list = list(scores)
    ranked = assign_review_bands(
        (score.account_ref, score.network_pattern_score)
        for score in score_list
        if score.scoring_eligible and score.network_pattern_score is not None
    )
    rows: list[tuple[object, ...]] = []
    for score in score_list:
        rank = ranked.get(score.account_ref)
        rows.append(
            (
                score.account_ref,
                score.scoring_eligible,
                score.network_pattern_score,
                rank.rank if rank else None,
                rank.percentile if rank else None,
                rank.network_review_band.value if rank else ReviewBand.UNSCORED.value,
                score.unscored_reason.value if score.unscored_reason else None,
                score.first_order_neighbor_count,
                score.second_order_neighbor_count,
                score.community_index,
                score.block_measure_1,
                score.block_measure_2,
                score.block_measure_3,
            )
        )
    return rows


def _load_score_stage(
    connection: duckdb.DuckDBPyConnection,
    rows: list[tuple[object, ...]],
) -> None:
    connection.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS detector_score_stage (
            account_ref VARCHAR,
            scoring_eligible BOOLEAN,
            network_pattern_score DOUBLE,
            rank BIGINT,
            percentile DOUBLE,
            network_review_band VARCHAR,
            unscored_reason VARCHAR,
            first_order_neighbor_count BIGINT,
            second_order_neighbor_count BIGINT,
            community_index BIGINT,
            block_measure_1 DOUBLE,
            block_measure_2 DOUBLE,
            block_measure_3 DOUBLE
        )
        """
    )
    connection.execute("DELETE FROM detector_score_stage")
    if rows:
        connection.executemany(
            "INSERT INTO detector_score_stage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


def _alert_rows_for_snapshot(
    connection: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    cutoff: datetime,
) -> list[tuple[object, ...]]:
    previous = connection.execute(
        """
        SELECT snapshot_id
        FROM detector_snapshots
        WHERE source_dataset = ? AND status = 'COMPLETE' AND cutoff_timestamp < ?
        ORDER BY cutoff_timestamp DESC
        LIMIT 1
        """,
        (SOURCE_DATASET, cutoff),
    ).fetchone()
    previous_snapshot_id = previous[0] if previous else None
    if previous_snapshot_id is None:
        candidates = connection.execute(
            """
            SELECT account_ref, network_pattern_score, rank, percentile, NULL
            FROM account_detector_states
            WHERE snapshot_id = ? AND network_review_band = 'HIGH'
            ORDER BY account_ref
            """,
            (snapshot_id,),
        ).fetchall()
    else:
        candidates = connection.execute(
            """
            SELECT current.account_ref, current.network_pattern_score,
                   current.rank, current.percentile, previous.network_review_band
            FROM account_detector_states AS current
            JOIN account_detector_states AS previous
              ON previous.account_ref = current.account_ref
             AND previous.snapshot_id = ?
            WHERE current.snapshot_id = ?
              AND current.network_review_band = 'HIGH'
            ORDER BY current.account_ref
            """,
            (previous_snapshot_id, snapshot_id),
        ).fetchall()
    return [
        (
            alert_ref_for(SOURCE_DATASET, account_ref, snapshot_id),
            account_ref,
            snapshot_id,
            cutoff,
            score,
            rank,
            percentile,
            ALERT_REASON_CODE,
            ALERT_CREATED_STATE,
        )
        for account_ref, score, rank, percentile, previous_band in candidates
        if creates_high_entry_alert(previous_band, ReviewBand.HIGH)
    ]


def _persist_snapshot(
    connection: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    cutoff: datetime,
    scores: Iterable[AccountScore],
    account_count: int,
) -> tuple[int, int]:
    stage_rows = _prepare_stage_rows(scores)
    eligible_count = sum(bool(row[1]) for row in stage_rows)
    _load_score_stage(connection, stage_rows)
    connection.execute("BEGIN TRANSACTION")
    try:
        connection.execute(
            "DELETE FROM network_alerts WHERE entry_snapshot_id = ?", (snapshot_id,)
        )
        connection.execute(
            "DELETE FROM account_detector_support WHERE snapshot_id = ?", (snapshot_id,)
        )
        connection.execute(
            "DELETE FROM account_detector_states WHERE snapshot_id = ?", (snapshot_id,)
        )
        unknown_stage_accounts = connection.execute(
            """
            SELECT COUNT(*)
            FROM detector_score_stage AS stage
            LEFT JOIN accounts USING (account_ref)
            WHERE accounts.account_ref IS NULL
            """
        ).fetchone()[0]
        if unknown_stage_accounts:
            raise DetectorContractError("scorer produced account refs outside WP01 accounts")

        connection.execute(
            """
            INSERT INTO account_detector_states
            SELECT ?, accounts.account_ref,
                   COALESCE(stage.scoring_eligible, FALSE),
                   stage.network_pattern_score,
                   stage.rank,
                   stage.percentile,
                   COALESCE(stage.network_review_band, 'UNSCORED'),
                   CASE
                       WHEN stage.account_ref IS NULL THEN 'NOT_YET_OBSERVED'
                       WHEN stage.scoring_eligible THEN NULL
                       ELSE stage.unscored_reason
                   END
            FROM accounts
            LEFT JOIN detector_score_stage AS stage USING (account_ref)
            ORDER BY accounts.account_ref
            """,
            (snapshot_id,),
        )
        connection.execute(
            """
            INSERT INTO account_detector_support
            SELECT ?, account_ref, first_order_neighbor_count,
                   second_order_neighbor_count, community_index,
                   block_measure_1, block_measure_2, block_measure_3,
                   network_pattern_score
            FROM detector_score_stage
            WHERE scoring_eligible
            ORDER BY account_ref
            """,
            (snapshot_id,),
        )
        persisted_state_count = connection.execute(
            "SELECT COUNT(*) FROM account_detector_states WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()[0]
        if persisted_state_count != account_count:
            raise DetectorContractError(
                f"snapshot state count {persisted_state_count} does not equal account count {account_count}"
            )

        alert_rows = _alert_rows_for_snapshot(connection, snapshot_id, cutoff)
        if alert_rows:
            connection.executemany(
                "INSERT INTO network_alerts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                alert_rows,
            )
        connection.execute(
            """
            UPDATE detector_snapshots
            SET status = 'COMPLETE', completed_at = ?,
                eligible_account_count = ?, scored_account_count = ?,
                failure_message_safe = NULL
            WHERE snapshot_id = ? AND status = 'RUNNING'
            """,
            (_utc_now_naive(), eligible_count, eligible_count, snapshot_id),
        )
        updated_status = connection.execute(
            "SELECT status FROM detector_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        if updated_status != (SnapshotStatus.COMPLETE.value,):
            raise DetectorContractError("snapshot completion transition was not singular")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute("DELETE FROM detector_score_stage")
    return eligible_count, len(alert_rows)


def _mark_running(connection: duckdb.DuckDBPyConnection, snapshot_id: str) -> None:
    connection.execute(
        """
        UPDATE detector_snapshots
        SET status = 'RUNNING', started_at = ?, completed_at = NULL,
            eligible_account_count = 0, scored_account_count = 0,
            failure_message_safe = NULL
        WHERE snapshot_id = ? AND status <> 'COMPLETE'
        """,
        (_utc_now_naive(), snapshot_id),
    )


def _mark_failed(
    connection: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    exception: BaseException,
) -> None:
    safe_message = f"{type(exception).__name__}: detector snapshot failed; inspect offline preparation logs"
    connection.execute(
        """
        UPDATE detector_snapshots
        SET status = 'FAILED', completed_at = ?, failure_message_safe = ?
        WHERE snapshot_id = ? AND status <> 'COMPLETE'
        """,
        (_utc_now_naive(), safe_message, snapshot_id),
    )


_TRANSACTION_REVIEW_INSERT_SQL = """
WITH snapshot_intervals AS (
    SELECT snapshot_id, cutoff_timestamp,
           LEAD(cutoff_timestamp) OVER (ORDER BY cutoff_timestamp) AS next_cutoff
    FROM detector_snapshots
    WHERE source_dataset = ? AND config_hash = ? AND status = 'COMPLETE'
),
alert_intervals AS (
    SELECT account_ref, alert_ref, entry_cutoff,
           LEAD(entry_cutoff) OVER (
               PARTITION BY account_ref ORDER BY entry_cutoff, alert_ref
           ) AS next_alert_cutoff
    FROM network_alerts
)
INSERT INTO transaction_review_states
SELECT
    transactions.transaction_ref,
    snapshots.snapshot_id,
    snapshots.cutoff_timestamp,
    sender.network_review_band,
    receiver.network_review_band,
    CASE
        WHEN sender.network_review_band = 'HIGH' OR receiver.network_review_band = 'HIGH' THEN 'HIGH'
        WHEN sender.network_review_band = 'MEDIUM' OR receiver.network_review_band = 'MEDIUM' THEN 'MEDIUM'
        WHEN sender.network_review_band = 'LOW' AND receiver.network_review_band = 'LOW' THEN 'LOW'
        ELSE 'UNSCORED'
    END,
    CASE
        WHEN sender.network_review_band = 'HIGH' AND receiver.network_review_band = 'HIGH' THEN 'BOTH_ENDPOINTS_HIGH'
        WHEN sender.network_review_band = 'HIGH' THEN 'SENDER_HIGH'
        WHEN receiver.network_review_band = 'HIGH' THEN 'RECEIVER_HIGH'
        WHEN sender.network_review_band = 'MEDIUM' AND receiver.network_review_band = 'MEDIUM' THEN 'BOTH_ENDPOINTS_MEDIUM'
        WHEN sender.network_review_band = 'MEDIUM' THEN 'SENDER_MEDIUM'
        WHEN receiver.network_review_band = 'MEDIUM' THEN 'RECEIVER_MEDIUM'
        WHEN sender.network_review_band = 'LOW' AND receiver.network_review_band = 'LOW' THEN 'BOTH_ENDPOINTS_LOW'
        ELSE 'INSUFFICIENT_NETWORK_CONTEXT'
    END,
    CASE
        WHEN sender.network_review_band = 'HIGH' AND receiver.network_review_band = 'HIGH'
            THEN 'Sender and receiver are HIGH in the latest valid network snapshot; transaction review priority is HIGH.'
        WHEN sender.network_review_band = 'HIGH'
            THEN 'Sender is HIGH in the latest valid network snapshot; transaction review priority is HIGH.'
        WHEN receiver.network_review_band = 'HIGH'
            THEN 'Receiver is HIGH in the latest valid network snapshot; transaction review priority is HIGH.'
        WHEN sender.network_review_band = 'MEDIUM' AND receiver.network_review_band = 'MEDIUM'
            THEN 'Sender and receiver are MEDIUM in the latest valid network snapshot; transaction review priority is MEDIUM.'
        WHEN sender.network_review_band = 'MEDIUM'
            THEN 'Sender is MEDIUM and neither endpoint is HIGH in the latest valid network snapshot; transaction review priority is MEDIUM.'
        WHEN receiver.network_review_band = 'MEDIUM'
            THEN 'Receiver is MEDIUM and neither endpoint is HIGH in the latest valid network snapshot; transaction review priority is MEDIUM.'
        WHEN sender.network_review_band = 'LOW' AND receiver.network_review_band = 'LOW'
            THEN 'Sender and receiver are LOW in the latest valid network snapshot; transaction review priority is LOW.'
        ELSE 'Neither endpoint is HIGH or MEDIUM and at least one endpoint is UNSCORED; transaction review priority has insufficient network context.'
    END,
    sender_alert.alert_ref IS NOT NULL OR receiver_alert.alert_ref IS NOT NULL,
    sender_alert.alert_ref,
    receiver_alert.alert_ref
FROM transactions
JOIN snapshot_intervals AS snapshots
  ON transactions.transaction_timestamp >= snapshots.cutoff_timestamp
 AND (snapshots.next_cutoff IS NULL OR transactions.transaction_timestamp < snapshots.next_cutoff)
JOIN account_detector_states AS sender
  ON sender.snapshot_id = snapshots.snapshot_id
 AND sender.account_ref = transactions.from_account_ref
JOIN account_detector_states AS receiver
  ON receiver.snapshot_id = snapshots.snapshot_id
 AND receiver.account_ref = transactions.to_account_ref
LEFT JOIN alert_intervals AS sender_alert
  ON sender_alert.account_ref = transactions.from_account_ref
 AND transactions.transaction_timestamp >= sender_alert.entry_cutoff
 AND (sender_alert.next_alert_cutoff IS NULL OR transactions.transaction_timestamp < sender_alert.next_alert_cutoff)
LEFT JOIN alert_intervals AS receiver_alert
  ON receiver_alert.account_ref = transactions.to_account_ref
 AND transactions.transaction_timestamp >= receiver_alert.entry_cutoff
 AND (receiver_alert.next_alert_cutoff IS NULL OR transactions.transaction_timestamp < receiver_alert.next_alert_cutoff)
"""


def materialize_transaction_review_states(
    connection: duckdb.DuckDBPyConnection,
    config_hash: str,
    expected_snapshot_count: int,
) -> int:
    complete_count = connection.execute(
        """
        SELECT COUNT(*) FROM detector_snapshots
        WHERE source_dataset = ? AND config_hash = ? AND status = 'COMPLETE'
        """,
        (SOURCE_DATASET, config_hash),
    ).fetchone()[0]
    if complete_count != expected_snapshot_count:
        raise DetectorContractError(
            "transaction review states require the complete derived snapshot sequence"
        )
    transaction_count = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    existing_count = connection.execute(
        "SELECT COUNT(*) FROM transaction_review_states"
    ).fetchone()[0]
    if existing_count:
        if existing_count != transaction_count:
            raise DetectorContractError(
                "partial transaction_review_states cannot be exposed or overwritten"
            )
        invalid = connection.execute(
            """
            SELECT COUNT(*)
            FROM transaction_review_states AS review
            LEFT JOIN transactions USING (transaction_ref)
            LEFT JOIN detector_snapshots USING (snapshot_id)
            WHERE transactions.transaction_ref IS NULL
               OR review.snapshot_id IS NULL
               OR detector_snapshots.status <> 'COMPLETE'
               OR detector_snapshots.cutoff_timestamp > transactions.transaction_timestamp
               OR EXISTS (
                   SELECT 1
                   FROM detector_snapshots AS later
                   WHERE later.status = 'COMPLETE'
                     AND later.source_dataset = detector_snapshots.source_dataset
                     AND later.config_hash = detector_snapshots.config_hash
                     AND later.cutoff_timestamp > detector_snapshots.cutoff_timestamp
                     AND later.cutoff_timestamp <= transactions.transaction_timestamp
               )
            """
        ).fetchone()[0]
        missing = connection.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            LEFT JOIN transaction_review_states USING (transaction_ref)
            WHERE transaction_review_states.transaction_ref IS NULL
            """
        ).fetchone()[0]
        if invalid or missing:
            raise DetectorContractError("persisted transaction review state violates point-in-time rules")
        return existing_count

    connection.execute("BEGIN TRANSACTION")
    try:
        connection.execute(
            _TRANSACTION_REVIEW_INSERT_SQL,
            (SOURCE_DATASET, config_hash),
        )
        persisted = connection.execute(
            "SELECT COUNT(*) FROM transaction_review_states"
        ).fetchone()[0]
        if persisted != transaction_count:
            raise DetectorContractError(
                f"materialized {persisted} transaction review states; expected {transaction_count}"
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return transaction_count


def run_detector_pipeline(
    database_path: str | Path,
    *,
    workers: int | None = None,
) -> DetectorRunSummary:
    if workers is not None and workers != 1:
        raise DetectorPreparationError(
            "reference-dense-v1 supports only one worker until target-Mac parity/resource approval"
        )
    if workers is None:
        configured_workers()
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise DetectorPreparationError(f"runtime DuckDB does not exist: {path}")
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        connection = duckdb.connect(str(path))
        account_count = _validate_wp01_contract(connection)
        create_detector_schema(connection)
        config_hash = detector_config_hash()
        cutoffs = derive_snapshot_cutoffs(connection)
        _ensure_snapshot_metadata(connection, cutoffs, config_hash, account_count)
        first_observed_nodes = _first_observed_nodes_by_day(connection)

        graph = nx.Graph()
        previous_cutoff: datetime | None = None
        results: list[SnapshotRunResult] = []
        for cutoff in cutoffs:
            if previous_cutoff is not None:
                for observed_day, account_refs in first_observed_nodes.items():
                    if previous_cutoff.date() <= observed_day < cutoff.date():
                        graph.add_nodes_from(account_refs)
                edge_rows = connection.execute(
                    """
                    SELECT account_ref_a, account_ref_b
                    FROM detector_edge_day_deltas
                    WHERE edge_day >= ? AND edge_day < ?
                    ORDER BY edge_day, account_ref_a, account_ref_b
                    """,
                    (previous_cutoff.date(), cutoff.date()),
                ).fetchall()
                add_canonical_edges(graph, edge_rows)
            snapshot_id = snapshot_id_for(SOURCE_DATASET, cutoff, config_hash)
            status = connection.execute(
                "SELECT status FROM detector_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()[0]
            if status == SnapshotStatus.COMPLETE.value:
                eligible_count, scored_count = _verify_complete_snapshot(
                    connection, snapshot_id, account_count
                )
                alert_count = connection.execute(
                    "SELECT COUNT(*) FROM network_alerts WHERE entry_snapshot_id = ?",
                    (snapshot_id,),
                ).fetchone()[0]
                results.append(
                    SnapshotRunResult(
                        snapshot_id,
                        cutoff,
                        SnapshotStatus.COMPLETE,
                        account_count,
                        eligible_count,
                        scored_count,
                        alert_count,
                        True,
                    )
                )
                previous_cutoff = cutoff
                continue

            _mark_running(connection, snapshot_id)
            try:
                if cutoff == cutoffs[0]:
                    scores: list[AccountScore] = []
                else:
                    filtered_graph, scores = preprocess_and_score(graph)
                    del filtered_graph
                eligible_count, alert_count = _persist_snapshot(
                    connection,
                    snapshot_id,
                    cutoff,
                    scores,
                    account_count,
                )
            except Exception as exc:
                _mark_failed(connection, snapshot_id, exc)
                raise DetectorPreparationError(
                    f"detector snapshot {snapshot_id} failed safely"
                ) from exc
            results.append(
                SnapshotRunResult(
                    snapshot_id,
                    cutoff,
                    SnapshotStatus.COMPLETE,
                    account_count,
                    eligible_count,
                    eligible_count,
                    alert_count,
                    False,
                )
            )
            previous_cutoff = cutoff

        transaction_review_count = materialize_transaction_review_states(
            connection,
            config_hash,
            len(cutoffs),
        )
        assert_detector_schema(connection)
        assert_ground_truth_firewall(
            connection,
            expected_tables=(*WP01_RUNTIME_TABLES, *WP02_RUNTIME_TABLES),
        )
        connection.execute("CHECKPOINT")
        return DetectorRunSummary(
            database_path=str(path),
            config_hash=config_hash,
            snapshot_results=tuple(results),
            transaction_review_state_count=transaction_review_count,
        )
    except (duckdb.Error, OSError, DetectorContractError) as exc:
        raise DetectorPreparationError(str(exc)) from exc
    finally:
        if connection is not None:
            connection.close()
