#!/usr/bin/env python3
"""Command-line interface for deterministic NoveltyAudit helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from composition import criticality_sensitivity, solve_mps
from deduplicate import deduplicate
from export_report import export
from normalize_paper import normalize_many
from providers import PROVIDERS
from resolve_dates import apply_cutoff_many
from validate_output import validate_report


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
    provider_class = PROVIDERS[args.provider]
    provider = provider_class()
    result = provider.search(args.query, before=args.before, limit=args.limit)
    write_json(args.output, {"provider": provider.name, "query": args.query, "before": args.before, "papers": result})
    return 0


def command_normalize(args: argparse.Namespace) -> int:
    write_json(args.output, normalize_many(records(read_json(args.input)), provider=args.provider))
    return 0


def command_dedupe(args: argparse.Namespace) -> int:
    write_json(args.output, deduplicate(records(read_json(args.input))))
    return 0


def command_dates(args: argparse.Namespace) -> int:
    write_json(args.output, apply_cutoff_many(records(read_json(args.input)), args.cutoff, strict=not args.non_strict))
    return 0


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
        return 1
    print("NoveltyAudit report invariants: OK")
    return 0


def command_export(args: argparse.Namespace) -> int:
    export(read_json(args.input), args.output, args.format)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="NoveltyAudit deterministic helpers")
    sub = root.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="search one scholarly provider")
    search.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--before")
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--output", required=True)
    search.set_defaults(func=command_search)

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
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
