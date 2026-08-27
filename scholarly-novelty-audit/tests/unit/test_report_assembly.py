from copy import deepcopy

import pytest

from report_assembly import evaluate_report_attempt


def test_valid_report_completes_without_retry(valid_report):
    result = evaluate_report_attempt(valid_report, max_attempts=3)
    assert result["status"] == "COMPLETE"
    assert result["report_valid"] is True
    assert result["retry_exhausted"] is False
    assert result["conclusion_cap"] == "NONE"
    assert result["validation_errors"] == []


def test_invalid_report_requires_retry_before_budget_is_exhausted(valid_report):
    report = deepcopy(valid_report)
    report.pop("claim_map")
    result = evaluate_report_attempt(report, max_attempts=2)
    assert result["status"] == "RETRY_REQUIRED"
    assert result["retry_exhausted"] is False
    assert result["conclusion_cap"] == "INCONCLUSIVE"
    assert result["validation_errors"]


def test_invalid_final_attempt_is_terminal_partial(valid_report):
    report = deepcopy(valid_report)
    report.pop("claim_map")
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
    report.pop("claim_map")
    state = evaluate_report_attempt(report, max_attempts=3)
    state["attempts"][0]["attempt"] = 2
    with pytest.raises(ValueError, match="not sequential"):
        evaluate_report_attempt(report, max_attempts=3, previous_state=state)

    terminal = evaluate_report_attempt(valid_report, max_attempts=3)
    with pytest.raises(ValueError, match="already terminal"):
        evaluate_report_attempt(valid_report, max_attempts=3, previous_state=terminal)


def test_retry_state_top_level_must_match_latest_history(valid_report):
    report = deepcopy(valid_report)
    report.pop("claim_map")
    state = evaluate_report_attempt(report, max_attempts=3)
    state["report_hash"] = "sha256:tampered"
    with pytest.raises(ValueError, match="conflicts with its latest"):
        evaluate_report_attempt(report, max_attempts=3, previous_state=state)
