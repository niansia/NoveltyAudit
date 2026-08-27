"""Independent DOI and arXiv identifier resolution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from normalize_paper import normalize_arxiv_id, normalize_doi
from providers.arxiv import ArxivProvider
from providers.base import ProviderError
from providers.crossref import CrossrefProvider


def verify_paper_identifiers(
    paper: dict[str, Any],
    *,
    crossref: Any | None = None,
    arxiv: Any | None = None,
) -> list[dict[str, Any]]:
    crossref = crossref or CrossrefProvider()
    arxiv = arxiv or ArxivProvider()
    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    checks = []
    doi = normalize_doi(paper.get("doi"))
    if doi:
        try:
            resolved = crossref.get_by_id(doi)
            resolved_id = normalize_doi(resolved.get("doi"))
            checks.append({"type": "DOI", "identifier": doi, "provider": "crossref", "valid": resolved_id == doi, "resolved_identifier": resolved_id, "checked_at": checked_at, "error_code": None if resolved_id == doi else "IDENTIFIER_MISMATCH"})
        except ProviderError as error:
            checks.append({"type": "DOI", "identifier": doi, "provider": "crossref", "valid": False, "resolved_identifier": None, "checked_at": checked_at, "error_code": "PROVIDER_FAILURE", "error": str(error)})
    arxiv_id = normalize_arxiv_id(paper.get("arxiv_id"))
    if arxiv_id:
        try:
            resolved = arxiv.get_by_id(arxiv_id)
            resolved_id = normalize_arxiv_id(resolved.get("arxiv_id"))
            checks.append({"type": "ARXIV", "identifier": arxiv_id, "provider": "arxiv", "valid": resolved_id == arxiv_id, "resolved_identifier": resolved_id, "checked_at": checked_at, "error_code": None if resolved_id == arxiv_id else "IDENTIFIER_MISMATCH"})
        except ProviderError as error:
            checks.append({"type": "ARXIV", "identifier": arxiv_id, "provider": "arxiv", "valid": False, "resolved_identifier": None, "checked_at": checked_at, "error_code": "PROVIDER_FAILURE", "error": str(error)})
    return checks


def verify_records(records: Iterable[dict[str, Any]], **kwargs: Any) -> tuple[list[dict[str, Any]], str]:
    verified = []
    status = "COMPLETE"
    for original in records:
        paper = dict(original)
        checks = verify_paper_identifiers(paper, **kwargs)
        paper["citation_validation"] = checks
        if any(item.get("error_code") == "PROVIDER_FAILURE" for item in checks):
            status = "PARTIAL"
        elif status != "PARTIAL" and any(item.get("valid") is not True for item in checks):
            status = "FAILED"
        verified.append(paper)
    return verified, status
