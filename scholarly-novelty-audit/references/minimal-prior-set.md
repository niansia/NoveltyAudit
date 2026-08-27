# Minimal Prior Set

Let the frozen critical facets be `F`. A Minimal Prior Set (MPS) is the smallest set of eligible prior papers whose evidence-bound `EXACT` or `FUNCTIONAL` coverage union contains every facet in `F`.

The implemented MPS search bound is `K ≤ 3`: enumerate combinations of size 1, then 2, then 3. Stop at the first size with valid sets, but retain all sets of that minimum size for bridge comparison. Every report must state this bound. If none is found, say only that no qualifying evidence-bound set of size three or smaller was found and explicitly state that larger combinations were not assessed. Sets larger than three may be described as fragmented background; do not treat them as a strong composition kill.

No final MPS may depend on Tier-1 `LIKELY` labels, a post-cutoff paper, a date-uncertain paper in strict mode, or a coverage label without evidence. If Tier-2 review removes coverage, solve again.

Rank same-size sets lexicographically by verified bridge class, evidence completeness, then earlier dates. Do not hide alternative minimal sets.

Every endpoint combination in every recomputed multi-paper MPS is a graph-expansion obligation. Only a `COMPLETE` expansion satisfies it. If any required pair is absent or `PARTIAL`, do not assert that precedent is fragmented or otherwise issue a conclusive composition verdict: return `INCONCLUSIVE` and record `GRAPH_EXPANSION_INCOMPLETE:<smaller-paper-id>:<larger-paper-id>` in `search.gaps`.
