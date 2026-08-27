# Bridge Evidence

Coverage alone does not establish that combining papers was historically natural.

## Discovery and promotion

First discover graph candidates deterministically: direct citation, co-citation by a third paper, or a shared citation neighborhood. Enforce the same cutoff on the bridge source.

Then inspect text and classify only supported relations:

- `EXPLICIT_EXTENSION`: one work states that it extends, adapts, or builds on the other;
- `SHARED_BENCHMARK`: a source directly compares both methods;
- `TAXONOMY_BRIDGE`: a survey places both in the same technical family;
- `SYNTHESIS_BRIDGE`: a source explains their complementary relationship;
- `COMBINATION_BRIDGE`: a source explicitly combines the relevant mechanisms.

`DIRECT_CITATION` and `CO_CITATION` are graph-only signals. They can support `PLAUSIBLE_COMPOSITION_RISK`, but never `STRONG_COMPOSITION_RISK` without textual evidence. Model intuition without external provenance is exploratory and cannot strengthen a verdict.

Every textual bridge source must be returned to the candidate pool and checked for direct facet coverage before finalizing the MPS. If the bridge source itself contains the claimed mechanism or interaction, solve the MPS again; do not leave it labeled as “bridge only.” Record `source_rechecked_as_candidate: true` in the report.
