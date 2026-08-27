<p align="center">
  <img src="scholarly-novelty-audit/assets/logo.svg" alt="NoveltyAudit" width="760">
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
| Emits one confidence or novelty score | Separates **Novelty Risk**, **Search Protocol Coverage**, and **Evidence Confidence** |
| “No results” becomes “probably novel” | Reports remaining gaps and allows **INCONCLUSIVE** |

The adjacent ecosystem is real and active. OpenNovelty provides a strong evidence-grounded single-paper comparison pipeline; paper-search-pro provides broad multi-source discovery; idea-novelty-auditor provides reviewer-style positioning; and novelty-assessment provides iterative harsh-critic search. NoveltyAudit deliberately focuses on composition-aware, time-safe, evidence-bound prosecution. See the dated [landscape review](docs/landscape.md).

## What ships today

- A concise, cross-agent `SKILL.md` reasoning contract with progressive references.
- OpenAlex, Semantic Scholar, arXiv, and Crossref adapters with a provider-neutral record shape.
- Canonical DOI/arXiv/title normalization and preprint-to-publisher deduplication.
- Earliest-public-date resolution with strict `ELIGIBLE`, `POST_CUTOFF`, and `DATE_UNCERTAIN` states.
- Evidence-bound Minimal Prior Set enumeration for sets of one to three papers.
- Active backward/forward citation expansion followed by deterministic direct-citation and co-citation discovery, with a high-citation base-rate guard, explicit textual promotion gates, and separate post-cutoff landscape bridges.
- Public Tier-2 PDF/HTML/text acquisition with private-address blocking, response-size limits, extracted-text files, cryptographic hashes, and evidence-to-acquisition validation.
- Criticality leave-one-out sensitivity analysis.
- Report invariant validation and standalone Markdown, JSON, and HTML export.
- Versioned run manifests and snapshot diffing that separate candidate changes from verdict changes.
- Auditable multi-page SearchRun records whose provider counts, saturation stop reasons, corpus and truncation deterministically derive Search Protocol Coverage.
- JSON Schemas, adversarial tests, a golden composition fixture, and a reviewer-grounded benchmark annotation schema.

No paid LLM API is required. Your host agent performs claim decomposition and evidence interpretation; the bundled Python scripts handle deterministic work.

## Install

Download the `scholarly-novelty-audit-v0.3.1.zip` runtime asset from GitHub Releases and extract it, or clone this repository. Copy the actual skill folder to a directory your agent discovers:

```bash
mkdir -p ~/.codex/skills
cp -r ./scholarly-novelty-audit ~/.codex/skills/scholarly-novelty-audit
python -m pip install -r ~/.codex/skills/scholarly-novelty-audit/requirements.txt
```

Claude Code users can copy it to `~/.claude/skills/scholarly-novelty-audit`; cross-agent installations commonly use `~/.agents/skills/scholarly-novelty-audit`. The folder must remain named `scholarly-novelty-audit` to satisfy the Agent Skills specification.

Release assets include a `.sha256` sidecar. Verify it before installation. The tag workflow rebuilds and validates the runtime ZIP before publishing it; development archives, tests, benchmarks, and local data are never included in that asset.

## Use

Ask naturally:

```text
Use $scholarly-novelty-audit on this claim:
“We are the first to combine adaptive memory with compression-aware selection
for long-video vision-language reasoning.”

Cutoff: 2025-09-18.
Be adversarial. Return the top five killer candidates, a Minimal Prior Set of
at most three papers, strict date filtering, residual novelty, and Markdown + JSON.
```

The host agent will use the skill workflow. Deterministic helpers can also be run directly:

```bash
python scholarly-novelty-audit/scripts/cli.py search \
  --provider openalex \
  --query "adaptive memory compression aware selection" \
  --before 2025-09-18 \
  --output run/openalex.json

python scholarly-novelty-audit/scripts/cli.py dates \
  --input run/openalex.json \
  --cutoff 2025-09-18 \
  --output run/dated.json

python scholarly-novelty-audit/scripts/cli.py expand-graph \
  --papers run/dated.json --paper-a W123 --paper-b W456 \
  --cutoff 2025-09-18 --limit 100 --output run/expanded.json

python scholarly-novelty-audit/scripts/cli.py fetch-fulltext \
  --papers run/expanded.json --paper-id W123 \
  --output-dir run/fulltext --manifest run/fulltext-manifest.json

python scholarly-novelty-audit/scripts/cli.py bridge \
  --papers run/expanded.json --paper-a W123 --paper-b W456 \
  --cutoff 2025-09-18 --high-citation-threshold 500 \
  --output run/bridges.json

python scholarly-novelty-audit/scripts/cli.py verify-citations \
  --input run/report.json --output run/report.verified.json
python scholarly-novelty-audit/scripts/cli.py report-attempt \
  --input run/report.verified.json --max-attempts 3 \
  --state run/report-assembly.json
python scholarly-novelty-audit/scripts/cli.py validate --input run/report.verified.json
python scholarly-novelty-audit/scripts/cli.py export \
  --input run/report.verified.json --format html --output run/report.html
```

The bridge threshold above is only an example. Use a documented, field-calibrated value; omit it when none is defensible, in which case co-citation remains `UNASSESSED` and cannot strengthen the verdict.

The host agent gets at most three structured-report attempts. Reusing the same assembly state appends a sequential hash and validation history, so exhaustion cannot be asserted without the preceding attempts. `report-attempt` returns `RETRY_REQUIRED` with exact validation failures before the budget is exhausted; an invalid final attempt returns terminal `PARTIAL`, caps the conclusion at `INCONCLUSIVE`, and must not be exported as a valid audit.

Provider keys are optional for basic use. `S2_API_KEY` reduces Semantic Scholar throttling. A free `OPENALEX_API_KEY` raises the OpenAlex daily API budget from the anonymous trial allowance to $1/day. `mailto` is not used because OpenAlex retired the polite-pool system in 2026. OpenAlex searches explicitly use `corpus=all`; a core-only run cannot claim `BROAD` coverage. The search plan follows provider pagination until exhaustion, no-new-results saturation, or an explicit page budget. arXiv offsets advance by raw API entries, never by the smaller post-cutoff eligible set. At least one deterministic query-family run bypasses aggressive provider-side date filtering as a temporal-recall backstop; the earliest-public-date resolver remains the final eligibility gate. Provider counts, incomplete obligations, unsaturated runs, truncation, and outages lower Search Protocol Coverage deterministically rather than silently becoming evidence of novelty. `BROAD` means broad execution of this bounded protocol; it is not demonstrated recall of all relevant literature.

The MPS search bound is always `K ≤ 3`. “None found” means no qualifying evidence-bound set of three or fewer papers was found; it does not establish that no larger combination exists.

Every endpoint pair in every recomputed multi-paper MPS must have a `COMPLETE` citation-graph expansion record. If any pair is missing or `PARTIAL`, the validator permits only `INCONCLUSIVE` and requires the deterministic search-gap marker `GRAPH_EXPANSION_INCOMPLETE:<smaller-paper-id>:<larger-paper-id>`. Consequently, `FRAGMENTED_PRECEDENT` means the relevant pairs were actually expanded and no qualifying historical bridge was verified—not merely that no bridge happened to be present in the initial candidate pool.

A graph call that returns exactly its requested limit is conservatively marked `possibly_truncated`; the expansion becomes `PARTIAL` with reason `LIMIT_REACHED`. OpenAlex backward expansion keeps scanning the complete raw reference-ID list when provider-side filtering makes an early batch underfull, and Semantic Scholar graph expansion follows its `next` offsets. Historical graph calls deliberately omit provider-side date filters, preserve later records for `LANDSCAPE_BRIDGE` review, and let the local earliest-public-date resolver decide eligibility. Therefore “no bridge” means no bridge was verified within a complete recorded expansion, and cannot silently support `FRAGMENTED_PRECEDENT` when the citation neighborhood may continue beyond the budget.

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
- `10`: partial completion after a backend failure or exhausted report retry budget;
- `20`: no searchable claim could be extracted;
- `30`: all configured scholarly providers failed;
- `40`: evidence or report validation failed;
- `50`: configuration or credential error.

## Test

```bash
python -m pytest scholarly-novelty-audit/tests -q
skills-ref validate ./scholarly-novelty-audit
```

Live smoke tests may encounter provider rate limits; those failures are expected to be explicit. All core algorithms and adversarial invariants run offline.

## Roadmap that needs public data, not synthetic theater

The deterministic core is implemented. The next growth asset is a licensed set of reviewer-grounded cases: bibliography-absent killer papers, genuine composition concerns, ancestor-term recoveries, temporal traps, and false-positive defenses. This repository intentionally does not fabricate 20 “real” demos or redistribute third-party review data under the wrong license. See [benchmark policy](scholarly-novelty-audit/benchmark/README.md).

External validation is not complete. The [empirical status page](docs/empirical-status.md) reports the exact non-synthetic counters: one licensed case has reached real provider graph expansion, zero cases have completed the full end-to-end audit, the first three fixed graph pairs recovered zero third-paper bridges, and benchmark metrics remain unmeasured.

The release gates are separated into user-trust requirements, benchmark evidence, and adoption evidence in [user-facing release acceptance](docs/release-acceptance.md).

## Contributing

High-value contributions are public reviewer-grounded cases, provider adapters, date golden tests, bridge-evidence edge cases, and report-faithfulness failures. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

Installable runtime archives must be built with the allowlist-based deterministic bundle tool; see [release packaging](docs/releasing.md). The repository is installed as an Agent Skill, not as a Python import package.

If NoveltyAudit finds a paper your reviewer could have found first, star the repo.
