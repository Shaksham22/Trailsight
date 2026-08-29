"""Isolated, aggregate-only evaluator for already-frozen label-blind outputs.

This module is deliberately not imported by ``trailsight_v2.detector`` or any
runtime preparation path. It opens the analytical database read-only, proves
that complete label-blind outputs already exist, and only then opens the raw
IBM CSV to read its offline-only label column.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb

from trailsight_v2.data.canonical import transaction_ref_for
from trailsight_v2.data.constants import REQUIRED_SOURCE_COLUMNS
from trailsight_v2.data.source import read_source_header, validate_source_header
from trailsight_v2.detector.errors import DetectorContractError

_OFFLINE_LABEL_COLUMN = "Is Laundering"


@dataclass(frozen=True, slots=True)
class OfflinePriorityEvaluation:
    evaluation_version: str
    labelled_transaction_count: int
    priority_counts: dict[str, int]
    high_or_medium_count: int
    high_or_medium_fraction: float | None

    def json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, indent=2) + "\n"


def validate_label_blind_outputs(connection: duckdb.DuckDBPyConnection) -> None:
    """Fail before any hidden source is opened unless outputs are complete."""
    transaction_count = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    review_count = connection.execute(
        "SELECT COUNT(*) FROM transaction_review_states"
    ).fetchone()[0]
    incomplete_count = connection.execute(
        "SELECT COUNT(*) FROM detector_snapshots WHERE status <> 'COMPLETE'"
    ).fetchone()[0]
    complete_count = connection.execute(
        "SELECT COUNT(*) FROM detector_snapshots WHERE status = 'COMPLETE'"
    ).fetchone()[0]
    if (
        transaction_count < 1
        or review_count != transaction_count
        or incomplete_count
        or complete_count < 1
    ):
        raise DetectorContractError(
            "offline evaluation requires a complete, already-materialized label-blind detector run"
        )


def _iter_positive_transaction_refs(source_path: Path):
    header = read_source_header(source_path)
    validate_source_header(header)
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for ordinal, values in enumerate(reader, start=1):
            if len(values) != len(REQUIRED_SOURCE_COLUMNS):
                raise DetectorContractError(
                    f"offline source row {ordinal} does not match the frozen IBM schema"
                )
            row = dict(zip(REQUIRED_SOURCE_COLUMNS, values, strict=True))
            label = row[_OFFLINE_LABEL_COLUMN].strip()
            if label not in {"0", "1"}:
                raise DetectorContractError(
                    f"offline source row {ordinal} has an invalid binary label"
                )
            if label == "1":
                yield transaction_ref_for(row, source_row_ordinal=ordinal)


def _priority_counts_for_refs(
    connection: duckdb.DuckDBPyConnection,
    transaction_refs: list[str],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for offset in range(0, len(transaction_refs), 500):
        chunk = transaction_refs[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = connection.execute(
            f"""
            SELECT aml_review_priority, COUNT(*)
            FROM transaction_review_states
            WHERE transaction_ref IN ({placeholders})
            GROUP BY aml_review_priority
            """,
            chunk,
        ).fetchall()
        counts.update({priority: count for priority, count in rows})
    return counts


def evaluate_labelled_transaction_priorities(
    *,
    database_path: str | Path,
    hidden_source_path: str | Path,
) -> OfflinePriorityEvaluation:
    database = Path(database_path).expanduser().resolve()
    source = Path(hidden_source_path).expanduser().resolve()
    connection = duckdb.connect(str(database), read_only=True)
    try:
        validate_label_blind_outputs(connection)
        positive_refs = list(_iter_positive_transaction_refs(source))
        counts = _priority_counts_for_refs(connection, positive_refs)
    finally:
        connection.close()
    matched = sum(counts.values())
    if matched != len(positive_refs):
        raise DetectorContractError(
            "offline labels do not resolve exactly to the frozen runtime transaction identities"
        )
    high_or_medium = counts["HIGH"] + counts["MEDIUM"]
    return OfflinePriorityEvaluation(
        evaluation_version="trailsight-offline-priority-eval-v1",
        labelled_transaction_count=matched,
        priority_counts={
            band: counts[band] for band in ("HIGH", "MEDIUM", "LOW", "UNSCORED")
        },
        high_or_medium_count=high_or_medium,
        high_or_medium_fraction=(high_or_medium / matched) if matched else None,
    )
