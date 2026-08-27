# Competitive landscape snapshot

Snapshot date: 2026-08-27. This is a positioning review, not a claim that adjacent projects lack value. Each comparison is pinned to the inspected commit so the technical claims do not silently drift with upstream changes. Star counts are intentionally omitted because they change continuously and do not affect product positioning.

| Project | Inspected commit | Strongest overlap | Material difference from NoveltyAudit |
|---|---|---|---|
| [OpenNovelty](https://github.com/january-blue/OpenNovelty) | [`f59f5f7`](https://github.com/january-blue/OpenNovelty/commit/f59f5f7f8af405e790b9b39f3869b4ce8a6c0b7a) | Claim extraction, semantic retrieval, full-text comparison, evidence-grounded novelty reports | Its public pipeline centers on contribution-to-paper comparison. The inspected code applies a publication cutoff at year granularity; the repository did not expose an MPS + textual bridge primitive. |
| [paper-search-pro](https://github.com/O0000-code/paper-search-pro) | [`d60dc10`](https://github.com/O0000-code/paper-search-pro/commit/d60dc10110e9efda934d3bb50796a01eab6f2fed) | Multi-source scholarly discovery, citation chasing, reproducible reports | Literature discovery is the product. It does not prosecute a frozen novelty claim through evidence-bound set cover and bridge-aware verdicts. |
| [Auto-claude-code-research-in-sleep / novelty-check](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/94d8093ed21d20a790830318190095b9f5036ce8/skills/novelty-check/SKILL.md) | [`94d8093`](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/commit/94d8093ed21d20a790830318190095b9f5036ce8) | Fast claim extraction, multi-source search, cross-model review, verified closest-work table, proceed/caution/abandon positioning | Its decision unit is the specific closest paper and claimed delta. NoveltyAudit's forensic mode requires frozen facets, bounded multi-paper MPS, historical bridge evidence, and schema-checked acquisition provenance. |
| [agent-research-skills / novelty-assessment](https://github.com/lingzhi227/agent-research-skills/tree/main/skills/novelty-assessment) | [`9e6c085`](https://github.com/lingzhi227/agent-research-skills/commit/9e6c085d65e313e475e921fdfe795ac11eb7589e) | Iterative literature search and harsh-critic novelty checking | It emits a binary novel/not-novel decision and treats significant single-paper overlap as the decision unit. NoveltyAudit forbids absence-as-proof and tests multi-paper composition. |
| [polish_skill / idea-novelty-auditor](https://github.com/yujie-jason-zhang/polish_skill/tree/main/idea-novelty-auditor) | [`9b2a86c`](https://github.com/yujie-jason-zhang/polish_skill/commit/9b2a86ca6ac88879a3d3490fecdb909673fd1562) | Abstract-paradigm reasoning, dangerous baselines, reviewer attacks, claim boundaries | It is a strong positioning advisor, but its skill contract does not provide deterministic date resolution, evidence-bound MPS, or graph-to-text bridge promotion. |
| [Eureka / novelty-competitive-audit](https://github.com/jeonnoin-alt/Eureka/blob/9f3d28a14b0b35010d8da6f2116aa3b4b8b790ff/skills/novelty-competitive-audit/SKILL.md) | [`9f3d28a`](https://github.com/jeonnoin-alt/Eureka/commit/9f3d28a14b0b35010d8da6f2116aa3b4b8b790ff) | Submission-time recent-preemption search, contribution-altitude review, differentiation rubric, PASS/CONCERN/BLOCK gate | It is a workflow gate for field drift near submission. NoveltyAudit instead reconstructs what was publicly available by an exact cutoff and validates multi-paper coverage plus bridge routes. |
| [research-direction-discovery](https://github.com/0neblaze/research-direction-discovery/blob/58ad97f94ba5dad63364954b01844f7efc443edf/skills/research-direction-discovery/SKILL.md) | [`58ad97f`](https://github.com/0neblaze/research-direction-discovery/commit/58ad97f94ba5dad63364954b01844f7efc443edf) | Topic discovery, three-round novelty audit, feasibility, formalization, kill criteria, pivot planning | It owns the broader decision from topic selection to prospectus. NoveltyAudit is the narrower forensic prosecution component and emits a machine-validated evidence record rather than a direction-management workspace. |
| [Microsoft ResearchStudio](https://github.com/microsoft/ResearchStudio) | [`6eee5a7`](https://github.com/microsoft/ResearchStudio/commit/6eee5a726ef70d8db20b41814fea290c7c173e0d) | Integrated research-idea generation and evaluation workflow with novelty-audit steps | It orchestrates the research lifecycle. NoveltyAudit is installable as a specialized audit primitive when historical composition and evidence provenance matter. |
| [QuantumNovelty](https://github.com/BoltzmannEntropy/QuantumNovelty/tree/main/skills/novelty_audit) | [`2a9d348`](https://github.com/BoltzmannEntropy/QuantumNovelty/commit/2a9d348eaba90a626b91596d871c483a09bf99f3) | Falsifiable novelty audit, retrieval preflight, provenance, adversarial checks | It is specialized to quantum-discovery Pareto rows and numerical manuscript claims. NoveltyAudit is domain-general and claim-facet/composition based. |
| [Agent Skills specification](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx) | [`69ef37e`](https://github.com/agentskills/agentskills/commit/69ef37e9424c0a7ea9dd2293b559e43ec8176379) | Portable skill format and progressive disclosure | NoveltyAudit follows this packaging standard; the specification is infrastructure, not a competing scholarly audit. |

## Collision assessment

The generic label “novelty audit” is crowded. Version 0.3.1 therefore distributes the narrower `scholarly-novelty-audit` skill and does not market “LLM checks whether your paper is novel” as its differentiation. The defensible product wedge is the combined invariant set:

1. frozen atomic claim facets;
2. evidence-bound Minimal Prior Set of at most three papers;
3. graph discovery followed by textual Bridge Evidence promotion;
4. earliest-public-date temporal safety;
5. independent Novelty Risk, Search Protocol Coverage, and Evidence Confidence.

Search and provider breadth are replaceable infrastructure. The composition and audit contracts are the product.

## Market-category view

| Category | Representative projects | Their natural strength | NoveltyAudit's boundary and advantage |
|---|---|---|---|
| Quick novelty checker | `novelty-check`, `novelty-assessment` | Fast closest-paper discovery and a direct proceed/reject recommendation | Forensic use only: evidence acquisition, exact cutoff, machine invariants, and multi-paper composition |
| Positioning advisor | `idea-novelty-auditor` | Reviewer attack, dangerous baselines, and defensible framing | Reproducible candidate/evidence contract and deterministic conclusion constraints |
| Research workflow | ResearchStudio, `research-direction-discovery` | Topic generation, feasibility, planning, gates, and pivots | A focused prosecution primitive that can fit inside a larger workflow |
| Submission gate | Eureka `novelty-competitive-audit` | Recent preemption and submission-time competitiveness | Exact historical cutoff plus Minimal Prior Set and Bridge Evidence |
| Domain-specific audit | QuantumNovelty | Numerical falsification for quantum claims | Domain-general claim-facet and composition semantics |
| Paper comparison system | OpenNovelty | Full-text comparison against individual papers | Bounded multi-paper coverage, historical connectability, and invariant validation |

At this snapshot, GitHub repository-name search returned no exact `NoveltyAudit` repository, so the proposed brand was not directly occupied. Name availability can change and should be rechecked immediately before publishing.
