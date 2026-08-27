# Claim decomposition

Decompose the claim before retrieval so search results cannot retroactively change what counts as the contribution.

## Facet roles

Use the narrowest applicable role: `problem`, `mechanism`, `selection_principle`, `representation`, `constraint`, `setting`, `data_regime`, `objective`, `evaluation_condition`, `interaction`, or `outcome`.

For every facet record:

- a stable ID and concrete text;
- `author_critical`: whether the author presents it as central;
- `structural_critical`: whether removing it leaves essentially the same contribution;
- a brief criticality rationale;
- `criticality_dispute: true` when the two judgments conflict.

Outcomes such as "improves accuracy" are normally supporting facets. Generic adjectives such as efficient, robust, or novel are not technical facets without a measurable or mechanistic definition.

## Freeze rule

Write `frozen_before_retrieval: true`, a timestamp, and the complete facet map before issuing the first scholarly query. Later corrections create a new version; they never silently replace the frozen map.

After the baseline audit, remove each critical facet in turn and solve the MPS again. Report any removal that creates a direct precedent or shortens the MPS.

