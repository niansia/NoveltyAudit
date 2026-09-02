# Reviewer-grounded Case 001: SafePatching as a composition attack

**Type:** `REVIEWER_GROUNDED`

**Failure mode:** `COMPOSITION_ATTACK`

**Source case:** TUdatalib `tudatalib/4988`, case `09JVxsEZPf`

**Performance status:** Targeted diagnostic only; no end-to-end NoveltyAudit score

## Target

[Towards Comprehensive and Efficient Post Safety Alignment of Large Language Models via Safety Patching](https://arxiv.org/abs/2405.13820) proposes SafePatching for safety enhancement, over-safety mitigation, and utility preservation. The target first appeared on arXiv on 2024-05-22, so this case uses the strict historical cutoff 2024-05-21.

## Reviewer-grounded concern

The licensed novelty-assessment record derives a multi-work concern from reviewer feedback: the target's controllable patching method appears to draw on SNIP's parameter-importance score and prior sparse-retention or model-merging ideas represented by Super Mario and HFT, while the distinctive advancement was not sufficiently isolated.

This is a paraphrase, not copied review text. It supports a composition *question*, not an automatically adjudicated MPS or verdict.

## Reviewer-named priors

1. [SNIP: Single-shot Network Pruning based on Connection Sensitivity](https://arxiv.org/abs/1810.02340) - connection-sensitivity scoring used as the parameter-importance mechanism.
2. [Language Models are Super Mario: Absorbing Abilities from Homologous Models as a Free Lunch](https://arxiv.org/abs/2311.03099) - sparse delta-parameter retention and model merging.
3. [HFT: Half Fine-Tuning for Large Language Models](https://arxiv.org/abs/2404.18466) - partial-parameter updating that preserves prior capabilities.

All three works appear in the target submission's bibliography. This case therefore must **not** be described as a missing-bibliography case.

## Expected audit behavior

- Recover all three named priors using mechanism and ancestor queries, without starting from their gold titles.
- Treat the concern as a possible multi-paper composition, not as proof that one paper is a direct precedent.
- Bind each claimed overlap to full text before constructing an MPS.
- Preserve the strict 2024-05-21 cutoff: SNIP, Super Mario, and the HFT preprint were public by then.
- Return `INCONCLUSIVE` rather than manufacture an MPS if the exact SafePatching interaction cannot be evidence-mapped.

## What is and is not measured

The existing project diagnostic resolved the reviewer-named titles and examined graph coverage, but it used gold titles and did not run a blind, end-to-end audit. This case therefore reports neither Recall@5 nor an expected NoveltyAudit verdict.

Machine-readable record: [`case.json`](case.json). Source and reuse restrictions are recorded there and in [`docs/DATA_LICENSES.md`](../../../docs/DATA_LICENSES.md).
