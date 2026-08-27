# Changelog

## 0.3.1 - 2026-08-27

- Renamed the distributable skill to `scholarly-novelty-audit` and narrowed its trigger to forensic, evidence-first, composition-aware scholarly audits.
- Replaced author-awareness inference with observable supplied-bibliography states.
- Reframed the coverage axis as Search Protocol Coverage and encoded that it is not a literature-recall guarantee.
- Made the `K ≤ 3` MPS search bound and larger-combination limitation explicit in machine and human outputs.
- Added provider-derived public Tier-2 PDF/HTML/text acquisition, safe URL checks, extraction hashes, manifests, and evidence-to-acquisition validation.
- Added a deterministic allowlist-based runtime ZIP builder that excludes tests, benchmarks, caches, and repository-only material.
- Made runtime ZIP metadata cross-platform deterministic and normalized schema date/date-time diagnostics.
- Made complete graph expansion a validator-enforced obligation for every endpoint pair in every multi-paper MPS; incomplete pairs force `INCONCLUSIVE` plus a deterministic search gap.
- Fixed arXiv traversal to advance by raw API entries after local cutoff filtering, preventing false no-new-results saturation and false `BROAD` coverage.
- Made graph-expansion limit exhaustion a first-class partial state and added a deterministic unfiltered temporal-recall backstop query.
- Preserved the canonical first version's provider ID during deduplication so real graph expansion cannot silently query a lower-provenance duplicate work ID.
- Fixed OpenAlex backward expansion to exhaust raw reference IDs after cutoff filtering makes an early batch underfull, preventing false `COMPLETE` graph records.
- Added paginated Semantic Scholar graph traversal and fail-closed cursor/offset guards for both graph providers.
- Made every historical graph expansion an unfiltered temporal-recall backstop whose final eligibility is decided by the local earliest-public-date resolver.
- Added a stateful three-attempt report assembly gate; sequential hashes and failures are retained, and exhausted invalid output terminates as `PARTIAL` plus `INCONCLUSIVE`.
- Added clean runtime ZIP installation and CLI smoke tests on Linux and macOS CI runners.
- Moved Agent Skills runtime compatibility to its specification-defined top-level frontmatter field.
- Expanded the competitive landscape and added a market-category comparison.

## 0.3.0 - 2026-08-27

- Made Search Coverage deterministic from provider-returned SearchRun counts, pagination, corpus, truncation, failures, obligations, and saturation.
- Added normalized author-bibliography auditing, sensitivity recomputation, ancestor provenance checks, and direct-precedent killer enforcement.
- Added a first-class bridge CLI, explicit OpenAlex `corpus=all`, canonical `per_page`, robust arXiv boolean query assembly, and month-precision date handling.
- Wired benchmark annotations to a prediction schema and metric adapter.
- Disabled accidental setuptools package discovery and documented clean `git archive` release packaging.
- Made CLI validation schema-first, then semantic, and closed taxonomy plus omitted-graph-bridge downgrade bypasses.
- Added provider cutoff pushdown, bounded multi-page saturation, independently reproduced bibliography mappings, calibrated co-citation base-rate guards, and non-adverse `LANDSCAPE_BRIDGE` reporting.
- Added active `expand-graph` backward/forward citation chasing so third-paper bridge sources can enter the candidate pool instead of needing to appear in claim-similarity search.

## 0.2.0 - 2026-08-27

- Retired the obsolete OpenAlex polite-pool `mailto` parameter and documented current API-key budgets.
- Added Agent Skills runtime compatibility metadata and the official `skills-ref` validation command.
- Strengthened candidate, evidence-level, negative-evidence, timestamp, temporal-cutoff, query-provenance, provider-failure, and verdict-risk invariants.
- Removed volatile GitHub star counts from the competitive landscape.
- Added user-facing score leakage checks, secret scanning, explicit CLI status codes, and versioned schema migration guidance.

## 0.1.0 - 2026-08-27

- Added the composition-aware NoveltyAudit Agent Skill.
- Added four scholarly provider adapters and canonical normalization.
- Added earliest-public-date cutoff enforcement and version deduplication.
- Added Minimal Prior Set, bridge discovery, criticality sensitivity, report validation, and export.
- Added schemas, adversarial tests, benchmark policy, and bilingual documentation.
