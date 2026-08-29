#!/usr/bin/env python3
"""Materialize Trailsight V2 GARG snapshots, priorities, and alerts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trailsight_v2.detector.errors import DetectorError
from trailsight_v2.detector.pipeline import run_detector_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/v2/runtime/trailsight_v2.duckdb"),
        help="WP01 runtime-safe DuckDB to extend atomically with WP02 outputs",
    )
    parser.add_argument("--workers", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        summary = run_detector_pipeline(arguments.database, workers=arguments.workers)
    except DetectorError as exc:
        print(f"detector preparation failed: {exc}", file=sys.stderr)
        return 2
    for line in summary.lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

