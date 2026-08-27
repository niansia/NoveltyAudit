"""Deterministically derive Search Coverage from auditable SearchRun records."""

from __future__ import annotations

from typing import Any


REQUIRED_FAMILIES = {"literal", "mechanism", "problem_function", "ancestor", "composition_bridge"}
PRIMARY_PROVIDERS = {"openalex", "semantic-scholar", "arxiv"}


def derive_search_coverage(search: dict[str, Any]) -> dict[str, Any]:
    runs = [run for run in search.get("query_runs") or [] if isinstance(run, dict)]
    successful = [run for run in runs if run.get("status") == "ok"]
    def canonical_provider(value: Any) -> str:
        return str(value).replace("semantic_scholar", "semantic-scholar")
    providers = {canonical_provider(run.get("provider")) for run in successful if run.get("provider")}
    unsupported = sorted(providers - PRIMARY_PROVIDERS)
    providers &= PRIMARY_PROVIDERS
    families = {str(run.get("family")) for run in successful if run.get("family")}
    failed_runs = [str(run.get("query_id")) for run in runs if run.get("status") != "ok"]
    incomplete = [
        str(item.get("id")) for item in search.get("obligations") or []
        if isinstance(item, dict) and item.get("status") != "COMPLETE"
    ]
    metadata_missing = []
    for run in runs:
        required = {"returned_count", "total_count", "truncated", "pagination", "corpus", "saturation_stop_reason"}
        if not required <= set(run) or not isinstance(run.get("returned_count"), int) or not isinstance(run.get("truncated"), bool) or not isinstance(run.get("pagination"), dict):
            metadata_missing.append(str(run.get("query_id") or "<unknown>"))
    truncated = [str(run.get("query_id")) for run in runs if run.get("truncated") is True]
    unsaturated_runs = [
        str(run.get("query_id")) for run in successful
        if run.get("saturation_stop_reason") not in {"PROVIDER_EXHAUSTED", "NO_NEW_RESULTS"}
    ]
    non_all_openalex = [
        str(run.get("query_id")) for run in successful
        if run.get("provider") == "openalex" and run.get("corpus") != "all"
    ]
    reasons = []
    if len(providers) < 2:
        reasons.append("fewer than two providers completed a query")
    if unsupported:
        reasons.append(f"unsupported primary search providers: {unsupported}")
    missing_families = sorted(REQUIRED_FAMILIES - families)
    if missing_families:
        reasons.append(f"missing successful query families: {missing_families}")
    if failed_runs:
        reasons.append(f"failed query runs: {failed_runs}")
    if truncated:
        reasons.append(f"truncated query runs: {truncated}")
    if unsaturated_runs:
        reasons.append(f"query runs lack a saturation stop: {unsaturated_runs}")
    if incomplete:
        reasons.append(f"incomplete search obligations: {incomplete}")
    if metadata_missing:
        reasons.append(f"SearchRun metadata missing: {metadata_missing}")
    if non_all_openalex:
        reasons.append(f"OpenAlex did not search corpus=all: {non_all_openalex}")
    if search.get("saturated") is not True:
        reasons.append("search saturation was not established")
    broad = not reasons and bool(runs)
    if broad:
        level = "BROAD"
    elif len(providers) >= 2 and len(families) >= 3 and not metadata_missing:
        level = "MODERATE"
    else:
        level = "NARROW"
    return {
        "level": level,
        "successful_providers": sorted(providers),
        "successful_families": sorted(families),
        "reasons": reasons,
    }
