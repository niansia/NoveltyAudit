# Schema migrations

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
- Replace the free-text `defensible_rewrite` with a structured object whose prior-coverage claims each carry evidence IDs.

Rebuild 0.1.0 artifacts from their preserved candidate and query logs. Do not invent missing provenance or timestamps merely to satisfy the new schema; downgrade the run to partial or inconclusive when the original evidence cannot support the new fields.
