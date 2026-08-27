# Adversarial query families

Run distinct query families; paraphrases of one family do not establish broad coverage.

1. **Literal:** distinctive phrases and declared contribution wording.
2. **Mechanism:** core operation plus close technical synonyms.
3. **Problem/function:** what the mechanism accomplishes without the author's new name.
4. **Ancestor:** historically attested predecessor terminology.
5. **Cross-domain:** the same mechanism in adjacent fields.
6. **Citation expansion:** backward and forward expansion from strong candidates using the bundled `expand-graph` command; preserve its call log, bridge candidate IDs, and provider failures.
7. **Composition bridge:** pairs of facet families plus `survey`, `taxonomy`, `extension`, `comparison`, or a shared benchmark.
8. **Negative control:** nearby papers expected not to cover the mechanism, used to detect overly broad matching.

Log the exact query, provider, timestamp, result count, truncation, and failure status in `search.query_runs`. `BROAD` requires successful structured query logs from at least two supported providers and successful runs for every required family. Stop only when required families ran and another expansion round adds no new high-threat paper or critical-facet coverage.
