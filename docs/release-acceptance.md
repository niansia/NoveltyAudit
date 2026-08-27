# User-facing release acceptance

The 168-point product specification mixes three different maturity levels. NoveltyAudit uses the following release priorities so an installable Skill is not blocked on claims that require a licensed benchmark or longitudinal user study, while user trust is never traded away.

## P0 — user trust and safe operation

Required before recommending a public beta:

- Every adverse conclusion is evidence-bound, every reported paper belongs to the candidate snapshot, and every DOI/arXiv identifier is independently resolved.
- Killer candidates show both coverage and non-coverage evidence plus supplied-bibliography status without inferring author awareness.
- Hard coverage is Tier-2 full-text evidence; metadata triage never becomes a final overlap verdict.
- Claim criticality is frozen and hashed before retrieval; every critical facet receives multiple query families and leave-one-out sensitivity.
- Cutoff enforcement is deterministic. Post-cutoff and date-uncertain records cannot enter killers, MPS, bridge support, or verdict evidence. At least one query family bypasses provider cutoff pushdown as a temporal-recall backstop.
- MPS minimality and bridge requirements are recomputed rather than trusted from model output.
- Co-citation cannot strengthen a verdict without complete citation counts and a documented calibrated threshold; post-cutoff graph routes remain visible only as non-adverse landscape bridges.
- Verdict, Novelty Risk, Search Protocol Coverage, and Evidence Confidence obey explicit consistency rules.
- Query IDs, discovery routes, provider page history, saturation stop reasons, failures, truncation, search gaps, evidence timestamps, and machine-readable status are preserved.
- Citation expansion actively calls provider reference and citation APIs, merges third-paper bridge sources into the candidate pool, and records partial expansion failures or exhausted limits. Every endpoint pair in every recomputed multi-paper MPS requires a complete, non-truncated expansion; otherwise the verdict is capped at `INCONCLUSIVE` with a deterministic search-gap marker.
- Markdown and HTML contain no novelty percentages, uncalibrated decimals, internal ranking features, raw machine JSON, or unescaped scholarly content.
- API keys never enter artifacts; telemetry is off; private manuscripts are not sent to scholarly providers; secret scanning runs in CI.
- The Skill follows the Agent Skills specification, declares runtime compatibility, publishes English and Traditional Chinese documentation, and states its legal boundary.

Most locally enforceable P0 gates are implemented in schema version 0.3.1 and guarded by offline adversarial tests. Remaining P0 work that needs a larger orchestration layer is tracked below.

## P1 — evidence that the product works

Required before making benchmark or performance claims:

- Calibrate query budgets, citation-expansion depth, candidate limits, Tier-2 promotion limits, MPS K, and high-citation bridge thresholds from real cases.
- Build the licensed reviewer-grounded corpus, dual annotation and adjudication process, downloader, mappings, and separate dataset licenses.
- Publish retrieval, MPS, bridge, facet, criticality, temporal, citation-validity, false-comfort, false-alarm, faithfulness, and calibration metrics.
- Publish baselines, ablations, repeated-run stability, latency, API cost, token cost, cache benefit, and failure cases.
- Add snapshot diff, incremental update, complete run metadata, and deterministic report regeneration tests.

No metric or calibration constant may be fabricated to satisfy this tier.

## P2 — adoption and usability evidence

Required for a mature 1.0 product, not for an honest alpha/beta Skill:

- Eight-researcher field study and five-person first-screen comprehension study.
- Rewrite adoption and Top-5 false-positive fatigue measurements.
- A demonstrated hard-case feedback loop.
- At least 20 licensed reviewer-grounded demos, three public failure cases, a before/after recovery story, report permalinks, and measured time-to-first-report.

## Remaining public-beta blockers

1. End-to-end host-agent report assembly with schema-retry exhaustion represented as `PARTIAL`. Multi-provider candidate search, fallback, identifier verification, public Tier-2 acquisition, run manifests, snapshot hashing, and snapshot diffing are bundled, but model-output retry remains client-controlled.
2. Clean-environment macOS and Linux install tests. CI covers Linux unit behavior, but installation timing and macOS have not been measured.

These blockers must remain visible in the README and release notes until evidence closes them.

## Blocks benchmark or performance claims

- Licensed reviewer-grounded cases and adjudicated labels.
- Calibration, baselines, ablations, repeated-run stability, and performance measurements listed under P1.

These are not blockers for an honestly labeled alpha or public beta, but NoveltyAudit must not make benchmark, calibration, or performance claims until they exist.

Current evidence is explicitly counted in [empirical validation status](empirical-status.md). As of 2026-08-27, one licensed case has reached real provider graph expansion, zero cases have completed the full end-to-end audit, zero third-paper bridge candidates were recovered in its three fixed pairs, and benchmark metrics remain unmeasured.
