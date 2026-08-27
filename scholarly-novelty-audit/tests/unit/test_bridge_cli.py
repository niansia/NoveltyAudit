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
