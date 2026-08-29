#!/usr/bin/env python3
"""
Create a clean Trailsight repository ZIP for worker/ChatGPT handoffs.

Usage:
    Put this file in the Trailsight repository root and run it:
        python make_trailsight_zip.py

Output:
    A clean ZIP named Trailsight_WORKER_INPUT.zip is created beside
    the Trailsight project folder.

The ZIP keeps required checked-in metadata such as:
    data/v2/metadata/bank_country_v1.json

but excludes large/generated/private data such as:
    data/v2/runtime/
    data/v2/source/
    data/v2/offline-evaluation/
    *.duckdb
    raw IBM CSV/TXT files
    .git/
    .venv/
    node_modules/
    dist/
    caches
    .env files
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ZIP = PROJECT_ROOT.parent / f"{PROJECT_ROOT.name}_WORKER_INPUT.zip"


# Entire directories that should never be included.
EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    ".idea",
    ".vscode",
    "__MACOSX",
    "eval_results",
    "traces",
}

# Repository-relative directory prefixes containing generated/raw data.
# Important: data/v2/metadata is intentionally NOT excluded.
EXCLUDED_RELATIVE_DIRS = {
    Path("data/v2/runtime"),
    Path("data/v2/source"),
    Path("data/v2/offline-evaluation"),
}

# Exact filenames that should not be distributed.
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".coverage",
}

# Large/private/generated extensions.
EXCLUDED_SUFFIXES = {
    ".duckdb",
    ".duckdb.wal",
    ".db-wal",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
}

# Raw IBM AML files should remain external to the repository ZIP.
# Matching is case-insensitive.
EXCLUDED_IBM_NAME_PARTS = (
    "hi-small_trans.csv",
    "hi-small_accounts.csv",
    "hi-small_patterns.txt",
    "is laundering",
)


def is_under_excluded_relative_dir(relative_path: Path) -> bool:
    for excluded in EXCLUDED_RELATIVE_DIRS:
        if relative_path == excluded or excluded in relative_path.parents:
            return True
    return False


def should_exclude(path: Path) -> tuple[bool, str]:
    relative = path.relative_to(PROJECT_ROOT)

    # Exclude this ZIP utility's output if someone changes OUTPUT_ZIP later
    # to point inside the repository.
    try:
        if path.resolve() == OUTPUT_ZIP.resolve():
            return True, "output ZIP"
    except FileNotFoundError:
        pass

    if is_under_excluded_relative_dir(relative):
        return True, "generated/raw data directory"

    if any(part in EXCLUDED_DIR_NAMES for part in relative.parts[:-1]):
        return True, "excluded development directory"

    if path.name in EXCLUDED_FILE_NAMES:
        return True, "private/generated file"

    lower_name = path.name.lower()

    if lower_name.startswith(".env"):
        return True, "environment/secrets file"

    if any(lower_name.endswith(suffix.lower()) for suffix in EXCLUDED_SUFFIXES):
        return True, "generated database/cache file"

    if any(part in lower_name for part in EXCLUDED_IBM_NAME_PARTS):
        return True, "raw/evaluation IBM data"

    # Common macOS AppleDouble metadata files.
    if path.name.startswith("._"):
        return True, "macOS metadata"

    return False, ""


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def main() -> None:
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Output ZIP   : {OUTPUT_ZIP}")
    print()
    print("Creating clean worker-input ZIP...")

    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    included_files = 0
    included_bytes = 0
    skipped_files = 0
    skipped_bytes = 0

    with zipfile.ZipFile(
        OUTPUT_ZIP,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as archive:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            root_path = Path(root)

            # Prune excluded directory names before os.walk descends into them.
            dirs[:] = [
                d for d in dirs
                if d not in EXCLUDED_DIR_NAMES
                and not is_under_excluded_relative_dir(
                    (root_path / d).relative_to(PROJECT_ROOT)
                )
            ]

            for filename in files:
                path = root_path / filename
                excluded, _reason = should_exclude(path)

                if excluded:
                    skipped_files += 1
                    try:
                        skipped_bytes += path.stat().st_size
                    except OSError:
                        pass
                    continue

                relative = path.relative_to(PROJECT_ROOT)

                try:
                    size = path.stat().st_size
                except OSError as exc:
                    print(f"WARNING: Could not read {relative}: {exc}")
                    continue

                # Put the project folder at the top level of the ZIP.
                archive_name = Path(PROJECT_ROOT.name) / relative
                archive.write(path, archive_name.as_posix())

                included_files += 1
                included_bytes += size

    zip_size = OUTPUT_ZIP.stat().st_size

    print()
    print("DONE")
    print(f"Included files : {included_files}")
    print(f"Included size  : {human_size(included_bytes)} before compression")
    print(f"Skipped files  : {skipped_files}")
    print(f"Skipped size   : {human_size(skipped_bytes)}")
    print(f"ZIP size       : {human_size(zip_size)}")
    print()
    print(f"Created: {OUTPUT_ZIP}")
    print()
    print("The ZIP intentionally keeps data/v2/metadata but excludes:")
    print("  - data/v2/runtime")
    print("  - data/v2/source")
    print("  - data/v2/offline-evaluation")
    print("  - raw IBM HI-Small CSV/TXT files")
    print("  - DuckDB/generated databases")
    print("  - .git / .venv / node_modules / dist / caches")
    print("  - .env and common secret files")


if __name__ == "__main__":
    main()
