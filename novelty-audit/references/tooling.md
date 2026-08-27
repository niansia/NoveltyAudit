# Deterministic tooling

Run commands from the user's working directory. Set the skill path explicitly when useful:

```text
python <skill>/scripts/cli.py search --provider openalex --query "..." --before 2025-09-18 --output candidates.json
python <skill>/scripts/cli.py dedupe --input candidates.json --output canonical.json
python <skill>/scripts/cli.py dates --input canonical.json --cutoff 2025-09-18 --output dated.json
python <skill>/scripts/cli.py mps --input report-draft.json --output mps.json
python <skill>/scripts/cli.py validate --input report.json
python <skill>/scripts/cli.py export --input report.json --format markdown --output report.md
```

Available providers are OpenAlex, Semantic Scholar, arXiv, and Crossref. API keys are optional; Semantic Scholar accepts `S2_API_KEY`, and OpenAlex accepts `OPENALEX_API_KEY` or a polite-pool email via `OPENALEX_MAILTO`. Provider failures must be logged and must lower Search Coverage.

The scripts never call an LLM. They normalize records, resolve dates, deduplicate versions, discover graph candidates, solve MPS, validate invariants, and render reports. The host agent remains responsible for facet decomposition and evidence interpretation.
