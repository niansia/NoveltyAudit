"""Canonical merge for preprint, DOI, and provider duplicates."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Iterable

from normalize_paper import normalize_many, normalize_title


def _author_tokens(paper: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for author in paper.get("authors") or []:
        name = author.get("name") if isinstance(author, dict) else author
        normalized = normalize_title(name)
        if normalized:
            result.add(normalized.split()[-1])
    return result


def _same_work(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("doi") and b.get("doi"):
        return a.get("doi") == b.get("doi")
    if a.get("arxiv_id") and b.get("arxiv_id"):
        return a.get("arxiv_id") == b.get("arxiv_id")
    title_a, title_b = a.get("title_normalized", ""), b.get("title_normalized", "")
    if not title_a or not title_b:
        return False
    years = {a.get("year"), b.get("year")} - {None, ""}
    if len(years) == 2:
        try:
            if abs(int(a.get("year")) - int(b.get("year"))) > 2:
                return False
        except (TypeError, ValueError):
            return False
    similarity = SequenceMatcher(None, title_a, title_b).ratio()
    author_overlap = bool(_author_tokens(a) & _author_tokens(b))
    return similarity >= 0.97 and author_overlap


def _prefer(left: Any, right: Any) -> Any:
    if left in (None, "", [], {}):
        return right
    if isinstance(left, str) and isinstance(right, str) and len(right) > len(left):
        return right
    return left


def _merge_unique(left: list[Any], right: list[Any]) -> list[Any]:
    items = left + right
    seen: set[str] = set()
    return [item for item in items if not (repr(item) in seen or seen.add(repr(item)))]


def merge_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(records[0])
    merged["versions"] = []
    latest_verified_versions: set[int] = set()
    for record in records:
        merged["versions"].append({
            "id": record.get("id"),
            "doi": record.get("doi"),
            "arxiv_id": record.get("arxiv_id"),
            "arxiv_version": record.get("arxiv_version"),
            "arxiv_latest_version_verified": bool(record.get("arxiv_latest_version_verified", False)),
            "arxiv_versions": record.get("arxiv_versions", []),
            "providers": record.get("providers", []),
            "dates": record.get("dates", []),
            "fulltext_urls": record.get("fulltext_urls", []),
        })
        for key in ("title", "abstract", "venue", "doi", "arxiv_id", "url", "year", "open_access"):
            merged[key] = _prefer(merged.get(key), record.get(key))
        known_arxiv_versions = [
            value for value in (merged.get("arxiv_version"), record.get("arxiv_version"))
            if isinstance(value, int) and not isinstance(value, bool) and value >= 1
        ]
        merged["arxiv_version"] = max(known_arxiv_versions) if known_arxiv_versions else None
        record_version = record.get("arxiv_version")
        if (
            record.get("arxiv_latest_version_verified") is True
            and isinstance(record_version, int)
            and not isinstance(record_version, bool)
            and record_version >= 1
        ):
            latest_verified_versions.add(record_version)
        citation_counts = [
            value for value in (merged.get("citation_count"), record.get("citation_count"))
            if isinstance(value, int) and not isinstance(value, bool)
        ]
        merged["citation_count"] = max(citation_counts) if citation_counts else None
        for key in (
            "providers", "references", "dates", "raw_provenance", "found_by_query_ids",
            "fulltext_urls", "arxiv_versions",
        ):
            merged[key] = _merge_unique(merged.get(key, []), record.get(key, []))
        provider_ids = merged.setdefault("provider_ids", {})
        for provider, provider_id in (record.get("provider_ids") or {}).items():
            provider_ids.setdefault(provider, provider_id)
        if len(record.get("authors") or []) > len(merged.get("authors") or []):
            merged["authors"] = record["authors"]
    merged["arxiv_latest_version_verified"] = bool(
        merged.get("arxiv_version") in latest_verified_versions
    )
    merged["canonical_key"] = next(
        (f"doi:{merged['doi']}" for _ in [0] if merged.get("doi")),
        f"arxiv:{merged['arxiv_id']}" if merged.get("arxiv_id") else merged.get("canonical_key"),
    )
    merged["cluster_id"] = merged["canonical_key"]
    return merged


def deduplicate(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = normalize_many(records)
    groups: list[list[dict[str, Any]]] = []
    for paper in normalized:
        for group in groups:
            if any(_same_work(paper, member) for member in group):
                group.append(paper)
                break
        else:
            groups.append([paper])
    return [merge_records(group) for group in groups]
