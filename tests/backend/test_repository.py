from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from conftest import build_runtime_database, selected_transaction, transaction
from trailsight.config import load_runtime_config
from trailsight.data.runtime_repository import RuntimeRepository
from trailsight.errors import ConfigurationError, DataIntegrityError


def test_valid_schema_opens_read_only(tmp_path: Path) -> None:
    path = build_runtime_database(tmp_path / "valid.duckdb")
    repository = RuntimeRepository(path)

    assert repository.list_cases()[0].case_ref == "demo-01"
    with pytest.raises(duckdb.Error):
        repository._connection.execute("CREATE TABLE forbidden_write (value INTEGER)")

    repository.close()


def test_repository_has_no_runtime_write_method(tmp_path: Path) -> None:
    path = build_runtime_database(tmp_path / "readonly.duckdb")
    repository = RuntimeRepository(path)

    public_methods = {
        name
        for name in dir(repository)
        if not name.startswith("_") and callable(getattr(repository, name))
    }
    assert not public_methods.intersection(
        {"execute", "insert", "update", "delete", "create", "write"}
    )
    repository.close()


def test_missing_database_fails(tmp_path: Path) -> None:
    with pytest.raises(DataIntegrityError, match="does not exist"):
        RuntimeRepository(tmp_path / "missing.duckdb")


def test_missing_runtime_table_fails(tmp_path: Path) -> None:
    path = tmp_path / "missing-table.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE TABLE cases (case_ref TEXT)")
    connection.close()

    with pytest.raises(DataIntegrityError, match="missing required tables"):
        RuntimeRepository(path)


def test_missing_runtime_column_fails(tmp_path: Path) -> None:
    path = build_runtime_database(tmp_path / "missing-column.duckdb")
    connection = duckdb.connect(str(path))
    connection.execute("ALTER TABLE transactions DROP COLUMN payment_format")
    connection.close()

    with pytest.raises(DataIntegrityError, match="missing required columns"):
        RuntimeRepository(path)


def test_non_decimal_runtime_amount_fails(tmp_path: Path) -> None:
    path = build_runtime_database(tmp_path / "wrong-type.duckdb")
    connection = duckdb.connect(str(path))
    connection.execute("ALTER TABLE transactions ALTER amount_paid TYPE DOUBLE")
    connection.close()

    with pytest.raises(DataIntegrityError, match="must use DECIMAL"):
        RuntimeRepository(path)


def test_forbidden_hidden_label_column_fails(tmp_path: Path) -> None:
    path = build_runtime_database(tmp_path / "hidden-label.duckdb")
    connection = duckdb.connect(str(path))
    connection.execute('ALTER TABLE transactions ADD COLUMN "Is Laundering" BOOLEAN')
    connection.close()

    with pytest.raises(DataIntegrityError, match="Forbidden hidden-label"):
        RuntimeRepository(path)


def test_case_history_is_constrained_by_case_role(tmp_path: Path) -> None:
    associated = transaction(1, datetime(2025, 1, 1))
    unassociated = transaction(2, datetime(2025, 1, 2))
    incoming = transaction(
        3,
        datetime(2025, 1, 3),
        from_bank="Other Bank",
        from_account="A000003",
        to_bank="Sender Bank",
        to_account="A016568",
    )
    path = build_runtime_database(
        tmp_path / "case-slice.duckdb",
        history=[associated],
        other_transactions=[unassociated, incoming],
    )
    repository = RuntimeRepository(path)
    rows = repository.get_case_history(
        "demo-01", sender_bank="Sender Bank", sender_account="A016568"
    )

    assert [row.transaction_ref for row in rows] == [associated["transaction_ref"]]
    repository.close()


def test_history_sender_uses_bank_and_account_identity(tmp_path: Path) -> None:
    wrong_bank = transaction(
        1,
        datetime(2025, 1, 1),
        from_bank="Different Bank",
        from_account="A016568",
    )
    path = build_runtime_database(
        tmp_path / "wrong-sender.duckdb", history=[wrong_bank]
    )
    repository = RuntimeRepository(path)

    with pytest.raises(DataIntegrityError, match="different sender"):
        repository.get_case_history(
            "demo-01", sender_bank="Sender Bank", sender_account="A016568"
        )
    repository.close()


def test_selected_role_must_match_case_metadata(tmp_path: Path) -> None:
    selected = selected_transaction()
    alternate = transaction(9, datetime(2025, 1, 1))
    path = build_runtime_database(
        tmp_path / "selected-mismatch.duckdb",
        selected=selected,
        other_transactions=[alternate],
    )
    connection = duckdb.connect(str(path))
    connection.execute(
        "UPDATE case_transactions SET transaction_ref = ? WHERE role = 'selected'",
        [alternate["transaction_ref"]],
    )
    connection.close()
    repository = RuntimeRepository(path)

    with pytest.raises(DataIntegrityError, match="do not match"):
        repository.get_selected_transaction("demo-01")
    repository.close()


def test_runtime_configuration_requires_database_path() -> None:
    with pytest.raises(ConfigurationError, match="TRAILSIGHT_DB_PATH"):
        load_runtime_config({})


def test_runtime_configuration_uses_approved_static_default() -> None:
    config = load_runtime_config({"TRAILSIGHT_DB_PATH": "runtime.duckdb"})

    assert config.database_path == Path("runtime.duckdb")
    assert config.static_directory == Path("frontend/dist")
