# Deterministic tooling

Run commands from the user's working directory. Set the skill path explicitly when useful:

```text
python <skill>/scripts/cli.py search --provider openalex --family mechanism --query "..." --before 2025-09-18 --output candidates.json
python <skill>/scripts/cli.py search-plan --input query-plan.json --output candidates.json
python <skill>/scripts/cli.py dedupe --input candidates.json --output canonical.json
python <skill>/scripts/cli.py dates --input canonical.json --cutoff 2025-09-18 --output dated.json
python <skill>/scripts/cli.py mps --input report-draft.json --output mps.json
python <skill>/scripts/cli.py bridge --papers canonical.json --paper-a W123 --paper-b W456 --cutoff 2025-09-18 --output bridges.json
python <skill>/scripts/cli.py verify-citations --input report.json --output report.verified.json
python <skill>/scripts/cli.py validate --input report.verified.json
python <skill>/scripts/cli.py export --input report.verified.json --format markdown --output report.md
python <skill>/scripts/cli.py snapshot-diff --before previous-report.json --after current-report.json --output diff.json
```

`query-plan.json` contains an explicit `cutoff`, candidate `limit`, provider list, and canonical queries. Every query supplies `query_id`, `family`, `query`, `reason`, `target_facets`, and `removed_author_terms`. The limit is mandatory rather than silently guessed. Each SearchRun records `returned_count`, provider `total_count`, `truncated`, `pagination`, `corpus`, raw provider `paper_ids`, and post-deduplication `canonical_paper_ids`. The command returns `COMPLETE`, `PARTIAL`, or `FAILED`, structured provider failures, canonical candidates, and a deterministic coverage derivation.

Search Coverage is not a model judgment. It is derived only from SearchRun records. `BROAD` requires complete run metadata, at least two successful providers, every required query family, no failed or truncated run, and `corpus=all` for every OpenAlex run. Separate search obligations remain reportable gaps but cannot inflate the derived level. The validator recomputes the level and rejects a conflicting report value.

Primary retrieval providers are OpenAlex, Semantic Scholar, and arXiv. Crossref is used only for DOI and metadata verification, not as a primary semantic search source. API keys are optional for basic use; Semantic Scholar accepts `S2_API_KEY`, and a free `OPENALEX_API_KEY` raises the OpenAlex daily API budget from the anonymous trial allowance to $1/day. OpenAlex retired the polite-pool system in 2026, so `mailto` is not sent. NoveltyAudit explicitly requests OpenAlex `corpus=all`; set `OPENALEX_CORPUS=core` or `expansion` only when intentionally narrowing the run, which prevents a `BROAD` classification.

The scripts never call an LLM. They normalize records, resolve dates, deduplicate versions, discover graph candidates, solve MPS, validate invariants, and render reports. The host agent remains responsible for facet decomposition and evidence interpretation.
