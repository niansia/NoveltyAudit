#!/usr/bin/env python3
"""Command-line interface for deterministic NoveltyAudit helpers."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Any

from composition import criticality_sensitivity, solve_mps
from citation_graph import find_bridges
from deduplicate import deduplicate
from export_report import export
from graph_expansion import expand_graph
from normalize_paper import normalize_many
from orchestrate_search import run_search_plan
from providers import SEARCH_PROVIDERS
from providers.base import ProviderError
from resolve_dates import apply_cutoff_many
from snapshot_diff import diff_reports
from validate_output import validate_report
from verify_citations import verify_records


EXIT_COMPLETE = 0
EXIT_PARTIAL = 10
EXIT_NO_SEARCHABLE_CLAIM = 20
EXIT_ALL_PROVIDERS_FAILED = 30
EXIT_EVIDENCE_VALIDATION_FAILED = 40
EXIT_CONFIG_ERROR = 50


def read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    for key in ("papers", "results", "records"):
        if isinstance(value, dict) and isinstance(value.get(key), list):
            return value[key]
    raise ValueError("input must be an array or an object containing papers/results/records")


def command_search(args: argparse.Namespace) -> int:
    provider_class = SEARCH_PROVIDERS[args.provider]
    provider = provider_class()
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        result = provider.search_with_metadata(args.query, before=args.before, limit=args.limit)
    except ProviderError as error:
        message = str(error)
        if "HTTP 429" in message:
            error_code = "RATE_LIMIT"
        elif any(value in message for value in ("HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")):
            error_code = "HTTP_5XX"
        elif "Timeout" in message or "URLError" in message:
            error_code = "TIMEOUT"
        elif "JSONDecodeError" in message:
            error_code = "MALFORMED_RESPONSE"
        else:
            error_code = "PROVIDER_UNAVAILABLE"
        write_json(args.output, {
            "status": "FAILED", "error_code": error_code, "provider": provider.name,
            "family": args.family, "query": args.query, "retrieved_at": retrieved_at,
            "before": args.before, "returned_count": 0, "total_count": None,
            "truncated": False, "pagination": {}, "corpus": getattr(provider, "corpus", "not_applicable"),
            "papers": [], "error": message,
        })
        return EXIT_ALL_PROVIDERS_FAILED
    status = "PARTIAL" if result.truncated else "COMPLETE"
    write_json(args.output, {
        "status": status, "error_code": "TRUNCATED" if result.truncated else None,
        "provider": provider.name, "family": args.family, "query": args.query,
        "retrieved_at": retrieved_at,
        "before": args.before, **result.audit_fields(), "papers": result.papers,
    })
    return EXIT_PARTIAL if result.truncated else EXIT_COMPLETE


def command_search_plan(args: argparse.Namespace) -> int:
    result = run_search_plan(read_json(args.input))
    write_json(args.output, result)
    if result["status"] == "FAILED":
        return EXIT_ALL_PROVIDERS_FAILED
    if result["status"] == "PARTIAL":
        return EXIT_PARTIAL
    return EXIT_COMPLETE


def command_normalize(args: argparse.Namespace) -> int:
    write_json(args.output, normalize_many(records(read_json(args.input)), provider=args.provider))
    return 0


def command_dedupe(args: argparse.Namespace) -> int:
    write_json(args.output, deduplicate(records(read_json(args.input))))
    return 0


def command_dates(args: argparse.Namespace) -> int:
    write_json(args.output, apply_cutoff_many(records(read_json(args.input)), args.cutoff, strict=not args.non_strict))
    return 0


def command_verify_citations(args: argparse.Namespace) -> int:
    payload = read_json(args.input)
    verified, status = verify_records(records(payload))
    if isinstance(payload, dict) and isinstance(payload.get("papers"), list):
        payload = dict(payload)
        payload["papers"] = verified
        payload["citation_validation_status"] = status
    else:
        payload = {"status": status, "papers": verified}
    write_json(args.output, payload)
    if status == "PARTIAL":
        return EXIT_PARTIAL
    if status == "FAILED":
        return EXIT_EVIDENCE_VALIDATION_FAILED
    return EXIT_COMPLETE


def command_snapshot_diff(args: argparse.Namespace) -> int:
    write_json(args.output, diff_reports(read_json(args.before), read_json(args.after)))
    return EXIT_COMPLETE


def command_bridge(args: argparse.Namespace) -> int:
    papers = records(read_json(args.papers))
    discovered = find_bridges(
        args.paper_a, args.paper_b, papers, cutoff=args.cutoff,
        high_citation_threshold=args.high_citation_threshold,
    )
    graph_bridges = [item for item in discovered if item.get("type") != "LANDSCAPE_BRIDGE"]
    landscape_bridges = [item for item in discovered if item.get("type") == "LANDSCAPE_BRIDGE"]
    write_json(args.output, {
        "paper_ids": [args.paper_a, args.paper_b],
        "cutoff": args.cutoff,
        "graph_bridges": graph_bridges,
        "landscape_bridges": landscape_bridges,
        "textual_bridge_required": any(item.get("base_rate_status") != "HIGH_BASE_RATE" for item in graph_bridges),
    })
    return EXIT_COMPLETE


def command_expand_graph(args: argparse.Namespace) -> int:
    payload = read_json(args.papers)
    papers = records(payload)
    index = {str(paper.get("id")): paper for paper in papers}
    endpoints = [index.get(args.paper_a), index.get(args.paper_b)]
    if any(paper is None for paper in endpoints):
        raise ValueError("paper-a and paper-b must exist as canonical IDs in the papers file")
    provider_names = [args.provider] if args.provider else ["openalex", "semantic-scholar"]
    selected = None
    for name in provider_names:
        if all(
            (paper.get("provider_ids") or {}).get(name)
            or (name in set(paper.get("providers") or []) and paper.get("id"))
            for paper in endpoints
        ):
            selected = name
            break
    if not selected:
        raise ValueError("no common OpenAlex or Semantic Scholar IDs exist for both endpoints; pass --provider after enriching provider_ids")
    result = expand_graph(
        papers, args.paper_a, args.paper_b, SEARCH_PROVIDERS[selected](),
        before=args.cutoff, limit=args.limit,
    )
    if isinstance(payload, dict):
        output = dict(payload)
        output["papers"] = result["papers"]
        if isinstance(output.get("candidate_ids"), list):
            output["candidate_ids"] = [str(paper.get("id")) for paper in result["papers"]]
        search = dict(output.get("search") or {})
        expansion_record = {key: value for key, value in result.items() if key != "papers"}
        search["graph_expansions"] = list(search.get("graph_expansions") or []) + [expansion_record]
        output["search"] = search
        output["graph_expansion_status"] = result["status"]
        write_json(args.output, output)
    else:
        write_json(args.output, result)
    return EXIT_PARTIAL if result["status"] == "PARTIAL" else EXIT_COMPLETE


def command_mps(args: argparse.Namespace) -> int:
    payload = read_json(args.input)
    papers = records(payload)
    if args.facets:
        facets = [value.strip() for value in args.facets.split(",") if value.strip()]
    else:
        facets = [str(item["id"]) for item in payload.get("claim_map", {}).get("facets", []) if item.get("critical") or item.get("structural_critical") is True]
    result = {
        "critical_facets": facets,
        "minimal_prior_sets": solve_mps(papers, facets, max_size=args.max_size, strict=not args.non_strict, bridges=payload.get("bridges") if isinstance(payload, dict) else None),
        "criticality_sensitivity": criticality_sensitivity(papers, facets, max_size=args.max_size, strict=not args.non_strict),
    }
    write_json(args.output, result)
    return 0


def command_validate(args: argparse.Namespace) -> int:
    errors = validate_report(read_json(args.input))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_EVIDENCE_VALIDATION_FAILED
    print("Schema: OK")
    print("Invariants: OK")
    print("NoveltyAudit report: VALID")
    return 0


def command_export(args: argparse.Namespace) -> int:
    export(read_json(args.input), args.output, args.format)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="NoveltyAudit deterministic scholarly-literature reconnaissance helpers",
        epilog="Not patentability, non-obviousness, freedom-to-operate, or legal advice. Exit codes: 0 complete, 10 partial, 20 no searchable claim, 30 all providers failed, 40 evidence validation failed, 50 config or credential error.",
    )
    sub = root.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="search one scholarly provider")
    search.add_argument("--provider", choices=sorted(SEARCH_PROVIDERS), required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--family", default="unspecified")
    search.add_argument("--before")
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--output", required=True)
    search.set_defaults(func=command_search)

    search_plan = sub.add_parser("search-plan", help="run canonical queries across providers with fallback")
    search_plan.add_argument("--input", required=True)
    search_plan.add_argument("--output", required=True)
    search_plan.set_defaults(func=command_search_plan)

    normalize = sub.add_parser("normalize", help="normalize scholarly records")
    normalize.add_argument("--input", required=True)
    normalize.add_argument("--output", required=True)
    normalize.add_argument("--provider")
    normalize.set_defaults(func=command_normalize)

    dedupe_parser = sub.add_parser("dedupe", help="merge duplicate versions")
    dedupe_parser.add_argument("--input", required=True)
    dedupe_parser.add_argument("--output", required=True)
    dedupe_parser.set_defaults(func=command_dedupe)

    dates = sub.add_parser("dates", help="resolve dates and apply cutoff")
    dates.add_argument("--input", required=True)
    dates.add_argument("--output", required=True)
    dates.add_argument("--cutoff", required=True)
    dates.add_argument("--non-strict", action="store_true")
    dates.set_defaults(func=command_dates)

    citations = sub.add_parser("verify-citations", help="resolve DOI and arXiv IDs independently")
    citations.add_argument("--input", required=True)
    citations.add_argument("--output", required=True)
    citations.set_defaults(func=command_verify_citations)

    snapshot = sub.add_parser("snapshot-diff", help="separate literature changes from verdict changes")
    snapshot.add_argument("--before", required=True)
    snapshot.add_argument("--after", required=True)
    snapshot.add_argument("--output", required=True)
    snapshot.set_defaults(func=command_snapshot_diff)

    bridge = sub.add_parser("bridge", help="discover deterministic citation-graph bridges")
    bridge.add_argument("--papers", required=True)
    bridge.add_argument("--paper-a", required=True)
    bridge.add_argument("--paper-b", required=True)
    bridge.add_argument("--cutoff")
    bridge.add_argument("--high-citation-threshold", type=int)
    bridge.add_argument("--output", required=True)
    bridge.set_defaults(func=command_bridge)

    expand_graph_parser = sub.add_parser("expand-graph", help="actively retrieve backward references and forward co-citation candidates")
    expand_graph_parser.add_argument("--papers", required=True)
    expand_graph_parser.add_argument("--paper-a", required=True)
    expand_graph_parser.add_argument("--paper-b", required=True)
    expand_graph_parser.add_argument("--provider", choices=["openalex", "semantic-scholar"])
    expand_graph_parser.add_argument("--cutoff")
    expand_graph_parser.add_argument("--limit", type=int, default=100)
    expand_graph_parser.add_argument("--output", required=True)
    expand_graph_parser.set_defaults(func=command_expand_graph)

    mps = sub.add_parser("mps", help="solve evidence-bound Minimal Prior Sets")
    mps.add_argument("--input", required=True)
    mps.add_argument("--output", required=True)
    mps.add_argument("--facets", help="comma-separated critical facet IDs")
    mps.add_argument("--max-size", type=int, choices=[1, 2, 3], default=3)
    mps.add_argument("--non-strict", action="store_true")
    mps.set_defaults(func=command_mps)

    validate = sub.add_parser("validate", help="validate report invariants")
    validate.add_argument("--input", required=True)
    validate.set_defaults(func=command_validate)

    export_parser = sub.add_parser("export", help="render a report")
    export_parser.add_argument("--input", required=True)
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument("--format", choices=["json", "markdown", "md", "html"], required=True)
    export_parser.set_defaults(func=command_export)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
