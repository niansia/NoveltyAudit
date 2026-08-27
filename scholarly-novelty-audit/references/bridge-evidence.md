# Bridge Evidence

Coverage alone does not establish that combining papers was historically natural.

## Discovery and promotion

First discover graph candidates deterministically: direct citation, co-citation by a third paper, or a shared citation neighborhood. Retrieve graph neighborhoods without provider-side date filtering, then enforce the cutoff with the local earliest-public-date resolver. This avoids losing an eligible preprint behind a later provider publication date and keeps post-cutoff sources available for landscape review.

Absence of a bridge is interpretable only after a complete graph expansion. Use each graph result's explicit provider-exhaustion signal rather than inferring truncation from result count. If any backward or forward traversal is not exhausted, record `possibly_truncated=true`, set the expansion to `PARTIAL` with `LIMIT_REACHED`, disclose the pair-specific search gap, and use `INCONCLUSIVE`. An exact-limit result is complete only when the provider also reports no continuation. Do not convert “none found within the budget” into `FRAGMENTED_PRECEDENT`.

Even a complete zero is conditional. Run `graph-preflight` before retrieval, then inspect each endpoint's provider-attributed observations after retrieval. `EMPTY_AT_PROVIDER` means only that one provider returned no backward records, not that the paper has no bibliography; the default expansion unions available OpenAlex and Semantic Scholar backward routes. Report `observation_window_days` and `observation_window_status`, measured from the newer endpoint's earliest verified public date to the cutoff, because recent pairs may not have had time to accumulate a survey or co-citing third paper. `MEETS_DIAGNOSTIC_THRESHOLD` means only that the exploratory 548-day threshold was met; it is not a maturity claim. Missing endpoint dates and post-cutoff endpoints receive distinct uninterpretable scopes. Use the deterministic `negative_result_scope` and retain the numeric facts; never collapse provider coverage, observation-window length, date uncertainty, and evidence of absence into the same zero.

Then inspect text and classify only supported relations:

- `EXPLICIT_EXTENSION`: one work states that it extends, adapts, or builds on the other;
- `SHARED_BENCHMARK`: a source directly compares both methods;
- `TAXONOMY_BRIDGE`: a survey places both in the same technical family;
- `SYNTHESIS_BRIDGE`: a source explains their complementary relationship;
- `COMBINATION_BRIDGE`: a source explicitly combines the relevant mechanisms.

`DIRECT_CITATION` and `CO_CITATION` are graph-only signals. They can support `PLAUSIBLE_COMPOSITION_RISK`, but never `STRONG_COMPOSITION_RISK` without textual evidence. A co-citation route qualifies only when both endpoint citation counts are known and below the documented `high_citation_threshold`. Version 0.3.1 defaults to 500 with status `SENSITIVITY_CHECKED`: the exploratory 82-case table was comparatively flat from 50 through 1,000, but this is an operational guard, not universal field calibration. A sourced custom threshold is `DOCUMENTED_OVERRIDE`; `CALIBRATED` requires machine-readable dataset and method provenance plus `preregistered=true`. If counts are missing, mark the route `UNASSESSED`; if either endpoint reaches the threshold, mark it `HIGH_BASE_RATE`. Neither status may strengthen the verdict.

Do not discard a bridge merely because its source appeared after the audit cutoff. Route it to `landscape_bridges` as `LANDSCAPE_BRIDGE`, retain its underlying graph type and date status, and set `affects_historical_verdict: false`. Explain that the connection was unavailable at the historical cutoff but may be visible to a present-day reviewer.

Every textual bridge source must be returned to the candidate pool and checked for direct facet coverage before finalizing the MPS. If the bridge source itself contains the claimed mechanism or interaction, solve the MPS again; do not leave it labeled as “bridge only.” Record `source_rechecked_as_candidate: true` in the report.
