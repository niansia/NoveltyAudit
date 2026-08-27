import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_bridge_is_a_first_class_cli_command(tmp_path):
    papers = [
        {"id": "A", "references": [], "cutoff_status": "ELIGIBLE"},
        {"id": "B", "references": [], "cutoff_status": "ELIGIBLE"},
        {"id": "C", "references": ["A", "B"], "cutoff_status": "ELIGIBLE"},
    ]
    source = tmp_path / "papers.json"
    output = tmp_path / "bridges.json"
    source.write_text(json.dumps(papers), encoding="utf-8")
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "cli.py"), "bridge",
        "--papers", str(source), "--paper-a", "A", "--paper-b", "B", "--output", str(output),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["graph_bridges"][0]["type"] == "CO_CITATION"
    assert payload["textual_bridge_required"] is True
    assert payload["bridge_policy"]["status"] == "SENSITIVITY_CHECKED"
    assert payload["bridge_policy"]["high_citation_threshold"] == 500
    assert payload["bridge_policy"]["evidence"]["preregistered"] is False


def test_custom_bridge_threshold_requires_a_policy_source(tmp_path):
    source = tmp_path / "papers.json"
    output = tmp_path / "bridges.json"
    source.write_text(json.dumps([
        {"id": "A", "references": [], "citation_count": 1, "cutoff_status": "ELIGIBLE"},
        {"id": "B", "references": [], "citation_count": 2, "cutoff_status": "ELIGIBLE"},
    ]), encoding="utf-8")
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "cli.py"), "bridge",
        "--papers", str(source), "--paper-a", "A", "--paper-b", "B",
        "--high-citation-threshold", "999", "--output", str(output),
    ], capture_output=True, text=True)
    assert result.returncode == 50
    assert "requires --bridge-policy-source" in result.stderr

    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "cli.py"), "bridge",
        "--papers", str(source), "--paper-a", "A", "--paper-b", "B",
        "--high-citation-threshold", "999",
        "--bridge-policy-source", "Documented local policy DOI:10.0000/example",
        "--output", str(output),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))["bridge_policy"]
    assert payload["status"] == "DOCUMENTED_OVERRIDE"
    assert payload["evidence"] == {"dataset": None, "method": None, "preregistered": None}


def test_calibrated_bridge_threshold_requires_machine_readable_evidence(tmp_path):
    source = tmp_path / "papers.json"
    output = tmp_path / "bridges.json"
    source.write_text(json.dumps([
        {"id": "A", "references": [], "citation_count": 1, "cutoff_status": "ELIGIBLE"},
        {"id": "B", "references": [], "citation_count": 2, "cutoff_status": "ELIGIBLE"},
    ]), encoding="utf-8")
    base = [
        sys.executable, str(ROOT / "scripts" / "cli.py"), "bridge",
        "--papers", str(source), "--paper-a", "A", "--paper-b", "B",
        "--high-citation-threshold", "999", "--bridge-policy-source", "Protocol DOI:10.0000/example",
    ]
    incomplete = subprocess.run([
        *base, "--calibration-dataset", "field-set-v1", "--output", str(output),
    ], capture_output=True, text=True)
    assert incomplete.returncode == 50
    assert "CALIBRATED requires" in incomplete.stderr

    result = subprocess.run([
        *base,
        "--calibration-dataset", "field-set-v1",
        "--calibration-method", "Preregistered threshold selection",
        "--calibration-preregistered",
        "--output", str(output),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))["bridge_policy"]
    assert payload["status"] == "CALIBRATED"
    assert payload["evidence"] == {
        "dataset": "field-set-v1",
        "method": "Preregistered threshold selection",
        "preregistered": True,
    }
