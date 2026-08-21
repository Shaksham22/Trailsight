"""End-to-end orchestration for WP01 data preparation."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from trailsight_data.cases import (
    build_case_slices,
    select_required_cases,
    write_case_catalog_atomic,
)
from trailsight_data.database import (
    assert_no_duplicate_transaction_refs,
    create_staging_database,
    unique_runtime_transactions,
    write_runtime_database_atomic,
)
from trailsight_data.entities import build_entity_index, select_runtime_entities
from trailsight_data.errors import RuntimeValidationError
from trailsight_data.models import CaseDefinition
from trailsight_data.source import validate_source, write_normalized_transactions


@dataclass(frozen=True, slots=True)
class PreparationSummary:
    source_commit: str | None
    source_commit_verified: bool
    source_transaction_count: int
    duplicate_or_collision_count: int
    cases: tuple[CaseDefinition, ...]
    output_path: str
    table_row_counts: dict[str, int]
    history_row_counts: dict[str, int]

    def lines(self) -> tuple[str, ...]:
        verification = "verified" if self.source_commit_verified else "unverified"
        case_lines = tuple(
            f"case {case.case_ref}: {case.selected_transaction_ref} ({case.selection_kind})"
            for case in self.cases
        )
        counts = ", ".join(
            f"{table}={count}" for table, count in self.table_row_counts.items()
        )
        histories = ", ".join(
            f"{case_ref}={count}"
            for case_ref, count in sorted(self.history_row_counts.items())
        )
        return (
            f"TransXion commit: {self.source_commit or 'unavailable'} ({verification})",
            f"source transactions: {self.source_transaction_count}",
            f"duplicate/colliding txref-v1 values: {self.duplicate_or_collision_count}",
            *case_lines,
            f"runtime database: {self.output_path}",
            f"runtime rows: {counts}",
            f"past-only history rows: {histories}",
            "schema firewall: passed",
            "past-only validation: passed",
        )


def prepare_runtime_data(
    *,
    source_root: str | Path,
    case_catalog_path: str | Path,
    output_path: str | Path,
    allow_unverified_source: bool = False,
) -> PreparationSummary:
    source = validate_source(
        source_root, allow_unverified_source=allow_unverified_source
    )
    output = Path(output_path).expanduser().resolve()
    catalog = Path(case_catalog_path).expanduser().resolve()

    with tempfile.TemporaryDirectory(prefix="trailsight-prepare-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        normalized_csv = temporary_root / "transactions-allowlisted.csv"
        staging_database = temporary_root / "source-staging.duckdb"
        source_transaction_count = write_normalized_transactions(
            source.tx_path, normalized_csv
        )
        staging = create_staging_database(normalized_csv, staging_database)
        try:
            staged_count = int(
                staging.execute("SELECT COUNT(*) FROM source_transactions").fetchone()[0]
            )
            if staged_count != source_transaction_count:
                raise RuntimeValidationError(
                    "normalized staging row count mismatch: "
                    f"wrote {source_transaction_count}, loaded {staged_count}"
                )
            assert_no_duplicate_transaction_refs(staging)
            cases = select_required_cases(staging)
            case_slices = build_case_slices(staging, cases)
        finally:
            staging.close()

        runtime_transactions = unique_runtime_transactions(case_slices)
        entity_index = build_entity_index(source.person_path, source.merchant_path)
        runtime_entities = select_runtime_entities(
            entity_index, runtime_transactions.values()
        )
        report = write_runtime_database_atomic(
            output,
            case_slices,
            runtime_entities,
            expected_demo_history=74,
        )
        write_case_catalog_atomic(cases, catalog)

    return PreparationSummary(
        source_commit=source.commit,
        source_commit_verified=source.commit_verified,
        source_transaction_count=source_transaction_count,
        duplicate_or_collision_count=0,
        cases=cases,
        output_path=str(output),
        table_row_counts=report.table_row_counts,
        history_row_counts=report.history_row_counts,
    )
