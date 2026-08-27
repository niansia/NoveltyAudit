"""Deterministic host-agent report validation and retry-exhaustion contract."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from validate_output import validate_report


def report_hash(report: dict[str, Any]) -> str:
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def evaluate_report_attempt(
    report: dict[str, Any],
    *,
    max_attempts: int,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one auditable retry attempt without accepting invalid output."""
    if not 1 <= max_attempts <= 3:
        raise ValueError("max-attempts must be between 1 and 3")
    attempts: list[dict[str, Any]] = []
    if previous_state is not None:
        if previous_state.get("status") != "RETRY_REQUIRED":
            raise ValueError("report assembly state is already terminal")
        if previous_state.get("max_attempts") != max_attempts:
            raise ValueError("max-attempts cannot change within one assembly state")
        previous_attempts = previous_state.get("attempts")
        if not isinstance(previous_attempts, list) or not previous_attempts:
            raise ValueError("report assembly state lacks attempt history")
        if previous_state.get("attempt_count") != len(previous_attempts):
            raise ValueError("report assembly attempt count disagrees with its history")
        if [item.get("attempt") for item in previous_attempts if isinstance(item, dict)] != list(
            range(1, len(previous_attempts) + 1)
        ):
            raise ValueError("report assembly attempt history is not sequential")
        latest = previous_attempts[-1]
        if (
            latest.get("valid") is not False
            or previous_state.get("report_valid") is not False
            or previous_state.get("retry_exhausted") is not False
            or previous_state.get("report_hash") != latest.get("report_hash")
            or previous_state.get("validation_errors") != latest.get("validation_errors")
        ):
            raise ValueError("report assembly state conflicts with its latest retry record")
        attempts = list(previous_attempts)

    attempt = len(attempts) + 1
    if attempt > max_attempts:
        raise ValueError("report retry budget is already exhausted")

    errors = validate_report(report)
    digest = report_hash(report)
    attempts.append({
        "attempt": attempt,
        "report_hash": digest,
        "valid": not errors,
        "validation_errors": errors,
    })
    if not errors:
        status = "COMPLETE"
        next_action = "EXPORT_VALIDATED_REPORT"
    elif attempt < max_attempts:
        status = "RETRY_REQUIRED"
        next_action = "REPAIR_FROM_VALIDATION_ERRORS"
    else:
        status = "PARTIAL"
        next_action = "DISCLOSE_RETRY_EXHAUSTION_AND_RETURN_INCONCLUSIVE"

    return {
        "status": status,
        "report_valid": not errors,
        "attempt_count": attempt,
        "max_attempts": max_attempts,
        "retry_exhausted": bool(errors and attempt == max_attempts),
        "conclusion_cap": "NONE" if not errors else "INCONCLUSIVE",
        "next_action": next_action,
        "report_hash": digest,
        "validation_errors": errors,
        "attempts": attempts,
    }
