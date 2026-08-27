# Bridge Evidence

Coverage alone does not establish that combining papers was historically natural.

## Discovery and promotion

First discover graph candidates deterministically: direct citation, co-citation by a third paper, or a shared citation neighborhood. Enforce the same cutoff on the bridge source.

Absence of a bridge is interpretable only after a complete graph expansion. If any backward or forward call returns its full requested limit, record `possibly_truncated=true`, set the expansion to `PARTIAL` with `LIMIT_REACHED`, disclose the pair-specific search gap, and use `INCONCLUSIVE`. Do not convert “none found within the budget” into `FRAGMENTED_PRECEDENT`.

Then inspect text and classify only supported relations:

- `EXPLICIT_EXTENSION`: one work states that it extends, adapts, or builds on the other;
- `SHARED_BENCHMARK`: a source directly compares both methods;
- `TAXONOMY_BRIDGE`: a survey places both in the same technical family;
- `SYNTHESIS_BRIDGE`: a source explains their complementary relationship;
- `COMBINATION_BRIDGE`: a source explicitly combines the relevant mechanisms.

`DIRECT_CITATION` and `CO_CITATION` are graph-only signals. They can support `PLAUSIBLE_COMPOSITION_RISK`, but never `STRONG_COMPOSITION_RISK` without textual evidence. A co-citation route qualifies only when both endpoint citation counts are known and below a documented, field-calibrated `high_citation_threshold`. If the threshold or counts are missing, mark it `UNASSESSED`; if either endpoint exceeds the threshold, mark it `HIGH_BASE_RATE`. Neither status may strengthen the verdict. Never invent a universal threshold.

Do not discard a bridge merely because its source appeared after the audit cutoff. Route it to `landscape_bridges` as `LANDSCAPE_BRIDGE`, retain its underlying graph type and date status, and set `affects_historical_verdict: false`. Explain that the connection was unavailable at the historical cutoff but may be visible to a present-day reviewer.

Every textual bridge source must be returned to the candidate pool and checked for direct facet coverage before finalizing the MPS. If the bridge source itself contains the claimed mechanism or interaction, solve the MPS again; do not leave it labeled as “bridge only.” Record `source_rechecked_as_candidate: true` in the report.
