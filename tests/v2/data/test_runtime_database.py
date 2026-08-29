from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import pytest

from trailsight_v2.data.constants import SOURCE_DATASET
from trailsight_v2.data.errors import GroundTruthLeakageError
from trailsight_v2.data.prepare import prepare_runtime_database
from trailsight_v2.data.queries import fetch_detector_edge_day_deltas
from trailsight_v2.data.schema import (
    WP01_RUNTIME_TABLES,
    assert_ground_truth_firewall,
    runtime_schema_columns,
)


def source_row(**overrides: str) -> dict[str, str]:
    row = {
        "Timestamp": "2022/09/01 00:20",
        "From Bank": "001",
        "Account": "A001",
        "To Bank": "Bank-B",
        "Account.1": "A002",
        "Amount Received": "100.00",
        "Receiving Currency": "USD",
        "Amount Paid": "100",
        "Payment Currency": "USD",
        "Payment Format": "ACH",
        "Is Laundering": "0",
    }
    row.update(overrides)
    return row


def fixture_rows() -> list[dict[str, str]]:
    return [
        source_row(
            **{
                "Timestamp": "2022/09/01 00:20",
                "From Bank": "001",
                "Account": "A",
                "To Bank": "002",
                "Account.1": "B",
                "Is Laundering": "1",
            }
        ),
        source_row(
            **{
                "Timestamp": "2022/09/01 02:20",
                "From Bank": "002",
                "Account": "B",
                "To Bank": "001",
                "Account.1": "A",
                "Amount Received": "50",
                "Amount Paid": "60",
                "Is Laundering": "0",
            }
        ),
        source_row(
            **{
                "Timestamp": "2022/09/02 01:00",
                "From Bank": "001",
                "Account": "A",
                "To Bank": "003",
                "Account.1": "A",
                "Receiving Currency": "USD",
                "Payment Currency": "CAD",
            }
        ),
        source_row(
            **{
                "Timestamp": "2022/09/02 04:00",
                "From Bank": "001",
                "Account": "SELF",
                "To Bank": "001",
                "Account.1": "SELF",
            }
        ),
    ]


def test_small_duckdb_preparation_schema_manifest_and_firewall(make_ibm_csv, tmp_path: Path) -> None:
    source = make_ibm_csv(fixture_rows())
    output = tmp_path / "runtime.duckdb"
    summary = prepare_runtime_database(source_path=source, output_path=output, batch_size=2)

    assert summary.row_count == 4
    assert summary.account_count == 4
    assert summary.bank_count == 3
    assert summary.edge_delta_count == 2
    assert summary.derived_snapshot_cutoff_count == 3
    assert summary.output_size_bytes > 0

    connection = duckdb.connect(str(output), read_only=True)
    schema = runtime_schema_columns(connection)
    assert set(WP01_RUNTIME_TABLES).issubset(schema)
    assert_ground_truth_firewall(connection)
    assert all(
        "launder" not in column.lower()
        for columns in schema.values()
        for column in columns
    )
    assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 4
    assert connection.execute(
        "SELECT COUNT(*) FROM transactions WHERE cross_currency"
    ).fetchone()[0] == 1

    manifest = connection.execute(
        """
        SELECT source_dataset, raw_transaction_sha256, row_count,
               min_timestamp, max_timestamp, data_contract_version
        FROM source_manifest
        """
    ).fetchone()
    assert manifest[0] == SOURCE_DATASET
    assert manifest[1] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest[2] == 4
    assert manifest[5] == "trailsight-v2-data-contract-v1"
    connection.close()


def test_detector_edge_day_inputs_are_canonical_undirected_unique_and_first_observed(
    make_ibm_csv, tmp_path: Path
) -> None:
    source = make_ibm_csv(fixture_rows())
    output = tmp_path / "runtime.duckdb"
    prepare_runtime_database(source_path=source, output_path=output)
    connection = duckdb.connect(str(output), read_only=True)
    edges = fetch_detector_edge_day_deltas(connection)
    connection.close()

    assert len(edges) == 2
    assert all(left < right for _, left, right in edges)
    assert edges[0][0].isoformat() == "2022-09-01"
    assert edges[1][0].isoformat() == "2022-09-02"


def test_account_identity_does_not_merge_same_account_id_across_banks(make_ibm_csv, tmp_path: Path) -> None:
    rows = [
        source_row(**{"From Bank": "001", "Account": "SAME"}),
        source_row(
            **{
                "Timestamp": "2022/09/01 00:21",
                "From Bank": "999",
                "Account": "SAME",
            }
        ),
    ]
    source = make_ibm_csv(rows)
    output = tmp_path / "runtime.duckdb"
    prepare_runtime_database(source_path=source, output_path=output)
    connection = duckdb.connect(str(output), read_only=True)
    refs = connection.execute(
        "SELECT account_ref FROM accounts WHERE account_id = 'SAME' ORDER BY bank_id"
    ).fetchall()
    connection.close()
    assert len(refs) == 2
    assert refs[0][0] != refs[1][0]


def test_firewall_detects_forbidden_runtime_column(tmp_path: Path) -> None:
    connection = duckdb.connect(str(tmp_path / "bad.duckdb"))
    for name in WP01_RUNTIME_TABLES:
        connection.execute(f"CREATE TABLE {name} (safe VARCHAR)")
    connection.execute("CREATE TABLE accidental_truth (is_laundering INTEGER)")
    with pytest.raises(GroundTruthLeakageError, match="accidental_truth.is_laundering"):
        assert_ground_truth_firewall(connection)
    connection.close()
