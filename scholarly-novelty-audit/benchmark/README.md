# Benchmark data policy

This directory intentionally ships schemas and metric code, not third-party reviewer data. Public releases must preserve each source dataset's license and attribution. In particular, code licenses and dataset licenses must not be conflated.

Primary retrieval metrics are Overlooked Killer Recall@5 and MRR on reviewer-cited papers absent from the submission bibliography. Composition cases additionally score Minimal Prior Set recall, bridge classification, temporal leakage, and evidence-supported claim rate.

Gold records must validate against `annotation.schema.json`; system outputs must validate against `prediction.schema.json`. Join them with `metrics.metric_case(annotation, prediction)` before passing the normalized record to retrieval metrics. This keeps gold field names and prediction field names explicit instead of relying on an undocumented adapter.

The first external source under evaluation is TUdatalib item `tudatalib/4988`, `eacl2026-assessing-paper-novelty` (CC BY-NC 4.0; official file MD5 `67d9e82abe79ed69ea5b5a3e4537ca3b`). Its raw data must not be relicensed or bundled into this Apache-2.0 repository. The observed archive has 182 submission directories but only 82 cases with human annotation payloads. See the repository's `docs/empirical-status.md` for the fixed pilot, exact current counters, and limitations, and `docs/DATA_LICENSES.md` for the derived-aggregate notice.

## Bridge base-rate measurement

`bridge_base_rate.py` reads the official ZIP directly and does not use an LLM. It conservatively links explicit novelty-statement mentions, numbered reviewer bibliographies, DOI/arXiv identifiers, and release-provided Semantic Scholar records. Every annotated case remains in the output, including extraction gaps, unresolved endpoints, rate limits, and result-cap exhaustion.

```bash
python scholarly-novelty-audit/benchmark/bridge_base_rate.py \
  --dataset-zip /path/to/data_novelty_assessment.zip \
  --output run/bridge-base-rate-cases.json \
  --summary-output run/bridge-base-rate-summary.json \
  --cache run/bridge-base-rate-cache.json \
  --snapshot-date 2026-08-27 \
  --submission-date 2024-10-01 \
  --max-paid-calls 100
```

The detailed output contains reviewer-derived case mappings and remains subject to CC BY-NC 4.0; do not commit or relicense it without review. The public aggregate snapshot is `docs/bridge-base-rate-summary.json`.

The measurement never equates a numeric zero with evidence of absence. It separately records incomplete queries, unresolved endpoints, OpenAlex-empty references, cross-provider coverage gaps, and the opportunity window between the newer endpoint and the historical cutoff. Co-citation rates are reported under multiple citation-count sensitivity guards so a few classic papers cannot silently dominate the result. The exact binomial interval is retained only for the case-level 4/18 estimate; pair-level rates are descriptive because pairs are clustered within cases. The ≥2-prior statistic is a deterministically detected rate, not a formal statistical lower bound or composition-objection prevalence, because extracted links have not yet received an independent precision audit.
