"""Explain whether two audit runs changed because candidates or reasoning changed."""

from __future__ import annotations

from typing import Any


PAPER_FIELDS = ("title", "doi", "arxiv_id", "providers", "dates", "references")
VERDICT_FIELDS = ("classification", "novelty_risk", "search_coverage", "evidence_confidence")


def diff_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_papers = {str(item.get("id")): item for item in before.get("papers") or []}
    after_papers = {str(item.get("id")): item for item in after.get("papers") or []}
    before_ids, after_ids = set(before_papers), set(after_papers)
    changed_papers = []
    for paper_id in sorted(before_ids & after_ids):
        changed = [field for field in PAPER_FIELDS if before_papers[paper_id].get(field) != after_papers[paper_id].get(field)]
        if changed:
            changed_papers.append({"paper_id": paper_id, "fields": changed})
    verdict_changes = {
        field: {"before": (before.get("verdict") or {}).get(field), "after": (after.get("verdict") or {}).get(field)}
        for field in VERDICT_FIELDS
        if (before.get("verdict") or {}).get(field) != (after.get("verdict") or {}).get(field)
    }
    before_queries = {str(item.get("query_id")) for item in (before.get("search") or {}).get("query_runs") or []}
    after_queries = {str(item.get("query_id")) for item in (after.get("search") or {}).get("query_runs") or []}
    literature_changed = bool(before_ids ^ after_ids or changed_papers)
    reasoning_changed = bool(verdict_changes)
    if literature_changed:
        cause = "LITERATURE_SNAPSHOT_CHANGE"
    elif reasoning_changed:
        cause = "MODEL_OR_REASONING_CHANGE"
    else:
        cause = "NO_MATERIAL_CHANGE"
    return {
        "status": "COMPLETE",
        "change_cause": cause,
        "candidate_added": sorted(after_ids - before_ids),
        "candidate_removed": sorted(before_ids - after_ids),
        "candidate_changed": changed_papers,
        "query_added": sorted(after_queries - before_queries),
        "query_removed": sorted(before_queries - after_queries),
        "verdict_changes": verdict_changes,
        "before_snapshot_hash": (before.get("run_manifest") or {}).get("candidate_snapshot_hash"),
        "after_snapshot_hash": (after.get("run_manifest") or {}).get("candidate_snapshot_hash"),
    }
