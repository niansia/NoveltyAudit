# Report fields

Use `schemas/report.schema.json` as the machine contract. Important human-facing sections are:

1. three-axis verdict and classification;
2. input claim, normalized claim, field, cutoff, and normalized author bibliography;
3. frozen atomic claim map;
4. Top Killer Papers with evidence and supplied-bibliography status, never inferred author awareness;
5. Minimal Prior Set and coverage matrix;
6. historical Bridge Evidence plus a separate non-adverse `landscape_bridges` section;
7. criticality sensitivity;
8. ancestor terminology trail;
9. residual novelty and defensible rewrite;
10. auditable SearchRun counts, raw/eligible page counts, temporal-recall backstop status, saturation stop reason, corpus, deterministic coverage derivation, graph-expansion limits and truncation provenance, obligations, failures, and gaps;
11. excluded, post-cutoff, and date-uncertain papers;
12. audit log and reproducibility metadata.

Every adverse report-level claim should link to stable evidence IDs. Use empty arrays or explicit `none found` explanations instead of omitting required negative findings.

For every recomputed MPS containing two or more papers, `search.graph_expansions` must include a `COMPLETE` record for every endpoint pair. Missing and `PARTIAL` pairs require `classification=INCONCLUSIVE`, `novelty_risk=INCONCLUSIVE`, and the exact lexicographically ordered gap marker `GRAPH_EXPANSION_INCOMPLETE:<paper-a>:<paper-b>`.

Every graph-expansion call records `limit` and `possibly_truncated`. `returned_count >= limit` requires `possibly_truncated=true`, `partial_reasons` must contain `LIMIT_REACHED`, and the expansion cannot be `COMPLETE`. Historical searches also require at least one SearchRun with `temporal_recall_backstop=true` and `provider_cutoff_applied=false`.

Breaking schema changes and field migrations are recorded in [schema migrations](schema-migrations.md).
