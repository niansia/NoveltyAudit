# Contributing

Contributions should strengthen observable behavior rather than add generic prompt rules.

High-value changes include reviewer-grounded public cases, temporal golden tests, provider adapters, canonical deduplication failures, bridge-evidence counterexamples, and report-faithfulness checks.

Before opening a pull request:

1. Add or update tests for the behavior.
2. Run `python -m pytest scholarly-novelty-audit/tests -q`.
3. Validate the skill with the Agent Skills or bundled quick validator.
4. Preserve source licenses and annotation provenance for benchmark data.
5. Disclose material AI assistance in the pull request description.

Do not commit private manuscripts, API keys, fabricated citations, or third-party datasets under an incompatible license. New adverse verdict logic must remain evidence-bound and temporally safe.

