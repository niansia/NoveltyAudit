from composition import classify, criticality_sensitivity, solve_mps


def paper(identifier, coverage, status="ELIGIBLE"):
    return {"id": identifier, "cutoff_status": status, "earliest_public_date": "2024-01-01", "coverage": coverage}


def test_finds_all_minimum_two_paper_sets():
    papers = [
        paper("A", {"F1": {"status": "EXACT", "evidence_ids": ["E1"]}}),
        paper("B", {"F2": {"status": "FUNCTIONAL", "evidence_ids": ["E2"]}}),
        paper("C", {"F2": {"status": "EXACT", "evidence_ids": ["E3"]}}),
    ]
    result = solve_mps(papers, ["F1", "F2"])
    assert {tuple(item["paper_ids"]) for item in result} == {("A", "B"), ("A", "C")}


def test_ignores_tier1_and_post_cutoff():
    papers = [
        paper("A", {"F1": "LIKELY"}),
        paper("B", {"F1": {"status": "EXACT", "evidence_ids": ["E"]}}, "POST_CUTOFF"),
    ]
    assert solve_mps(papers, ["F1"]) == []


def test_direct_precedent_and_sensitivity():
    papers = [
        paper("A", {"F1": {"status": "EXACT", "evidence_ids": ["E1"]}, "F2": {"status": "EXACT", "evidence_ids": ["E2"]}})
    ]
    mps = solve_mps(papers, ["F1", "F2"])
    assert classify(mps, []) == "DIRECT_PRECEDENT"
    assert all(item["alternative_size"] == 1 for item in criticality_sensitivity(papers, ["F1", "F2"]))


def test_bridge_controls_composition_verdict():
    mps = [{"paper_ids": ["A", "B"], "size": 2}]
    assert classify(mps, []) == "FRAGMENTED_PRECEDENT"
    assert classify(mps, [{"type": "CO_CITATION", "paper_ids": ["A", "B"], "graph_verified": True, "cutoff_status": "ELIGIBLE", "base_rate_status": "PASSED"}]) == "PLAUSIBLE_COMPOSITION_RISK"
    assert classify(mps, [{"type": "COMBINATION_BRIDGE", "paper_ids": ["A", "B"], "text_verified": True, "evidence_ids": ["E"]}]) == "STRONG_COMPOSITION_RISK"
    assert classify(mps, [{"type": "COMBINATION_BRIDGE", "paper_ids": ["A", "B"], "text_verified": False, "evidence_ids": []}]) == "FRAGMENTED_PRECEDENT"


def test_three_paper_set_requires_connected_bridges():
    mps = [{"paper_ids": ["A", "B", "C"], "size": 3}]
    one_edge = [{"type": "COMBINATION_BRIDGE", "paper_ids": ["A", "B"], "text_verified": True, "evidence_ids": ["E1"]}]
    connected = one_edge + [{"type": "EXPLICIT_EXTENSION", "paper_ids": ["B", "C"], "text_verified": True, "evidence_ids": ["E2"]}]
    assert classify(mps, one_edge) == "FRAGMENTED_PRECEDENT"
    assert classify(mps, connected) == "STRONG_COMPOSITION_RISK"


def test_rejects_sets_larger_than_three():
    import pytest

    with pytest.raises(ValueError):
        solve_mps([], ["F1"], max_size=4)


def test_same_size_sets_rank_textual_bridge_first():
    papers = [
        paper("A", {"F1": {"status": "EXACT", "evidence_ids": ["E1"]}}),
        paper("B", {"F2": {"status": "EXACT", "evidence_ids": ["E2"]}}),
        paper("C", {"F2": {"status": "EXACT", "evidence_ids": ["E3"]}}),
    ]
    bridges = [{"type": "TAXONOMY_BRIDGE", "paper_ids": ["A", "C"], "text_verified": True, "evidence_ids": ["EB"]}]
    result = solve_mps(papers, ["F1", "F2"], bridges=bridges)
    assert result[0]["paper_ids"] == ["A", "C"]
