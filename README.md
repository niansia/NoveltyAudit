<p align="center">
  <img src="novelty-audit/assets/logo.svg" alt="NoveltyAudit" width="760">
</p>

<p align="center">
  <strong>No single paper kills your novelty? Maybe three do.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img alt="Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <a href="https://github.com/agentskills/agentskills"><img alt="Agent Skills" src="https://img.shields.io/badge/Agent%20Skills-compatible-7C3AED"></a>
  <a href="README.zh-TW.md"><img alt="繁體中文" src="https://img.shields.io/badge/README-繁體中文-0F766E"></a>
</p>

NoveltyAudit is an evidence-first Agent Skill for adversarial scholarly novelty checks. It asks a harder question than “Which paper is most similar?”:

> What is the smallest historically connected set of prior papers that can collectively cover the critical parts of this claim?

It then shows what the set covers, what it does not cover, why the papers were historically combinable, whether they existed before the cutoff, and what novelty still survives.

## Why it is different

| Common novelty workflow | NoveltyAudit |
|---|---|
| Ranks individually similar papers | Solves a **Minimal Prior Set** of 1–3 papers |
| Treats any combination as an attack | Requires **Bridge Evidence** before a strong composition verdict |
| Filters by publication year | Resolves the **earliest verified public date** and isolates uncertain records |
| Emits one confidence or novelty score | Separates **Novelty Risk**, **Search Coverage**, and **Evidence Confidence** |
| “No results” becomes “probably novel” | Reports remaining gaps and allows **INCONCLUSIVE** |

The adjacent ecosystem is real and active. OpenNovelty provides a strong evidence-grounded single-paper comparison pipeline; paper-search-pro provides broad multi-source discovery; idea-novelty-auditor provides reviewer-style positioning; and novelty-assessment provides iterative harsh-critic search. NoveltyAudit deliberately focuses on composition-aware, time-safe, evidence-bound prosecution. See the dated [landscape review](docs/landscape.md).

## What ships today

- A concise, cross-agent `SKILL.md` reasoning contract with progressive references.
- OpenAlex, Semantic Scholar, arXiv, and Crossref adapters with a provider-neutral record shape.
- Canonical DOI/arXiv/title normalization and preprint-to-publisher deduplication.
- Earliest-public-date resolution with strict `ELIGIBLE`, `POST_CUTOFF`, and `DATE_UNCERTAIN` states.
- Evidence-bound Minimal Prior Set enumeration for sets of one to three papers.
- Deterministic direct-citation and co-citation bridge discovery, with explicit textual promotion gates.
- Criticality leave-one-out sensitivity analysis.
- Report invariant validation and standalone Markdown, JSON, and HTML export.
- Versioned run manifests and snapshot diffing that separate candidate changes from verdict changes.
- Auditable SearchRun records whose provider counts, pagination, corpus and truncation deterministically derive Search Coverage.
- JSON Schemas, adversarial tests, a golden composition fixture, and a reviewer-grounded benchmark annotation schema.

No paid LLM API is required. Your host agent performs claim decomposition and evidence interpretation; the bundled Python scripts handle deterministic work.

## Install

Download or clone this repository, then copy the actual skill folder from the checkout to a directory your agent discovers:

```bash
mkdir -p ~/.codex/skills
cp -r ./novelty-audit ~/.codex/skills/novelty-audit
```

Claude Code users can copy it to `~/.claude/skills/novelty-audit`; cross-agent installations commonly use `~/.agents/skills/novelty-audit`. The folder must remain named `novelty-audit` to satisfy the Agent Skills specification.

## Use

Ask naturally:

```text
Use $novelty-audit on this claim:
“We are the first to combine adaptive memory with compression-aware selection
for long-video vision-language reasoning.”

Cutoff: 2025-09-18.
Be adversarial. Return the top five killer candidates, a Minimal Prior Set of
at most three papers, strict date filtering, residual novelty, and Markdown + JSON.
```

The host agent will use the skill workflow. Deterministic helpers can also be run directly:

```bash
python novelty-audit/scripts/cli.py search \
  --provider openalex \
  --query "adaptive memory compression aware selection" \
  --before 2025-09-18 \
  --output run/openalex.json

python novelty-audit/scripts/cli.py dates \
  --input run/openalex.json \
  --cutoff 2025-09-18 \
  --output run/dated.json

python novelty-audit/scripts/cli.py bridge \
  --papers run/dated.json --paper-a W123 --paper-b W456 \
  --cutoff 2025-09-18 --output run/bridges.json

python novelty-audit/scripts/cli.py verify-citations \
  --input run/report.json --output run/report.verified.json
python novelty-audit/scripts/cli.py validate --input run/report.verified.json
python novelty-audit/scripts/cli.py export \
  --input run/report.verified.json --format html --output run/report.html
```

Provider keys are optional for basic use. `S2_API_KEY` reduces Semantic Scholar throttling. A free `OPENALEX_API_KEY` raises the OpenAlex daily API budget from the anonymous trial allowance to $1/day. `mailto` is not used because OpenAlex retired the polite-pool system in 2026. OpenAlex searches explicitly use `corpus=all`; a core-only run cannot claim `BROAD` coverage. Provider counts, truncation and outages lower Search Coverage deterministically rather than silently becoming evidence of novelty.

## Verdicts

- `DIRECT_PRECEDENT`: one eligible paper covers every critical facet with evidence.
- `STRONG_COMPOSITION_RISK`: 2–3 eligible papers cover the claim and textual bridge evidence supports the combination.
- `PLAUSIBLE_COMPOSITION_RISK`: the set covers the claim, but only graph-level bridge evidence is verified.
- `FRAGMENTED_PRECEDENT`: components are individually known, but no meaningful historical bridge is verified.
- `RESIDUAL_NOVELTY`: at least one critical mechanism or interaction remains uncovered.
- `INCONCLUSIVE`: search coverage, dates, full text, or evidence are insufficient.

These are bounded audit classifications, not legal opinions or guarantees of originality.

NoveltyAudit performs scholarly-literature reconnaissance only. It does not provide patentability, non-obviousness, freedom-to-operate, or any other legal opinion.

## CLI exit codes

- `0`: complete;
- `10`: partial completion after a backend failure;
- `20`: no searchable claim could be extracted;
- `30`: all configured scholarly providers failed;
- `40`: evidence or report validation failed;
- `50`: configuration or credential error.

## Test

```bash
python -m pytest novelty-audit/tests -q
skills-ref validate ./novelty-audit
```

Live smoke tests may encounter provider rate limits; those failures are expected to be explicit. All core algorithms and adversarial invariants run offline.

## Roadmap that needs public data, not synthetic theater

The deterministic core is implemented. The next growth asset is a licensed set of reviewer-grounded cases: overlooked killer papers, genuine composition concerns, ancestor-term recoveries, temporal traps, and false-positive defenses. This repository intentionally does not fabricate 20 “real” demos or redistribute third-party review data under the wrong license. See [benchmark policy](novelty-audit/benchmark/README.md).

The release gates are separated into user-trust requirements, benchmark evidence, and adoption evidence in [user-facing release acceptance](docs/release-acceptance.md).

## Contributing

High-value contributions are public reviewer-grounded cases, provider adapters, date golden tests, bridge-evidence edge cases, and report-faithfulness failures. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

Release archives must be built from tracked Git content; see [release packaging](docs/releasing.md). The repository is installed as an Agent Skill, not as a Python import package.

If NoveltyAudit finds a paper your reviewer could have found first, star the repo.
