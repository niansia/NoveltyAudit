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

The raw archive and extracted content are not committed or redistributed under this Apache-2.0 repository. Reproducible mappings may cite source case IDs, checksums, and derived evaluation records subject to the dataset license. See [data and derived-artifact notices](DATA_LICENSES.md).

## Fixed first pilot

Selection rule: lexicographically first case ID among cases containing `annotation.json`. This rule was fixed before inspecting whether NoveltyAudit would succeed.

- Case ID: `09JVxsEZPf`
- Submission: “Towards Comprehensive and Efficient Post Safety Alignment of Large Language Models via Safety Patching”
- Human label: `not_novel`
- Reviewer-named prior components: SNIP; “Language Models are Super Mario”; HFT.
- Historical graph cutoff used for the pilot: 2024-05-21, the day before the target work's recorded first public date in the dataset's system metadata.

Targeted title-resolution diagnostics retrieved all three reviewer-named works from OpenAlex, but this is not a fair retrieval benchmark: the queries used gold titles and the aggregate search stopped at its explicit page budget. No Recall@5 or MRR is reported from this diagnostic.

Graph expansion results with verified OpenAlex work IDs:

| Pair | Backward records | Forward records | Opportunity after newer endpoint | Third-paper bridge candidates |
| --- | ---: | ---: | ---: | ---: |
| SNIP × Super Mario | 22 + 0 | 2 | 197 days | 0 |
| SNIP × HFT | 22 + 0 | 0 | 22 days | 0 |
| Super Mario × HFT | 0 + 0 | 0 | 22 days | 0 |

The three zeros are not evidence that the three works were historically disconnected. Semantic Scholar reports 49, 74, and 75 references for SNIP, Super Mario, and HFT, while the corresponding OpenAlex snapshot exposes 29, 0, and 0. Every pair therefore has an OpenAlex endpoint-coverage caveat, and every pair also has less than 18 months between its newer endpoint and the cutoff. The correct result is `ZERO_WITH_SHORT_WINDOW_AND_COVERAGE_CAVEAT`, not an unqualified negative bridge finding.

The pilot also exposed a real integration defect: deduplication could preserve the first canonical work ID while overwriting its provider ID with a duplicate OpenAlex version. That caused a false zero-reference backward expansion. Version 0.3.1 now preserves the canonical first version's provider ID; the table above is from the corrected rerun.

## 82-case bridge base-rate measurement

The official archive's 82 annotated cases were measured without LLMs, facet decomposition, or Tier-2 retrieval. Reviewer novelty statements were deterministically linked to paper records already present in the release, including numbered reviewer bibliographies. Semantic Scholar supplied batched identifiers and reference counts; OpenAlex supplied work resolution, reference coverage, and unfiltered co-citation queries. Each case uses the day before the earlier of a matched target public date and the official [ICLR 2025 full-paper deadline](https://iclr.cc/Conferences/2025/CallForPapers), 2024-10-01. Provider-side date filtering was not used for bridge queries; the cutoff was applied locally.

The complete aggregate is machine-readable in [`bridge-base-rate-summary.json`](bridge-base-rate-summary.json).

| Measurement | Result |
| --- | ---: |
| Annotated cases represented | 82 / 82 |
| Cases with at least one deterministically detected named prior | 37 |
| Cases with at least two deterministically detected named priors | 23 / 82 (28.05% detected rate, not composition objections) |
| Named priors | 83 |
| OpenAlex-resolved priors | 77 / 83 (92.77%) |
| Priors with nonempty OpenAlex references | 21 / 83 (25.30%) |
| Confirmed OpenAlex-empty / Semantic Scholar-nonempty gaps | 35 / 83 (42.17%) |
| Observed nonempty backward coverage with Semantic Scholar fallback | 56 / 83 (67.47% lower bound) |
| Complete multi-prior cases | 18 |
| Complete endpoint pairs | 72 / 74 |
| Complete cases with at least one pre-cutoff bridge | 4 / 18 (22.22%; exact 95% interval 6.41%–47.64%) |
| Complete pairs with at least one pre-cutoff bridge | 12 / 72 (16.67%, descriptive; pairs are clustered within 18 cases) |
| Pair bridge rate after citation-count sensitivity guards | 8.47%–12.12% |
| Complete pairs with less than 18 months of observation | 61 / 72 (84.72%) |
| Median pair opportunity window | 224 days |

The 60 complete zero-bridge pairs split into four materially different states:

| Zero state | Pairs |
| --- | ---: |
| Short window and provider-coverage caveat | 56 |
| Provider-coverage caveat only | 2 |
| Short observation window only | 1 |
| Zero under a complete, ≥18-month, nonempty provider snapshot | 1 |

Two additional high-base-rate pairs returned more than the 1,000-work measurement cap and are `UNINTERPRETABLE_INCOMPLETE_QUERY`; they are excluded from all zero and complete-case denominators. Pair rates remained between 8.47% and 12.12% across endpoint thresholds 50, 100, 250, 500, and 1,000. Version 0.3.1 therefore uses 500 as a sensitivity-checked operational guard. This is not universal field calibration or a performance claim, and a preregistered field policy may override it.

Twenty-three of 82 cases (28.05%) had at least two deterministically detected reviewer-named priors. Another 23 cases are `POTENTIAL_MISSED_MENTIONS`, so the detector likely undercounts explicit mentions; however, extracted links have not yet been independently precision-audited, false positives cannot be assumed to be zero, and 28.05% is not asserted as a formal statistical lower bound. It also does not measure the prevalence of compositional novelty objections, because mentioning two works does not establish that the reviewer treated their combination as an attack.

### Product interpretation

Bridge Evidence is not a universal primary signal. It is a conditional positive signal for longer-window, adequately covered literature neighborhoods. Four of 18 complete multi-prior cases were positive, so bridges were a minority in this sample; the case-level exact interval is wide enough that this is not a precise population estimate. The 12/72 pair rate is descriptive only because multiple pairs share cases, reviewers, fields, cutoffs, and papers. Pair rates remained roughly 8%–12% under the tested citation guards, OpenAlex backward-reference coverage is often missing, and most endpoint pairs are too recent to have accumulated a survey or co-citation trail.

The product hierarchy is therefore:

1. exact historical cutoff, frozen claim facets, and evidence-bound Minimal Prior Sets;
2. ancestor terminology and overlooked-killer retrieval;
3. Bridge Evidence as a useful positive signal in longer-window fields, never as silent negative reassurance.

Runtime `graph-preflight` now exposes the observation window before provider calls. `expand-graph` unions every available OpenAlex and Semantic Scholar backward route, unions forward candidates in shared namespaces, and records provider-attributed endpoint observations, historical versus landscape candidates, and a deterministic negative-result scope. The measured 35 OpenAlex-empty/Semantic Scholar-nonempty priors directly motivated this runtime change. A zero cannot be reported without these diagnostics.

## Current measured counters

| Counter | Current value |
| --- | ---: |
| Licensed annotated cases included in deterministic batch measurement | 82 |
| Complete end-to-end reviewer-grounded NoveltyAudit reports | 0 |
| Complete multi-prior cases in the bridge base-rate study | 18 |
| Complete cases with a pre-cutoff graph bridge | 4 |
| Published retrieval Recall@5 / MRR | N/A — not measured |

This measurement answers prevalence, provider coverage, age, and graph base-rate questions; it does not validate facet coverage, textual bridge meaning, retrieval quality, or reviewer prediction. The next milestone remains a preregistered multi-case end-to-end pilot with blind query construction and independent annotation/adjudication.
