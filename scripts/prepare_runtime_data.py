#!/usr/bin/env python3
"""Build Trailsight's bounded runtime DuckDB from the pinned TransXion source."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trailsight_data.errors import DataPreparationError
from trailsight_data.prepare import prepare_runtime_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument(
        "--case-catalog",
        type=Path,
        default=Path("data/cases/cases.yaml"),
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--allow-unverified-source",
        action="store_true",
        help="developer fixtures only; never use for acceptance preparation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        summary = prepare_runtime_data(
            source_root=arguments.source_root,
            case_catalog_path=arguments.case_catalog,
            output_path=arguments.output,
            allow_unverified_source=arguments.allow_unverified_source,
        )
    except DataPreparationError as exc:
        print(f"preparation failed: {exc}", file=sys.stderr)
        return 2
    for line in summary.lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
