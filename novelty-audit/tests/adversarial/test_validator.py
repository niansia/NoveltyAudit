from copy import deepcopy

from validate_output import validate_report


def test_valid_fixture_passes(valid_report):
    assert validate_report(valid_report) == []


def test_rejects_missing_nested_schema_fields(valid_report):
    report = deepcopy(valid_report)
    report["search"].pop("providers")
    report["excluded"].pop("other")
    errors = validate_report(report)
    assert any("search missing required field: providers" in error for error in errors)
    assert any("excluded missing required field: other" in error for error in errors)


def test_rejects_paper_missing_machine_contract_fields(valid_report):
    report = deepcopy(valid_report)
    report["papers"][0].pop("title")
    report["papers"][0].pop("providers")
    errors = validate_report(report)
    assert any("missing required field: title" in error for error in errors)
    assert any("missing required field: providers" in error for error in errors)


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
    report["bridges"] = [{"type": "CO_CITATION", "paper_ids": ["A", "B"], "cutoff_status": "ELIGIBLE", "text_verified": False}]
    assert any("requires an eligible textual bridge" in error for error in validate_report(report))


def test_rejects_unrelated_textual_bridge_as_strong(valid_report):
    report = deepcopy(valid_report)
    report["bridges"][0]["paper_ids"] = ["A", "C"]
    assert any("requires an eligible textual bridge" in error for error in validate_report(report))


def test_rejects_bridge_without_source_paper(valid_report):
    report = deepcopy(valid_report)
    report["bridges"][0].pop("source_paper_id")
    assert any("lacks source_paper_id" in error for error in validate_report(report))


def test_textual_bridge_source_must_be_rechecked_as_candidate(valid_report):
    report = deepcopy(valid_report)
    report["bridges"][0]["source_rechecked_as_candidate"] = False
    assert any("was not rechecked" in error for error in validate_report(report))


def test_rejects_fabricated_co_citation(valid_report):
    report = deepcopy(valid_report)
    report["verdict"]["classification"] = "PLAUSIBLE_COMPOSITION_RISK"
    report["bridges"] = [{"type": "CO_CITATION", "paper_ids": ["A", "B"], "source_paper_id": "C", "cutoff_status": "ELIGIBLE", "graph_verified": True, "text_verified": False}]
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
    report["evidence"].append({"id": "E6", "paper_id": "A", "span": "Selection is conditioned on compression.", "location": "Method 3.2", "source": "https://example.org/a", "retrieved_at": "2026-08-27T07:30:00Z", "evidence_kind": "METHOD", "supports": ["F2"]})
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


def test_broad_requires_known_structured_providers_and_query_logs(valid_report):
    report = deepcopy(valid_report)
    report["search"]["providers"] = ["fake-one", "fake-two"]
    report["search"]["query_runs"] = []
    errors = validate_report(report)
    assert any("structured provider records" in error for error in errors)
    assert any("successful query logs from two providers" in error for error in errors)


def test_result_evidence_allowed_for_outcome_facet(valid_report):
    report = deepcopy(valid_report)
    report["claim_map"]["facets"][1]["type"] = "outcome"
    report["evidence"][1]["evidence_kind"] = "RESULT"
    assert validate_report(report) == []
