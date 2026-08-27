import json
import subprocess
import sys
from pathlib import Path


def test_cli_validates_and_exports(valid_report, tmp_path):
    root = Path(__file__).resolve().parents[2]
    cli = root / "scripts" / "cli.py"
    source = tmp_path / "report.json"
    target = tmp_path / "report.md"
    source.write_text(json.dumps(valid_report), encoding="utf-8")
    validated = subprocess.run([sys.executable, str(cli), "validate", "--input", str(source)], capture_output=True, text=True)
    assert validated.returncode == 0, validated.stderr
    assert validated.stdout.splitlines() == ["Schema: OK", "Invariants: OK", "NoveltyAudit report: VALID"]
    exported = subprocess.run([sys.executable, str(cli), "export", "--input", str(source), "--format", "markdown", "--output", str(target)], capture_output=True, text=True)
    assert exported.returncode == 0, exported.stderr
    assert target.exists()
