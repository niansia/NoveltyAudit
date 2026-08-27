# Verdict taxonomy

- `DIRECT_PRECEDENT`: one eligible paper evidence-binds all frozen critical facets.
- `STRONG_COMPOSITION_RISK`: two or three eligible papers jointly cover all critical facets and a verified textual bridge supports the combination.
- `PLAUSIBLE_COMPOSITION_RISK`: two or three eligible papers jointly cover all critical facets, but support is limited to a verified graph relation.
- `FRAGMENTED_PRECEDENT`: known components can be assembled only without a meaningful verified bridge, or require more than three papers.
- `RESIDUAL_NOVELTY`: at least one critical interaction or mechanism remains uncovered after an adequate search.
- `INCONCLUSIVE`: dates, full text, provider coverage, or evidence are insufficient for a defensible classification.

Novelty Risk is not identical to classification. Search Coverage and Evidence Confidence can force a downgrade to `INCONCLUSIVE`; they must never be averaged into one score.

## Verdict and Novelty Risk consistency

- `DIRECT_PRECEDENT`: `HIGH` or `MEDIUM`; `LOW` and `INCONCLUSIVE` are forbidden.
- `STRONG_COMPOSITION_RISK`: `HIGH` or `MEDIUM`; `LOW` and `INCONCLUSIVE` are forbidden.
- `PLAUSIBLE_COMPOSITION_RISK`: `HIGH` or `MEDIUM`; graph evidence alone cannot justify false precision.
- `FRAGMENTED_PRECEDENT`: normally `MEDIUM`, `LOW`, or `INCONCLUSIVE`. `HIGH` requires a non-empty structured `risk_basis` explaining the additional risk.
- `RESIDUAL_NOVELTY`: normally `MEDIUM` or `LOW`. `HIGH` requires a structured `risk_basis` whose type is `CRITICALITY_SENSITIVITY_COLLAPSE`, `CRITICALITY_DISPUTE`, or `OTHER_EXPLICIT_RISK`.
- `INCONCLUSIVE`: Novelty Risk must be `INCONCLUSIVE`.

When `risk_basis` is required, each entry must include a type and a concrete explanation. Sensitivity-based entries must be consistent with the frozen claim map and leave-one-out results.
