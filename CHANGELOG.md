# Changelog

## Unreleased

- Pin strict historical arXiv full-text evidence to the latest verified version available at or before the cutoff. Complete version metadata is resolved through versioned arXiv API IDs; incomplete histories and redirects to unversioned/current PDFs now fail closed.
- Preserve arXiv version numbers, exact version dates, versioned PDF URLs, and version-history metadata across normalization and deduplication.
- Add regression coverage for post-cutoff revision leakage, incomplete histories, redirect drift, provider metadata parsing, and provider-order-independent deduplication.

## 0.3.1 - 2026-08-28 — Initial public release

- Evidence-first scholarly novelty audits with frozen claim facets, supplied-bibliography states, strict historical cutoffs, and separate Novelty Risk, Search Protocol Coverage, and Evidence Confidence axes.
- Evidence-bound Minimal Prior Sets with the explicit `K ≤ 3` search bound, leave-one-out criticality sensitivity, residual novelty, and defensible claim rewrites.
- Multi-provider search, canonical identifier verification, earliest-public-date resolution, public Tier-2 full-text acquisition, and auditable SearchRun provenance.
- Active backward/forward citation expansion with complete-pair obligations, truncation detection, high-citation base-rate guards, textual bridge promotion gates, and non-adverse post-cutoff landscape bridges.
- Interpretable negative graph results with endpoint provider-reference observations, historical/landscape candidate routing, numeric observation windows, and validator-recomputed result scopes.
- Reproducible, no-LLM TUdatalib 82-case bridge base-rate measurement with resumable provider caching, conservative reviewer-reference extraction, citation-count sensitivity analysis, and a public aggregate snapshot.
- Temporal-recall backstops for ordinary search and graph expansion, including raw arXiv traversal, complete OpenAlex reference-ID scanning, and paginated fail-closed graph provider adapters.
- Deterministic report invariants, stateful three-attempt assembly gating, Markdown/JSON/HTML export, snapshot diffing, and explicit partial or inconclusive terminal states.
- Agent Skills-compatible metadata, bilingual documentation, adversarial offline tests, clean Linux/macOS install CI, secret scanning, and a byte-for-byte deterministic runtime ZIP.
- Release hardening adds the complete Apache-2.0 license to the runtime ZIP, tag-gated Ubuntu/macOS clean installation, DNS-pinned and peer-verified full-text connections, audit-identity-bound report retries, and provider-declared graph exhaustion.
- Final RC hardening unions OpenAlex and Semantic Scholar graph neighborhoods, adds a zero-network observation-window preflight without claiming field maturity, adopts a documented sensitivity-checked 500-citation operational guard, distinguishes `DOCUMENTED_OVERRIDE` from `CALIBRATION_DECLARED`, and machine-binds Python plus evidence-processing dependency versions before report validation and hashing.
- Empirical reporting now names 23/82 as a deterministically detected multi-prior mention rate rather than a formal lower bound, retains the exact interval only for the case-level 4/18 estimate, labels the clustered 12/72 pair rate descriptive, separates data-license notices, and fixes cross-platform checksum-sidecar line endings.
