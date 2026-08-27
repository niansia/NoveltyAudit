"""Validate NoveltyAudit report invariants beyond JSON shape."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import hashlib
from itertools import combinations
import json
import re
from typing import Any

from composition import GRAPH_BRIDGES, HARD_COVERAGE, TEXTUAL_BRIDGES, bridge_strength, criticality_sensitivity, solve_mps
from citation_graph import find_bridges, graph_bridge_qualifies, relation_route_exists
from export_report import to_html, to_markdown, validate_user_output
from normalize_paper import normalize_arxiv_id, normalize_doi, normalize_title
from resolve_dates import apply_cutoff
from search_coverage import derive_search_coverage
from schema_validation import validate_report_schema


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
PRIOR_AWARENESS = {"OVERLOOKED", "ALREADY_CITED", "UNKNOWN"}
EVIDENCE_LEVELS = {"TIER_1_METADATA", "TIER_2_FULLTEXT", "GRAPH", "DATE"}


def _coverage(paper: dict[str, Any], facet: str) -> tuple[str, list[str]]:
    value = (paper.get("coverage") or {}).get(facet, "UNKNOWN")
    if isinstance(value, str):
        return value.upper(), []
    return str(value.get("status", "UNKNOWN")).upper(), list(value.get("evidence_ids") or [])


def claim_map_hash(claim_map: dict[str, Any]) -> str:
    frozen_payload = {
        "claim_id": claim_map.get("claim_id"),
        "claim_text": claim_map.get("claim_text"),
        "normalized_claim": claim_map.get("normalized_claim"),
        "facets": claim_map.get("facets") or [],
    }
    encoded = json.dumps(frozen_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def candidate_snapshot_hash(papers: list[dict[str, Any]]) -> str:
    fields = ("id", "title", "doi", "arxiv_id", "providers", "dates", "references", "found_by_query_ids")
    payload = [{field: paper.get(field) for field in fields} for paper in sorted(papers, key=lambda item: str(item.get("id")))]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def validate_report(report: dict[str, Any]) -> list[str]:
    schema_errors = validate_report_schema(report)
    if schema_errors:
        return schema_errors
    errors: list[str] = []
    for field in ("schema_version", "audit_id", "generated_at", "candidate_ids", "run_manifest", "input", "author_bibliography", "claim_map", "verdict", "papers", "evidence", "top_killers", "minimal_prior_sets", "bridges", "landscape_bridges", "criticality_sensitivity", "ancestor_terms", "residual_novelty", "defensible_rewrite", "search", "excluded", "audit_log"):
        if field not in report:
            errors.append(f"missing required field: {field}")
    if errors:
        return errors

    verdict = report["verdict"]
    if report.get("schema_version") != "0.3.0":
        errors.append(f"unsupported schema_version: {report.get('schema_version')}")
    if not str(report.get("audit_id") or "").strip():
        errors.append("audit_id must be non-empty")
    if not str(report.get("generated_at") or "").strip():
        errors.append("generated_at must be non-empty")
    for field in ("claim", "normalized_claim", "cutoff", "strict_date"):
        if field not in report["input"]:
            errors.append(f"input missing required field: {field}")
    for field in ("claim_id", "claim_text", "frozen_before_retrieval", "frozen_at", "freeze_hash", "facets"):
        if field not in report["claim_map"]:
            errors.append(f"claim_map missing required field: {field}")
    for field in ("classification", "novelty_risk", "search_coverage", "evidence_confidence", "main_concern", "evidence_ids", "decided_at"):
        if field not in verdict:
            errors.append(f"verdict missing required field: {field}")
    for field in ("providers", "query_families", "query_runs", "failures", "gaps", "obligations", "bridge_policy", "coverage_derivation", "saturated"):
        if field not in report["search"]:
            errors.append(f"search missing required field: {field}")
    for index, provider in enumerate(report["search"].get("providers") or []):
        if not isinstance(provider, dict) or not provider.get("name") or not provider.get("status"):
            errors.append(f"search provider {index} must be a structured provider record")
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
    expected_freeze_hash = claim_map_hash(report["claim_map"])
    if report["claim_map"].get("freeze_hash") != expected_freeze_hash:
        errors.append("claim map freeze_hash does not match the frozen claim content")
    freeze_events = [item for item in report.get("audit_log") or [] if isinstance(item, dict) and item.get("event") == "claim_map_frozen"]
    if not freeze_events or not any(item.get("freeze_hash") == expected_freeze_hash for item in freeze_events):
        errors.append("audit log does not preserve the claim map freeze_hash")

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

    def comparable(left: datetime, right: datetime) -> tuple[datetime, datetime]:
        if left.tzinfo and not right.tzinfo:
            right = right.replace(tzinfo=left.tzinfo)
        elif right.tzinfo and not left.tzinfo:
            left = left.replace(tzinfo=right.tzinfo)
        return left, right

    generated_at = parse_datetime(report.get("generated_at"), "generated_at")
    frozen_at = parse_datetime(report["claim_map"].get("frozen_at"), "claim_map.frozen_at")
    decided_at = parse_datetime(verdict.get("decided_at"), "verdict.decided_at")
    if generated_at and frozen_at:
        generated_compare = generated_at if generated_at.tzinfo else generated_at.replace(tzinfo=frozen_at.tzinfo)
        frozen_compare = frozen_at if frozen_at.tzinfo else frozen_at.replace(tzinfo=generated_compare.tzinfo)
        if frozen_compare > generated_compare:
            errors.append("claim map freeze time is after report generation")
    if generated_at and decided_at:
        generated_compare, decided_compare = comparable(generated_at, decided_at)
        if decided_compare > generated_compare:
            errors.append("verdict time is after report generation")

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
    candidate_ids = {str(value) for value in report.get("candidate_ids") or []}
    if not candidate_ids:
        errors.append("candidate_ids must contain the canonical candidate snapshot")
    for paper_id in papers:
        if paper_id not in candidate_ids:
            errors.append(f"paper {paper_id} does not exist in candidate_ids")
    bibliography = report.get("author_bibliography") or {}
    if bibliography.get("status") not in {"PROVIDED", "NOT_PROVIDED"}:
        errors.append("author_bibliography.status must be PROVIDED or NOT_PROVIDED")
    bibliography_ids = {str(value) for value in bibliography.get("normalized_paper_ids") or []}
    bibliography_entries = bibliography.get("entries") or []
    derived_bibliography_ids: set[str] = set()
    derived_unmatched_entries: list[str] = []
    for index, entry in enumerate(bibliography_entries):
        if not isinstance(entry, dict) or not str(entry.get("raw_entry") or "").strip() or entry.get("match_basis") not in {"DOI", "ARXIV_ID", "TITLE_AUTHOR", "MANUAL", "NONE"}:
            errors.append(f"author bibliography entry {index} is malformed")
            continue
        matched = entry.get("matched_paper_id")
        if matched in (None, ""):
            if entry.get("match_basis") != "NONE":
                errors.append(f"author bibliography entry {index} without a match must use match_basis NONE")
            derived_unmatched_entries.append(str(entry.get("raw_entry")))
        else:
            matched = str(matched)
            if entry.get("match_basis") == "NONE":
                errors.append(f"author bibliography entry {index} with a match cannot use match_basis NONE")
            paper = papers.get(matched)
            raw = str(entry.get("raw_entry") or "")
            basis = entry.get("match_basis")
            verified_match = False
            if not paper:
                errors.append(f"author bibliography entry {index} references unknown candidate {matched}")
            elif basis == "DOI":
                doi_candidates = re.findall(r"10\.\d{4,9}/[^\s\]\[<>\"']+", raw, flags=re.I)
                verified_match = bool(paper.get("doi")) and normalize_doi(paper.get("doi")) in {
                    normalize_doi(value) for value in doi_candidates
                }
            elif basis == "ARXIV_ID":
                arxiv_candidates = re.findall(r"(?:arxiv:\s*)?([a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", raw, flags=re.I)
                verified_match = bool(paper.get("arxiv_id")) and normalize_arxiv_id(paper.get("arxiv_id")) in {
                    normalize_arxiv_id(value) for value in arxiv_candidates
                }
            elif basis == "TITLE_AUTHOR":
                normalized_raw = normalize_title(raw)
                title = normalize_title(paper.get("title"))
                authors = paper.get("authors") or []
                surnames = {
                    normalize_title((author.get("name") if isinstance(author, dict) else author)).split(" ")[-1]
                    for author in authors
                    if normalize_title(author.get("name") if isinstance(author, dict) else author)
                }
                raw_years = set(re.findall(r"\b(?:18|19|20)\d{2}\b", raw))
                author_ok = not surnames or bool(surnames & set(normalized_raw.split()))
                year_ok = not raw_years or not paper.get("year") or str(paper.get("year")) in raw_years
                verified_match = bool(title) and title in normalized_raw and author_ok and year_ok
            elif basis == "MANUAL":
                errors.append(f"author bibliography entry {index} MANUAL match cannot establish prior awareness")
            if verified_match:
                derived_bibliography_ids.add(matched)
            elif basis != "MANUAL":
                errors.append(f"author bibliography entry {index} {basis} match is not independently reproduced")
    if bibliography_ids != derived_bibliography_ids:
        errors.append("author_bibliography.normalized_paper_ids disagrees with bibliography entries")
    if list(bibliography.get("unmatched_entries") or []) != derived_unmatched_entries:
        errors.append("author_bibliography.unmatched_entries disagrees with bibliography entries")
    if not bibliography_ids <= candidate_ids:
        errors.append("author_bibliography.normalized_paper_ids must reference canonical candidate IDs")
    if bibliography.get("status") == "NOT_PROVIDED" and bibliography_ids:
        errors.append("author_bibliography cannot contain normalized IDs when it was not provided")
    if bibliography.get("status") == "NOT_PROVIDED" and bibliography_entries:
        errors.append("author_bibliography cannot contain entries when it was not provided")
    bridge_policy = report["search"].get("bridge_policy") or {}
    high_citation_threshold = bridge_policy.get("high_citation_threshold")
    if bridge_policy.get("status") == "CALIBRATED" and not isinstance(high_citation_threshold, int):
        errors.append("CALIBRATED bridge policy requires an integer high_citation_threshold")
    if bridge_policy.get("status") == "UNCONFIGURED" and high_citation_threshold is not None:
        errors.append("UNCONFIGURED bridge policy cannot claim a high_citation_threshold")
    manifest = report.get("run_manifest") or {}
    for field in ("tool_version", "config_hash", "cutoff", "domain", "model_name", "prompt_version", "retrieval_started_at", "retrieval_completed_at", "candidate_snapshot_hash", "provider_endpoints"):
        if not manifest.get(field):
            errors.append(f"run_manifest missing {field}")
    if manifest.get("tool_version") != "0.3.0":
        errors.append("run_manifest.tool_version must match this validator version")
    if manifest.get("cutoff") != cutoff:
        errors.append("run_manifest.cutoff disagrees with input.cutoff")
    if manifest.get("candidate_snapshot_hash") != candidate_snapshot_hash(report["papers"]):
        errors.append("run_manifest candidate_snapshot_hash does not match canonical candidates")
    retrieval_started_at = parse_datetime(manifest.get("retrieval_started_at"), "run_manifest.retrieval_started_at")
    retrieval_completed_at = parse_datetime(manifest.get("retrieval_completed_at"), "run_manifest.retrieval_completed_at")
    if retrieval_started_at and frozen_at:
        start_compare, freeze_compare = comparable(retrieval_started_at, frozen_at)
        if start_compare < freeze_compare:
            errors.append("retrieval started before the claim map was frozen")
    if retrieval_started_at and retrieval_completed_at:
        start_compare, completed_compare = comparable(retrieval_started_at, retrieval_completed_at)
        if completed_compare < start_compare:
            errors.append("retrieval completed before it started")
    if retrieval_completed_at and decided_at:
        completed_compare, decided_compare = comparable(retrieval_completed_at, decided_at)
        if decided_compare < completed_compare:
            errors.append("verdict was decided before retrieval completed")
    for index, endpoint in enumerate(manifest.get("provider_endpoints") or []):
        if not isinstance(endpoint, dict) or not endpoint.get("name") or not endpoint.get("endpoint") or not endpoint.get("version"):
            errors.append(f"run_manifest provider endpoint {index} is incomplete")

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
        checks = paper.get("citation_validation") or []
        if paper.get("doi"):
            doi = normalize_doi(paper.get("doi"))
            if not any(item.get("type") == "DOI" and item.get("provider") == "crossref" and item.get("valid") is True and normalize_doi(item.get("identifier")) == doi for item in checks if isinstance(item, dict)):
                errors.append(f"paper {paper_id} DOI was not independently validated by Crossref")
        if paper.get("arxiv_id"):
            arxiv_id = normalize_arxiv_id(paper.get("arxiv_id"))
            if not any(item.get("type") == "ARXIV" and item.get("provider") == "arxiv" and item.get("valid") is True and normalize_arxiv_id(item.get("identifier")) == arxiv_id for item in checks if isinstance(item, dict)):
                errors.append(f"paper {paper_id} arXiv ID was not independently validated by arXiv")

    for evidence_id, item in evidence.items():
        for field in ("canonical_paper_id", "span", "location", "source", "source_level", "retrieved_at"):
            if not item.get(field):
                errors.append(f"evidence {evidence_id} missing {field}")
        canonical_paper_id = str(item.get("canonical_paper_id") or "")
        if canonical_paper_id not in papers:
            errors.append(f"evidence {evidence_id} references unknown paper {canonical_paper_id}")
        if item.get("source_level") not in EVIDENCE_LEVELS:
            errors.append(f"evidence {evidence_id} has invalid source_level {item.get('source_level')}")
        retrieved_at = parse_datetime(item.get("retrieved_at"), f"evidence {evidence_id}.retrieved_at")
        if evidence_id in {str(value) for value in verdict.get("evidence_ids") or []} and retrieved_at and decided_at:
            retrieved_compare, decided_compare = comparable(retrieved_at, decided_at)
            if retrieved_compare > decided_compare:
                errors.append(f"verdict was decided before evidence {evidence_id} was retrieved")
            paper = papers.get(canonical_paper_id)
            if not paper or paper.get("cutoff_status") != "ELIGIBLE":
                errors.append(f"verdict evidence {evidence_id} comes from a non-eligible paper")

    killer_clusters: list[str] = []
    for killer in report["top_killers"]:
        paper_id = str(killer.get("paper_id"))
        required_killer_evidence: set[str] = set()
        if paper_id not in papers:
            errors.append(f"top killer references unknown paper {paper_id}")
        elif papers[paper_id].get("cutoff_status") != "ELIGIBLE" or not papers[paper_id].get("earliest_public_date"):
            errors.append(f"top killer {paper_id} is not strictly cutoff-eligible")
        if paper_id in papers:
            killer_clusters.append(str(papers[paper_id].get("cluster_id") or papers[paper_id].get("canonical_key") or paper_id))
        if "covers" not in killer or "does_not_cover" not in killer:
            errors.append(f"top killer {paper_id} must state covers and does_not_cover")
        elif not killer.get("does_not_cover") and classification != "DIRECT_PRECEDENT":
            errors.append(f"top killer {paper_id} must state at least one does_not_cover facet")
        if killer.get("prior_awareness") not in PRIOR_AWARENESS:
            errors.append(f"top killer {paper_id} has invalid prior_awareness")
        expected_awareness = (
            "UNKNOWN" if bibliography.get("status") != "PROVIDED" else
            "ALREADY_CITED" if paper_id in bibliography_ids else "OVERLOOKED"
        )
        if killer.get("prior_awareness") != expected_awareness:
            errors.append(f"top killer {paper_id} prior_awareness disagrees with normalized author bibliography")
        for facet in killer.get("covers") or []:
            status, ids_for_facet = _coverage(papers.get(paper_id, {}), str(facet))
            required_killer_evidence.update(str(value) for value in ids_for_facet)
            allowed_kinds = {"METHOD", "RESULT"} if str(facet) in {
                facet_id for facet_id, facet_type in facet_types.items() if facet_type in {"outcome", "evaluation_condition"}
            } else {"METHOD"}
            if status not in HARD_COVERAGE or not ids_for_facet:
                errors.append(f"top killer {paper_id} claims unsupported coverage for {facet}")
            for evidence_id in ids_for_facet:
                item = evidence.get(str(evidence_id))
                if not item or str(item.get("canonical_paper_id")) != paper_id or item.get("source_level") != "TIER_2_FULLTEXT" or item.get("evidence_kind") not in allowed_kinds or str(facet) not in set(str(value) for value in item.get("supports") or []):
                    errors.append(f"top killer {paper_id} coverage for {facet} is not evidence-bound")
        for facet in killer.get("does_not_cover") or []:
            status, ids_for_facet = _coverage(papers.get(paper_id, {}), str(facet))
            required_killer_evidence.update(str(value) for value in ids_for_facet)
            if status not in {"NO", "PARTIAL"} or not ids_for_facet:
                errors.append(f"top killer {paper_id} lacks negative evidence for {facet}")
            for evidence_id in ids_for_facet:
                item = evidence.get(str(evidence_id))
                if not item or str(item.get("canonical_paper_id")) != paper_id or item.get("source_level") != "TIER_2_FULLTEXT" or str(facet) not in set(str(value) for value in item.get("supports") or []):
                    errors.append(f"top killer {paper_id} does_not_cover for {facet} is not evidence-bound")
        for evidence_id in killer.get("evidence_ids") or []:
            if str(evidence_id) not in evidence:
                errors.append(f"top killer {paper_id} references unknown evidence {evidence_id}")
        missing_killer_evidence = required_killer_evidence - {str(value) for value in killer.get("evidence_ids") or []}
        if missing_killer_evidence:
            errors.append(f"top killer {paper_id} omits coverage or non-coverage evidence IDs: {sorted(missing_killer_evidence)}")
    if len(killer_clusters) != len(set(killer_clusters)):
        errors.append("top killers contain multiple versions from the same work cluster")

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
                            if str(evidence[str(evidence_id)].get("canonical_paper_id")) != paper_id:
                                errors.append(f"paper {paper_id} coverage for {facet} uses evidence from another paper")
                            allowed_kinds = {"METHOD", "RESULT"} if facet_types.get(facet) in {"outcome", "evaluation_condition"} else {"METHOD"}
                            if evidence[str(evidence_id)].get("source_level") != "TIER_2_FULLTEXT":
                                errors.append(f"paper {paper_id} hard coverage for {facet} is not Tier-2 full-text evidence")
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
                and str(evidence[evidence_id].get("canonical_paper_id")) == str(paper.get("id"))
                and evidence[evidence_id].get("source_level") == "TIER_2_FULLTEXT"
                and evidence[evidence_id].get("evidence_kind") in ({"METHOD", "RESULT"} if facet_types.get(str(facet)) in {"outcome", "evaluation_condition"} else {"METHOD"})
                and str(facet) in set(str(value) for value in evidence[evidence_id].get("supports") or [])
                for evidence_id in ids_for_facet
            )
            if not valid:
                paper["coverage"][facet] = {"status": "UNKNOWN", "evidence_ids": []}
    computed_mps = solve_mps(verified_papers, critical, max_size=3, strict=True, require_evidence=True) if critical else []
    computed_size = computed_mps[0]["size"] if computed_mps else None
    recomputed_graph_bridges: list[dict[str, Any]] = []
    for mps in computed_mps:
        for paper_a, paper_b in combinations([str(value) for value in mps.get("paper_ids") or []], 2):
            recomputed_graph_bridges.extend(find_bridges(
                paper_a, paper_b, papers.values(), cutoff=cutoff,
                high_citation_threshold=high_citation_threshold,
            ))
    def bridge_route_key(bridge: dict[str, Any]) -> tuple[str, tuple[str, ...], str]:
        kind = str(bridge.get("underlying_type") or bridge.get("type") or "").upper()
        return kind, tuple(sorted(str(value) for value in bridge.get("paper_ids") or [])), str(bridge.get("source_paper_id") or "")
    unique_recomputed = {bridge_route_key(item): item for item in recomputed_graph_bridges}
    recomputed_graph_bridges = list(unique_recomputed.values())
    expected_landscape = {
        bridge_route_key(item) for item in recomputed_graph_bridges
        if item.get("type") == "LANDSCAPE_BRIDGE"
    }
    submitted_landscape = {
        bridge_route_key(item) for item in report.get("landscape_bridges") or []
        if isinstance(item, dict)
    }
    if submitted_landscape != expected_landscape:
        missing = sorted(expected_landscape - submitted_landscape)
        extra = sorted(submitted_landscape - expected_landscape)
        errors.append(f"landscape bridges disagree with deterministic citation graph; missing={missing}, extra={extra}")
    for bridge in report.get("landscape_bridges") or []:
        if not relation_route_exists(bridge, papers.values()):
            errors.append(f"landscape bridge {bridge_route_key(bridge)} is not reproduced by source references")
        source = papers.get(str(bridge.get("source_paper_id") or ""))
        if source and source.get("cutoff_status") == "ELIGIBLE":
            errors.append(f"landscape bridge {bridge_route_key(bridge)} incorrectly uses a cutoff-eligible source")
    submitted_size = min(valid_sizes) if valid_sizes else None
    if submitted_size is not None and computed_size != submitted_size:
        errors.append(f"submitted MPS size {submitted_size} is not globally minimal; recomputed size is {computed_size}")
    if computed_size is not None and submitted_size is None:
        errors.append(f"report omits a recomputed Minimal Prior Set of size {computed_size}")
    if computed_size == 1 and classification != "DIRECT_PRECEDENT":
        errors.append("classification conflicts with recomputed one-paper direct precedent")
    if computed_size in {2, 3} and classification not in {"STRONG_COMPOSITION_RISK", "PLAUSIBLE_COMPOSITION_RISK", "FRAGMENTED_PRECEDENT"}:
        errors.append("classification conflicts with recomputed multi-paper prior set")
    if computed_size is None and classification not in {"RESIDUAL_NOVELTY", "INCONCLUSIVE"}:
        errors.append("classification conflicts with absence of any recomputed Minimal Prior Set")
    if classification == "FRAGMENTED_PRECEDENT" and computed_size not in {2, 3}:
        errors.append("FRAGMENTED_PRECEDENT requires a recomputed two- or three-paper Minimal Prior Set")
    for mps in computed_mps:
        ids = [str(value) for value in mps.get("paper_ids") or []]
        recomputed_strength = bridge_strength(recomputed_graph_bridges, ids)
        submitted_strength = bridge_strength(report.get("bridges") or [], ids)
        if recomputed_strength == "GRAPH" and submitted_strength == "NONE":
            errors.append(f"report omits a deterministic graph bridge for MPS {ids}")
        if classification == "FRAGMENTED_PRECEDENT" and recomputed_strength == "GRAPH":
            errors.append(f"FRAGMENTED_PRECEDENT hides a qualifying deterministic graph bridge for MPS {ids}")
    if classification in ADVERSE and not mps_sets:
        errors.append(f"{classification} requires a Minimal Prior Set")
    if classification == "DIRECT_PRECEDENT" and (not valid_sizes or min(valid_sizes) != 1):
        errors.append("DIRECT_PRECEDENT requires a one-paper MPS")
    if classification == "DIRECT_PRECEDENT":
        direct_ids = {str(value) for item in computed_mps if item.get("size") == 1 for value in item.get("paper_ids") or []}
        killer_ids = {str(item.get("paper_id")) for item in report.get("top_killers") or []}
        if not direct_ids or not (direct_ids & killer_ids):
            errors.append("DIRECT_PRECEDENT requires its recomputed one-paper precedent in top_killers")
    if classification in {"STRONG_COMPOSITION_RISK", "PLAUSIBLE_COMPOSITION_RISK"} and (not valid_sizes or min(valid_sizes) not in {2, 3}):
        errors.append(f"{classification} requires a two- or three-paper MPS")

    eligible_bridges: list[dict[str, Any]] = []
    for bridge in report["bridges"]:
        bridge_type = str(bridge.get("type", "")).upper()
        bridge_eligible = bridge.get("cutoff_status", "ELIGIBLE") == "ELIGIBLE"
        expected_provenance = "text" if bridge_type in TEXTUAL_BRIDGES else "graph" if bridge_type in GRAPH_BRIDGES else None
        if bridge.get("provenance_type") != expected_provenance:
            errors.append(f"bridge {bridge_type} has invalid provenance_type")
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
                bridge_eligible = False
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
            if bridge_type == "CO_CITATION":
                matching = next((item for item in recomputed_graph_bridges if bridge_route_key(item) == bridge_route_key(bridge)), None)
                if not matching or bridge.get("base_rate_status") != matching.get("base_rate_status"):
                    errors.append("CO_CITATION base-rate assessment disagrees with deterministic citation counts and policy")
                if not graph_bridge_qualifies(matching or bridge):
                    bridge_eligible = False
        if bridge_type in TEXTUAL_BRIDGES and source_id in papers:
            textual_route_ok = relation_route_exists(bridge, papers.values())
            if not textual_route_ok:
                errors.append(f"textual bridge {bridge_type} is not grounded by the source citation route")
        if bridge_eligible and source_id in papers and papers[source_id].get("cutoff_status") == "ELIGIBLE":
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
                elif source_id and str(evidence[str(evidence_id)].get("canonical_paper_id")) != source_id:
                    errors.append(f"textual bridge {bridge_type} uses evidence from a different source paper")
                elif evidence[str(evidence_id)].get("source_level") != "TIER_2_FULLTEXT":
                    errors.append(f"textual bridge {bridge_type} is not backed by Tier-2 full-text evidence")

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
        if term.get("admitted", True) and (not term.get("source_paper_id") or not term.get("evidence_ids") or not term.get("first_observed")):
            errors.append(f"ancestor term {term.get('term')} lacks provenance")
        for evidence_id in term.get("evidence_ids") or []:
            if str(evidence_id) not in evidence:
                errors.append(f"ancestor term {term.get('term')} references unknown evidence {evidence_id}")
        source_paper_id = str(term.get("source_paper_id") or "")
        if source_paper_id and source_paper_id not in papers:
            errors.append(f"ancestor term {term.get('term')} references unknown source paper {source_paper_id}")
        for evidence_id in term.get("evidence_ids") or []:
            item = evidence.get(str(evidence_id))
            if item and source_paper_id and str(item.get("canonical_paper_id")) != source_paper_id:
                errors.append(f"ancestor term {term.get('term')} evidence comes from a different paper")

    rewrite = report.get("defensible_rewrite")
    if not isinstance(rewrite, dict) or not str(rewrite.get("text") or "").strip() or not isinstance(rewrite.get("prior_coverage_claims"), list):
        errors.append("defensible_rewrite must contain text and prior_coverage_claims")
    else:
        for index, claim in enumerate(rewrite.get("prior_coverage_claims") or []):
            if not isinstance(claim, dict) or not str(claim.get("text") or "").strip() or not claim.get("evidence_ids"):
                errors.append(f"defensible rewrite coverage claim {index} lacks evidence")
                continue
            for evidence_id in claim.get("evidence_ids") or []:
                item = evidence.get(str(evidence_id))
                source_paper = papers.get(str((item or {}).get("canonical_paper_id")))
                if not item or not source_paper or source_paper.get("cutoff_status") != "ELIGIBLE":
                    errors.append(f"defensible rewrite coverage claim {index} references invalid evidence {evidence_id}")

    sensitivity = report.get("criticality_sensitivity") or []
    removed_facets = [str(item.get("removed_facet")) for item in sensitivity if isinstance(item, dict)]
    if len(sensitivity) != len(critical) or set(removed_facets) != critical or len(removed_facets) != len(set(removed_facets)):
        errors.append("criticality sensitivity must contain exactly one result per critical facet")
    expected_sensitivity = criticality_sensitivity(
        verified_papers, sorted(critical), max_size=3, strict=True, require_evidence=True
    ) if critical else []
    def normalized_sensitivity(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            [{
                "removed_facet": str(item.get("removed_facet")),
                "baseline_size": item.get("baseline_size"),
                "alternative_size": item.get("alternative_size"),
                "alternative_classification": item.get("alternative_classification"),
            } for item in values if isinstance(item, dict)],
            key=lambda item: item["removed_facet"],
        )
    if normalized_sensitivity(sensitivity) != normalized_sensitivity(expected_sensitivity):
        errors.append("criticality sensitivity disagrees with deterministic leave-one-facet-out recomputation")

    post_cutoff = {str(value) for value in report["excluded"].get("post_cutoff") or []}
    date_uncertain = {str(value) for value in report["excluded"].get("date_uncertain") or []}
    expected_post_cutoff = {paper_id for paper_id, paper in papers.items() if paper.get("cutoff_status") == "POST_CUTOFF"}
    expected_date_uncertain = {paper_id for paper_id, paper in papers.items() if paper.get("cutoff_status") in {"DATE_UNCERTAIN", "ELIGIBILITY_UNCERTAIN"}}
    if post_cutoff != expected_post_cutoff:
        errors.append("excluded.post_cutoff does not match the canonical paper statuses")
    if date_uncertain != expected_date_uncertain:
        errors.append("excluded.date_uncertain does not match the canonical paper statuses")
    used_papers = {str(item.get("paper_id")) for item in report.get("top_killers") or []}
    used_papers |= {str(value) for item in mps_sets for value in item.get("paper_ids") or []}
    if used_papers & (post_cutoff | date_uncertain):
        errors.append("post-cutoff or date-uncertain papers appear in killers or MPS")

    if classification in {"RESIDUAL_NOVELTY", "INCONCLUSIVE"} and not (report["search"].get("gaps") or []):
        errors.append(f"{classification} must disclose search gaps")
    if classification == "INCONCLUSIVE" and verdict.get("novelty_risk") != "INCONCLUSIVE":
        errors.append("INCONCLUSIVE classification requires INCONCLUSIVE novelty risk")
    if classification in ADVERSE and verdict.get("evidence_confidence") == "WEAK":
        errors.append("adverse classification requires non-WEAK evidence confidence")
    risk_matrix = {
        "DIRECT_PRECEDENT": {"HIGH", "MEDIUM"},
        "STRONG_COMPOSITION_RISK": {"HIGH", "MEDIUM"},
        "PLAUSIBLE_COMPOSITION_RISK": {"HIGH", "MEDIUM"},
        "FRAGMENTED_PRECEDENT": {"HIGH", "MEDIUM", "LOW", "INCONCLUSIVE"},
        "RESIDUAL_NOVELTY": {"HIGH", "MEDIUM", "LOW"},
        "INCONCLUSIVE": {"INCONCLUSIVE"},
    }
    if classification in risk_matrix and verdict.get("novelty_risk") not in risk_matrix[classification]:
        errors.append(f"novelty risk {verdict.get('novelty_risk')} conflicts with {classification}")
    if verdict.get("novelty_risk") == "LOW" and (verdict.get("search_coverage") != "BROAD" or verdict.get("evidence_confidence") == "WEAK"):
        errors.append("LOW novelty risk requires BROAD search coverage and non-WEAK evidence confidence")
    risk_basis = verdict.get("risk_basis") or []
    if classification in {"FRAGMENTED_PRECEDENT", "RESIDUAL_NOVELTY"} and verdict.get("novelty_risk") == "HIGH":
        if not risk_basis:
            errors.append(f"HIGH novelty risk with {classification} requires an explicit risk_basis")
        allowed_basis = {"CRITICALITY_SENSITIVITY_COLLAPSE", "CRITICALITY_DISPUTE", "OTHER_EXPLICIT_RISK"}
        for index, basis in enumerate(risk_basis):
            if not isinstance(basis, dict) or basis.get("type") not in allowed_basis or not str(basis.get("detail") or "").strip():
                errors.append(f"risk_basis {index} must have a supported type and concrete detail")
            for evidence_id in (basis.get("evidence_ids") or []) if isinstance(basis, dict) else []:
                if str(evidence_id) not in evidence:
                    errors.append(f"risk_basis {index} references unknown evidence {evidence_id}")

    obligations = report["search"].get("obligations") or []
    incomplete_obligations = []
    for index, obligation in enumerate(obligations):
        if not isinstance(obligation, dict) or not obligation.get("id") or obligation.get("status") not in {"COMPLETE", "INCOMPLETE"}:
            errors.append(f"search obligation {index} is malformed")
            continue
        if obligation.get("status") == "INCOMPLETE":
            incomplete_obligations.append(str(obligation.get("id")))
    if incomplete_obligations and not report["search"].get("gaps"):
        errors.append(f"incomplete search obligations require concrete gaps: {incomplete_obligations}")

    failure_types = {"RATE_LIMIT", "TIMEOUT", "HTTP_5XX", "MALFORMED_RESPONSE", "TRUNCATED", "AUTH", "OTHER"}
    structured_failures = []
    for index, failure in enumerate(report["search"].get("failures") or []):
        if not isinstance(failure, dict) or not failure.get("provider") or failure.get("type") not in failure_types:
            errors.append(f"search failure {index} must identify provider and failure type")
        else:
            structured_failures.append(failure)
    query_runs = report["search"].get("query_runs") or []
    query_ids: list[str] = []
    facet_query_families = {facet: set() for facet in critical}
    for index, run in enumerate(query_runs):
        required = ("query_id", "provider", "family", "query", "reason", "target_facets", "retrieved_at", "returned_count", "total_count", "truncated", "pagination", "corpus", "saturation_stop_reason", "paper_ids", "canonical_paper_ids", "status")
        if not isinstance(run, dict) or any(field not in run for field in required):
            errors.append(f"query run {index} is missing required reproducibility fields")
            continue
        query_id = str(run.get("query_id"))
        query_ids.append(query_id)
        if not isinstance(run.get("returned_count"), int) or run.get("returned_count", -1) < 0:
            errors.append(f"query {query_id} returned_count must be a non-negative integer")
        if run.get("total_count") is not None and (not isinstance(run.get("total_count"), int) or run.get("total_count", -1) < 0):
            errors.append(f"query {query_id} total_count must be null or a non-negative integer")
        if not isinstance(run.get("pagination"), dict) or not str(run.get("corpus") or "").strip():
            errors.append(f"query {query_id} lacks auditable pagination or corpus metadata")
        if len(run.get("paper_ids") or []) != run.get("returned_count"):
            errors.append(f"query {query_id} returned_count disagrees with paper_ids")
        if len(run.get("paper_ids") or []) != len(set(str(value) for value in run.get("paper_ids") or [])):
            errors.append(f"query {query_id} paper_ids must be unique provider-returned IDs")
        if run.get("total_count") is not None and run.get("returned_count", 0) > run.get("total_count", 0):
            errors.append(f"query {query_id} returned_count exceeds provider total_count")
        canonical_for_run = [str(value) for value in run.get("canonical_paper_ids") or []]
        if len(canonical_for_run) != len(set(canonical_for_run)) or not set(canonical_for_run) <= candidate_ids:
            errors.append(f"query {query_id} canonical_paper_ids must be unique canonical candidates")
        retrieved_at = parse_datetime(run.get("retrieved_at"), f"search.query_runs[{index}].retrieved_at")
        if retrieved_at and frozen_at:
            retrieved_compare, frozen_compare = comparable(retrieved_at, frozen_at)
            if retrieved_compare < frozen_compare:
                errors.append(f"query {query_id} ran before the claim map was frozen")
        if retrieved_at and retrieval_started_at and retrieval_completed_at:
            retrieved_compare, started_compare = comparable(retrieved_at, retrieval_started_at)
            retrieved_to_complete, completed_compare = comparable(retrieved_at, retrieval_completed_at)
            if retrieved_compare < started_compare or retrieved_to_complete > completed_compare:
                errors.append(f"query {query_id} falls outside the retrieval window")
        for facet in set(str(value) for value in run.get("target_facets") or []) & critical:
            if run.get("status") == "ok":
                facet_query_families[facet].add(str(run.get("family")))
        needs_failure = run.get("status") != "ok" or run.get("truncated") is True
        if needs_failure:
            expected_type = "TRUNCATED" if run.get("truncated") is True else None
            matched = any(
                str(item.get("provider")) == str(run.get("provider"))
                and (expected_type is None or item.get("type") == expected_type)
                for item in structured_failures
            )
            if not matched:
                errors.append(f"query {query_id} failure or truncation is not disclosed")
    if len(query_ids) != len(set(query_ids)) or any(not value.strip() for value in query_ids):
        errors.append("query_id values must be non-empty and unique")
    recomputed_saturated = bool(query_runs) and all(
        isinstance(run, dict)
        and run.get("status") == "ok"
        and run.get("saturation_stop_reason") in {"PROVIDER_EXHAUSTED", "NO_NEW_RESULTS"}
        for run in query_runs
    )
    if report["search"].get("saturated") is not recomputed_saturated:
        errors.append(f"search.saturated disagrees with SearchRun stop reasons: expected {recomputed_saturated}")
    for facet, families in facet_query_families.items():
        if len(families) < 2:
            errors.append(f"critical facet {facet} is covered by fewer than two query families")
    if not any(run.get("removed_author_terms") is True for run in query_runs if isinstance(run, dict)):
        errors.append("at least one query must remove author-created terminology")
    if not any(run.get("family") == "composition_bridge" for run in query_runs if isinstance(run, dict)):
        errors.append("at least one composition_bridge query is required")
    for failure in structured_failures:
        if not any(
            str(run.get("provider")) == str(failure.get("provider"))
            and (run.get("status") != "ok" or run.get("truncated") is True)
            for run in query_runs if isinstance(run, dict)
        ):
            errors.append(f"provider failure for {failure.get('provider')} is not linked to a failed or truncated SearchRun")
    query_id_set = set(query_ids)
    query_papers = {str(run.get("query_id")): {str(value) for value in run.get("canonical_paper_ids") or []} for run in query_runs if isinstance(run, dict)}
    for paper_id, paper in papers.items():
        found_by = {str(value) for value in paper.get("found_by_query_ids") or []}
        if not found_by:
            errors.append(f"paper {paper_id} lacks found_by_query_ids")
        elif not found_by <= query_id_set:
            errors.append(f"paper {paper_id} references unknown discovery query IDs")
        for query_id in found_by & query_id_set:
            if paper_id not in query_papers.get(query_id, set()):
                errors.append(f"paper {paper_id} discovery query {query_id} does not list the paper")

    derived_coverage = derive_search_coverage(report["search"])
    if report["search"].get("coverage_derivation") != derived_coverage:
        errors.append("search.coverage_derivation does not match deterministic SearchRun derivation")
    if verdict.get("search_coverage") != derived_coverage["level"]:
        errors.append(f"verdict Search Coverage must equal deterministic SearchRun derivation: {derived_coverage['level']}")

    for format_name, rendered in (("markdown", to_markdown(report)), ("html", to_html(report))):
        for error in validate_user_output(rendered, format_name):
            errors.append(f"{format_name}: {error}")
    return errors
