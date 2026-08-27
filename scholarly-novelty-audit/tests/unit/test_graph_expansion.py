import json
from types import SimpleNamespace

import cli
from graph_expansion import expand_graph
from providers.base import GraphResult


def paper(identifier, provider_id, citation_count, *, references=None, date="2024-01-01"):
    return {
        "id": identifier,
        "title": f"Paper {identifier}",
        "providers": ["openalex"],
        "provider_ids": {"openalex": provider_id},
        "citation_count": citation_count,
        "references": references or [],
        "dates": [{"value": date, "source": "publication", "verified": True}],
        "found_by_query_ids": ["Q"],
        "coverage": {},
    }


class FakeGraphProvider:
    name = "openalex"

    def __init__(self):
        self.reference_calls = []
        self.citation_calls = []

    def references(self, paper_id, *, before=None, limit=100):
        self.reference_calls.append((paper_id, before, limit))
        suffix = paper_id.rsplit("-", 1)[-1]
        return [paper(f"R{suffix}", f"W-R{suffix}", 1)]

    def citations(self, paper_id, *, before=None, limit=100):
        self.citation_calls.append((paper_id, before, limit))
        return [
            paper("C", "W-C", 3, references=["W-A", "W-B"]),
            paper("X", "W-X", 3, references=[paper_id]),
        ]

    def references_with_metadata(self, paper_id, *, before=None, limit=100):
        papers = self.references(paper_id, before=before, limit=limit)
        exhausted = len(papers) < limit
        return GraphResult(papers=papers, exhausted=exhausted, next_token=None if exhausted else "more")

    def citations_with_metadata(self, paper_id, *, before=None, limit=100):
        papers = self.citations(paper_id, before=before, limit=limit)
        exhausted = len(papers) < limit
        return GraphResult(papers=papers, exhausted=exhausted, next_token=None if exhausted else "more")


def test_expansion_actively_fetches_graph_and_merges_bridge_source():
    provider = FakeGraphProvider()
    result = expand_graph(
        [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "A", "B", provider, before="2025-01-01", limit=25,
    )
    assert provider.reference_calls == [("W-A", None, 25), ("W-B", None, 25)]
    assert provider.citation_calls == [("W-A", None, 25)]
    assert result["anchor_selection"] == "LOWER_CITATION_COUNT"
    assert result["temporal_recall_backstop"] is True
    assert result["provider_cutoff_applied"] is False
    assert result["status"] == "COMPLETE"
    assert result["partial_reasons"] == []
    assert result["bridge_candidate_ids"] == ["C"]
    assert result["historical_bridge_candidate_ids"] == ["C"]
    assert result["landscape_bridge_candidate_ids"] == []
    assert result["observation_window_days"] == 366
    assert result["negative_result_scope"] == "HISTORICAL_CANDIDATE_PRESENT"
    assert result["endpoint_reference_observations"] == [
        {"paper_id": "A", "provider_returned_count": 1, "status": "NONEMPTY"},
        {"paper_id": "B", "provider_returned_count": 1, "status": "NONEMPTY"},
    ]
    assert set(result["new_paper_ids"]) == {"RA", "RB", "C"}
    assert "X" not in {item["id"] for item in result["papers"]}
    source = next(item for item in result["papers"] if item["id"] == "C")
    assert source["cutoff_status"] == "ELIGIBLE"
    assert "EXPAND-GRAPH:openalex:A:B" in source["found_by_query_ids"]


def test_missing_citation_count_expands_both_forward_directions():
    provider = FakeGraphProvider()
    result = expand_graph(
        [paper("A", "W-A", None), paper("B", "W-B", 100)],
        "A", "B", provider, limit=10,
    )
    assert result["anchor_selection"] == "CITATION_COUNT_INCOMPLETE_EXPAND_BOTH"
    assert [call[0] for call in provider.citation_calls] == ["W-A", "W-B"]


def test_graph_backstop_retains_post_cutoff_candidate_for_landscape_review():
    provider = FakeGraphProvider()
    provider.citations = lambda paper_id, before=None, limit=100: [
        paper("L", "W-L", 3, references=["W-A", "W-B"], date="2026-01-01")
    ]
    result = expand_graph(
        [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "A", "B", provider, before="2025-01-01", limit=25,
    )
    landscape_source = next(item for item in result["papers"] if item["id"] == "L")
    assert landscape_source["cutoff_status"] == "POST_CUTOFF"
    assert result["bridge_candidate_ids"] == ["L"]
    assert result["historical_bridge_candidate_ids"] == []
    assert result["landscape_bridge_candidate_ids"] == ["L"]
    assert result["negative_result_scope"] == "NO_HISTORICAL_CANDIDATE_WITHIN_COMPLETE_EXPANSION"


def test_full_call_budget_is_partial_even_without_provider_failure():
    provider = FakeGraphProvider()
    result = expand_graph(
        [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "A", "B", provider, limit=2,
    )
    assert result["status"] == "PARTIAL"
    assert result["partial_reasons"] == ["LIMIT_REACHED"]
    assert result["negative_result_scope"] == "NO_HISTORICAL_CUTOFF"
    forward_call = next(call for call in result["calls"] if call["direction"] == "FORWARD")
    assert forward_call == {
        "direction": "FORWARD", "anchor_paper_id": "A", "returned_count": 2,
        "limit": 2, "exhausted": False, "next_token": "more",
        "provider_total": None, "raw_examined_count": None,
        "possibly_truncated": True,
    }


def test_explicit_provider_exhaustion_avoids_false_partial_at_exact_limit():
    class ExactProvider(FakeGraphProvider):
        def references_with_metadata(self, paper_id, *, before=None, limit=100):
            papers = [paper(f"R{index}", f"W-R{index}", 1) for index in range(limit)]
            return GraphResult(
                papers=papers, exhausted=True, provider_total=limit,
                raw_examined_count=limit,
            )

        def citations_with_metadata(self, paper_id, *, before=None, limit=100):
            papers = [paper("C", "W-C", 3, references=["W-A", "W-B"])]
            papers.extend(paper(f"X{index}", f"W-X{index}", 3) for index in range(1, limit))
            return GraphResult(
                papers=papers, exhausted=True, provider_total=limit,
                raw_examined_count=limit,
            )

    result = expand_graph(
        [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "A", "B", ExactProvider(), before="2025-01-01", limit=2,
    )
    assert result["status"] == "COMPLETE"
    assert result["partial_reasons"] == []
    assert all(call["returned_count"] == 2 for call in result["calls"])
    assert all(call["exhausted"] is True for call in result["calls"])
    assert all(call["possibly_truncated"] is False for call in result["calls"])


def test_legacy_list_only_graph_provider_fails_closed_without_exhaustion_metadata():
    class LegacyProvider:
        name = "openalex"

        def references(self, paper_id, *, before=None, limit=100):
            return []

        def citations(self, paper_id, *, before=None, limit=100):
            return []

    result = expand_graph(
        [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "A", "B", LegacyProvider(), before="2025-01-01", limit=25,
    )
    assert result["status"] == "PARTIAL"
    assert result["partial_reasons"] == ["LIMIT_REACHED"]
    assert all(call["exhausted"] is False for call in result["calls"])
    assert all(call["next_token"] == "UNREPORTED" for call in result["calls"])


def test_empty_provider_references_caveat_negative_graph_result():
    provider = FakeGraphProvider()
    provider.references = lambda paper_id, before=None, limit=100: []
    provider.citations = lambda paper_id, before=None, limit=100: []
    result = expand_graph(
        [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "A", "B", provider, before="2025-01-01", limit=25,
    )
    assert result["status"] == "COMPLETE"
    assert result["bridge_candidate_ids"] == []
    assert result["negative_result_scope"] == "NO_HISTORICAL_CANDIDATE_PROVIDER_COVERAGE_LIMITED"
    assert {item["status"] for item in result["endpoint_reference_observations"]} == {"EMPTY_AT_PROVIDER"}


def test_missing_or_post_cutoff_endpoint_dates_make_negative_scope_explicit():
    provider = FakeGraphProvider()
    provider.references = lambda paper_id, before=None, limit=100: []
    provider.citations = lambda paper_id, before=None, limit=100: []
    missing = expand_graph(
        [paper("A", "W-A", 10, date=None), paper("B", "W-B", 100)],
        "A", "B", provider, before="2025-01-01", limit=25,
    )
    assert missing["observation_window_days"] is None
    assert missing["negative_result_scope"] == "NO_HISTORICAL_CANDIDATE_ENDPOINT_DATE_UNRESOLVED"

    post_cutoff = expand_graph(
        [paper("A", "W-A", 10, date="2025-02-01"), paper("B", "W-B", 100)],
        "A", "B", provider, before="2025-01-01", limit=25,
    )
    assert post_cutoff["observation_window_days"] == -31
    assert post_cutoff["negative_result_scope"] == "NO_HISTORICAL_CANDIDATE_POST_CUTOFF_ENDPOINT"


def test_cli_preserves_candidate_payload_and_appends_expansion_log(tmp_path, monkeypatch):
    source = tmp_path / "candidates.json"
    output = tmp_path / "expanded.json"
    source.write_text(json.dumps({
        "candidate_ids": ["A", "B"],
        "papers": [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "search": {"query_runs": []},
    }), encoding="utf-8")
    monkeypatch.setitem(cli.SEARCH_PROVIDERS, "openalex", FakeGraphProvider)
    code = cli.command_expand_graph(SimpleNamespace(
        papers=str(source), paper_a="A", paper_b="B", provider="openalex",
        cutoff="2025-01-01", limit=25, output=str(output),
    ))
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert set(payload["candidate_ids"]) == {"A", "B", "RA", "RB", "C"}
    assert payload["search"]["graph_expansions"][0]["bridge_candidate_ids"] == ["C"]


def test_cli_records_limit_exhaustion_as_partial_gap(tmp_path, monkeypatch):
    source = tmp_path / "candidates.json"
    output = tmp_path / "expanded.json"
    source.write_text(json.dumps({
        "candidate_ids": ["A", "B"],
        "papers": [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "search": {"query_runs": [], "gaps": []},
    }), encoding="utf-8")
    monkeypatch.setitem(cli.SEARCH_PROVIDERS, "openalex", FakeGraphProvider)
    code = cli.command_expand_graph(SimpleNamespace(
        papers=str(source), paper_a="A", paper_b="B", provider="openalex",
        cutoff="2025-01-01", limit=2, output=str(output),
    ))
    payload = json.loads(output.read_text(encoding="utf-8"))
    expansion = payload["search"]["graph_expansions"][0]
    assert code == cli.EXIT_PARTIAL
    assert expansion["status"] == "PARTIAL"
    assert expansion["partial_reasons"] == ["LIMIT_REACHED"]
    assert payload["search"]["gaps"] == ["GRAPH_EXPANSION_INCOMPLETE:A:B"]
