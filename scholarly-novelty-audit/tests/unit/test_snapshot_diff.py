import importlib.util
from copy import deepcopy
from pathlib import Path


path = Path(__file__).resolve().parents[2] / "scripts" / "snapshot_diff.py"
spec = importlib.util.spec_from_file_location("snapshot_diff", path)
snapshot_diff = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(snapshot_diff)


def test_snapshot_diff_separates_reasoning_and_literature_changes(valid_report):
    changed_verdict = deepcopy(valid_report)
    changed_verdict["verdict"]["novelty_risk"] = "MEDIUM"
    reasoning = snapshot_diff.diff_reports(valid_report, changed_verdict)
    assert reasoning["change_cause"] == "MODEL_OR_REASONING_CHANGE"

    changed_literature = deepcopy(valid_report)
    changed_literature["papers"][0]["title"] = "Updated title"
    literature = snapshot_diff.diff_reports(valid_report, changed_literature)
    assert literature["change_cause"] == "LITERATURE_SNAPSHOT_CHANGE"
    assert literature["candidate_changed"][0]["paper_id"] == "A"
