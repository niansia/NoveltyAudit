# Contributing

Contributions should strengthen observable behavior rather than add generic prompt rules.

High-value changes include reviewer-grounded public cases, temporal golden tests, provider adapters, canonical deduplication failures, bridge-evidence counterexamples, and report-faithfulness checks.

## Case studies

Public failure-mode records live under [`case-studies/`](case-studies/README.md), separate from runtime Skill references and benchmark code. A case contribution must include both a human-readable `README.md` and a machine-readable `case.json` that validates against `case-studies/case.schema.json`.

- Choose exactly one evidence type: `SYNTHETIC`, `REVIEWER_GROUNDED`, or `PUBLIC_CASE_STUDY`.
- Record a strict historical cutoff, stable identifiers, bibliography status, expected audit behavior, provenance, source license, and limitations.
- Do not convert a reviewer mention into an adjudicated MPS, or a curated literature decomposition into benchmark gold.
- Do not commit third-party PDFs, copied review text, dataset dumps, or confidential manuscript material.
- Mark unmeasured fields `NOT_ASSESSED`, `NOT_RUN`, or `null` rather than inferring them.

Before opening a pull request:

1. Add or update tests for the behavior.
2. Run `python -m pytest scholarly-novelty-audit/tests -q`.
3. Validate the skill with the Agent Skills or bundled quick validator.
4. Preserve source licenses and annotation provenance for benchmark data.
5. Disclose material AI assistance in the pull request description.

Do not commit private manuscripts, API keys, fabricated citations, or third-party datasets under an incompatible license. New adverse verdict logic must remain evidence-bound and temporally safe.
