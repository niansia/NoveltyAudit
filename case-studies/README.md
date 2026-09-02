# NoveltyAudit case studies

Tests show that the implementation obeys its contracts. These case studies explain why those contracts matter in real research workflows.

The directory is intentionally separate from `scholarly-novelty-audit/references/`, which contains instructions loaded by the Agent Skill, and from `scholarly-novelty-audit/benchmark/`, which contains evaluation schemas and metric code. Case studies are public, source-attributed failure-mode records for people and tools.

## Initial cases

| Failure mode | Case | Evidence status | Performance status |
|---|---|---|---|
| Missing killer paper | [Synthetic missing-killer fixture](missing-killer-paper/synthetic-001/README.md) | `SYNTHETIC` | Contract fixture, not a benchmark |
| Multi-paper composition attack | [SafePatching reviewer-grounded case](composition-attack/reviewer-grounded-001/README.md) | `REVIEWER_GROUNDED` | Targeted diagnostic only; no end-to-end score |
| Claim structure and residual novelty | [RAG public literature case](claim-structure/public-001/README.md) | `PUBLIC_CASE_STUDY` | Curated audit hypothesis; not yet run end to end |

Each case includes a human-readable `README.md` and a machine-readable `case.json` validated by [`case.schema.json`](case.schema.json). The labels are deliberately different:

- `SYNTHETIC` is a designed contract example.
- `REVIEWER_GROUNDED` is anchored in a licensed reviewer-derived source.
- `PUBLIC_CASE_STUDY` is a project-authored decomposition of public literature, not reviewer gold.

No case may turn a hypothesis, diagnostic, or synthetic fixture into a retrieval metric or reviewer-prediction claim. Current end-to-end reviewer-grounded Recall@5 and MRR remain unmeasured.

## Data and copyright boundary

This directory stores identifiers, source URLs, project-authored summaries, and minimal derived labels. It does not store third-party PDFs, review text, or dataset dumps.

- Project-authored case structure and synthetic text follow the repository's Apache-2.0 license.
- Dataset-derived fields retain the source dataset's stated terms. The reviewer-grounded case uses TUdatalib item `tudatalib/4988`, released under CC BY-NC 4.0.
- Public OpenReview comments are CC BY 4.0 under the [OpenReview Terms of Use](https://openreview.net/legal/terms). An article's own license is separate.
- Linked papers remain under their publishers' or authors' licenses. Linking metadata does not relicense the papers.

See [`docs/DATA_LICENSES.md`](../docs/DATA_LICENSES.md) for the repository-level notice.

## Contributing a case

Submit the smallest record that makes the failure mode auditable:

1. Copy one existing case directory and choose exactly one `case_type` and `failure_mode`.
2. Include stable identifiers, a historical cutoff, author-bibliography status, expected audit behavior, provenance, source license, and limitations.
3. Prefer DOI, arXiv, OpenAlex, Semantic Scholar, OpenReview, or dataset case IDs over copied text.
4. Do not submit paper PDFs, review dumps, confidential manuscripts, or content without redistribution permission.
5. Use `null`, `NOT_ASSESSED`, or `NOT_RUN` instead of inventing a label or performance result.
6. Run `python -m pytest scholarly-novelty-audit/tests -q`; the case-study schema test validates every `case.json`.

Have a reviewer-grounded novelty failure case? Open a Discussion first if its license or anonymity boundary is unclear.
