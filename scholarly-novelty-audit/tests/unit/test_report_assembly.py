from copy import deepcopy

import pytest
import report_assembly
from report_assembly import RUNTIME_BINDING, evaluate_report_attempt, report_hash


def test_valid_report_completes_without_retry(valid_report):
    result = evaluate_report_attempt(valid_report, max_attempts=3)
    assert result["status"] == "COMPLETE"
    assert result["report_valid"] is True
    assert result["retry_exhausted"] is False
    assert result["conclusion_cap"] == "NONE"
    assert result["validation_errors"] == []
    assert result["runtime_binding"] == RUNTIME_BINDING
    assert result["runtime_environment"] == valid_report["run_manifest"]["runtime_environment"]
    assert result["report_hash"] == report_hash(valid_report)
    assert result["next_action"] == "EXPORT_MACHINE_BOUND_REPORT"
    assert result["audit_identity"] == {
        "audit_id": valid_report["audit_id"],
        "claim_id": valid_report["claim_map"]["claim_id"],
        "claim_freeze_hash": valid_report["claim_map"]["freeze_hash"],
        "cutoff": valid_report["run_manifest"]["cutoff"],
    }


def test_report_attempt_overwrites_fake_runtime_before_validation_and_hash(valid_report, monkeypatch):
    fake = {
        "python_version": "0.0.0-fake",
        "dependencies": {"jsonschema": "fake", "pypdf": "fake"},
    }
    actual = {
        "python_version": "3.12.13",
        "dependencies": {"jsonschema": "4.26.0", "pypdf": "6.16.2"},
    }
    valid_report["run_manifest"]["runtime_environment"] = fake
    monkeypatch.setattr(report_assembly, "runtime_environment", lambda: actual)

    result = evaluate_report_attempt(valid_report, max_attempts=3)

    assert result["status"] == "COMPLETE"
    assert valid_report["run_manifest"]["runtime_environment"] == actual
    assert result["runtime_environment"] == actual
    assert result["attempts"][0]["runtime_environment"] == actual
    assert result["report_hash"] == report_hash(valid_report)


def test_invalid_report_requires_retry_before_budget_is_exhausted(valid_report):
    report = deepcopy(valid_report)
    report.pop("verdict")
    result = evaluate_report_attempt(report, max_attempts=2)
    assert result["status"] == "RETRY_REQUIRED"
    assert result["retry_exhausted"] is False
    assert result["conclusion_cap"] == "INCONCLUSIVE"
    assert result["validation_errors"]


def test_invalid_final_attempt_is_terminal_partial(valid_report):
    report = deepcopy(valid_report)
    report.pop("verdict")
    first = evaluate_report_attempt(report, max_attempts=2)
    result = evaluate_report_attempt(report, max_attempts=2, previous_state=first)
    assert result["status"] == "PARTIAL"
    assert result["report_valid"] is False
    assert result["retry_exhausted"] is True
    assert result["next_action"] == "DISCLOSE_RETRY_EXHAUSTION_AND_RETURN_INCONCLUSIVE"


@pytest.mark.parametrize("maximum", [0, 4])
def test_invalid_retry_budget_is_rejected(valid_report, maximum):
    with pytest.raises(ValueError):
        evaluate_report_attempt(valid_report, max_attempts=maximum)


def test_retry_history_must_be_sequential_and_nonterminal(valid_report):
    report = deepcopy(valid_report)
    report.pop("verdict")
    state = evaluate_report_attempt(report, max_attempts=3)
    state["attempts"][0]["attempt"] = 2
    with pytest.raises(ValueError, match="not sequential"):
        evaluate_report_attempt(report, max_attempts=3, previous_state=state)

    terminal = evaluate_report_attempt(valid_report, max_attempts=3)
    with pytest.raises(ValueError, match="already terminal"):
        evaluate_report_attempt(valid_report, max_attempts=3, previous_state=terminal)


def test_retry_state_top_level_must_match_latest_history(valid_report):
    report = deepcopy(valid_report)
    report.pop("verdict")
    state = evaluate_report_attempt(report, max_attempts=3)
    state["report_hash"] = "sha256:tampered"
    with pytest.raises(ValueError, match="conflicts with its latest"):
        evaluate_report_attempt(report, max_attempts=3, previous_state=state)


def test_retry_state_cannot_forge_previous_runtime_binding(valid_report):
    report = deepcopy(valid_report)
    report.pop("verdict")
    state = evaluate_report_attempt(report, max_attempts=3)
    state["attempts"][0]["runtime_environment"] = {
        "python_version": "0.0.0-fake",
        "dependencies": {"jsonschema": "fake", "pypdf": "fake"},
    }
    with pytest.raises(ValueError, match="conflicts with its latest"):
        evaluate_report_attempt(report, max_attempts=3, previous_state=state)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("audit_id",), "different-audit"),
        (("claim_map", "claim_id"), "different-claim"),
        (("claim_map", "freeze_hash"), "sha256:different-freeze"),
        (("run_manifest", "cutoff"), "2025-01-01"),
    ],
)
def test_retry_state_cannot_cross_audit_identity(valid_report, path, replacement):
    invalid = deepcopy(valid_report)
    invalid.pop("verdict")
    state = evaluate_report_attempt(invalid, max_attempts=3)
    other = deepcopy(valid_report)
    target = other
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(ValueError, match="different audit identity"):
        evaluate_report_attempt(other, max_attempts=3, previous_state=state)
