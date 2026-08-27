import importlib.util
from pathlib import Path

from providers.base import ProviderError


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
