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

Every graph-expansion call records `limit`, `exhausted`, `next_token`, provider/raw counts, and `possibly_truncated`. The validator requires `possibly_truncated == not exhausted`; an exhausted call cannot retain a continuation token. Non-exhausted calls require `LIMIT_REACHED` and prevent `COMPLETE`, while an exact-limit result may remain complete when the provider explicitly reports exhaustion. Every graph expansion records `provider_cutoff_applied=false`; historical expansions additionally require `temporal_recall_backstop=true` because final eligibility is resolved locally. Historical ordinary searches also require at least one SearchRun with the same backstop pairing.
