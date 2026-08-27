from copy import deepcopy

from validate_output import (
    candidate_snapshot_hash,
    claim_map_hash,
    graph_expansion_gap_marker,
    graph_expansion_obligations,
    validate_arxiv_page_history,
    validate_report,
)


def refreeze(report):
    value = claim_map_hash(report["claim_map"])
    report["claim_map"]["freeze_hash"] = value
    next(item for item in report["audit_log"] if item.get("event") == "claim_map_frozen")["freeze_hash"] = value


def test_valid_fixture_passes(valid_report):
    assert validate_report(valid_report) == []


def test_rejects_missing_nested_schema_fields(valid_report):
    report = deepcopy(valid_report)
    report["search"].pop("providers")
    report["excluded"].pop("other")
    errors = validate_report(report)
    assert any("'providers' is a required property" in error for error in errors)
    assert any("'other' is a required property" in error for error in errors)


def test_rejects_paper_missing_machine_contract_fields(valid_report):
    report = deepcopy(valid_report)
    report["papers"][0].pop("title")
    report["papers"][0].pop("providers")
    errors = validate_report(report)
    assert any("'title' is a required property" in error for error in errors)
    assert any("'providers' is a required property" in error for error in errors)


def test_rejects_high_verdict_without_evidence(valid_report):
    report = deepcopy(valid_report)
    report["verdict"]["evidence_ids"] = []
    assert any("lacks report-level evidence" in error for error in validate_report(report))


def test_rejects_post_cutoff_paper_in_mps(valid_report):
    report = deepcopy(valid_report)
    report["papers"][1]["cutoff_status"] = "POST_CUTOFF"
    assert any("non-eligible paper B" in error for error in validate_report(report))


def test_rejects_false_eligible_date_after_cutoff(valid_report):
    report = deepcopy(valid_report)
    report["papers"][1]["earliest_public_date"] = "2025-10-01"
    assert any("post-dates the cutoff" in error for error in validate_report(report))


def test_recomputes_derived_date_and_cutoff_from_observed_dates(valid_report):
    report = deepcopy(valid_report)
    report["papers"][0]["dates"] = [{"value": "2030-01-01", "source": "arxiv_v1", "verified": True}]
    errors = validate_report(report)
    assert any("earliest_public_date disagrees" in error for error in errors)
    assert any("cutoff_status disagrees" in error for error in errors)


def test_rejects_eligible_paper_without_verified_date(valid_report):
    report = deepcopy(valid_report)
    report["papers"][0]["earliest_public_date"] = None
    assert any("lacks a verified earliest public date" in error for error in validate_report(report))


def test_rejects_graph_only_bridge_as_strong(valid_report):
    report = deepcopy(valid_report)
    report["bridges"] = [{"type": "CO_CITATION", "provenance_type": "graph", "paper_ids": ["A", "B"], "source_paper_id": "C", "cutoff_status": "ELIGIBLE", "graph_verified": True, "text_verified": False, "evidence_ids": [], "base_rate_status": "UNASSESSED"}]
    assert any("requires an eligible textual bridge" in error for error in validate_report(report))


def test_rejects_unrelated_textual_bridge_as_strong(valid_report):
    report = deepcopy(valid_report)
    report["bridges"][0]["paper_ids"] = ["A", "C"]
    assert any("requires an eligible textual bridge" in error for error in validate_report(report))


def test_rejects_bridge_without_source_paper(valid_report):
    report = deepcopy(valid_report)
    report["bridges"][0].pop("source_paper_id")
    assert any("'source_paper_id' is a required property" in error for error in validate_report(report))


def test_textual_bridge_source_must_be_rechecked_as_candidate(valid_report):
    report = deepcopy(valid_report)
    report["bridges"][0]["source_rechecked_as_candidate"] = False
    assert any("was not rechecked" in error for error in validate_report(report))


def test_rejects_fabricated_co_citation(valid_report):
    report = deepcopy(valid_report)
    report["verdict"]["classification"] = "PLAUSIBLE_COMPOSITION_RISK"
    report["bridges"] = [{"type": "CO_CITATION", "provenance_type": "graph", "paper_ids": ["A", "B"], "source_paper_id": "C", "cutoff_status": "ELIGIBLE", "graph_verified": True, "text_verified": False, "evidence_ids": [], "base_rate_status": "UNASSESSED"}]
    report["papers"][2]["references"] = []
    assert any("not reproduced by source references" in error for error in validate_report(report))


def test_rejects_hard_coverage_without_evidence(valid_report):
    report = deepcopy(valid_report)
    report["papers"][0]["coverage"]["F1"]["evidence_ids"] = []
    errors = validate_report(report)
    assert any("hard-covers F1 without evidence" in error for error in errors)


def test_rejects_coverage_evidence_from_another_paper(valid_report):
    report = deepcopy(valid_report)
    report["papers"][0]["coverage"]["F1"]["evidence_ids"] = ["E2"]
    assert any("uses evidence from another paper" in error for error in validate_report(report))


def test_rejects_duplicate_facet_and_paper_ids(valid_report):
    report = deepcopy(valid_report)
    report["claim_map"]["facets"][1]["id"] = "F1"
    report["papers"][1]["id"] = "A"
    errors = validate_report(report)
    assert any("duplicate facet IDs" in error for error in errors)
    assert any("duplicate paper IDs" in error for error in errors)


def test_evidence_must_explicitly_support_each_covered_facet(valid_report):
    report = deepcopy(valid_report)
    report["papers"][0]["coverage"]["F2"] = {"status": "EXACT", "evidence_ids": ["E1"]}
    assert any("does not declare support for that facet" in error for error in validate_report(report))


def test_recomputes_global_minimum_instead_of_trusting_submitted_mps(valid_report):
    report = deepcopy(valid_report)
    report["evidence"].append({"id": "E6", "canonical_paper_id": "A", "source_level": "TIER_2_FULLTEXT", "acquisition_id": "FT:A:fixture", "span": "Selection is conditioned on compression.", "location": "Method 3.2", "source": "https://example.org/a", "retrieved_at": "2026-08-27T07:30:00Z", "evidence_kind": "METHOD", "supports": ["F2"]})
    report["papers"][0]["coverage"]["F2"] = {"status": "EXACT", "evidence_ids": ["E6"]}
    assert any("not globally minimal" in error for error in validate_report(report))


def test_residual_novelty_requires_search_gaps(valid_report):
    report = deepcopy(valid_report)
    report["verdict"].update({"classification": "RESIDUAL_NOVELTY", "novelty_risk": "LOW", "evidence_ids": []})
    report["minimal_prior_sets"] = []
    report["bridges"] = []
    report["search"]["gaps"] = []
    assert any("must disclose search gaps" in error for error in validate_report(report))


def test_low_risk_requires_broad_nonweak_search(valid_report):
    report = deepcopy(valid_report)
    report["verdict"].update({"classification": "RESIDUAL_NOVELTY", "novelty_risk": "LOW", "search_coverage": "NARROW", "evidence_confidence": "WEAK", "evidence_ids": []})
    report["minimal_prior_sets"] = []
    report["bridges"] = []
    assert any("LOW novelty risk requires BROAD" in error for error in validate_report(report))


def test_classification_cannot_hide_recomputed_mps(valid_report):
    report = deepcopy(valid_report)
    report["verdict"].update({"classification": "RESIDUAL_NOVELTY", "novelty_risk": "LOW", "evidence_ids": []})
    report["minimal_prior_sets"] = []
    report["bridges"] = []
    errors = validate_report(report)
    assert any("omits a recomputed Minimal Prior Set" in error for error in errors)
    assert any("classification conflicts with recomputed multi-paper" in error for error in errors)


def test_novelty_risk_must_match_classification(valid_report):
    report = deepcopy(valid_report)
    report["verdict"]["novelty_risk"] = "LOW"
    assert any("conflicts with STRONG_COMPOSITION_RISK" in error for error in validate_report(report))


def test_strong_composition_allows_medium_risk(valid_report):
    report = deepcopy(valid_report)
    report["verdict"]["novelty_risk"] = "MEDIUM"
    assert validate_report(report) == []


def test_broad_requires_known_structured_providers_and_query_logs(valid_report):
    report = deepcopy(valid_report)
    report["search"]["providers"] = ["fake-one", "fake-two"]
    report["search"]["query_runs"] = []
    errors = validate_report(report)
    assert any("is not of type 'object'" in error for error in errors)


def test_result_evidence_allowed_for_outcome_facet(valid_report):
    report = deepcopy(valid_report)
    report["claim_map"]["facets"][1]["type"] = "outcome"
    report["evidence"][1]["evidence_kind"] = "RESULT"
    refreeze(report)
    assert validate_report(report) == []


def test_rejects_mutated_frozen_claim_map(valid_report):
    report = deepcopy(valid_report)
    report["claim_map"]["facets"][0]["text"] = "changed after retrieval"
    assert any("freeze_hash does not match" in error for error in validate_report(report))


def test_rejects_killer_without_negative_evidence_or_valid_bibliography_status(valid_report):
    report = deepcopy(valid_report)
    report["top_killers"][0]["does_not_cover"] = []
    report["top_killers"][0]["bibliography_status"] = "INVALID"
    assert any("is not one of" in error for error in validate_report(report))

    report = deepcopy(valid_report)
    report["top_killers"][0]["does_not_cover"] = []
    assert any("at least one does_not_cover" in error for error in validate_report(report))


def test_rejects_tier1_hard_coverage(valid_report):
    report = deepcopy(valid_report)
    report["evidence"][0]["source_level"] = "TIER_1_METADATA"
    assert any("not Tier-2" in error or "not evidence-bound" in error for error in validate_report(report))


def test_rejects_evidence_retrieved_after_verdict(valid_report):
    report = deepcopy(valid_report)
    report["evidence"][0]["retrieved_at"] = "2030-01-01T00:00:00Z"
    assert any("decided before evidence E1" in error for error in validate_report(report))


def test_rejects_query_before_claim_freeze(valid_report):
    report = deepcopy(valid_report)
    report["search"]["query_runs"][0]["retrieved_at"] = "2025-01-01T00:00:00Z"
    assert any("ran before the claim map was frozen" in error for error in validate_report(report))


def test_rejects_freeze_timestamp_after_first_retrieval(valid_report):
    report = deepcopy(valid_report)
    report["claim_map"]["frozen_at"] = "2026-08-27T07:11:00Z"
    assert any("before the claim map was frozen" in error for error in validate_report(report))


def test_recomputes_criticality_sensitivity(valid_report):
    missing = deepcopy(valid_report)
    missing["criticality_sensitivity"] = []
    errors = validate_report(missing)
    assert any("exactly one result per critical facet" in error for error in errors)
    assert any("deterministic leave-one-facet-out" in error for error in errors)

    fabricated = deepcopy(valid_report)
    fabricated["criticality_sensitivity"][0]["alternative_size"] = 3
    assert any("deterministic leave-one-facet-out" in error for error in validate_report(fabricated))


def test_recomputes_bibliography_status(valid_report):
    report = deepcopy(valid_report)
    report["top_killers"][0]["bibliography_status"] = "IN_BIBLIOGRAPHY"
    assert any("disagrees with normalized author bibliography" in error for error in validate_report(report))


def test_unavailable_status_required_when_bibliography_missing(valid_report):
    report = deepcopy(valid_report)
    report["author_bibliography"].update({"status": "NOT_PROVIDED", "entries": [], "normalized_paper_ids": []})
    assert any("disagrees with normalized author bibliography" in error for error in validate_report(report))


def test_normalized_bibliography_set_is_recomputed_from_entries(valid_report):
    report = deepcopy(valid_report)
    report["author_bibliography"]["normalized_paper_ids"] = ["A"]
    assert any("disagrees with bibliography entries" in error for error in validate_report(report))


def test_rejects_unknown_ancestor_source_and_cross_paper_evidence(valid_report):
    report = deepcopy(valid_report)
    report["ancestor_terms"] = [{"term": "memory state", "source_paper_id": "MISSING", "first_observed": "2020-01-01", "evidence_ids": ["E1"]}]
    errors = validate_report(report)
    assert any("unknown source paper MISSING" in error for error in errors)
    assert any("evidence comes from a different paper" in error for error in errors)


def test_rejects_invalid_evidence_datetime(valid_report):
    report = deepcopy(valid_report)
    report["evidence"][0]["retrieved_at"] = "banana"
    assert any("must be an ISO 8601 date-time" in error for error in validate_report(report))


def test_broad_coverage_is_recomputed_and_rejects_truncation(valid_report):
    report = deepcopy(valid_report)
    report["search"]["query_runs"][0]["truncated"] = True
    report["search"]["query_runs"][0]["total_count"] = 100
    errors = validate_report(report)
    assert any("coverage_derivation does not match" in error for error in errors)
    assert any("Search Protocol Coverage must equal deterministic" in error for error in errors)


def test_search_run_requires_provider_metadata(valid_report):
    report = deepcopy(valid_report)
    report["search"]["query_runs"][0].pop("total_count")
    assert any("'total_count' is a required property" in error for error in validate_report(report))


def test_direct_precedent_must_appear_in_top_killers(valid_report):
    report = deepcopy(valid_report)
    report["evidence"].append({"id": "E6", "canonical_paper_id": "A", "source_level": "TIER_2_FULLTEXT", "acquisition_id": "FT:A:fixture", "span": "Selection responds to compression.", "location": "Method 3.2", "source": "https://example.org/a", "retrieved_at": "2026-08-27T07:33:00Z", "evidence_kind": "METHOD", "supports": ["F2"]})
    report["papers"][0]["coverage"]["F2"] = {"status": "EXACT", "evidence_ids": ["E6"]}
    report["minimal_prior_sets"] = [{"paper_ids": ["A"], "size": 1, "covered_facets": ["F1", "F2"], "coverage_by_paper": {"A": ["F1", "F2"]}, "evidence_ids": ["E1", "E6"]}]
    report["criticality_sensitivity"] = [
        {"removed_facet": "F1", "baseline_size": 1, "alternative_size": 1, "alternative_classification": "DIRECT_PRECEDENT"},
        {"removed_facet": "F2", "baseline_size": 1, "alternative_size": 1, "alternative_classification": "DIRECT_PRECEDENT"},
    ]
    report["verdict"].update({"classification": "DIRECT_PRECEDENT", "evidence_ids": ["E1", "E6"]})
    report["top_killers"] = []
    report["bridges"] = []
    assert any("recomputed one-paper precedent in top_killers" in error for error in validate_report(report))


def test_rejects_tier2_evidence_without_matching_acquisition(valid_report):
    report = deepcopy(valid_report)
    report["evidence"][0]["acquisition_id"] = "FT:MISSING"
    assert any("lacks a recorded full-text acquisition" in error for error in validate_report(report))

    report = deepcopy(valid_report)
    report["fulltext_acquisitions"][0]["paper_id"] = "B"
    assert any("from another paper" in error for error in validate_report(report))


def test_rejects_paper_outside_candidate_snapshot(valid_report):
    report = deepcopy(valid_report)
    report["candidate_ids"].remove("C")
    assert any("paper C does not exist in candidate_ids" in error for error in validate_report(report))


def test_rejects_post_cutoff_evidence_in_verdict(valid_report):
    report = deepcopy(valid_report)
    report["candidate_ids"].append("D")
    report["papers"].append({
        "id": "D", "title": "Late paper", "providers": ["openalex"],
        "dates": [{"value": "2026-01-01", "source": "publisher_online"}],
        "earliest_public_date": "2026-01-01", "cutoff_status": "POST_CUTOFF",
        "found_by_query_ids": ["Q-literal"], "coverage": {},
    })
    report["excluded"]["post_cutoff"].append("D")
    report["evidence"].append({
        "id": "ED", "canonical_paper_id": "D", "source_level": "TIER_1_METADATA",
        "span": "Late claim", "location": "Abstract", "source": "https://example.org/d",
        "retrieved_at": "2026-08-27T07:40:00Z", "evidence_kind": "ABSTRACT",
    })
    report["verdict"]["evidence_ids"].append("ED")
    assert any("comes from a non-eligible paper" in error for error in validate_report(report))


def test_high_residual_risk_requires_structured_basis(valid_report):
    report = deepcopy(valid_report)
    report["verdict"].update({"classification": "RESIDUAL_NOVELTY", "novelty_risk": "HIGH", "evidence_ids": []})
    report["minimal_prior_sets"] = []
    report["bridges"] = []
    assert any("requires an explicit risk_basis" in error for error in validate_report(report))


def test_rejects_unverified_doi_and_arxiv_id(valid_report):
    report = deepcopy(valid_report)
    report["papers"][0]["doi"] = "10.9999/not-verified"
    report["papers"][0]["arxiv_id"] = "2401.01234"
    errors = validate_report(report)
    assert any("DOI was not independently validated" in error for error in errors)
    assert any("arXiv ID was not independently validated" in error for error in errors)


def test_rejects_provider_failure_hidden_behind_broad_coverage(valid_report):
    report = deepcopy(valid_report)
    report["search"]["failures"] = [{"provider": "openalex", "type": "RATE_LIMIT", "detail": "HTTP 429"}]
    errors = validate_report(report)
    assert any("not linked to a failed or truncated SearchRun" in error for error in errors)


def test_fragmented_precedent_requires_recomputed_mps(valid_report):
    report = deepcopy(valid_report)
    report["verdict"]["classification"] = "FRAGMENTED_PRECEDENT"
    report["minimal_prior_sets"] = []
    report["bridges"] = []
    report["top_killers"] = []
    for paper in report["papers"]:
        paper["coverage"] = {}
    errors = validate_report(report)
    assert any("FRAGMENTED_PRECEDENT requires a recomputed" in error for error in errors)


def test_cannot_omit_deterministic_graph_bridge_and_downgrade(valid_report):
    report = deepcopy(valid_report)
    report["verdict"].update({"classification": "FRAGMENTED_PRECEDENT", "novelty_risk": "MEDIUM"})
    report["bridges"] = []
    errors = validate_report(report)
    assert any("omits a deterministic graph bridge" in error for error in errors)
    assert any("hides a qualifying deterministic graph bridge" in error for error in errors)


def test_multi_paper_mps_requires_complete_graph_expansion_and_exact_gap(valid_report):
    report = deepcopy(valid_report)
    report["search"].pop("graph_expansions")
    errors = validate_report(report)
    assert any("graph expansion obligation incomplete" in error for error in errors)
    assert any("forces INCONCLUSIVE" in error for error in errors)
    assert any("GRAPH_EXPANSION_INCOMPLETE:A:B" in error for error in errors)

    report["verdict"].update({"classification": "INCONCLUSIVE", "novelty_risk": "INCONCLUSIVE"})
    report["search"]["gaps"].append("GRAPH_EXPANSION_INCOMPLETE:A:B")
    errors = validate_report(report)
    assert errors == []


def test_partial_graph_expansion_cannot_support_a_conclusive_verdict(valid_report):
    report = deepcopy(valid_report)
    expansion = report["search"]["graph_expansions"][0]
    expansion["status"] = "PARTIAL"
    expansion["partial_reasons"] = ["PROVIDER_FAILURE"]
    expansion["failures"] = [{"direction": "FORWARD", "anchor_paper_id": "A", "detail": "rate limited"}]
    report["search"]["gaps"].append("GRAPH_EXPANSION_INCOMPLETE:A:B")
    errors = validate_report(report)
    assert any("graph expansion obligation incomplete" in error for error in errors)
    assert any("forces INCONCLUSIVE" in error for error in errors)


def test_three_paper_mps_requires_every_endpoint_pair():
    mps = [{"paper_ids": ["C", "A", "B"], "size": 3}]
    expansions = [{"paper_ids": ["B", "A"], "status": "COMPLETE"}]
    required, incomplete = graph_expansion_obligations(mps, expansions)
    assert required == {("A", "B"), ("A", "C"), ("B", "C")}
    assert incomplete == {("A", "C"), ("B", "C")}
    assert graph_expansion_gap_marker(("A", "C")) == "GRAPH_EXPANSION_INCOMPLETE:A:C"


def test_broad_rejects_incomplete_obligation_and_unsaturated_flag(valid_report):
    report = deepcopy(valid_report)
    report["search"]["obligations"][0]["status"] = "INCOMPLETE"
    report["search"]["saturated"] = False
    errors = validate_report(report)
    assert any("coverage_derivation does not match" in error for error in errors)
    assert any("Search Protocol Coverage must equal deterministic" in error for error in errors)


def test_historical_search_requires_an_unfiltered_temporal_recall_backstop(valid_report):
    report = deepcopy(valid_report)
    for run in report["search"]["query_runs"]:
        run["temporal_recall_backstop"] = False
        run["provider_cutoff_applied"] = True
    assert any("unfiltered temporal recall backstop" in error for error in validate_report(report))


def test_temporal_backstop_cannot_claim_provider_cutoff_was_applied(valid_report):
    report = deepcopy(valid_report)
    backstop = next(run for run in report["search"]["query_runs"] if run["temporal_recall_backstop"])
    backstop["provider_cutoff_applied"] = True
    errors = validate_report(report)
    assert any("temporal recall backstop cannot apply" in error for error in errors)
    assert any("unfiltered temporal recall backstop" in error for error in errors)


def test_historical_graph_expansion_requires_local_temporal_backstop(valid_report):
    report = deepcopy(valid_report)
    expansion = report["search"]["graph_expansions"][0]
    expansion["temporal_recall_backstop"] = False
    expansion["provider_cutoff_applied"] = True
    errors = validate_report(report)
    assert any("must not apply a provider-side cutoff" in error for error in errors)
    assert any("must use an unfiltered temporal recall backstop" in error for error in errors)


def test_arxiv_filtered_page_cannot_fake_no_new_results_saturation(valid_report):
    report = deepcopy(valid_report)
    run = next(run for run in report["search"]["query_runs"] if run["provider"] == "arxiv")
    page = run["pagination"]["pages"][0]
    page.update({"returned_count": 0, "total_count": 1000, "truncated": True})
    page["pagination"].update({
        "raw_returned_count": 100, "eligible_returned_count": 0, "next": 100,
    })
    run.update({"total_count": 1000, "saturation_stop_reason": "NO_NEW_RESULTS"})
    run["pagination"]["stop_reason"] = "NO_NEW_RESULTS"
    errors = validate_report(report)
    assert any("filtered raw page cannot establish NO_NEW_RESULTS" in error for error in errors)


def test_arxiv_raw_page_history_rejects_nonadvancing_offsets():
    run = {
        "query_id": "Q:arxiv", "saturation_stop_reason": "PAGE_BUDGET_EXHAUSTED",
        "pagination": {"pages": [
            {"returned_count": 0, "pagination": {"start": 0, "raw_returned_count": 100, "eligible_returned_count": 0, "next": 0}},
        ]},
    }
    assert any("invalid next raw offset" in error for error in validate_arxiv_page_history(run))


def test_limit_exhausted_graph_expansion_cannot_claim_complete(valid_report):
    report = deepcopy(valid_report)
    expansion = report["search"]["graph_expansions"][0]
    expansion["partial_reasons"] = ["LIMIT_REACHED"]
    expansion["calls"][0].update({
        "returned_count": 100,
        "exhausted": False,
        "next_token": "next-page",
        "possibly_truncated": True,
    })
    errors = validate_report(report)
    assert any("COMPLETE graph expansion" in error and "incomplete work" in error for error in errors)


def test_graph_exhaustion_metadata_cannot_contradict_itself(valid_report):
    report = deepcopy(valid_report)
    call = report["search"]["graph_expansions"][0]["calls"][0]
    call["next_token"] = "unexpected-next"
    call["provider_total"] = 10
    call["raw_examined_count"] = 0
    errors = validate_report(report)
    assert any("exhausted calls cannot retain" in error for error in errors)
    assert any("must account for the provider total" in error for error in errors)

    call.update({
        "exhausted": False,
        "possibly_truncated": True,
        "next_token": None,
        "provider_total": None,
        "raw_examined_count": None,
    })
    errors = validate_report(report)
    assert any("need a continuation token or a full result budget" in error for error in errors)


def test_schema_rejects_duplicate_candidates_wrong_boolean_and_missing_bibliography_source(valid_report):
    report = deepcopy(valid_report)
    report["candidate_ids"].append("A")
    report["input"]["strict_date"] = "yes"
    report["author_bibliography"].pop("source")
    errors = validate_report(report)
    assert any("has non-unique elements" in error for error in errors)
    assert any("is not of type 'boolean'" in error for error in errors)
    assert any("'source' is a required property" in error for error in errors)


def test_title_author_bibliography_mapping_is_independently_reproduced(valid_report):
    report = deepcopy(valid_report)
    report["author_bibliography"]["entries"][0]["raw_entry"] = "Marine biology field methods (2023)"
    assert any("TITLE_AUTHOR match is not independently reproduced" in error for error in validate_report(report))


def test_graph_expansion_is_an_auditable_discovery_route(valid_report):
    report = deepcopy(valid_report)
    expansion_id = "EXPAND-GRAPH:openalex:A:B"
    report["papers"][2]["found_by_query_ids"].append(expansion_id)
    report["search"]["graph_expansions"] = [{
        "expansion_id": expansion_id,
        "status": "COMPLETE",
        "partial_reasons": [],
        "provider": "openalex",
        "paper_ids": ["A", "B"],
        "cutoff": "2025-09-18",
        "temporal_recall_backstop": True,
        "provider_cutoff_applied": False,
        "limit_per_call": 100,
        "anchor_selection": "CITATION_COUNT_INCOMPLETE_EXPAND_BOTH",
        "calls": [
            {"direction": "BACKWARD", "anchor_paper_id": "A", "returned_count": 0, "limit": 100, "exhausted": True, "next_token": None, "provider_total": None, "raw_examined_count": None, "possibly_truncated": False},
            {"direction": "BACKWARD", "anchor_paper_id": "B", "returned_count": 0, "limit": 100, "exhausted": True, "next_token": None, "provider_total": None, "raw_examined_count": None, "possibly_truncated": False},
            {"direction": "FORWARD", "anchor_paper_id": "A", "returned_count": 1, "limit": 100, "exhausted": True, "next_token": None, "provider_total": None, "raw_examined_count": None, "possibly_truncated": False},
            {"direction": "FORWARD", "anchor_paper_id": "B", "returned_count": 1, "limit": 100, "exhausted": True, "next_token": None, "provider_total": None, "raw_examined_count": None, "possibly_truncated": False},
        ],
        "failures": [],
        "bridge_candidate_ids": ["C"],
        "historical_bridge_candidate_ids": ["C"],
        "landscape_bridge_candidate_ids": [],
        "endpoint_reference_observations": [
            {"paper_id": "A", "provider_returned_count": 0, "status": "EMPTY_AT_PROVIDER"},
            {"paper_id": "B", "provider_returned_count": 0, "status": "EMPTY_AT_PROVIDER"},
        ],
        "observation_window_days": 900,
        "negative_result_scope": "HISTORICAL_CANDIDATE_PRESENT",
        "discovered_paper_ids": ["C"],
        "new_paper_ids": [],
    }]
    report["run_manifest"]["candidate_snapshot_hash"] = candidate_snapshot_hash(report["papers"])
    assert validate_report(report) == []

    report["search"].pop("graph_expansions")
    assert any("unknown discovery query IDs" in error for error in validate_report(report))


def test_graph_negative_diagnostics_are_recomputed(valid_report):
    report = deepcopy(valid_report)
    expansion = report["search"]["graph_expansions"][0]
    expansion["observation_window_days"] = 1
    expansion["endpoint_reference_observations"][0]["status"] = "NONEMPTY"
    expansion["historical_bridge_candidate_ids"] = []
    expansion["landscape_bridge_candidate_ids"] = ["C"]
    expansion["negative_result_scope"] = "NO_HISTORICAL_CANDIDATE_WITHIN_COMPLETE_EXPANSION"
    errors = validate_report(report)
    assert any("observation_window_days is inconsistent" in error for error in errors)
    assert any("reference observation for A disagrees" in error for error in errors)
    assert any("historical/landscape candidate routing is inconsistent" in error for error in errors)
    assert any("negative_result_scope is inconsistent" in error for error in errors)
