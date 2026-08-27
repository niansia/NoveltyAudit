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


def test_mps_cli_discloses_bound_and_larger_combination_limit(tmp_path):
    root = Path(__file__).resolve().parents[2]
    cli = root / "scripts" / "cli.py"
    source = tmp_path / "papers.json"
    target = tmp_path / "mps.json"
    source.write_text(json.dumps({
        "claim_map": {"facets": [{"id": "F1", "critical": True}]},
        "papers": [{"id": "A", "cutoff_status": "ELIGIBLE", "coverage": {}}],
    }), encoding="utf-8")
    result = subprocess.run([
        sys.executable, str(cli), "mps", "--input", str(source), "--output", str(target),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["search_bound"] == {"max_papers": 3, "larger_combinations_assessed": False}
    assert "does not assess larger combinations" in payload["no_result_explanation"]
