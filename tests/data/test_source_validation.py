from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from trailsight_data.errors import SourceValidationError
from trailsight_data.source import REQUIRED_TRANSACTION_HEADERS, validate_source


def test_missing_source_root_fails(tmp_path: Path) -> None:
    with pytest.raises(SourceValidationError, match="does not exist"):
        validate_source(tmp_path / "missing")


def test_missing_transaction_file_fails(make_source) -> None:
    source_root = make_source()
    (source_root / "data" / "tx.csv").unlink()
    with pytest.raises(SourceValidationError, match="tx.csv"):
        validate_source(source_root, allow_unverified_source=True)


def test_unresolved_git_lfs_pointer_fails(make_source) -> None:
    source_root = make_source()
    (source_root / "data" / "tx.csv").write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:abc\nsize 123\n",
        encoding="utf-8",
    )
    with pytest.raises(SourceValidationError, match="unresolved Git LFS pointer"):
        validate_source(source_root, allow_unverified_source=True)


def test_unexpected_source_commit_fails(make_source) -> None:
    source_root = make_source()
    subprocess.run(["git", "init", "-q", str(source_root)], check=True)
    subprocess.run(
        ["git", "-C", str(source_root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source_root), "config", "user.name", "Test"], check=True
    )
    subprocess.run(["git", "-C", str(source_root), "add", "data"], check=True)
    subprocess.run(
        ["git", "-C", str(source_root), "commit", "-qm", "fixture"], check=True
    )
    actual = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with pytest.raises(SourceValidationError, match=f"actual {actual}"):
        validate_source(source_root)


def test_missing_required_transaction_header_fails(make_source) -> None:
    header = tuple(
        name for name in REQUIRED_TRANSACTION_HEADERS if name != "To Account"
    )
    source_root = make_source(tx_header=header, tx_rows=[["x"] * len(header)])
    with pytest.raises(SourceValidationError, match="To Account"):
        validate_source(source_root, allow_unverified_source=True)


def test_pinned_explicit_header_names_validate(make_source) -> None:
    source_root = make_source()
    result = validate_source(source_root, allow_unverified_source=True)
    assert result.commit is None
    assert result.commit_verified is False

