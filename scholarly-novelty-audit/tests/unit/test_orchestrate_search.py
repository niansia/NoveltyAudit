import importlib.util
from pathlib import Path

from providers.base import ProviderError, SearchResult


path = Path(__file__).resolve().parents[2] / "scripts" / "orchestrate_search.py"
spec = importlib.util.spec_from_file_location("orchestrate_search", path)
orchestrate_search = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(orchestrate_search)


class GoodProvider:
    def search(self, query, *, before=None, limit=100):
        return [{"id": "A", "title": "A paper", "doi": "10.1000/a", "authors": ["A. Lee"], "year": 2024, "providers": ["good"], "dates": [{"value": "2024-01-01", "source": "publication"}]}]


class FailedProvider:
    def search(self, query, *, before=None, limit=100):
        raise ProviderError("request failed for https://example.test/works: HTTP 429")


class PagedProvider:
    corpus = "all"

    def search_with_metadata(self, query, *, before=None, limit=100, page_token=None):
        offset = int(page_token or 0)
        papers = [{"id": f"P{offset}", "title": f"Paper {offset}", "providers": ["paged"], "dates": []}]
        return SearchResult(papers=papers, total_count=2, pagination={"offset": offset, "limit": 1}, corpus="all")


class FilteredPagedProvider:
    corpus = "not_applicable"

    def __init__(self):
        self.tokens = []

    def search_with_metadata(self, query, *, before=None, limit=100, page_token=None):
        offset = int(page_token or 0)
        self.tokens.append(offset)
        papers = [] if offset < 200 else [{"id": "P200", "title": "Eligible", "providers": ["filtered"], "dates": []}]
        next_token = offset + 100 if offset < 200 else None
        return SearchResult(
            papers=papers,
            total_count=300,
            pagination={
                "start": offset,
                "raw_returned_count": 100,
                "eligible_returned_count": len(papers),
                "next": next_token,
            },
        )


class CutoffTrackingProvider:
    corpus = "not_applicable"

    def __init__(self):
        self.cutoffs = []

    def search_with_metadata(self, query, *, before=None, limit=100, page_token=None):
        self.cutoffs.append((query, before))
        return SearchResult(papers=[], total_count=0, pagination={"offset": 0, "limit": limit})


def plan():
    return {
        "providers": ["good", "failed"],
        "cutoff": "2025-01-01",
        "limit": 10,
        "queries": [{
            "query_id": "Q1", "family": "mechanism", "query": "adaptive state",
            "reason": "mechanism search", "target_facets": ["F1"], "removed_author_terms": True,
        }],
    }


def test_search_plan_returns_partial_with_machine_readable_failure():
    result = orchestrate_search.run_search_plan(plan(), {"good": GoodProvider, "failed": FailedProvider})
    assert result["status"] == "PARTIAL"
    assert result["error_code"] == "BACKEND_DEGRADED"
    assert result["search"]["failures"][0]["type"] == "RATE_LIMIT"
    assert result["papers"][0]["found_by_query_ids"] == ["Q1:good"]
    assert result["search"]["query_runs"][0]["canonical_paper_ids"] == ["A"]


def test_search_plan_all_failures_is_not_a_novelty_verdict():
    value = plan()
    value["providers"] = ["failed"]
    result = orchestrate_search.run_search_plan(value, {"failed": FailedProvider})
    assert result["status"] == "FAILED"
    assert result["error_code"] == "ALL_PROVIDERS_FAILED"
    assert result["search"]["coverage_derivation"]["level"] == "NARROW"


def test_search_plan_pages_until_provider_exhaustion():
    value = plan()
    value.update({"providers": ["paged"], "limit": 1, "max_pages": 3})
    result = orchestrate_search.run_search_plan(value, {"paged": PagedProvider})
    run = result["search"]["query_runs"][0]
    assert run["paper_ids"] == ["P0", "P1"]
    assert run["pagination"]["stop_reason"] == "PROVIDER_EXHAUSTED"
    assert run["truncated"] is False
    assert result["search"]["saturated"] is True


def test_locally_filtered_empty_pages_keep_advancing_raw_provider_offsets():
    provider = FilteredPagedProvider()
    value = plan()
    value.update({"providers": ["filtered"], "limit": 100, "max_pages": 3})
    result = orchestrate_search.run_search_plan(value, {"filtered": lambda: provider})
    run = result["search"]["query_runs"][0]
    assert provider.tokens == [0, 100, 200]
    assert run["paper_ids"] == ["P200"]
    assert run["saturation_stop_reason"] == "PROVIDER_EXHAUSTED"
    assert result["search"]["saturated"] is True


def test_one_query_family_is_a_temporal_recall_backstop():
    provider = CutoffTrackingProvider()
    value = plan()
    value["providers"] = ["tracked"]
    value["queries"].append({
        "query_id": "Q2", "family": "ancestor", "query": "older terminology",
        "reason": "temporal recall", "target_facets": ["F1"], "removed_author_terms": True,
    })
    result = orchestrate_search.run_search_plan(value, {"tracked": lambda: provider})
    assert provider.cutoffs == [("adaptive state", "2025-01-01"), ("older terminology", None)]
    runs = result["search"]["query_runs"]
    assert runs[0]["provider_cutoff_applied"] is True
    assert runs[0]["temporal_recall_backstop"] is False
    assert runs[1]["provider_cutoff_applied"] is False
    assert runs[1]["temporal_recall_backstop"] is True
