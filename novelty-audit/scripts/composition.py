"""Evidence-bound Minimal Prior Set and verdict algorithms."""

from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable


HARD_COVERAGE = {"EXACT", "FUNCTIONAL"}
TEXTUAL_BRIDGES = {
    "EXPLICIT_EXTENSION",
    "SHARED_BENCHMARK",
    "TAXONOMY_BRIDGE",
    "SYNTHESIS_BRIDGE",
    "COMBINATION_BRIDGE",
}
GRAPH_BRIDGES = {"DIRECT_CITATION", "CO_CITATION", "SHARED_DESCENDANT"}


def _coverage_entry(paper: dict[str, Any], facet_id: str) -> tuple[str, list[str]]:
    value = (paper.get("coverage") or {}).get(facet_id, "UNKNOWN")
    if isinstance(value, str):
        return value.upper(), []
    return str(value.get("status", "UNKNOWN")).upper(), list(value.get("evidence_ids") or [])


def hard_covered_facets(paper: dict[str, Any], require_evidence: bool = True) -> set[str]:
    covered: set[str] = set()
    for facet_id in (paper.get("coverage") or {}):
        status, evidence_ids = _coverage_entry(paper, facet_id)
        if status in HARD_COVERAGE and (evidence_ids or not require_evidence):
            covered.add(facet_id)
    return covered


def eligible_candidates(papers: Iterable[dict[str, Any]], strict: bool = True) -> list[dict[str, Any]]:
    accepted = {"ELIGIBLE"} if strict else {"ELIGIBLE", "ELIGIBILITY_UNCERTAIN"}
    return [
        paper for paper in papers
        if paper.get("cutoff_status") in accepted
        and (not strict or bool(paper.get("earliest_public_date")))
    ]


def solve_mps(
    papers: Iterable[dict[str, Any]],
    critical_facets: Iterable[str],
    max_size: int = 3,
    strict: bool = True,
    require_evidence: bool = True,
    bridges: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    facets = set(critical_facets)
    if not facets:
        raise ValueError("at least one critical facet is required")
    if not 1 <= max_size <= 3:
        raise ValueError("max_size must be between 1 and 3")
    candidates = eligible_candidates(papers, strict=strict)
    paper_index = {str(paper.get("id")): paper for paper in candidates}
    for size in range(1, min(max_size, len(candidates)) + 1):
        found: list[dict[str, Any]] = []
        for group in combinations(candidates, size):
            union: set[str] = set()
            by_paper: dict[str, list[str]] = {}
            evidence_ids: set[str] = set()
            for paper in group:
                covered = hard_covered_facets(paper, require_evidence=require_evidence) & facets
                union |= covered
                by_paper[str(paper.get("id"))] = sorted(covered)
                for facet in covered:
                    _, ids = _coverage_entry(paper, facet)
                    evidence_ids.update(ids)
            if facets <= union:
                found.append({
                    "paper_ids": [str(paper.get("id")) for paper in group],
                    "size": size,
                    "covered_facets": sorted(union),
                    "coverage_by_paper": by_paper,
                    "evidence_ids": sorted(evidence_ids),
                })
        if found:
            bridge_list = list(bridges or [])
            strength_rank = {"TEXTUAL": 0, "GRAPH": 1, "NONE": 2}
            found.sort(key=lambda item: (
                strength_rank[bridge_strength(bridge_list, item["paper_ids"])],
                -len(item["evidence_ids"]),
                tuple(sorted(str(paper_index[paper_id].get("earliest_public_date") or "9999-99-99") for paper_id in item["paper_ids"])),
                tuple(item["paper_ids"]),
            ))
            return found
    return []


def criticality_sensitivity(
    papers: Iterable[dict[str, Any]], critical_facets: Iterable[str], **kwargs: Any
) -> list[dict[str, Any]]:
    papers = list(papers)
    facets = list(critical_facets)
    baseline = solve_mps(papers, facets, **kwargs)
    baseline_size = baseline[0]["size"] if baseline else None
    result = []
    for removed in facets:
        remaining = [facet for facet in facets if facet != removed]
        alternative = solve_mps(papers, remaining, **kwargs) if remaining else []
        alternative_size = alternative[0]["size"] if alternative else None
        result.append({
            "removed_facet": removed,
            "baseline_size": baseline_size,
            "alternative_size": alternative_size,
            "alternative_classification": (
                "DIRECT_PRECEDENT" if alternative_size == 1 else
                "COMPOSITION_CANDIDATE" if alternative_size in {2, 3} else
                "NO_COMPLETE_SET"
            ),
        })
    return result


def bridge_strength(bridges: Iterable[dict[str, Any]], paper_ids: Iterable[str]) -> str:
    ids = set(paper_ids)
    bridge_list = list(bridges)

    def connected(kind_set: set[str], predicate: Any) -> bool:
        if not ids:
            return False
        adjacency = {paper_id: set() for paper_id in ids}
        for bridge in bridge_list:
            endpoints = set(str(value) for value in bridge.get("paper_ids") or [])
            kind = str(bridge.get("type", "")).upper()
            if kind not in kind_set or not predicate(bridge) or bridge.get("cutoff_status", "ELIGIBLE") != "ELIGIBLE":
                continue
            if len(endpoints) < 2 or not endpoints <= ids:
                continue
            for left in endpoints:
                adjacency[left].update(endpoints - {left})
        reached: set[str] = set()
        frontier = [next(iter(ids))]
        while frontier:
            current = frontier.pop()
            if current in reached:
                continue
            reached.add(current)
            frontier.extend(adjacency[current] - reached)
        return reached == ids

    if connected(TEXTUAL_BRIDGES, lambda bridge: bridge.get("text_verified") is True and bool(bridge.get("evidence_ids"))):
        return "TEXTUAL"
    if connected(GRAPH_BRIDGES, lambda bridge: bridge.get("graph_verified") is True):
        return "GRAPH"
    return "NONE"


def classify(mps: list[dict[str, Any]], bridges: Iterable[dict[str, Any]], unresolved: bool = False) -> str:
    if unresolved:
        return "INCONCLUSIVE"
    if not mps:
        return "RESIDUAL_NOVELTY"
    size = mps[0]["size"]
    if size == 1:
        return "DIRECT_PRECEDENT"
    strengths = {bridge_strength(bridges, candidate["paper_ids"]) for candidate in mps}
    if "TEXTUAL" in strengths:
        return "STRONG_COMPOSITION_RISK"
    if "GRAPH" in strengths:
        return "PLAUSIBLE_COMPOSITION_RISK"
    return "FRAGMENTED_PRECEDENT"
