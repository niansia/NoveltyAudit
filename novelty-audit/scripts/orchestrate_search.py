"""Execute a canonical query plan across providers with explicit degradation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from deduplicate import deduplicate
from providers import SEARCH_PROVIDERS
from providers.base import ProviderError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def classify_provider_error(error: Exception) -> str:
    message = str(error)
    if "HTTP 429" in message:
        return "RATE_LIMIT"
    if any(value in message for value in ("HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")):
        return "HTTP_5XX"
    if "Timeout" in message or "URLError" in message:
        return "TIMEOUT"
    if "JSONDecodeError" in message or "ParseError" in message:
        return "MALFORMED_RESPONSE"
    if "HTTP 401" in message or "HTTP 403" in message:
        return "AUTH"
    return "OTHER"


def run_search_plan(plan: dict[str, Any], provider_registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = provider_registry or SEARCH_PROVIDERS
    provider_names = list(plan.get("providers") or [])
    queries = list(plan.get("queries") or [])
    cutoff = plan.get("cutoff")
    limit = plan.get("limit")
    if not provider_names or not queries:
        raise ValueError("search plan requires providers and queries")
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        raise ValueError("search plan limit must be an explicit integer between 1 and 100")
    required_query_fields = {"query_id", "family", "query", "reason", "target_facets", "removed_author_terms"}
    if any(not isinstance(query, dict) or not required_query_fields <= set(query) for query in queries):
        raise ValueError("every planned query requires query_id, family, query, reason, target_facets, and removed_author_terms")

    papers = []
    query_runs = []
    failures = []
    provider_states = []
    successful_calls = 0
    attempted_calls = 0
    for provider_name in provider_names:
        if provider_name not in registry:
            raise ValueError(f"unknown or non-search provider: {provider_name}")
        provider = registry[provider_name]()
        provider_success = 0
        provider_failures = 0
        for query in queries:
            attempted_calls += 1
            run_query_id = f"{query['query_id']}:{provider_name}"
            retrieved_at = _now()
            try:
                results = provider.search(str(query["query"]), before=cutoff, limit=limit)
                successful_calls += 1
                provider_success += 1
                for paper in results:
                    record = dict(paper)
                    record["found_by_query_ids"] = list(dict.fromkeys((record.get("found_by_query_ids") or []) + [run_query_id]))
                    papers.append(record)
                query_runs.append({
                    **query, "query_id": run_query_id, "logical_query_id": str(query["query_id"]),
                    "provider": provider_name, "retrieved_at": retrieved_at,
                    "result_count": len(results), "truncated": len(results) >= limit, "status": "ok",
                })
                if len(results) >= limit:
                    failures.append({"provider": provider_name, "type": "TRUNCATED", "detail": f"{run_query_id} reached the explicit candidate limit"})
            except ProviderError as error:
                provider_failures += 1
                failure_type = classify_provider_error(error)
                query_runs.append({
                    **query, "query_id": run_query_id, "logical_query_id": str(query["query_id"]),
                    "provider": provider_name, "retrieved_at": retrieved_at,
                    "result_count": 0, "truncated": False, "status": "failed", "error_code": failure_type,
                })
                failures.append({"provider": provider_name, "type": failure_type, "detail": str(error)})
        provider_states.append({
            "name": provider_name,
            "status": "ok" if provider_failures == 0 else "partial" if provider_success else "failed",
            "successful_queries": provider_success, "failed_queries": provider_failures,
        })

    canonical = deduplicate(papers)
    if successful_calls == 0:
        status, error_code, suggested_coverage = "FAILED", "ALL_PROVIDERS_FAILED", "NARROW"
    elif successful_calls < attempted_calls or failures:
        status, error_code, suggested_coverage = "PARTIAL", "BACKEND_DEGRADED", "MODERATE"
    else:
        status, error_code, suggested_coverage = "COMPLETE", None, "BROAD"
    return {
        "status": status, "error_code": error_code, "cutoff": cutoff,
        "candidate_ids": [str(paper.get("id")) for paper in canonical], "papers": canonical,
        "search": {
            "providers": provider_states,
            "query_families": sorted({str(query.get("family")) for query in queries}),
            "query_runs": query_runs, "failures": failures,
            "gaps": ["One or more provider queries failed or were truncated."] if status != "COMPLETE" else [],
            "suggested_coverage": suggested_coverage,
        },
    }
