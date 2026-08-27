"""Deterministic bridge-candidate discovery from a citation graph."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from normalize_paper import normalize_arxiv_id, normalize_doi


DEFAULT_HIGH_CITATION_THRESHOLD = 500
DEFAULT_BRIDGE_POLICY_STATUS = "SENSITIVITY_CHECKED"
DEFAULT_BRIDGE_POLICY_SOURCE = (
    "TUdatalib 82-case exploratory snapshot dated 2026-08-27: pair bridge rates were "
    "8.47%-12.12% across endpoint thresholds 50, 100, 250, 500, and 1000. The 500-citation "
    "default is an operational base-rate guard, not a universal field calibration or performance claim."
)


def _alias_forms(value: Any) -> set[str]:
    if value in (None, ""):
        return set()
    raw = str(value).strip()
    forms = {raw, raw.casefold(), raw.rsplit("/", 1)[-1], raw.rsplit("/", 1)[-1].casefold()}
    if "doi" in raw.casefold() or raw.casefold().startswith("10."):
        doi = normalize_doi(raw)
        if doi:
            forms.update({doi, f"doi:{doi}"})
    if "arxiv" in raw.casefold() or raw[:4].isdigit():
        arxiv_id = normalize_arxiv_id(raw)
        if arxiv_id:
            forms.update({arxiv_id, f"arxiv:{arxiv_id}"})
    return {form for form in forms if form}


def _paper_aliases(paper: dict[str, Any]) -> set[str]:
    values = [paper.get("id"), paper.get("canonical_key"), paper.get("doi"), paper.get("arxiv_id")]
    values.extend((paper.get("provider_ids") or {}).values())
    aliases: set[str] = set()
    for value in values:
        aliases.update(_alias_forms(value))
    return aliases


def _alias_index(papers: Iterable[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    paper_index = {str(paper["id"]): paper for paper in papers}
    candidates: dict[str, set[str]] = {}
    for paper_id, paper in paper_index.items():
        for alias in _paper_aliases(paper):
            candidates.setdefault(alias, set()).add(paper_id)
    aliases = {alias: next(iter(ids)) for alias, ids in candidates.items() if len(ids) == 1}
    return paper_index, aliases


def _resolve(value: Any, aliases: dict[str, str]) -> str:
    for form in _alias_forms(value):
        if form in aliases:
            return aliases[form]
    return str(value)


def _cutoff_status(paper: dict[str, Any], cutoff: str | None) -> str:
    if paper.get("cutoff_status"):
        return str(paper["cutoff_status"])
    if not cutoff:
        return "ELIGIBLE"
    value = paper.get("earliest_public_date")
    if not value:
        return "DATE_UNCERTAIN"
    return "ELIGIBLE" if date.fromisoformat(value) <= date.fromisoformat(cutoff) else "POST_CUTOFF"


def assess_co_citation(
    paper_a: dict[str, Any], paper_b: dict[str, Any], high_citation_threshold: int | None
) -> dict[str, Any]:
    counts = {
        str(paper_a.get("id")): paper_a.get("citation_count"),
        str(paper_b.get("id")): paper_b.get("citation_count"),
    }
    numeric = [value for value in counts.values() if isinstance(value, int) and not isinstance(value, bool)]
    if high_citation_threshold is None or len(numeric) != 2:
        status = "UNASSESSED"
    elif any(value >= high_citation_threshold for value in numeric):
        status = "HIGH_BASE_RATE"
    else:
        status = "PASSED"
    return {"base_rate_status": status, "citation_counts": counts, "high_citation_threshold": high_citation_threshold}


def graph_bridge_qualifies(bridge: dict[str, Any]) -> bool:
    if bridge.get("cutoff_status", "ELIGIBLE") != "ELIGIBLE" or bridge.get("type") == "LANDSCAPE_BRIDGE":
        return False
    kind = str(bridge.get("type", "")).upper()
    return kind != "CO_CITATION" or bridge.get("base_rate_status") == "PASSED"


def _bridge_record(
    kind: str,
    endpoints: list[str],
    source_id: str,
    source: dict[str, Any],
    paper_a: dict[str, Any],
    paper_b: dict[str, Any],
    cutoff: str | None,
    high_citation_threshold: int | None,
) -> dict[str, Any]:
    cutoff_status = _cutoff_status(source, cutoff)
    result: dict[str, Any] = {
        "type": kind if cutoff_status == "ELIGIBLE" else "LANDSCAPE_BRIDGE",
        "provenance_type": "graph",
        "paper_ids": endpoints,
        "source_paper_id": source_id,
        "cutoff_status": cutoff_status,
        "graph_verified": True,
        "text_verified": False,
        "evidence_ids": [],
        "affects_historical_verdict": cutoff_status == "ELIGIBLE",
        "base_rate_status": "NOT_APPLICABLE",
    }
    if cutoff_status != "ELIGIBLE":
        result["underlying_type"] = kind
    if kind == "CO_CITATION":
        result.update(assess_co_citation(paper_a, paper_b, high_citation_threshold))
    return result


def find_bridges(
    paper_a: str,
    paper_b: str,
    papers: Iterable[dict[str, Any]],
    cutoff: str | None = None,
    high_citation_threshold: int | None = DEFAULT_HIGH_CITATION_THRESHOLD,
) -> list[dict[str, Any]]:
    index, aliases = _alias_index(list(papers))
    paper_a = _resolve(paper_a, aliases)
    paper_b = _resolve(paper_b, aliases)
    if paper_a not in index or paper_b not in index:
        raise KeyError("both endpoint papers must exist in the graph")
    result: list[dict[str, Any]] = []
    a_refs = {_resolve(item, aliases) for item in index[paper_a].get("references") or []}
    b_refs = {_resolve(item, aliases) for item in index[paper_b].get("references") or []}
    if paper_a in b_refs:
        result.append(_bridge_record("DIRECT_CITATION", [paper_a, paper_b], paper_b, index[paper_b], index[paper_a], index[paper_b], cutoff, high_citation_threshold))
    if paper_b in a_refs:
        result.append(_bridge_record("DIRECT_CITATION", [paper_a, paper_b], paper_a, index[paper_a], index[paper_a], index[paper_b], cutoff, high_citation_threshold))
    for paper_id, paper in index.items():
        if paper_id in {paper_a, paper_b}:
            continue
        refs = {_resolve(item, aliases) for item in paper.get("references") or []}
        if {paper_a, paper_b} <= refs:
            result.append(_bridge_record("CO_CITATION", [paper_a, paper_b], paper_id, paper, index[paper_a], index[paper_b], cutoff, high_citation_threshold))
    return result


def relation_route_exists(bridge: dict[str, Any], papers: Iterable[dict[str, Any]]) -> bool:
    """Reproduce a bridge's citation route using canonical/provider aliases."""
    index, aliases = _alias_index(list(papers))
    source_id = _resolve(bridge.get("source_paper_id"), aliases)
    endpoints = {_resolve(value, aliases) for value in bridge.get("paper_ids") or []}
    if source_id not in index or len(endpoints) < 2:
        return False
    refs = {_resolve(value, aliases) for value in index[source_id].get("references") or []}
    if source_id in endpoints:
        return (endpoints - {source_id}) <= refs
    return endpoints <= refs


def promote_bridge(candidate: dict[str, Any], bridge_type: str, evidence_ids: Iterable[str]) -> dict[str, Any]:
    allowed = {
        "EXPLICIT_EXTENSION", "SHARED_BENCHMARK", "TAXONOMY_BRIDGE",
        "SYNTHESIS_BRIDGE", "COMBINATION_BRIDGE",
    }
    bridge_type = bridge_type.upper()
    evidence = list(evidence_ids)
    if bridge_type not in allowed:
        raise ValueError(f"unsupported textual bridge type: {bridge_type}")
    if not evidence:
        raise ValueError("textual bridge promotion requires evidence IDs")
    result = dict(candidate)
    result.update({"type": bridge_type, "text_verified": True, "evidence_ids": evidence})
    return result
