"""Draft 2020-12 validation for NoveltyAudit machine reports."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from normalize_paper import normalize_arxiv_id, split_arxiv_id


SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas"
ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
ARXIV_VERSION_LOCK = "LATEST_VERIFIED_VERSION_AT_OR_BEFORE_CUTOFF"
ARXIV_VERSION_SELECTION_METHODS = {
    "LOCAL_LATEST_VERSION_METADATA",
    "ARXIV_API_COMPLETE_VERSION_HISTORY",
}


def _date(value: Any) -> date | None:
    text = str(value or "").strip()
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _arxiv_pdf_identity(value: Any) -> tuple[str, int | None] | None:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return None
    if (parsed.hostname or "").casefold() not in ARXIV_HOSTS or not parsed.path.startswith("/pdf/"):
        return None
    identifier = parsed.path.removeprefix("/pdf/")
    if identifier.casefold().endswith(".pdf"):
        identifier = identifier[:-4]
    base_id, version = split_arxiv_id(identifier)
    return (base_id, version) if base_id else None


def _validate_acquisition_history(
    acquisition: dict[str, Any], paper_arxiv_id: str, path: str, errors: list[str]
) -> dict[int, dict[str, Any]]:
    raw_history = acquisition.get("arxiv_version_history")
    if not isinstance(raw_history, list) or not raw_history:
        errors.append(f"schema {path}.arxiv_version_history: must record the version-selection evidence")
        return {}
    entries: dict[int, dict[str, Any]] = {}
    previous_date: date | None = None
    for history_index, raw in enumerate(raw_history):
        history_path = f"{path}.arxiv_version_history.{history_index}"
        if not isinstance(raw, dict):
            errors.append(f"schema {history_path}: must be a structured arXiv version record")
            continue
        version = raw.get("version")
        submitted_at = _date(raw.get("submitted_at"))
        identity = _arxiv_pdf_identity(raw.get("pdf_url"))
        identifier_base, identifier_version = split_arxiv_id(raw.get("identifier"))
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            errors.append(f"schema {history_path}.version: must be a positive integer")
            continue
        if raw.get("verified") is not True:
            errors.append(f"schema {history_path}.verified: must be true")
        if submitted_at is None:
            errors.append(f"schema {history_path}.submitted_at: must be a complete verified date")
        if identifier_base != paper_arxiv_id or identifier_version != version:
            errors.append(f"schema {history_path}.identifier: must match the paper and version")
        if identity != (paper_arxiv_id, version):
            errors.append(f"schema {history_path}.pdf_url: must be an exact versioned arXiv PDF")
        if version in entries:
            errors.append(f"schema {history_path}.version: duplicate arXiv version")
            continue
        entries[version] = raw
        if submitted_at is not None:
            if previous_date is not None and submitted_at < previous_date:
                errors.append(f"schema {path}.arxiv_version_history: version dates are not monotonic")
            previous_date = submitted_at
    return entries


def validate_historical_arxiv_acquisitions(report: dict[str, Any]) -> list[str]:
    """Reject unversioned, unproven, or post-cutoff arXiv evidence in strict reports."""
    input_record = report.get("input") or {}
    if input_record.get("strict_date", True) is not True:
        return []
    papers = {
        str(paper.get("id")): paper
        for paper in report.get("papers") or []
        if isinstance(paper, dict) and paper.get("id")
    }
    report_cutoff = input_record.get("cutoff")
    errors: list[str] = []
    for index, acquisition in enumerate(report.get("fulltext_acquisitions") or []):
        if not isinstance(acquisition, dict):
            continue
        paper = papers.get(str(acquisition.get("paper_id") or ""))
        if not paper or paper.get("cutoff_status") != "ELIGIBLE":
            continue
        paper_arxiv_id = normalize_arxiv_id(paper.get("arxiv_id"))
        identity = _arxiv_pdf_identity(acquisition.get("source_url"))
        if not paper_arxiv_id or identity is None:
            continue

        path = f"fulltext_acquisitions.{index}"
        source_arxiv_id, source_version = identity
        if source_arxiv_id != paper_arxiv_id:
            errors.append(f"schema {path}.source_url: arXiv identifier disagrees with its paper")
        if source_version is None:
            errors.append(f"schema {path}.source_url: strict historical arXiv evidence requires an explicit vN")
        if acquisition.get("arxiv_version") != source_version:
            errors.append(f"schema {path}.arxiv_version: must match the explicit source URL version")
        if acquisition.get("version_lock") != ARXIV_VERSION_LOCK:
            errors.append(f"schema {path}.version_lock: missing strict historical arXiv version lock")
        method = acquisition.get("version_selection_method")
        if method not in ARXIV_VERSION_SELECTION_METHODS:
            errors.append(f"schema {path}.version_selection_method: invalid or missing arXiv selection method")

        cutoff_text = str(paper.get("cutoff") or report_cutoff or "")
        if acquisition.get("historical_cutoff") != cutoff_text:
            errors.append(f"schema {path}.historical_cutoff: disagrees with the audit cutoff")
        cutoff = _date(cutoff_text)
        version_date = _date(acquisition.get("arxiv_version_date"))
        if version_date is None:
            errors.append(f"schema {path}.arxiv_version_date: must be a complete verified date")
        elif cutoff is None or version_date > cutoff:
            errors.append(f"schema {path}.arxiv_version_date: selected arXiv version post-dates the cutoff")

        entries = _validate_acquisition_history(acquisition, paper_arxiv_id, path, errors)
        selected = entries.get(source_version) if isinstance(source_version, int) else None
        if selected is None:
            errors.append(f"schema {path}.arxiv_version_history: does not contain the selected version")
        else:
            if selected.get("submitted_at") != acquisition.get("arxiv_version_date"):
                errors.append(f"schema {path}.arxiv_version_date: disagrees with the version history")
            if _arxiv_pdf_identity(selected.get("pdf_url")) != identity:
                errors.append(f"schema {path}.source_url: disagrees with the version history")

        if entries and cutoff is not None:
            eligible_versions = [
                version
                for version, entry in entries.items()
                if (submitted := _date(entry.get("submitted_at"))) is not None
                and submitted <= cutoff
                and _arxiv_pdf_identity(entry.get("pdf_url")) == (paper_arxiv_id, version)
            ]
            recomputed = max(eligible_versions) if eligible_versions else None
            if method == "ARXIV_API_COMPLETE_VERSION_HISTORY":
                latest = max(entries)
                if acquisition.get("arxiv_version_history_complete") is not True:
                    errors.append(f"schema {path}.arxiv_version_history_complete: must be true for API history selection")
                if set(entries) != set(range(1, latest + 1)):
                    errors.append(f"schema {path}.arxiv_version_history: API history must be complete and contiguous")
                if (
                    paper.get("arxiv_latest_version_verified") is True
                    and paper.get("arxiv_version") != latest
                ):
                    errors.append(f"schema {path}.arxiv_version_history: disagrees with the verified latest paper version")
                if source_version != recomputed:
                    errors.append(f"schema {path}.arxiv_version: is not the latest verified version at or before the cutoff")
            elif method == "LOCAL_LATEST_VERSION_METADATA":
                if paper.get("arxiv_latest_version_verified") is not True:
                    errors.append(f"schema {path}.version_selection_method: local latest version was not independently verified")
                if paper.get("arxiv_version") != source_version:
                    errors.append(f"schema {path}.arxiv_version: local selection does not match the verified latest paper version")
    return errors


def validate_report_schema(report: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from referencing import Registry, Resource
    except ImportError:
        return ["schema validation unavailable: install jsonschema>=4.23"]

    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in SCHEMA_ROOT.glob("*.schema.json")]
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
    )
    report_schema = next(schema for schema in schemas if schema.get("title") == "NoveltyAudit Report")
    validator = Draft202012Validator(report_schema, registry=registry, format_checker=FormatChecker())
    errors = []
    for error in sorted(validator.iter_errors(report), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(value) for value in error.absolute_path) or "$"
        if error.validator == "format" and error.validator_value == "date-time":
            message = "must be an ISO 8601 date-time"
        elif error.validator == "format" and error.validator_value == "date":
            message = "must be a complete ISO 8601 date"
        else:
            message = error.message
        errors.append(f"schema {path}: {message}")
    errors.extend(validate_historical_arxiv_acquisitions(report))
    return errors
