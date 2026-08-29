#!/usr/bin/env python3
"""Benchmark full-final HI-Small GARG preprocessing/scoring without DB writes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trailsight_v2.detector.benchmark import benchmark_final_snapshot
from trailsight_v2.detector.errors import DetectorError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/v2/runtime/trailsight_v2.duckdb"),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="optional generated benchmark report path outside the runtime DB",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = benchmark_final_snapshot(arguments.database)
    except (DetectorError, OSError) as exc:
        print(f"benchmark failed: {exc}", file=sys.stderr)
        return 2
    for line in result.lines():
        print(line)
    if arguments.json_output:
        arguments.json_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.json_output.write_text(result.json(), encoding="utf-8")
    return 0 if result.gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

