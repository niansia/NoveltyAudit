from graph_expansion import expand_graph
import json
from types import SimpleNamespace

import cli


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


def test_expansion_actively_fetches_graph_and_merges_bridge_source():
    provider = FakeGraphProvider()
    result = expand_graph(
        [paper("A", "W-A", 10), paper("B", "W-B", 100)],
        "A", "B", provider, before="2025-01-01", limit=25,
    )
    assert provider.reference_calls == [("W-A", "2025-01-01", 25), ("W-B", "2025-01-01", 25)]
    assert provider.citation_calls == [("W-A", "2025-01-01", 25)]
    assert result["anchor_selection"] == "LOWER_CITATION_COUNT"
    assert result["bridge_candidate_ids"] == ["C"]
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
