"""Normalize provider-specific scholarly records into a stable shape."""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any, Iterable


DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)
ARXIV_PREFIX = re.compile(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:\s*)", re.I)
ARXIV_VERSION = re.compile(r"v\d+$", re.I)
NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
SPACE = re.compile(r"\s+")


def normalize_doi(value: Any) -> str | None:
    if not value:
        return None
    doi = DOI_PREFIX.sub("", str(value).strip()).strip().rstrip(".,;)")
    return doi.casefold() or None


def normalize_arxiv_id(value: Any) -> str | None:
    if not value:
        return None
    arxiv_id = ARXIV_PREFIX.sub("", str(value).strip()).replace(".pdf", "")
    arxiv_id = ARXIV_VERSION.sub("", arxiv_id).strip().casefold()
    return arxiv_id or None


def normalize_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return SPACE.sub(" ", NON_WORD.sub(" ", text)).strip()


def normalize_author(author: Any) -> dict[str, Any]:
    if isinstance(author, str):
        return {"name": SPACE.sub(" ", author.strip())}
    if isinstance(author, dict):
        result = {"name": SPACE.sub(" ", str(author.get("name") or "").strip())}
        for key in ("orcid", "id"):
            if author.get(key):
                result[key] = str(author[key])
        return result
    return {"name": str(author)}


def _string_list(values: Any) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    return list(dict.fromkeys(str(value) for value in values if value))


def canonical_key(paper: dict[str, Any]) -> str:
    if paper.get("doi"):
        return f"doi:{normalize_doi(paper['doi'])}"
    if paper.get("arxiv_id"):
        return f"arxiv:{normalize_arxiv_id(paper['arxiv_id'])}"
    title = normalize_title(paper.get("title"))
    authors = paper.get("authors") or []
    first = normalize_title(authors[0].get("name") if authors and isinstance(authors[0], dict) else authors[0] if authors else "")
    year = paper.get("year") or "unknown"
    return f"title:{title}|{first}|{year}"


def normalize_paper(record: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
    """Return a provider-neutral paper record without mutating the input."""
    source = deepcopy(record)
    external_ids = source.get("external_ids") or source.get("externalIds") or {}
    doi = normalize_doi(source.get("doi") or external_ids.get("DOI") or external_ids.get("doi"))
    arxiv_id = normalize_arxiv_id(
        source.get("arxiv_id") or external_ids.get("ArXiv") or external_ids.get("arxiv")
    )
    authors = [normalize_author(author) for author in (source.get("authors") or [])]
    providers = _string_list(source.get("providers"))
    if provider and provider not in providers:
        providers.append(provider)

    result: dict[str, Any] = {
        "id": str(source.get("id") or source.get("paper_id") or ""),
        "title": SPACE.sub(" ", str(source.get("title") or "").strip()),
        "title_normalized": normalize_title(source.get("title")),
        "abstract": source.get("abstract"),
        "authors": authors,
        "year": source.get("year"),
        "venue": source.get("venue"),
        "doi": doi,
        "arxiv_id": arxiv_id,
        "url": source.get("url"),
        "providers": providers,
        "provider_ids": dict(source.get("provider_ids") or {}),
        "dates": list(source.get("dates") or []),
        "references": _string_list(source.get("references")),
        "citation_count": source.get("citation_count"),
        "open_access": source.get("open_access"),
        "raw_provenance": list(source.get("raw_provenance") or []),
    }
    if provider and result["id"]:
        result["provider_ids"].setdefault(provider, result["id"])
    result["canonical_key"] = canonical_key(result)
    return result


def normalize_many(records: Iterable[dict[str, Any]], provider: str | None = None) -> list[dict[str, Any]]:
    return [normalize_paper(record, provider=provider) for record in records]

