# Competitive landscape snapshot

Snapshot date: 2026-08-27. This is a positioning review, not a claim that adjacent projects lack value. Each comparison is pinned to the inspected commit so the technical claims do not silently drift with upstream changes. Star counts are intentionally omitted because they change continuously and do not affect product positioning.

| Project | Inspected commit | Strongest overlap | Material difference from NoveltyAudit |
|---|---|---|---|
| [OpenNovelty](https://github.com/january-blue/OpenNovelty) | [`f59f5f7`](https://github.com/january-blue/OpenNovelty/commit/f59f5f7f8af405e790b9b39f3869b4ce8a6c0b7a) | Claim extraction, semantic retrieval, full-text comparison, evidence-grounded novelty reports | Its public pipeline centers on contribution-to-paper comparison. The inspected code applies a publication cutoff at year granularity; the repository did not expose an MPS + textual bridge primitive. |
| [paper-search-pro](https://github.com/O0000-code/paper-search-pro) | [`d60dc10`](https://github.com/O0000-code/paper-search-pro/commit/d60dc10110e9efda934d3bb50796a01eab6f2fed) | Multi-source scholarly discovery, citation chasing, reproducible reports | Literature discovery is the product. It does not prosecute a frozen novelty claim through evidence-bound set cover and bridge-aware verdicts. |
| [agent-research-skills / novelty-assessment](https://github.com/lingzhi227/agent-research-skills/tree/main/skills/novelty-assessment) | [`9e6c085`](https://github.com/lingzhi227/agent-research-skills/commit/9e6c085d65e313e475e921fdfe795ac11eb7589e) | Iterative literature search and harsh-critic novelty checking | It emits a binary novel/not-novel decision and treats significant single-paper overlap as the decision unit. NoveltyAudit forbids absence-as-proof and tests multi-paper composition. |
| [polish_skill / idea-novelty-auditor](https://github.com/yujie-jason-zhang/polish_skill/tree/main/idea-novelty-auditor) | [`9b2a86c`](https://github.com/yujie-jason-zhang/polish_skill/commit/9b2a86ca6ac88879a3d3490fecdb909673fd1562) | Abstract-paradigm reasoning, dangerous baselines, reviewer attacks, claim boundaries | It is a strong positioning advisor, but its skill contract does not provide deterministic date resolution, evidence-bound MPS, or graph-to-text bridge promotion. |
| [QuantumNovelty](https://github.com/BoltzmannEntropy/QuantumNovelty/tree/main/skills/novelty_audit) | [`2a9d348`](https://github.com/BoltzmannEntropy/QuantumNovelty/commit/2a9d348eaba90a626b91596d871c483a09bf99f3) | Falsifiable novelty audit, retrieval preflight, provenance, adversarial checks | It is specialized to quantum-discovery Pareto rows and numerical manuscript claims. NoveltyAudit is domain-general and claim-facet/composition based. |
| [Agent Skills specification](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx) | [`69ef37e`](https://github.com/agentskills/agentskills/commit/69ef37e9424c0a7ea9dd2293b559e43ec8176379) | Portable skill format and progressive disclosure | NoveltyAudit follows this packaging standard; the specification is infrastructure, not a competing scholarly audit. |

## Collision assessment

The generic label “novelty audit” is crowded. The repository therefore must not market “LLM checks whether your paper is novel” as its differentiation. The defensible product wedge is the combined invariant set:

1. frozen atomic claim facets;
2. evidence-bound Minimal Prior Set of at most three papers;
3. graph discovery followed by textual Bridge Evidence promotion;
4. earliest-public-date temporal safety;
5. independent Novelty Risk, Search Coverage, and Evidence Confidence.

Search and provider breadth are replaceable infrastructure. The composition and audit contracts are the product.

At this snapshot, GitHub repository-name search returned no exact `NoveltyAudit` repository, so the proposed brand was not directly occupied. Name availability can change and should be rechecked immediately before publishing.
