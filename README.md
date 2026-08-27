<p align="center">
  <img src="scholarly-novelty-audit/assets/logo.svg" alt="NoveltyAudit" width="760">
</p>

<p align="center">
  <strong>No single paper kills your novelty? Maybe three do.</strong>
</p>

<p align="center">
  <a href="https://github.com/niansia/NoveltyAudit/releases/tag/v0.3.1"><img alt="Alpha v0.3.1" src="https://img.shields.io/badge/release-v0.3.1%20alpha-6D46D8"></a>
  <a href="https://github.com/niansia/NoveltyAudit/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/niansia/NoveltyAudit/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="LICENSE"><img alt="Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <a href="https://github.com/agentskills/agentskills"><img alt="Agent Skills" src="https://img.shields.io/badge/Agent%20Skills-compatible-7C3AED"></a>
  <a href="README.zh-TW.md"><img alt="繁體中文" src="https://img.shields.io/badge/README-繁體中文-0F766E"></a>
</p>

NoveltyAudit is an evidence-first Agent Skill for adversarial scholarly novelty checks. It asks a harder question than “Which paper is most similar?”:

> What is the smallest set of prior papers that can collectively cover the critical parts of this claim—and is there historical evidence that they were meaningfully connected?

It then shows what the set covers, what it does not cover, why the papers were historically combinable, whether they existed before the cutoff, and what novelty still survives.

<p align="center">
  <img src="docs/assets/architecture.png" alt="NoveltyAudit architecture: claim freeze, multi-provider retrieval, evidence binding, Minimal Prior Set and graph expansion, then deterministic validation and export" width="100%">
</p>

<p align="center"><sub>Editable source: <a href="docs/assets/noveltyaudit-architecture.pptx">PowerPoint architecture diagram</a></sub></p>

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
- Multi-provider backward/forward citation expansion followed by deterministic direct-citation and co-citation discovery, with provider-attributed endpoint coverage, a pre-retrieval observation-window diagnostic, a sensitivity-checked high-citation guard, textual promotion gates, and separate post-cutoff landscape bridges.
- Public Tier-2 PDF/HTML/text acquisition with DNS-pinned public-address connections, actual-peer verification, response-size limits, extracted-text files, cryptographic hashes, and evidence-to-acquisition validation.
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

Release assets include a `.sha256` sidecar. Verify it before installation. The tag workflow requires clean installation on Ubuntu and macOS, then rebuilds and validates the runtime ZIP before publishing it. The archive includes the complete Apache-2.0 `LICENSE`; development archives, tests, benchmarks, and local data are never included.

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

python scholarly-novelty-audit/scripts/cli.py graph-preflight \
  --papers run/dated.json --paper-a W123 --paper-b W456 \
  --cutoff 2025-09-18 --output run/graph-preflight.json

python scholarly-novelty-audit/scripts/cli.py expand-graph \
  --papers run/dated.json --paper-a W123 --paper-b W456 \
  --cutoff 2025-09-18 --limit 100 --output run/expanded.json

python scholarly-novelty-audit/scripts/cli.py fetch-fulltext \
  --papers run/expanded.json --paper-id W123 \
  --output-dir run/fulltext --manifest run/fulltext-manifest.json

python scholarly-novelty-audit/scripts/cli.py bridge \
  --papers run/expanded.json --paper-a W123 --paper-b W456 \
  --cutoff 2025-09-18 \
  --output run/bridges.json

python scholarly-novelty-audit/scripts/cli.py verify-citations \
  --input run/report.json --output run/report.verified.json
python scholarly-novelty-audit/scripts/cli.py report-attempt \
  --input run/report.verified.json --max-attempts 3 \
  --output run/report.bound.json \
  --state run/report-assembly.json
python scholarly-novelty-audit/scripts/cli.py validate --input run/report.bound.json
python scholarly-novelty-audit/scripts/cli.py export \
  --input run/report.bound.json --format html --output run/report.html
```

The bridge command defaults to a 500-citation operational guard. The 82-case exploratory sensitivity table was comparatively flat across thresholds 50–1,000 (8.47%–12.12% pair rates), so the bundled policy is labeled `SENSITIVITY_CHECKED`, not universally field-calibrated. A custom threshold with a source is only `DOCUMENTED_OVERRIDE`; `CALIBRATION_DECLARED` additionally requires structured dataset and method provenance plus `preregistered=true`. Those fields are a documented assertion, not independent proof that the calibration exists or supports the threshold. Missing endpoint citation counts still make co-citation `UNASSESSED`.

The host agent gets at most three structured-report attempts. Before validation and hashing, `report-attempt` replaces any host-supplied runtime claim with the Python, `jsonschema`, and `pypdf` versions resolved by that process, writes the same machine-bound report to `--output`, and records the binding in every attempt. The input draft is not overwritten. Reusing the same assembly state appends a sequential hash and validation history bound to the immutable `audit_id`, claim ID, claim-freeze hash, and cutoff; a state from another audit or an internally inconsistent earlier runtime record is rejected. `RETRY_REQUIRED` reports exact failures before exhaustion; only the bound output from a `COMPLETE` attempt may be exported. An invalid final attempt returns terminal `PARTIAL`, caps the conclusion at `INCONCLUSIVE`, and must not be exported as a valid audit. Standalone `validate` intentionally checks historical runtime provenance for structure, not equality with the machine performing a later review.

Provider keys are optional for basic use. `S2_API_KEY` reduces Semantic Scholar throttling. A free `OPENALEX_API_KEY` raises the OpenAlex daily API budget from the anonymous trial allowance to $1/day. `mailto` is not used because OpenAlex retired the polite-pool system in 2026. OpenAlex searches explicitly use `corpus=all`; a core-only run cannot claim `BROAD` coverage. The search plan follows provider pagination until exhaustion, no-new-results saturation, or an explicit page budget. arXiv offsets advance by raw API entries, never by the smaller post-cutoff eligible set. At least one deterministic query-family run bypasses aggressive provider-side date filtering as a temporal-recall backstop; the earliest-public-date resolver remains the final eligibility gate. Provider counts, incomplete obligations, unsaturated runs, truncation, and outages lower Search Protocol Coverage deterministically rather than silently becoming evidence of novelty. `BROAD` means broad execution of this bounded protocol; it is not demonstrated recall of all relevant literature.

The MPS search bound is always `K ≤ 3`. “None found” means no qualifying evidence-bound set of three or fewer papers was found; it does not establish that no larger combination exists.

Every endpoint pair in every recomputed multi-paper MPS must have a `COMPLETE` citation-graph expansion record. If any pair is missing or `PARTIAL`, the validator permits only `INCONCLUSIVE` and requires the deterministic search-gap marker `GRAPH_EXPANSION_INCOMPLETE:<smaller-paper-id>:<larger-paper-id>`. Consequently, `FRAGMENTED_PRECEDENT` means the relevant pairs were actually expanded and no qualifying historical bridge was verified—not merely that no bridge happened to be present in the initial candidate pool.

Before network retrieval, `graph-preflight` computes the pair's observation window. `BELOW_DIAGNOSTIC_THRESHOLD` warns that a zero bridge finding will be low-information; `MEETS_DIAGNOSTIC_THRESHOLD` means only that the exploratory 548-day threshold was met, not that the field is mature. Neither result skips retrieval. By default, `expand-graph` unions backward references from every available OpenAlex and Semantic Scholar endpoint ID and unions forward candidates from every namespace shared by both endpoints. Every call remains provider-attributed. If no provider namespace spans both endpoints, available backward evidence is preserved but the expansion becomes `PARTIAL` instead of raising or claiming a complete zero.

Graph providers return an explicit exhaustion signal and continuation token. A call is `possibly_truncated` only when the provider traversal is not exhausted; `returned_count == limit` can remain complete when the provider also proves there is no next page. Non-exhausted calls become `PARTIAL` with reason `LIMIT_REACHED`. OpenAlex backward expansion scans the complete raw reference-ID list, and Semantic Scholar follows graph `next` offsets. Historical graph calls deliberately omit provider-side date filters, preserve later records for `LANDSCAPE_BRIDGE` review, and let the local earliest-public-date resolver decide eligibility.

Every expansion also records per-provider `endpoint_reference_observations`, `observation_window_days`, `observation_window_status`, historical versus landscape candidate IDs, and a deterministic `negative_result_scope`. An empty provider bibliography is a coverage caveat, not evidence that a paper has no references; missing or post-cutoff endpoint dates get separate uninterpretable scopes, and a short window says that co-citation may not yet have had time to form. Therefore “no bridge” can only mean no bridge was verified inside the stated complete provider union and observation window. It is never silent reassurance.

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

The deterministic core is implemented. The next growth asset is a licensed set of end-to-end reviewer-grounded cases: bibliography-absent killer papers, genuine composition concerns, ancestor-term recoveries, temporal traps, and false-positive defenses. This repository intentionally does not fabricate “real” demos or redistribute third-party review data under the wrong license. See [benchmark policy](scholarly-novelty-audit/benchmark/README.md).

External validation is not complete, but bridge base rates are no longer unmeasured. The [82-case empirical study](docs/empirical-status.md) found explicit named priors in 37 cases and at least two deterministically detected priors in 23 cases (28.05%). Another 23 cases were `POTENTIAL_MISSED_MENTIONS`, so the detector likely undercounts explicit mentions; because extracted links have not yet been independently precision-audited, 28.05% is not asserted as a formal statistical lower bound or composition-objection prevalence. Among 18 complete multi-prior cases, 4 had a pre-cutoff co-citation bridge (22.22%; case-level exact 95% binomial interval 6.41%–47.64%), so this supports a minority signal in this sample, not a precise population rate. The 12/72 pair rate is descriptive only because pairs cluster within cases. OpenAlex alone exposed nonempty references for 25.30% of named priors. Observed nonempty backward coverage with Semantic Scholar fallback was 56/83 (67.47%). Bridge Evidence remains a conditional positive signal for longer-window, adequately covered fields—not a universal negative test. Full end-to-end reports, Recall@5, MRR, and reviewer-prediction validation remain unmeasured.

The release gates are separated into user-trust requirements, benchmark evidence, and adoption evidence in [user-facing release acceptance](docs/release-acceptance.md). External data and derived-aggregate notices are separated in [data licenses](docs/DATA_LICENSES.md).

## Contributing

High-value contributions are public reviewer-grounded cases, provider adapters, date golden tests, bridge-evidence edge cases, and report-faithfulness failures. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

Installable runtime archives must be built with the allowlist-based deterministic bundle tool; see [release packaging](docs/releasing.md). The repository is installed as an Agent Skill, not as a Python import package.

If NoveltyAudit finds a paper your reviewer could have found first, star the repo.
