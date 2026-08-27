# Benchmark data policy

This directory intentionally ships schemas and metric code, not third-party reviewer data. Public releases must preserve each source dataset's license and attribution. In particular, code licenses and dataset licenses must not be conflated.

Primary retrieval metrics are Overlooked Killer Recall@5 and MRR on reviewer-cited papers absent from the submission bibliography. Composition cases additionally score Minimal Prior Set recall, bridge classification, temporal leakage, and evidence-supported claim rate.

Gold records must validate against `annotation.schema.json`; system outputs must validate against `prediction.schema.json`. Join them with `metrics.metric_case(annotation, prediction)` before passing the normalized record to retrieval metrics. This keeps gold field names and prediction field names explicit instead of relying on an undocumented adapter.

The first external source under evaluation is TUdatalib item `tudatalib/4988`, `eacl2026-assessing-paper-novelty` (CC BY-NC 4.0; official file MD5 `67d9e82abe79ed69ea5b5a3e4537ca3b`). Its raw data must not be relicensed or bundled into this Apache-2.0 repository. The observed archive has 182 submission directories but only 82 cases with human annotation payloads. See the repository's `docs/empirical-status.md` for the fixed pilot, exact current counters, and limitations.
