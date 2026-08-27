# Deterministic tooling

Run commands from the user's working directory. Set the skill path explicitly when useful:

```text
python <skill>/scripts/cli.py search --provider openalex --family mechanism --query "..." --before 2025-09-18 --output candidates.json
python <skill>/scripts/cli.py search-plan --input query-plan.json --output candidates.json
python <skill>/scripts/cli.py dedupe --input candidates.json --output canonical.json
python <skill>/scripts/cli.py dates --input canonical.json --cutoff 2025-09-18 --output dated.json
python <skill>/scripts/cli.py mps --input report-draft.json --output mps.json
python <skill>/scripts/cli.py expand-graph --papers dated.json --paper-a W123 --paper-b W456 --cutoff 2025-09-18 --limit 100 --output expanded.json
python <skill>/scripts/cli.py bridge --papers canonical.json --paper-a W123 --paper-b W456 --cutoff 2025-09-18 --high-citation-threshold <field-calibrated-value> --output bridges.json
python <skill>/scripts/cli.py verify-citations --input report.json --output report.verified.json
python <skill>/scripts/cli.py validate --input report.verified.json
python <skill>/scripts/cli.py export --input report.verified.json --format markdown --output report.md
python <skill>/scripts/cli.py snapshot-diff --before previous-report.json --after current-report.json --output diff.json
```

`query-plan.json` contains an explicit `cutoff`, per-page candidate `limit`, optional `max_pages` (default 10), provider list, and canonical queries. Every query supplies `query_id`, `family`, `query`, `reason`, `target_facets`, and `removed_author_terms`. Each SearchRun records aggregate counts, every page response, provider `total_count`, `truncated`, `corpus`, raw and canonical paper IDs, and a `saturation_stop_reason`: `PROVIDER_EXHAUSTED`, `NO_NEW_RESULTS`, `PAGE_BUDGET_EXHAUSTED`, or `PROVIDER_ERROR`. The command returns `COMPLETE`, `PARTIAL`, or `FAILED`, structured provider failures, canonical candidates, and a deterministic coverage derivation.

Search Coverage is not a model judgment. It is derived only from SearchRun records. `BROAD` requires complete run metadata, at least two successful providers, every required query family, no failed or truncated run, a saturation stop for every successful run, all search obligations complete, and `corpus=all` for every OpenAlex run. The validator independently recomputes both `search.saturated` and the coverage level.

Primary retrieval providers are OpenAlex, Semantic Scholar, and arXiv. Crossref is used only for DOI and metadata verification, not as a primary semantic search source. API keys are optional for basic use; Semantic Scholar accepts `S2_API_KEY`, and a free `OPENALEX_API_KEY` raises the OpenAlex daily API budget from the anonymous trial allowance to $1/day. OpenAlex retired the polite-pool system in 2026, so `mailto` is not sent. NoveltyAudit explicitly requests OpenAlex `corpus=all`; set `OPENALEX_CORPUS=core` or `expansion` only when intentionally narrowing the run, which prevents a `BROAD` classification.

The scripts never call an LLM. They normalize records, resolve dates, deduplicate versions, discover graph candidates, solve MPS, validate invariants, and render reports. The host agent remains responsible for facet decomposition and evidence interpretation.

`expand-graph` is the active citation-chasing stage. It auto-selects a provider shared by both endpoint records, preferring OpenAlex and then Semantic Scholar, or accepts `--provider`. Both endpoints must carry that provider's ID in `provider_ids`. It calls `references()` for backward expansion and `citations()` for forward expansion, admits a third paper as a co-citation candidate only when its returned reference list contains the other endpoint, merges new records into `papers`, reapplies the cutoff, and emits call/failure provenance. A `PARTIAL` result must remain a disclosed search gap.
