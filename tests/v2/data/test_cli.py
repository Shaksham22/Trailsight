from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path



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


def test_preparation_cli_uses_frozen_environment_variable(make_ibm_csv, tmp_path: Path) -> None:
    source = make_ibm_csv([source_row()])
    output = tmp_path / "cli.duckdb"
    environment = os.environ.copy()
    environment["IBM_HI_SMALL_TRANSACTIONS_PATH"] = str(source)
    result = subprocess.run(
        [sys.executable, "scripts/v2_data_prepare.py", "--output", str(output)],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "row_count=1" in result.stdout
    assert "runtime_schema_firewall=PASS" in result.stdout
    assert output.is_file()
