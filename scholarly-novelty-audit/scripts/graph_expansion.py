"""Active backward/forward citation expansion for bridge discovery."""

from __future__ import annotations

from typing import Any

from deduplicate import deduplicate
from normalize_paper import normalize_doi
from providers.base import ProviderError
from resolve_dates import apply_cutoff_many


def _forms(value: Any) -> set[str]:
    if value in (None, ""):
        return set()
    raw = str(value).strip()
    forms = {raw.casefold(), raw.rsplit("/", 1)[-1].casefold()}
    doi = normalize_doi(raw)
    if doi and (raw.casefold().startswith("10.") or "doi" in raw.casefold()):
        forms.update({doi, f"doi:{doi}"})
    return forms


def _provider_id(paper: dict[str, Any], provider_name: str) -> str | None:
    provider_ids = paper.get("provider_ids") or {}
    if provider_ids.get(provider_name):
        return str(provider_ids[provider_name])
    if provider_name in {str(value) for value in paper.get("providers") or []}:
        return str(paper.get("id"))
    return None


def _anchors(paper_a: dict[str, Any], paper_b: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    counts = [paper_a.get("citation_count"), paper_b.get("citation_count")]
    if all(isinstance(value, int) and not isinstance(value, bool) for value in counts):
        ordered = sorted((paper_a, paper_b), key=lambda paper: (paper["citation_count"], str(paper["id"])))
        return [ordered[0]], "LOWER_CITATION_COUNT"
    return [paper_a, paper_b], "CITATION_COUNT_INCOMPLETE_EXPAND_BOTH"


def expand_graph(
    papers: list[dict[str, Any]],
    paper_a_id: str,
    paper_b_id: str,
    provider: Any,
    *,
    before: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    if not 1 <= limit <= 1000:
        raise ValueError("graph expansion limit must be between 1 and 1000")
    index = {str(paper.get("id")): paper for paper in papers}
    if paper_a_id not in index or paper_b_id not in index or paper_a_id == paper_b_id:
        raise ValueError("paper-a and paper-b must be distinct canonical IDs in the papers file")
    paper_a, paper_b = index[paper_a_id], index[paper_b_id]
    provider_name = str(provider.name)
    provider_ids = {
        paper_a_id: _provider_id(paper_a, provider_name),
        paper_b_id: _provider_id(paper_b, provider_name),
    }
    if not all(provider_ids.values()):
        raise ValueError(f"both endpoints require {provider_name} provider IDs for graph expansion")

    expansion_id = f"EXPAND-GRAPH:{provider_name}:{paper_a_id}:{paper_b_id}"
    fetched: list[dict[str, Any]] = []
    bridge_candidates: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    calls: list[dict[str, Any]] = []

    def record_call(direction: str, anchor_paper_id: str, results: list[dict[str, Any]]) -> None:
        calls.append({
            "direction": direction,
            "anchor_paper_id": anchor_paper_id,
            "returned_count": len(results),
            "limit": limit,
            "possibly_truncated": len(results) >= limit,
        })

    for endpoint_id in (paper_a_id, paper_b_id):
        try:
            # Retrieve a wider graph neighborhood and make the shared local
            # earliest-public-date resolver the historical eligibility gate.
            # Provider publication dates can otherwise hide an eligible preprint
            # whose later journal version falls after the cutoff.
            results = provider.references(provider_ids[endpoint_id], before=None, limit=limit)
            record_call("BACKWARD", endpoint_id, results)
            fetched.extend(results)
        except (ProviderError, NotImplementedError) as error:
            failures.append({"direction": "BACKWARD", "anchor_paper_id": endpoint_id, "detail": str(error)})

    anchors, selection_reason = _anchors(paper_a, paper_b)
    for anchor in anchors:
        anchor_id = str(anchor["id"])
        other_id = paper_b_id if anchor_id == paper_a_id else paper_a_id
        other_forms = _forms(provider_ids[other_id]) | _forms(other_id)
        try:
            results = provider.citations(provider_ids[anchor_id], before=None, limit=limit)
            record_call("FORWARD", anchor_id, results)
            for candidate in results:
                reference_forms = {form for value in candidate.get("references") or [] for form in _forms(value)}
                if reference_forms & other_forms:
                    bridge_candidates.append(candidate)
        except (ProviderError, NotImplementedError) as error:
            failures.append({"direction": "FORWARD", "anchor_paper_id": anchor_id, "detail": str(error)})

    additions = fetched + bridge_candidates
    for paper in additions:
        paper["found_by_query_ids"] = list(dict.fromkeys(
            (paper.get("found_by_query_ids") or []) + [expansion_id]
        ))
    merged = deduplicate(papers + additions)
    if before:
        merged = apply_cutoff_many(merged, before, strict=True)
    original_ids = set(index)
    new_ids = [str(paper.get("id")) for paper in merged if str(paper.get("id")) not in original_ids]
    bridge_keys = {
        str(paper.get("canonical_key") or paper.get("id")) for paper in deduplicate(bridge_candidates)
    }
    merged_bridge_ids = [
        str(paper.get("id")) for paper in merged
        if str(paper.get("canonical_key") or paper.get("id")) in bridge_keys
    ]
    discovered_ids = [
        str(paper.get("id")) for paper in merged
        if expansion_id in {str(value) for value in paper.get("found_by_query_ids") or []}
    ]
    partial_reasons = []
    if failures:
        partial_reasons.append("PROVIDER_FAILURE")
    if any(call["possibly_truncated"] for call in calls):
        partial_reasons.append("LIMIT_REACHED")
    return {
        "expansion_id": expansion_id,
        "status": "PARTIAL" if partial_reasons else "COMPLETE",
        "partial_reasons": partial_reasons,
        "provider": provider_name,
        "paper_ids": [paper_a_id, paper_b_id],
        "provider_ids": provider_ids,
        "cutoff": before,
        "temporal_recall_backstop": bool(before),
        "provider_cutoff_applied": False,
        "limit_per_call": limit,
        "anchor_selection": selection_reason,
        "calls": calls,
        "failures": failures,
        "bridge_candidate_ids": merged_bridge_ids,
        "discovered_paper_ids": discovered_ids,
        "new_paper_ids": new_ids,
        "papers": merged,
    }
