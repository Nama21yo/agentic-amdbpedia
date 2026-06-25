from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
VALIDATOR = PROJECT_ROOT / "scripts" / "validate_corpus.py"


def run_validator(corpus_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(corpus_dir)],
        check=False,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )


def test_validate_corpus_cli_success() -> None:
    result = run_validator(DATA_DIR)
    assert result.returncode == 0, result.stderr
    assert "Validated 7 classes and 28 properties" in result.stdout


def test_validate_corpus_cli_reports_missing_required_field(tmp_path: Path) -> None:
    broken_data = tmp_path / "data"
    shutil.copytree(DATA_DIR, broken_data)
    airport = broken_data / "Airport.md"
    airport.write_text(
        airport.read_text(encoding="utf-8").replace("- xsd type: xsd:string\n", "", 1),
        encoding="utf-8",
    )

    result = run_validator(broken_data)

    assert result.returncode == 1
    assert "Airport.md:9" in result.stderr
    assert "missing required field 'xsd type'" in result.stderr
