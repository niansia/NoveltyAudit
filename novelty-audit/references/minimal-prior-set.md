# Minimal Prior Set

Let the frozen critical facets be `F`. A Minimal Prior Set (MPS) is the smallest set of eligible prior papers whose evidence-bound `EXACT` or `FUNCTIONAL` coverage union contains every facet in `F`.

Enumerate combinations of size 1, then 2, then 3. Stop at the first size with valid sets, but retain all sets of that minimum size for bridge comparison. Sets larger than three may be described as fragmented background; do not treat them as a strong composition kill.

No final MPS may depend on Tier-1 `LIKELY` labels, a post-cutoff paper, a date-uncertain paper in strict mode, or a coverage label without evidence. If Tier-2 review removes coverage, solve again.

Rank same-size sets lexicographically by verified bridge class, evidence completeness, then earlier dates. Do not hide alternative minimal sets.

