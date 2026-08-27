"""Active backward/forward citation expansion for bridge discovery."""

from __future__ import annotations

from datetime import date
from typing import Any

from deduplicate import deduplicate
from normalize_paper import normalize_doi
from providers.base import GraphResult, ProviderError
from resolve_dates import apply_cutoff_many, resolve_earliest_public_date


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


def _observation_window_days(
    paper_a: dict[str, Any], paper_b: dict[str, Any], cutoff: str | None,
) -> int | None:
    if not cutoff:
        return None
    dates = [
        resolve_earliest_public_date(paper).get("earliest_public_date")
        for paper in (paper_a, paper_b)
    ]
    if not all(dates):
        return None
    return (date.fromisoformat(cutoff) - max(date.fromisoformat(value) for value in dates)).days


def _graph_result(
    provider: Any,
    method: str,
    paper_id: str,
    *,
    before: str | None,
    limit: int,
) -> GraphResult:
    metadata_method = getattr(provider, f"{method}_with_metadata", None)
    if callable(metadata_method):
        result = metadata_method(paper_id, before=before, limit=limit)
        if not isinstance(result, GraphResult):
            raise TypeError(f"{method}_with_metadata must return GraphResult")
        return result
    papers = getattr(provider, method)(paper_id, before=before, limit=limit)
    if not isinstance(papers, list):
        raise TypeError(f"{method} must return a list of papers")
    # Legacy provider adapters have no explicit continuation signal. Fail closed
    # instead of converting a short but potentially incomplete list into proof
    # of provider exhaustion.
    return GraphResult(papers=papers, exhausted=False, next_token="UNREPORTED")


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

    def record_call(direction: str, anchor_paper_id: str, result: GraphResult) -> None:
        calls.append({
            "direction": direction,
            "anchor_paper_id": anchor_paper_id,
            "returned_count": result.returned_count,
            "limit": limit,
            "exhausted": result.exhausted,
            "next_token": result.next_token,
            "provider_total": result.provider_total,
            "raw_examined_count": result.raw_examined_count,
            "possibly_truncated": not result.exhausted,
        })

    for endpoint_id in (paper_a_id, paper_b_id):
        try:
            # Retrieve a wider graph neighborhood and make the shared local
            # earliest-public-date resolver the historical eligibility gate.
            # Provider publication dates can otherwise hide an eligible preprint
            # whose later journal version falls after the cutoff.
            result = _graph_result(provider, "references", provider_ids[endpoint_id], before=None, limit=limit)
            record_call("BACKWARD", endpoint_id, result)
            fetched.extend(result.papers)
        except (ProviderError, NotImplementedError) as error:
            failures.append({"direction": "BACKWARD", "anchor_paper_id": endpoint_id, "detail": str(error)})

    anchors, selection_reason = _anchors(paper_a, paper_b)
    for anchor in anchors:
        anchor_id = str(anchor["id"])
        other_id = paper_b_id if anchor_id == paper_a_id else paper_a_id
        other_forms = _forms(provider_ids[other_id]) | _forms(other_id)
        try:
            result = _graph_result(provider, "citations", provider_ids[anchor_id], before=None, limit=limit)
            record_call("FORWARD", anchor_id, result)
            for candidate in result.papers:
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
    endpoint_reference_observations = []
    for endpoint_id in (paper_a_id, paper_b_id):
        backward = next((
            call for call in calls
            if call["direction"] == "BACKWARD" and call["anchor_paper_id"] == endpoint_id
        ), None)
        failed = any(
            failure["direction"] == "BACKWARD" and failure["anchor_paper_id"] == endpoint_id
            for failure in failures
        )
        endpoint_reference_observations.append({
            "paper_id": endpoint_id,
            "provider_returned_count": backward["returned_count"] if backward else None,
            "status": (
                "FAILED" if failed or backward is None
                else "NONEMPTY" if backward["returned_count"] > 0
                else "EMPTY_AT_PROVIDER"
            ),
        })
    merged_index = {str(paper.get("id")): paper for paper in merged}
    historical_bridge_candidate_ids = [
        paper_id for paper_id in merged_bridge_ids
        if before and (merged_index.get(paper_id) or {}).get("cutoff_status") == "ELIGIBLE"
    ]
    landscape_bridge_candidate_ids = [
        paper_id for paper_id in merged_bridge_ids
        if before and (merged_index.get(paper_id) or {}).get("cutoff_status") != "ELIGIBLE"
    ]
    observation_window_days = _observation_window_days(paper_a, paper_b, before)
    if not before:
        negative_result_scope = "NO_HISTORICAL_CUTOFF"
    elif partial_reasons:
        negative_result_scope = "INCOMPLETE_EXPANSION"
    elif historical_bridge_candidate_ids:
        negative_result_scope = "HISTORICAL_CANDIDATE_PRESENT"
    elif observation_window_days is None:
        negative_result_scope = "NO_HISTORICAL_CANDIDATE_ENDPOINT_DATE_UNRESOLVED"
    elif observation_window_days < 0:
        negative_result_scope = "NO_HISTORICAL_CANDIDATE_POST_CUTOFF_ENDPOINT"
    elif any(item["status"] != "NONEMPTY" for item in endpoint_reference_observations):
        negative_result_scope = "NO_HISTORICAL_CANDIDATE_PROVIDER_COVERAGE_LIMITED"
    else:
        negative_result_scope = "NO_HISTORICAL_CANDIDATE_WITHIN_COMPLETE_EXPANSION"
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
        "historical_bridge_candidate_ids": historical_bridge_candidate_ids,
        "landscape_bridge_candidate_ids": landscape_bridge_candidate_ids,
        "endpoint_reference_observations": endpoint_reference_observations,
        "observation_window_days": observation_window_days,
        "negative_result_scope": negative_result_scope,
        "discovered_paper_ids": discovered_ids,
        "new_paper_ids": new_ids,
        "papers": merged,
    }
