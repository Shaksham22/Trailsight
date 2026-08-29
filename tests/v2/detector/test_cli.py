from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run_script(script: str, *arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / script), *map(str, arguments)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_prepare_benchmark_and_offline_evaluation_clis(
    prepared_detector_db: tuple[Path, Path], tmp_path: Path
) -> None:
    database, source = prepared_detector_db
    prepared = run_script("v2_detector_prepare.py", "--database", database)
    assert prepared.returncode == 0, prepared.stderr
    assert "complete_snapshot_count=3" in prepared.stdout
    assert "transaction_review_state_count=4" in prepared.stdout

    benchmark = run_script("v2_detector_benchmark.py", "--database", database)
    assert benchmark.returncode == 0, benchmark.stderr
    assert "scorer=reference-dense-v1" in benchmark.stdout
    assert "workers=1" in benchmark.stdout
    assert "gate_pass=True" in benchmark.stdout

    report_path = tmp_path / "offline" / "report.json"
    evaluated = run_script(
        "v2_detector_offline_evaluate.py",
        "--database",
        database,
        "--hidden-source",
        source,
        "--output",
        report_path,
    )
    assert evaluated.returncode == 0, evaluated.stderr
    assert "labelled_transaction_count=1" in evaluated.stdout
    assert report_path.is_file()
    assert "txn_" not in report_path.read_text(encoding="utf-8")

