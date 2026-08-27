import json
import subprocess
import sys
from pathlib import Path

from report_assembly import RUNTIME_BINDING, report_hash, runtime_environment


def test_cli_validates_and_exports(valid_report, tmp_path):
    root = Path(__file__).resolve().parents[2]
    cli = root / "scripts" / "cli.py"
    source = tmp_path / "report.json"
    target = tmp_path / "report.md"
    source.write_text(json.dumps(valid_report), encoding="utf-8")
    validated = subprocess.run(
        [sys.executable, str(cli), "validate", "--input", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert validated.returncode == 0, validated.stderr
    assert validated.stdout.splitlines() == ["Schema: OK", "Invariants: OK", "NoveltyAudit report: VALID"]
    exported = subprocess.run(
        [sys.executable, str(cli), "export", "--input", str(source), "--format", "markdown", "--output", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert exported.returncode == 0, exported.stderr
    assert target.exists()


def test_cli_records_terminal_partial_when_report_retries_are_exhausted(valid_report, tmp_path):
    root = Path(__file__).resolve().parents[2]
    cli = root / "scripts" / "cli.py"
    source = tmp_path / "invalid-report.json"
    bound = tmp_path / "invalid-report.bound.json"
    state = tmp_path / "assembly-state.json"
    valid_report.pop("verdict")
    source.write_text(json.dumps(valid_report), encoding="utf-8")
    command = [
        sys.executable, str(cli), "report-attempt", "--input", str(source),
        "--output", str(bound), "--max-attempts", "3", "--state", str(state),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 40, first.stderr
    assert second.returncode == 40, second.stderr
    assert result.returncode == 10, result.stderr
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert payload["status"] == "PARTIAL"
    assert payload["retry_exhausted"] is True
    assert payload["conclusion_cap"] == "INCONCLUSIVE"
    assert [item["attempt"] for item in payload["attempts"]] == [1, 2, 3]
    assert payload["runtime_binding"] == RUNTIME_BINDING
    assert payload["report_hash"] == report_hash(json.loads(bound.read_text(encoding="utf-8")))


def test_report_attempt_cli_machine_binds_fake_runtime_before_complete(valid_report, tmp_path):
    root = Path(__file__).resolve().parents[2]
    cli = root / "scripts" / "cli.py"
    source = tmp_path / "fake-runtime-report.json"
    bound = tmp_path / "bound-report.json"
    state = tmp_path / "assembly-state.json"
    fake = {
        "python_version": "0.0.0-fake",
        "dependencies": {"jsonschema": "fake", "pypdf": "fake"},
    }
    valid_report["run_manifest"]["runtime_environment"] = fake
    source.write_text(json.dumps(valid_report), encoding="utf-8")

    result = subprocess.run([
        sys.executable, str(cli), "report-attempt", "--input", str(source),
        "--output", str(bound), "--max-attempts", "3", "--state", str(state),
    ], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert json.loads(source.read_text(encoding="utf-8"))["run_manifest"]["runtime_environment"] == fake
    bound_report = json.loads(bound.read_text(encoding="utf-8"))
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert bound_report["run_manifest"]["runtime_environment"] == runtime_environment()
    assert payload["status"] == "COMPLETE"
    assert payload["next_action"] == "EXPORT_MACHINE_BOUND_REPORT"
    assert payload["runtime_binding"] == RUNTIME_BINDING
    assert payload["report_hash"] == report_hash(bound_report)


def test_report_attempt_refuses_to_overwrite_input_or_state(valid_report, tmp_path):
    root = Path(__file__).resolve().parents[2]
    cli = root / "scripts" / "cli.py"
    source = tmp_path / "report.json"
    state = tmp_path / "assembly-state.json"
    source.write_text(json.dumps(valid_report), encoding="utf-8")
    original = source.read_bytes()

    result = subprocess.run([
        sys.executable, str(cli), "report-attempt", "--input", str(source),
        "--output", str(source), "--state", str(state),
    ], capture_output=True, text=True, check=False)

    assert result.returncode == 50
    assert "three different files" in result.stderr
    assert source.read_bytes() == original
    assert not state.exists()


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
    ], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["search_bound"] == {"max_papers": 3, "larger_combinations_assessed": False}
    assert "does not assess larger combinations" in payload["no_result_explanation"]
