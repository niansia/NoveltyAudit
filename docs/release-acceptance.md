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
- Citation expansion actively calls provider reference and citation APIs, merges third-paper bridge sources into the candidate pool, and records partial expansion failures or exhausted limits. Every endpoint pair in every recomputed multi-paper MPS requires a complete, non-truncated expansion; otherwise the verdict is capped at `INCONCLUSIVE` with a deterministic search-gap marker. Complete zero results must also expose endpoint provider-reference observations, the numeric observation window, historical/landscape routing, and a validator-recomputed negative-result scope.
- Markdown and HTML contain no novelty percentages, uncalibrated decimals, internal ranking features, raw machine JSON, or unescaped scholarly content.
- API keys never enter artifacts; telemetry is off; private manuscripts are not sent to scholarly providers; secret scanning runs in CI.
- Full-text HTTP(S) resolves and validates every address once, connects to a pinned validated address, verifies the actual peer, disables proxy bypass, and repeats the contract after redirects.
- The Skill follows the Agent Skills specification, declares runtime compatibility, publishes English and Traditional Chinese documentation, and states its legal boundary.
- The distributable ZIP contains the complete Apache-2.0 `LICENSE`, and the tag workflow cannot publish until clean ZIP installation succeeds on GitHub-hosted Ubuntu and macOS.

The locally enforceable P0 gates are implemented in schema version 0.3.1 and guarded by offline adversarial tests. Host-agent report assembly uses a fixed three-attempt gate bound to the immutable audit/claim/freeze/cutoff identity; cross-audit state reuse is rejected, and invalid final output becomes terminal `PARTIAL` with an `INCONCLUSIVE` conclusion cap.

## P1 — evidence that the product works

Required before making benchmark or performance claims:

- Calibrate query budgets, citation-expansion depth, candidate limits, Tier-2 promotion limits, MPS K, and high-citation bridge thresholds from real cases.
- Build the licensed reviewer-grounded corpus, dual annotation and adjudication process, downloader, mappings, and separate dataset licenses.
- Publish retrieval, MPS, bridge, facet, criticality, temporal, citation-validity, false-comfort, false-alarm, faithfulness, and calibration metrics.
- Publish baselines, ablations, repeated-run stability, latency, API cost, token cost, and failure cases.
- Add snapshot diff, incremental update, complete run metadata, and deterministic report regeneration tests.

No metric or calibration constant may be fabricated to satisfy this tier.

## P2 — adoption and usability evidence

Required for a mature 1.0 product, not for an honest alpha/beta Skill:

- Eight-researcher field study and five-person first-screen comprehension study.
- Rewrite adoption and Top-5 false-positive fatigue measurements.
- A demonstrated hard-case feedback loop.
- At least 20 licensed reviewer-grounded demos, three public failure cases, a before/after recovery story, report permalinks, and measured time-to-first-report.

## Public-beta gate status

- End-to-end host-agent report assembly now has a deterministic `report-attempt` contract: at most three same-audit attempts, immutable identity binding, exact validation feedback, and terminal `PARTIAL` plus `INCONCLUSIVE` when the budget is exhausted.
- Clean runtime installation is now exercised from the distributable ZIP on both `ubuntu-latest` and `macos-latest`, including dependency installation timing and CLI startup. The first green GitHub Actions run is still required as external evidence before marking this gate passed; a workflow definition alone is not a test result.

## Blocks benchmark or performance claims

- End-to-end reviewer-grounded claim maps, Tier-2 evidence, and independently adjudicated labels beyond the current prevalence study.
- Calibration, baselines, ablations, repeated-run stability, and performance measurements listed under P1.

These are not blockers for an honestly labeled alpha or public beta, but NoveltyAudit must not make benchmark, calibration, or performance claims until they exist.

Current evidence is explicitly counted in [empirical validation status](empirical-status.md). As of 2026-08-27, all 82 licensed annotated cases have entered a deterministic no-LLM bridge base-rate study: 23 have at least two detected reviewer-named priors, 18 have complete endpoint/pair coverage, and 4 of those 18 contain a pre-cutoff co-citation bridge. This establishes prevalence and provider/maturity limitations, not end-to-end audit quality. Zero cases have completed the full reviewer-grounded claim-to-evidence pipeline; Recall@5, MRR, calibration, and reviewer prediction remain unmeasured.
