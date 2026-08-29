#!/usr/bin/env python3
"""Prepare the Trailsight V2 runtime-safe DuckDB from IBM AMLworld HI-Small."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trailsight_v2.data.errors import DataPreparationError
from trailsight_v2.data.prepare import prepare_runtime_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        help="external IBM HI-Small transaction CSV; defaults to IBM_HI_SMALL_TRANSACTIONS_PATH",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/v2/runtime/trailsight_v2.duckdb"),
        help="generated runtime-safe DuckDB path",
    )
    parser.add_argument("--batch-size", type=int, default=10_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.batch_size < 1:
        print("preparation failed: --batch-size must be positive", file=sys.stderr)
        return 2
    try:
        summary = prepare_runtime_database(
            source_path=arguments.source,
            output_path=arguments.output,
            batch_size=arguments.batch_size,
        )
    except DataPreparationError as exc:
        print(f"preparation failed: {exc}", file=sys.stderr)
        return 2
    for line in summary.lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
