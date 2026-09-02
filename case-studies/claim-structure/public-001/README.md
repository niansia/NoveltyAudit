# Public Case 001: RAG and residual novelty after claim decomposition

**Type:** `PUBLIC_CASE_STUDY`

**Failure mode:** `CLAIM_STRUCTURE_RESIDUAL_NOVELTY`

**Performance status:** Curated audit hypothesis; not yet run end to end

## Target

[Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html) describes RAG as a general-purpose recipe that combines a pre-trained sequence-to-sequence generator with a dense non-parametric Wikipedia memory accessed by a neural retriever.

The arXiv record first appeared on 2020-05-22. This case therefore uses 2020-05-21 as the strict historical cutoff.

## Claim decomposition to test

| Facet | Public prior | Audit interpretation |
|---|---|---|
| Pre-trained sequence-to-sequence generator | [BART](https://aclanthology.org/2020.acl-main.703/) | The generator component was already public. |
| Dense passage retrieval | [DPR](https://aclanthology.org/2020.emnlp-main.550/) | The dense retriever component was already public as a preprint. |
| Parametric model plus retrieved non-parametric memory | [REALM](https://proceedings.mlr.press/v119/guu20a.html) | An ancestor formulation was already public for retrieval-augmented language-model pre-training and extractive QA. |
| Generation-specific coupling, marginalization, and joint task fine-tuning | Target-specific question | This is the candidate residual contribution; it must be tested rather than assumed. |

The case illustrates a claim-structure audit: several ingredients are known, but that does not automatically erase the target's interaction-level contribution.

## Expected audit behavior

- Freeze the generator, retriever, memory, and interaction facets before retrieval.
- Treat BART + DPR as a candidate two-paper coverage set to test, not as an already-proven MPS.
- Search REALM as an ancestor term and distinguish its extractive or pre-training scope from RAG's generation scope.
- Preserve residual novelty around the generation-specific integration unless an eligible prior covers it with full-text evidence.
- Do not report a verdict or performance score from this curated decomposition alone.

## Source boundary

This case contains project-authored summaries and bibliographic metadata only. It does not copy the papers. ACL Anthology and PMLR source pages state CC BY 4.0 terms for the linked publications; the NeurIPS target is linked without asserting a redistribution license.

Machine-readable record: [`case.json`](case.json).
