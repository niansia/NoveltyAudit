"""Render a structured audit report to Markdown or standalone HTML."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


NOVELTY_SCORE = re.compile(r"(?:novelty.{0,40}(?:\d+(?:\.\d{2})?\s*%|\b\d+\.\d{2}\b)|(?:\d+(?:\.\d{2})?\s*%|\b\d+\.\d{2}\b).{0,40}novelty)", re.I | re.S)
INTERNAL_FIELDS = {"embedding_score", "similarity_score", "ranking_feature", "bridge_rank", "internal_score"}


def validate_user_output(content: str, format_name: str) -> list[str]:
    """Reject fake novelty scores and internal ranking fields in user-facing output."""
    visible = content
    if format_name == "html":
        visible = re.sub(r"<style\b.*?</style>", " ", visible, flags=re.I | re.S)
        visible = re.sub(r"<[^>]+>", " ", visible)
        visible = html.unescape(visible)
    errors = []
    if NOVELTY_SCORE.search(visible):
        errors.append("user-facing output contains a novelty percentage or uncalibrated decimal score")
    lowered = visible.casefold()
    for field in INTERNAL_FIELDS:
        if field in lowered:
            errors.append(f"user-facing output exposes internal ranking field: {field}")
    return errors


def _failure_text(value: Any) -> str:
    if isinstance(value, dict):
        return f"{value.get('provider', 'unknown')}: {value.get('type', 'OTHER')} — {value.get('detail', 'no detail')}"
    return str(value)


def _rewrite_text(report: dict[str, Any]) -> str:
    value = report.get("defensible_rewrite")
    return str(value.get("text") or "") if isinstance(value, dict) else str(value or "")


def _md_inline(value: Any) -> str:
    text = re.sub(r"[\r\n]+", " ", str(value if value is not None else ""))
    text = html.escape(text, quote=False)
    text = re.sub(r"([\\`*_[\]{}()#+.!>])", r"\\\1", text)
    return text.replace("|", "\\|").strip()


def _md_join(items: list[Any]) -> str:
    return ", ".join(_md_inline(item) for item in items)


def _list(items: list[Any], empty: str = "None recorded") -> str:
    return "\n".join(f"- {_md_inline(item)}" for item in items) if items else f"- {_md_inline(empty)}"


def to_markdown(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    claim_map = report["claim_map"]
    papers = {str(paper["id"]): paper for paper in report.get("papers") or []}
    lines = [
        "# NoveltyAudit Report",
        "",
        f"**Novelty Risk:** {_md_inline(verdict['novelty_risk'])}  ",
        f"**Search Protocol Coverage:** {_md_inline(verdict['search_coverage'])}  ",
        "**Coverage scope:** Protocol execution only; this is not demonstrated recall of all relevant literature.  ",
        f"**Evidence Confidence:** {_md_inline(verdict['evidence_confidence'])}  ",
        f"**Classification:** {_md_inline(verdict['classification'])}",
        "",
        f"> {_md_inline(verdict.get('main_concern') or 'No main concern recorded.')}",
        "",
        "## Input",
        "",
        f"- Claim: {_md_inline(report['input'].get('claim', ''))}",
        f"- Normalized claim: {_md_inline(report['input'].get('normalized_claim', ''))}",
        f"- Field: {_md_inline(report['input'].get('field', 'unspecified'))}",
        f"- Cutoff: {_md_inline(report['input'].get('cutoff'))} ({'strict' if report['input'].get('strict_date', True) else 'non-strict'})",
        "",
        "## Frozen Claim Map",
        "",
        "| ID | Type | Facet | Critical |",
        "|---|---|---|---|",
    ]
    for facet in claim_map.get("facets") or []:
        critical = "yes" if facet.get("critical") or facet.get("structural_critical") is True else "no"
        lines.append(f"| {_md_inline(facet.get('id'))} | {_md_inline(facet.get('type', ''))} | {_md_inline(facet.get('text', ''))} | {critical} |")

    lines += ["", "## Top Killer Papers", ""]
    if not report.get("top_killers"):
        lines.append("No evidence-bound killer paper was found in this audit.")
    for rank, killer in enumerate(report.get("top_killers") or [], start=1):
        paper = papers.get(str(killer.get("paper_id")), {})
        observed_dates = paper.get("observed_dates") or paper.get("dates") or []
        date_sources = [f"{item.get('value')} ({item.get('source', 'unknown')})" if isinstance(item, dict) else str(item) for item in observed_dates]
        lines += [
            f"### {rank}. {_md_inline(paper.get('title', killer.get('paper_id')))}",
            "",
            f"- Date: {_md_inline(paper.get('earliest_public_date') or 'uncertain')} ({_md_inline(paper.get('cutoff_status', 'unknown'))})",
            f"- Observed date sources: {_md_join(date_sources) or 'none'}",
            f"- Supplied bibliography status: {_md_inline(killer.get('bibliography_status', 'BIBLIOGRAPHY_UNAVAILABLE'))}",
            f"- Covers: {_md_join(killer.get('covers') or []) or 'none verified'}",
            f"- Does not cover: {_md_join(killer.get('does_not_cover') or []) or 'none recorded'}",
            f"- Evidence: {_md_join(killer.get('evidence_ids') or []) or 'none'}",
            "",
        ]

    lines += ["## Minimal Prior Set", "", "**MPS search bound: K ≤ 3.**"]
    if report.get("minimal_prior_sets"):
        for mps in report["minimal_prior_sets"]:
            titles = [papers.get(str(value), {}).get("title", str(value)) for value in mps.get("paper_ids") or []]
            lines.append(f"- {' + '.join(_md_inline(title) for title in titles)} covers: {_md_join(mps.get('covered_facets') or [])}")
    else:
        lines.append("No qualifying evidence-bound prior set of size three or smaller was found. This is not evidence that no larger combination exists.")

    lines += ["", "## Bridge Evidence", ""]
    if report.get("bridges"):
        for bridge in report["bridges"]:
            lines.append(f"- {_md_inline(bridge.get('type'))}: papers {_md_join(bridge.get('paper_ids') or [])}; evidence {_md_join(bridge.get('evidence_ids') or []) or 'graph only'}")
    else:
        lines.append("No meaningful historical bridge was verified.")

    lines += ["", "## Present-day Landscape Bridges", ""]
    if report.get("landscape_bridges"):
        for bridge in report["landscape_bridges"]:
            lines.append(
                f"- {_md_inline(bridge.get('underlying_type'))}: papers {_md_join(bridge.get('paper_ids') or [])}; "
                f"source {_md_inline(bridge.get('source_paper_id'))} is {_md_inline(bridge.get('cutoff_status'))} and does not affect the historical verdict."
            )
    else:
        lines.append("No post-cutoff or date-uncertain bridge was recorded.")

    lines += [
        "", "## Residual Novelty", "", _md_inline(report.get("residual_novelty") or "Not established."),
        "", "## Defensible Claim Rewrite", "", _md_inline(_rewrite_text(report) or "No rewrite recorded."),
        "", "## Search Gaps", "", _list(report.get("search", {}).get("gaps") or []),
        "", "## Provider Failures", "", _list([_failure_text(value) for value in report.get("search", {}).get("failures") or []]),
        "", "## Exclusions", "",
        f"- Post-cutoff: {_md_join(report.get('excluded', {}).get('post_cutoff') or []) or 'none'}",
        f"- Date-uncertain: {_md_join(report.get('excluded', {}).get('date_uncertain') or []) or 'none'}",
        "", "## Reproducibility", "",
        f"- Audit ID: {_md_inline(report.get('audit_id', 'not recorded'))}",
        f"- Generated at: {_md_inline(report.get('generated_at', 'not recorded'))}",
        f"- Schema: {_md_inline(report.get('schema_version'))}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def to_html(report: dict[str, Any]) -> str:
    def e(value: Any) -> str:
        return html.escape(str(value if value is not None else ""))

    def chips(values: list[Any], empty: str = "none") -> str:
        return "".join(f"<span class=\"chip\">{e(value)}</span>" for value in values) or f"<span class=\"muted\">{e(empty)}</span>"

    verdict = report["verdict"]
    papers = {str(paper["id"]): paper for paper in report.get("papers") or []}
    facets = "".join(
        f"<tr><td>{e(facet.get('id'))}</td><td>{e(facet.get('type'))}</td><td>{e(facet.get('text'))}</td><td>{'yes' if facet.get('critical') or facet.get('structural_critical') is True else 'no'}</td></tr>"
        for facet in report.get("claim_map", {}).get("facets") or []
    )
    killers = []
    for rank, killer in enumerate(report.get("top_killers") or [], start=1):
        paper = papers.get(str(killer.get("paper_id")), {})
        observed_dates = paper.get("observed_dates") or paper.get("dates") or []
        date_sources = ", ".join(f"{item.get('value')} ({item.get('source', 'unknown')})" if isinstance(item, dict) else str(item) for item in observed_dates)
        killers.append(f"""<article class=\"card killer\"><div class=\"eyebrow\">Killer candidate {rank}</div><h3>{e(paper.get('title') or killer.get('paper_id'))}</h3><div class=\"meta\">{e(paper.get('earliest_public_date') or 'date uncertain')} · {e(paper.get('cutoff_status') or 'unknown')} · {e(killer.get('bibliography_status') or 'BIBLIOGRAPHY_UNAVAILABLE')}</div><p class=\"meta\">Observed date sources: {e(date_sources or 'none')}</p><h4>Covers</h4><div>{chips(killer.get('covers') or [], 'none verified')}</div><h4>Does not cover</h4><div>{chips(killer.get('does_not_cover') or [], 'none recorded')}</div><p class=\"evidence\">Evidence: {e(', '.join(killer.get('evidence_ids') or []) or 'none')}</p></article>""")
    if not killers:
        killers.append("<p class=\"muted\">No evidence-bound killer paper was found in this audit.</p>")

    mps_items = []
    for mps in report.get("minimal_prior_sets") or []:
        titles = [papers.get(str(value), {}).get("title", str(value)) for value in mps.get("paper_ids") or []]
        mps_items.append(f"<li><strong>{e(' + '.join(titles))}</strong><br><span class=\"muted\">Covers {e(', '.join(mps.get('covered_facets') or []))}</span></li>")
    if not mps_items:
        mps_items.append("<li>No qualifying evidence-bound prior set of size three or smaller was found. This is not evidence that no larger combination exists.</li>")

    bridge_items = []
    for bridge in report.get("bridges") or []:
        bridge_items.append(f"<li><strong>{e(bridge.get('type'))}</strong> · papers {e(', '.join(str(value) for value in bridge.get('paper_ids') or []))} · evidence {e(', '.join(bridge.get('evidence_ids') or []) or 'graph only')}</li>")
    if not bridge_items:
        bridge_items.append("<li>No meaningful historical bridge was verified.</li>")

    landscape_items = []
    for bridge in report.get("landscape_bridges") or []:
        landscape_items.append(
            f"<li><strong>{e(bridge.get('underlying_type'))}</strong> · papers {e(', '.join(str(value) for value in bridge.get('paper_ids') or []))} · source {e(bridge.get('source_paper_id'))} is {e(bridge.get('cutoff_status'))} and does not affect the historical verdict</li>"
        )
    if not landscape_items:
        landscape_items.append("<li>No post-cutoff or date-uncertain bridge was recorded.</li>")

    gaps = "".join(f"<li>{e(value)}</li>" for value in report.get("search", {}).get("gaps") or []) or "<li>None recorded</li>"
    failures = "".join(f"<li>{e(_failure_text(value))}</li>" for value in report.get("search", {}).get("failures") or []) or "<li>None recorded</li>"
    body = f"""
<header class=\"hero\">
  <div class=\"eyebrow\">Composition-aware scholarly novelty audit</div>
  <h1>NoveltyAudit Report</h1>
  <p class=\"claim\">{e(report['input'].get('claim'))}</p>
  <div class=\"axes\">
    <div><span>Novelty Risk</span><strong>{e(verdict.get('novelty_risk'))}</strong></div>
    <div><span>Search Protocol Coverage</span><strong>{e(verdict.get('search_coverage'))}</strong></div>
    <div><span>Evidence Confidence</span><strong>{e(verdict.get('evidence_confidence'))}</strong></div>
  </div>
  <div class=\"classification\">{e(verdict.get('classification'))}</div>
  <p class=\"concern\">{e(verdict.get('main_concern') or 'No main concern recorded.')}</p>
</header>
<main>
  <section><h2>Input and cutoff</h2><div class=\"card keyvals\"><div><span>Normalized claim</span>{e(report['input'].get('normalized_claim'))}</div><div><span>Field</span>{e(report['input'].get('field') or 'unspecified')}</div><div><span>Cutoff</span>{e(report['input'].get('cutoff'))} ({'strict' if report['input'].get('strict_date', True) else 'non-strict'})</div></div></section>
  <section><h2>Frozen Claim Map</h2><div class=\"table-wrap\"><table><thead><tr><th>ID</th><th>Type</th><th>Facet</th><th>Critical</th></tr></thead><tbody>{facets}</tbody></table></div></section>
  <section><h2>Top Killer Papers</h2><div class=\"grid\">{''.join(killers)}</div></section>
  <section><p class=\"muted\">Search Protocol Coverage describes bounded protocol execution, not demonstrated recall of all relevant literature.</p></section>
  <section class=\"split\"><div class=\"card\"><h2>Minimal Prior Set</h2><p><strong>MPS search bound: K ≤ 3.</strong></p><ul>{''.join(mps_items)}</ul></div><div class=\"card\"><h2>Bridge Evidence</h2><ul>{''.join(bridge_items)}</ul></div></section>
  <section><div class=\"card\"><h2>Present-day Landscape Bridges</h2><ul>{''.join(landscape_items)}</ul></div></section>
  <section class=\"split\"><div><h2>Residual Novelty</h2><p>{e(report.get('residual_novelty') or 'Not established.')}</p></div><div class=\"rewrite\"><h2>Defensible Claim Rewrite</h2><p>{e(_rewrite_text(report) or 'No rewrite recorded.')}</p></div></section>
  <section class=\"split\"><div><h2>Search Gaps</h2><ul>{gaps}</ul></div><div><h2>Provider Failures</h2><ul>{failures}</ul></div></section>
  <section><h2>Exclusions</h2><div class=\"card keyvals\"><div><span>Post-cutoff</span>{e(', '.join(str(value) for value in report.get('excluded', {}).get('post_cutoff') or []) or 'none')}</div><div><span>Date-uncertain</span>{e(', '.join(str(value) for value in report.get('excluded', {}).get('date_uncertain') or []) or 'none')}</div></div></section>
  <footer>Audit {e(report.get('audit_id') or 'not recorded')} · generated {e(report.get('generated_at') or 'not recorded')} · schema {e(report.get('schema_version'))}</footer>
</main>"""
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>NoveltyAudit Report</title><style>:root{{--ink:#111827;--muted:#6b7280;--violet:#6d28d9;--soft:#f5f3ff;--line:#e5e7eb}}*{{box-sizing:border-box}}body{{margin:0;background:#fafafa;color:var(--ink);font:16px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}}.hero{{padding:64px max(24px,calc((100vw - 1080px)/2));background:linear-gradient(135deg,#111827,#3b0764);color:white}}.eyebrow{{font-size:.78rem;letter-spacing:.12em;text-transform:uppercase;color:#c4b5fd;font-weight:700}}h1{{font-size:clamp(2.4rem,6vw,4.6rem);line-height:1;margin:.45rem 0 1rem}}h2{{font-size:1.45rem;margin:0 0 1rem}}h3{{font-size:1.2rem;margin:.3rem 0}}h4{{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;margin:1.2rem 0 .4rem;color:var(--muted)}}.claim{{max-width:780px;font-size:1.18rem;color:#e5e7eb}}.axes{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:32px 0 18px}}.axes div{{background:#ffffff12;border:1px solid #ffffff24;border-radius:14px;padding:15px}}.axes span,.keyvals span{{display:block;font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:#c4b5fd}}.axes strong{{display:block;font-size:1.3rem;margin-top:4px}}.classification{{display:inline-block;background:#a78bfa;color:#1f1147;border-radius:999px;padding:7px 13px;font-weight:800;font-size:.8rem}}.concern{{max-width:820px;margin:18px 0 0;padding-left:16px;border-left:3px solid #a78bfa}}main{{max-width:1080px;margin:auto;padding:48px 24px}}section{{margin-bottom:48px}}.card,.table-wrap,.rewrite{{background:white;border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:0 8px 30px #11182708}}.keyvals,.split,.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}.keyvals div{{font-weight:600}}.keyvals span{{color:var(--muted);margin-bottom:5px}}.grid{{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}.meta,.muted,.evidence,footer{{color:var(--muted)}}.chip{{display:inline-block;background:var(--soft);color:var(--violet);border-radius:999px;padding:5px 9px;margin:3px;font-size:.86rem;font-weight:700}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px;text-align:left;border-bottom:1px solid var(--line)}}th{{font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}ul{{padding-left:20px}}li{{margin:.55rem 0}}footer{{border-top:1px solid var(--line);padding:22px 0}}@media(max-width:720px){{.axes,.keyvals,.split{{grid-template-columns:1fr}}.hero{{padding-top:42px}}.table-wrap{{overflow-x:auto}}}}</style></head><body>{body}</body></html>"""


def export(report: dict[str, Any], output: str | Path, format_name: str) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    format_name = format_name.lower()
    if format_name == "json":
        content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    elif format_name in {"markdown", "md"}:
        content = to_markdown(report)
    elif format_name == "html":
        content = to_html(report)
    else:
        raise ValueError(f"unsupported format: {format_name}")
    if format_name in {"markdown", "md", "html"}:
        errors = validate_user_output(content, "html" if format_name == "html" else "markdown")
        if errors:
            raise ValueError("; ".join(errors))
    path.write_text(content, encoding="utf-8")
    return path
