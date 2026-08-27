"""Validate NoveltyAudit report invariants beyond JSON shape."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any

from composition import GRAPH_BRIDGES, HARD_COVERAGE, TEXTUAL_BRIDGES, solve_mps
from citation_graph import relation_route_exists
from resolve_dates import apply_cutoff


CLASSIFICATIONS = {
    "DIRECT_PRECEDENT", "STRONG_COMPOSITION_RISK", "PLAUSIBLE_COMPOSITION_RISK",
    "FRAGMENTED_PRECEDENT", "RESIDUAL_NOVELTY", "INCONCLUSIVE",
}
AXES = {
    "novelty_risk": {"HIGH", "MEDIUM", "LOW", "INCONCLUSIVE"},
    "search_coverage": {"BROAD", "MODERATE", "NARROW"},
    "evidence_confidence": {"STRONG", "MIXED", "WEAK"},
}
ADVERSE = {"DIRECT_PRECEDENT", "STRONG_COMPOSITION_RISK", "PLAUSIBLE_COMPOSITION_RISK"}


def _coverage(paper: dict[str, Any], facet: str) -> tuple[str, list[str]]:
    value = (paper.get("coverage") or {}).get(facet, "UNKNOWN")
    if isinstance(value, str):
        return value.upper(), []
    return str(value.get("status", "UNKNOWN")).upper(), list(value.get("evidence_ids") or [])


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("schema_version", "audit_id", "generated_at", "input", "claim_map", "verdict", "papers", "evidence", "top_killers", "minimal_prior_sets", "bridges", "criticality_sensitivity", "ancestor_terms", "residual_novelty", "defensible_rewrite", "search", "excluded", "audit_log"):
        if field not in report:
            errors.append(f"missing required field: {field}")
    if errors:
        return errors

    verdict = report["verdict"]
    if report.get("schema_version") != "0.1.0":
        errors.append(f"unsupported schema_version: {report.get('schema_version')}")
    if not str(report.get("audit_id") or "").strip():
        errors.append("audit_id must be non-empty")
    if not str(report.get("generated_at") or "").strip():
        errors.append("generated_at must be non-empty")
    for field in ("claim", "normalized_claim", "cutoff", "strict_date"):
        if field not in report["input"]:
            errors.append(f"input missing required field: {field}")
    for field in ("claim_id", "claim_text", "frozen_before_retrieval", "frozen_at", "facets"):
        if field not in report["claim_map"]:
            errors.append(f"claim_map missing required field: {field}")
    for field in ("classification", "novelty_risk", "search_coverage", "evidence_confidence", "main_concern", "evidence_ids"):
        if field not in verdict:
            errors.append(f"verdict missing required field: {field}")
    for field in ("providers", "query_families", "query_runs", "failures", "gaps"):
        if field not in report["search"]:
            errors.append(f"search missing required field: {field}")
    for field in ("post_cutoff", "date_uncertain", "other"):
        if field not in report["excluded"]:
            errors.append(f"excluded missing required field: {field}")
    for index, facet in enumerate(report["claim_map"].get("facets") or []):
        for field in ("id", "type", "text", "critical"):
            if field not in facet:
                errors.append(f"facet {index} missing required field: {field}")
    classification = verdict.get("classification")
    if classification not in CLASSIFICATIONS:
        errors.append(f"invalid classification: {classification}")
    for field, allowed in AXES.items():
        if verdict.get(field) not in allowed:
            errors.append(f"invalid {field}: {verdict.get(field)}")
    if not report["claim_map"].get("frozen_before_retrieval"):
        errors.append("claim map was not frozen before retrieval")

    cutoff = report["input"].get("cutoff")
    cutoff_date = None
    try:
        cutoff_date = date.fromisoformat(cutoff)
        if len(cutoff) != 10:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("input.cutoff must be a complete YYYY-MM-DD date")

    def parse_datetime(value: Any, field: str) -> datetime | None:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            errors.append(f"{field} must be an ISO 8601 date-time")
            return None

    generated_at = parse_datetime(report.get("generated_at"), "generated_at")
    frozen_at = parse_datetime(report["claim_map"].get("frozen_at"), "claim_map.frozen_at")
    if generated_at and frozen_at:
        generated_compare = generated_at if generated_at.tzinfo else generated_at.replace(tzinfo=frozen_at.tzinfo)
        frozen_compare = frozen_at if frozen_at.tzinfo else frozen_at.replace(tzinfo=generated_compare.tzinfo)
        if frozen_compare > generated_compare:
            errors.append("claim map freeze time is after report generation")

    facet_ids = [str(facet.get("id")) for facet in report["claim_map"].get("facets", [])]
    facet_types = {str(facet.get("id")): str(facet.get("type")) for facet in report["claim_map"].get("facets", [])}
    if len(facet_ids) != len(set(facet_ids)):
        errors.append("claim map contains duplicate facet IDs")
    critical = {str(facet.get("id")) for facet in report["claim_map"].get("facets", []) if facet.get("critical") or facet.get("structural_critical") is True}
    if not critical:
        errors.append("claim map has no critical facets")
    paper_ids_all = [str(paper.get("id")) for paper in report["papers"]]
    evidence_ids_all = [str(item.get("id")) for item in report["evidence"]]
    if len(paper_ids_all) != len(set(paper_ids_all)):
        errors.append("report contains duplicate paper IDs")
    if len(evidence_ids_all) != len(set(evidence_ids_all)):
        errors.append("report contains duplicate evidence IDs")
    papers = {str(paper.get("id")): paper for paper in report["papers"]}
    evidence = {str(item.get("id")): item for item in report["evidence"]}

    for paper_id, paper in papers.items():
        for field in ("id", "title", "providers", "dates", "cutoff_status", "coverage"):
            if field not in paper:
                errors.append(f"paper {paper_id} missing required field: {field}")
        if cutoff_date:
            try:
                recomputed = apply_cutoff(paper, cutoff_date.isoformat(), strict=True)
                if paper.get("earliest_public_date") != recomputed.get("earliest_public_date"):
                    errors.append(f"paper {paper_id} earliest_public_date disagrees with observed dates")
                if paper.get("cutoff_status") != recomputed.get("cutoff_status"):
                    errors.append(f"paper {paper_id} cutoff_status disagrees with observed dates")
            except (TypeError, ValueError) as error:
                errors.append(f"paper {paper_id} date resolution failed: {error}")

    for evidence_id, item in evidence.items():
        for field in ("paper_id", "span", "location", "source", "retrieved_at"):
            if not item.get(field):
                errors.append(f"evidence {evidence_id} missing {field}")
        if str(item.get("paper_id")) not in papers:
            errors.append(f"evidence {evidence_id} references unknown paper {item.get('paper_id')}")

    for killer in report["top_killers"]:
        paper_id = str(killer.get("paper_id"))
        if paper_id not in papers:
            errors.append(f"top killer references unknown paper {paper_id}")
        elif papers[paper_id].get("cutoff_status") != "ELIGIBLE" or not papers[paper_id].get("earliest_public_date"):
            errors.append(f"top killer {paper_id} is not strictly cutoff-eligible")
        if "covers" not in killer or "does_not_cover" not in killer:
            errors.append(f"top killer {paper_id} must state covers and does_not_cover")
        for facet in killer.get("covers") or []:
            status, ids_for_facet = _coverage(papers.get(paper_id, {}), str(facet))
            allowed_kinds = {"METHOD", "RESULT"} if str(facet) in {
                facet_id for facet_id, facet_type in facet_types.items() if facet_type in {"outcome", "evaluation_condition"}
            } else {"METHOD"}
            if status not in HARD_COVERAGE or not ids_for_facet:
                errors.append(f"top killer {paper_id} claims unsupported coverage for {facet}")
            for evidence_id in ids_for_facet:
                item = evidence.get(str(evidence_id))
                if not item or str(item.get("paper_id")) != paper_id or item.get("evidence_kind") not in allowed_kinds or str(facet) not in set(str(value) for value in item.get("supports") or []):
                    errors.append(f"top killer {paper_id} coverage for {facet} is not evidence-bound")
        for evidence_id in killer.get("evidence_ids") or []:
            if str(evidence_id) not in evidence:
                errors.append(f"top killer {paper_id} references unknown evidence {evidence_id}")

    mps_sets = report["minimal_prior_sets"]
    valid_sizes: list[int] = []
    for index, mps in enumerate(mps_sets):
        ids = [str(value) for value in mps.get("paper_ids") or []]
        if not 1 <= len(ids) <= 3:
            errors.append(f"MPS {index} must contain one to three papers")
            continue
        if mps.get("size") != len(ids):
            errors.append(f"MPS {index} size field does not match paper_ids")
        valid_sizes.append(len(ids))
        covered: set[str] = set()
        for paper_id in ids:
            paper = papers.get(paper_id)
            if not paper:
                errors.append(f"MPS {index} references unknown paper {paper_id}")
                continue
            if paper.get("cutoff_status") != "ELIGIBLE":
                errors.append(f"MPS {index} contains non-eligible paper {paper_id}: {paper.get('cutoff_status')}")
            if not paper.get("earliest_public_date"):
                errors.append(f"MPS {index} paper {paper_id} lacks a verified earliest public date")
            elif cutoff_date:
                try:
                    if date.fromisoformat(paper["earliest_public_date"]) > cutoff_date:
                        errors.append(f"MPS {index} paper {paper_id} is marked ELIGIBLE but post-dates the cutoff")
                except ValueError:
                    errors.append(f"paper {paper_id} has invalid earliest_public_date")
            for facet in critical:
                status, ids_for_facet = _coverage(paper, facet)
                if status in HARD_COVERAGE:
                    if not ids_for_facet:
                        errors.append(f"paper {paper_id} hard-covers {facet} without evidence")
                    elif all(str(value) in evidence for value in ids_for_facet):
                        covered.add(facet)
                        for evidence_id in ids_for_facet:
                            if str(evidence[str(evidence_id)].get("paper_id")) != paper_id:
                                errors.append(f"paper {paper_id} coverage for {facet} uses evidence from another paper")
                            allowed_kinds = {"METHOD", "RESULT"} if facet_types.get(facet) in {"outcome", "evaluation_condition"} else {"METHOD"}
                            if evidence[str(evidence_id)].get("evidence_kind") not in allowed_kinds:
                                errors.append(f"paper {paper_id} hard coverage for {facet} uses an invalid evidence kind")
                            if facet not in set(str(value) for value in evidence[str(evidence_id)].get("supports") or []):
                                errors.append(f"paper {paper_id} coverage for {facet} uses evidence that does not declare support for that facet")
                    else:
                        errors.append(f"paper {paper_id} coverage for {facet} references missing evidence")
        missing = critical - covered
        if missing:
            errors.append(f"MPS {index} does not evidence-cover critical facets: {sorted(missing)}")

    if valid_sizes and any(size != min(valid_sizes) for size in valid_sizes):
        errors.append("minimal_prior_sets contains non-minimal set sizes")
    verified_papers = deepcopy(list(papers.values()))
    for paper in verified_papers:
        for facet, entry in list((paper.get("coverage") or {}).items()):
            if isinstance(entry, str) or str(entry.get("status", "")).upper() not in HARD_COVERAGE:
                continue
            ids_for_facet = [str(value) for value in entry.get("evidence_ids") or []]
            valid = bool(ids_for_facet) and all(
                evidence_id in evidence
                and str(evidence[evidence_id].get("paper_id")) == str(paper.get("id"))
                and evidence[evidence_id].get("evidence_kind") in ({"METHOD", "RESULT"} if facet_types.get(str(facet)) in {"outcome", "evaluation_condition"} else {"METHOD"})
                and str(facet) in set(str(value) for value in evidence[evidence_id].get("supports") or [])
                for evidence_id in ids_for_facet
            )
            if not valid:
                paper["coverage"][facet] = {"status": "UNKNOWN", "evidence_ids": []}
    computed_mps = solve_mps(verified_papers, critical, max_size=3, strict=True, require_evidence=True) if critical else []
    computed_size = computed_mps[0]["size"] if computed_mps else None
    submitted_size = min(valid_sizes) if valid_sizes else None
    if submitted_size is not None and computed_size != submitted_size:
        errors.append(f"submitted MPS size {submitted_size} is not globally minimal; recomputed size is {computed_size}")
    if computed_size is not None and submitted_size is None:
        errors.append(f"report omits a recomputed Minimal Prior Set of size {computed_size}")
    if computed_size == 1 and classification != "DIRECT_PRECEDENT":
        errors.append("classification conflicts with recomputed one-paper direct precedent")
    if computed_size in {2, 3} and classification not in {"STRONG_COMPOSITION_RISK", "PLAUSIBLE_COMPOSITION_RISK", "FRAGMENTED_PRECEDENT"}:
        errors.append("classification conflicts with recomputed multi-paper prior set")
    if classification in ADVERSE and not mps_sets:
        errors.append(f"{classification} requires a Minimal Prior Set")
    if classification == "DIRECT_PRECEDENT" and (not valid_sizes or min(valid_sizes) != 1):
        errors.append("DIRECT_PRECEDENT requires a one-paper MPS")
    if classification in {"STRONG_COMPOSITION_RISK", "PLAUSIBLE_COMPOSITION_RISK"} and (not valid_sizes or min(valid_sizes) not in {2, 3}):
        errors.append(f"{classification} requires a two- or three-paper MPS")

    eligible_bridges: list[dict[str, Any]] = []
    for bridge in report["bridges"]:
        bridge_type = str(bridge.get("type", "")).upper()
        source_id = str(bridge.get("source_paper_id") or "")
        endpoints = set(str(value) for value in bridge.get("paper_ids") or [])
        if not source_id:
            errors.append(f"bridge {bridge_type} lacks source_paper_id")
        else:
            source_paper = papers.get(source_id)
            if not source_paper:
                errors.append(f"bridge {bridge_type} references unknown source paper {source_id}")
            elif source_paper.get("cutoff_status") != "ELIGIBLE":
                errors.append(f"bridge {bridge_type} source paper {source_id} is not cutoff-eligible")
            elif not source_paper.get("earliest_public_date"):
                errors.append(f"bridge {bridge_type} source paper {source_id} lacks a verified earliest public date")
        if bridge_type in GRAPH_BRIDGES and source_id in papers:
            graph_relation_ok = relation_route_exists(bridge, papers.values())
            if bridge_type == "DIRECT_CITATION" and source_id not in endpoints:
                graph_relation_ok = False
            if bridge_type in {"CO_CITATION", "SHARED_DESCENDANT"} and source_id in endpoints:
                graph_relation_ok = False
            if not bridge.get("graph_verified") or not graph_relation_ok:
                errors.append(f"graph bridge {bridge_type} is not reproduced by source references")
        if bridge_type in TEXTUAL_BRIDGES and source_id in papers:
            textual_route_ok = relation_route_exists(bridge, papers.values())
            if not textual_route_ok:
                errors.append(f"textual bridge {bridge_type} is not grounded by the source citation route")
        if bridge.get("cutoff_status", "ELIGIBLE") == "ELIGIBLE" and source_id in papers and papers[source_id].get("cutoff_status") == "ELIGIBLE":
            eligible_bridges.append(bridge)
        if bridge_type in TEXTUAL_BRIDGES:
            if bridge.get("source_rechecked_as_candidate") is not True:
                errors.append(f"textual bridge {bridge_type} source was not rechecked as a direct/MPS candidate")
            if not bridge.get("text_verified") or not bridge.get("evidence_ids"):
                errors.append(f"textual bridge {bridge_type} lacks verified textual evidence")
            for evidence_id in bridge.get("evidence_ids") or []:
                if str(evidence_id) not in evidence:
                    errors.append(f"bridge {bridge_type} references unknown evidence {evidence_id}")
                elif evidence[str(evidence_id)].get("evidence_kind") != "BRIDGE_TEXT":
                    errors.append(f"textual bridge {bridge_type} evidence {evidence_id} is not BRIDGE_TEXT")
                elif source_id and str(evidence[str(evidence_id)].get("paper_id")) != source_id:
                    errors.append(f"textual bridge {bridge_type} uses evidence from a different source paper")

    def connected_mps_exists(allowed_types: set[str]) -> bool:
        for mps in mps_sets:
            members = set(str(value) for value in mps.get("paper_ids") or [])
            adjacency = {member: set() for member in members}
            for bridge in eligible_bridges:
                if str(bridge.get("type", "")).upper() not in allowed_types:
                    continue
                endpoints = set(str(value) for value in bridge.get("paper_ids") or [])
                if len(endpoints) < 2 or not endpoints <= members:
                    continue
                for left in endpoints:
                    adjacency[left].update(endpoints - {left})
            if not members:
                continue
            reached = set()
            frontier = [next(iter(members))]
            while frontier:
                current = frontier.pop()
                if current in reached:
                    continue
                reached.add(current)
                frontier.extend(adjacency[current] - reached)
            if reached == members:
                return True
        return False

    if classification == "STRONG_COMPOSITION_RISK" and not connected_mps_exists(TEXTUAL_BRIDGES):
        errors.append("STRONG_COMPOSITION_RISK requires an eligible textual bridge")
    if classification == "PLAUSIBLE_COMPOSITION_RISK" and not connected_mps_exists(GRAPH_BRIDGES):
        errors.append("PLAUSIBLE_COMPOSITION_RISK requires an eligible graph bridge")

    verdict_evidence = [str(value) for value in verdict.get("evidence_ids") or []]
    if (classification in ADVERSE or verdict.get("novelty_risk") == "HIGH") and not verdict_evidence:
        errors.append("adverse or HIGH verdict lacks report-level evidence IDs")
    if classification in ADVERSE and not str(verdict.get("main_concern") or "").strip():
        errors.append("adverse verdict lacks a main concern explanation")
    for evidence_id in verdict_evidence:
        if evidence_id not in evidence:
            errors.append(f"verdict references unknown evidence {evidence_id}")

    for term in report.get("ancestor_terms") or []:
        if term.get("admitted", True) and (not term.get("source_paper_id") or not term.get("evidence_ids")):
            errors.append(f"ancestor term {term.get('term')} lacks provenance")

    if classification in {"RESIDUAL_NOVELTY", "INCONCLUSIVE"} and not (report["search"].get("gaps") or []):
        errors.append(f"{classification} must disclose search gaps")
    if classification == "INCONCLUSIVE" and verdict.get("novelty_risk") != "INCONCLUSIVE":
        errors.append("INCONCLUSIVE classification requires INCONCLUSIVE novelty risk")
    if classification in ADVERSE and verdict.get("evidence_confidence") == "WEAK":
        errors.append("adverse classification requires non-WEAK evidence confidence")
    risk_matrix = {
        "DIRECT_PRECEDENT": {"HIGH"},
        "STRONG_COMPOSITION_RISK": {"HIGH"},
        "PLAUSIBLE_COMPOSITION_RISK": {"HIGH", "MEDIUM"},
        "FRAGMENTED_PRECEDENT": {"MEDIUM", "LOW", "INCONCLUSIVE"},
        "RESIDUAL_NOVELTY": {"MEDIUM", "LOW"},
        "INCONCLUSIVE": {"INCONCLUSIVE"},
    }
    if classification in risk_matrix and verdict.get("novelty_risk") not in risk_matrix[classification]:
        errors.append(f"novelty risk {verdict.get('novelty_risk')} conflicts with {classification}")
    if verdict.get("novelty_risk") == "LOW" and (verdict.get("search_coverage") != "BROAD" or verdict.get("evidence_confidence") == "WEAK"):
        errors.append("LOW novelty risk requires BROAD search coverage and non-WEAK evidence confidence")
    if verdict.get("search_coverage") == "BROAD":
        known_providers = {"openalex", "semantic-scholar", "arxiv", "crossref"}
        successful_names = set()
        for provider in report["search"].get("providers") or []:
            if isinstance(provider, dict):
                if provider.get("status") == "ok" and provider.get("name") in known_providers:
                    successful_names.add(str(provider.get("name")))
            else:
                errors.append("BROAD search coverage requires structured provider records")
        required_families = {"literal", "mechanism", "problem_function", "ancestor", "composition_bridge"}
        actual_families = set(report["search"].get("query_families") or [])
        if len(successful_names - {"", "None"}) < 2:
            errors.append("BROAD search coverage requires at least two successful providers")
        if not required_families <= actual_families:
            errors.append(f"BROAD search coverage is missing query families: {sorted(required_families - actual_families)}")
        if report["search"].get("saturated") is not True:
            errors.append("BROAD search coverage requires an explicit saturation check")
        query_runs = report["search"].get("query_runs") or []
        successful_run_providers = set()
        successful_run_families = set()
        for index, run in enumerate(query_runs):
            required = ("provider", "family", "query", "retrieved_at", "result_count", "truncated", "status")
            if not isinstance(run, dict) or any(field not in run for field in required):
                errors.append(f"query run {index} is missing required reproducibility fields")
                continue
            parse_datetime(run.get("retrieved_at"), f"search.query_runs[{index}].retrieved_at")
            if run.get("status") == "ok" and run.get("provider") in known_providers:
                successful_run_providers.add(str(run.get("provider")))
                successful_run_families.add(str(run.get("family")))
        if len(successful_run_providers) < 2:
            errors.append("BROAD search coverage requires successful query logs from two providers")
        if not required_families <= successful_run_families:
            errors.append(f"BROAD search query log is missing families: {sorted(required_families - successful_run_families)}")
    return errors
