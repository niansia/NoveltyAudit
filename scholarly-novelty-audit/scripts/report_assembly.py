"""Deterministic host-agent report validation and retry-exhaustion contract."""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
import platform
from typing import Any

from validate_output import validate_report


def runtime_environment() -> dict[str, Any]:
    """Return the resolved interpreter and evidence-processing dependency versions."""
    return {
        "python_version": platform.python_version(),
        "dependencies": {
            "jsonschema": metadata.version("jsonschema"),
            "pypdf": metadata.version("pypdf"),
        },
    }


RUNTIME_BINDING = "MACHINE_INJECTED_BEFORE_VALIDATION_AND_HASH"
TOOL_VERSION = "0.3.2"


def bind_runtime_environment(report: dict[str, Any]) -> dict[str, Any]:
    """Replace host-supplied runtime claims with this process's resolved environment."""
    manifest = report.get("run_manifest")
    if not isinstance(manifest, dict):
        manifest = {}
    else:
        manifest = dict(manifest)
    actual = runtime_environment()
    manifest["runtime_environment"] = actual
    manifest["tool_version"] = TOOL_VERSION
    report["run_manifest"] = manifest
    return actual


def report_hash(report: dict[str, Any]) -> str:
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def audit_identity(report: dict[str, Any]) -> dict[str, str]:
    claim_map = report.get("claim_map") if isinstance(report.get("claim_map"), dict) else {}
    run_manifest = report.get("run_manifest") if isinstance(report.get("run_manifest"), dict) else {}
    identity = {
        "audit_id": str(report.get("audit_id") or "").strip(),
        "claim_id": str(claim_map.get("claim_id") or "").strip(),
        "claim_freeze_hash": str(claim_map.get("freeze_hash") or "").strip(),
        "cutoff": str(run_manifest.get("cutoff") or "").strip(),
    }
    missing = [key for key, value in identity.items() if not value]
    if missing:
        raise ValueError(f"report lacks immutable audit identity fields: {', '.join(missing)}")
    return identity


def audit_identity_hash(identity: dict[str, str]) -> str:
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def evaluate_report_attempt(
    report: dict[str, Any],
    *,
    max_attempts: int,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Machine-bind runtime provenance, then append one auditable validation attempt."""
    if not 1 <= max_attempts <= 3:
        raise ValueError("max-attempts must be between 1 and 3")
    actual_runtime = bind_runtime_environment(report)
    identity = audit_identity(report)
    identity_digest = audit_identity_hash(identity)
    attempts: list[dict[str, Any]] = []
    if previous_state is not None:
        if previous_state.get("status") != "RETRY_REQUIRED":
            raise ValueError("report assembly state is already terminal")
        if previous_state.get("max_attempts") != max_attempts:
            raise ValueError("max-attempts cannot change within one assembly state")
        if previous_state.get("audit_identity") != identity:
            raise ValueError("report assembly state belongs to a different audit identity")
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
            or previous_state.get("runtime_binding") != RUNTIME_BINDING
            or previous_state.get("runtime_environment") != latest.get("runtime_environment")
            or latest.get("audit_identity_hash") != identity_digest
            or any(item.get("audit_identity_hash") != identity_digest for item in previous_attempts)
            or any(item.get("runtime_binding") != RUNTIME_BINDING for item in previous_attempts)
            or any(not isinstance(item.get("runtime_environment"), dict) for item in previous_attempts)
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
        "audit_identity_hash": identity_digest,
        "runtime_binding": RUNTIME_BINDING,
        "runtime_environment": actual_runtime,
        "valid": not errors,
        "validation_errors": errors,
    })
    if not errors:
        status = "COMPLETE"
        next_action = "EXPORT_MACHINE_BOUND_REPORT"
    elif attempt < max_attempts:
        status = "RETRY_REQUIRED"
        next_action = "REPAIR_FROM_VALIDATION_ERRORS"
    else:
        status = "PARTIAL"
        next_action = "DISCLOSE_RETRY_EXHAUSTION_AND_RETURN_INCONCLUSIVE"

    return {
        "status": status,
        "audit_identity": identity,
        "runtime_binding": RUNTIME_BINDING,
        "runtime_environment": actual_runtime,
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
