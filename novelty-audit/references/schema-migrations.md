# Schema migrations

## 0.2.0 to 0.3.0

Version 0.3.0 makes Search Coverage and prior awareness independently auditable.

- Replace `query_runs[].result_count` with `returned_count` and provider-reported `total_count`.
- Add required query-run `pagination`, `corpus`, raw provider `paper_ids`, and post-deduplication `canonical_paper_ids`.
- Add `search.coverage_derivation`; it must exactly match deterministic validator output.
- Add top-level `author_bibliography` with raw entries, match bases, canonical matches, a recomputed normalized ID set, and unmatched entries.
- Criticality sensitivity values are now recomputed, not merely shape-checked.
- OpenAlex runs record `corpus`; a core-only run cannot derive `BROAD` coverage.

## 0.1.0 to 0.2.0

Version 0.2.0 strengthens user-facing audit invariants and is intentionally breaking.

- Add top-level `candidate_ids`; every reported paper must belong to this canonical candidate snapshot.
- Add a versioned `run_manifest` with config hash, model/prompt identity, provider endpoint versions, retrieval window, and candidate snapshot hash.
- Add `verdict.decided_at` and require verdict evidence to have been retrieved earlier.
- Replace `evidence.paper_id` with `evidence.canonical_paper_id`.
- Add required `evidence.source_level`; hard coverage requires `TIER_2_FULLTEXT`.
- Add `paper.found_by_query_ids`.
- Add independent Crossref/arXiv `citation_validation` records when a paper carries those identifiers.
- Add stable `query_id`, `reason`, `target_facets`, and `removed_author_terms` fields to query runs.
- Add structured search obligations and structured provider failures.
- Add bridge `provenance_type` and structured optional verdict `risk_basis`.
- Add calibrated co-citation `base_rate_status`, non-adverse `landscape_bridges`, and deterministic bridge omission checks.
- Add page-level search history, saturation stop reasons, provider cutoff pushdown, and schema-first CLI validation.
- Reproduce DOI, arXiv, and conservative title/author bibliography matches before assigning prior awareness.
- Add optional `search.graph_expansions` provenance so actively retrieved reference/citation candidates remain valid, auditable paper discovery routes.
- Replace the free-text `defensible_rewrite` with a structured object whose prior-coverage claims each carry evidence IDs.

Rebuild 0.1.0 artifacts from their preserved candidate and query logs. Do not invent missing provenance or timestamps merely to satisfy the new schema; downgrade the run to partial or inconclusive when the original evidence cannot support the new fields.
