#!/usr/bin/env python3
"""Evaluate frozen detector priority outputs against offline IBM labels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trailsight_v2.detector.errors import DetectorError
from trailsight_v2.detector.offline_evaluation import evaluate_labelled_transaction_priorities


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--hidden-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        report = evaluate_labelled_transaction_priorities(
            database_path=arguments.database,
            hidden_source_path=arguments.hidden_source,
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(report.json(), encoding="utf-8")
    except (DetectorError, OSError) as exc:
        print(f"offline evaluation failed: {exc}", file=sys.stderr)
        return 2
    print(f"offline_evaluation_output={arguments.output.resolve()}")
    print(f"labelled_transaction_count={report.labelled_transaction_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

