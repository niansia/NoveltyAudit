# Report fields

Use `schemas/report.schema.json` as the machine contract. Important human-facing sections are:

1. three-axis verdict and classification;
2. input claim, normalized claim, field, and cutoff;
3. frozen atomic claim map;
4. Top Killer Papers with evidence and prior awareness;
5. Minimal Prior Set and coverage matrix;
6. Bridge Evidence;
7. criticality sensitivity;
8. ancestor terminology trail;
9. residual novelty and defensible rewrite;
10. search coverage obligations, failures, and gaps;
11. excluded, post-cutoff, and date-uncertain papers;
12. audit log and reproducibility metadata.

Every adverse report-level claim should link to stable evidence IDs. Use empty arrays or explicit `none found` explanations instead of omitting required negative findings.

Breaking schema changes and field migrations are recorded in [schema migrations](schema-migrations.md).
