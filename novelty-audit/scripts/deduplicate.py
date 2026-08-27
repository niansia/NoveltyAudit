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


def merge_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(records[0])
    merged["versions"] = []
    for record in records:
        merged["versions"].append({
            "id": record.get("id"),
            "doi": record.get("doi"),
            "arxiv_id": record.get("arxiv_id"),
            "providers": record.get("providers", []),
            "dates": record.get("dates", []),
        })
        for key in ("title", "abstract", "venue", "doi", "arxiv_id", "url", "year", "citation_count", "open_access"):
            merged[key] = _prefer(merged.get(key), record.get(key))
        for key in ("providers", "references", "dates", "raw_provenance"):
            items = merged.get(key, []) + record.get(key, [])
            seen: set[str] = set()
            merged[key] = [item for item in items if not (repr(item) in seen or seen.add(repr(item)))]
        merged.setdefault("provider_ids", {}).update(record.get("provider_ids") or {})
        if len(record.get("authors") or []) > len(merged.get("authors") or []):
            merged["authors"] = record["authors"]
    merged["canonical_key"] = next(
        (f"doi:{merged['doi']}" for _ in [0] if merged.get("doi")),
        f"arxiv:{merged['arxiv_id']}" if merged.get("arxiv_id") else merged.get("canonical_key"),
    )
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
