# Empirical validation status

Snapshot date: 2026-08-27

NoveltyAudit's deterministic implementation is not evidence that it works on reviewer-grounded literature cases. This page records measured external-validation status and must not be replaced by synthetic fixtures or unit-test counts.

## Licensed source identified

- Dataset: [eacl2026-assessing-paper-novelty](https://tudatalib.ulb.tu-darmstadt.de/handle/tudatalib/4988)
- File: `data_novelty_assessment.zip`
- Official size: 219,589,883 bytes
- Official and locally verified MD5: `67d9e82abe79ed69ea5b5a3e4537ca3b`
- Dataset license: CC BY-NC 4.0
- Observed structure: 182 submission directories, 82 cases with `annotation.json`, 351 reviewer-text files, and 182 system structured representations.
- Human-label payload: 86 review outputs across the 82 annotated cases—63 `not_novel`, 18 `novel`, and 5 with a blank class.

The raw archive and extracted content are not committed or redistributed under this Apache-2.0 repository. Reproducible mappings may cite source case IDs, checksums, and derived evaluation records subject to the dataset license.

## Fixed first pilot

Selection rule: lexicographically first case ID among cases containing `annotation.json`. This rule was fixed before inspecting whether NoveltyAudit would succeed.

- Case ID: `09JVxsEZPf`
- Submission: “Towards Comprehensive and Efficient Post Safety Alignment of Large Language Models via Safety Patching”
- Human label: `not_novel`
- Reviewer-named prior components: SNIP; “Language Models are Super Mario”; HFT.
- Historical graph cutoff used for the pilot: 2024-05-21, the day before the target work's recorded first public date in the dataset's system metadata.

Targeted title-resolution diagnostics retrieved all three reviewer-named works from OpenAlex, but this is not a fair retrieval benchmark: the queries used gold titles and the aggregate search stopped at its explicit page budget. No Recall@5 or MRR is reported from this diagnostic.

Graph expansion results with verified OpenAlex work IDs:

| Pair | Backward records | Forward records | Limit exhausted | Third-paper bridge candidates |
| --- | ---: | ---: | --- | ---: |
| SNIP × Super Mario | 22 + 0 | 2 | No | 0 |
| SNIP × HFT | 22 + 0 | 0 | No | 0 |
| Super Mario × HFT | 0 + 0 | 0 | No | 0 |

This is a valid negative graph result, not a product success claim. It shows that the first reviewer `not_novel` label does not come with a qualifying third-paper graph bridge under this cutoff and provider snapshot. A full NoveltyAudit report still requires frozen facet decomposition, Tier-2 evidence, bibliography normalization, MPS recomputation, and independent adjudication.

The pilot also exposed a real integration defect: deduplication could preserve the first canonical work ID while overwriting its provider ID with a duplicate OpenAlex version. That caused a false zero-reference backward expansion. Version 0.3.1 now preserves the canonical first version's provider ID; the table above is from the corrected rerun.

## Current measured counters

| Counter | Current value |
| --- | ---: |
| Licensed reviewer-grounded cases exercised through real provider graph expansion | 1 |
| Complete end-to-end reviewer-grounded NoveltyAudit reports | 0 |
| Third-paper bridge candidates recovered across the three fixed pilot pairs | 0 |
| Published benchmark metrics | N/A — not measured |

The next milestone is a preregistered multi-case pilot with blind query construction and independent annotation/adjudication. Until then, NoveltyAudit must not claim retrieval quality, bridge recall, calibration, or reviewer prediction performance.
