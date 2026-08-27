# Benchmark data policy

This directory intentionally ships schemas and metric code, not third-party reviewer data. Public releases must preserve each source dataset's license and attribution. In particular, code licenses and dataset licenses must not be conflated.

Primary retrieval metrics are Overlooked Killer Recall@5 and MRR on reviewer-cited papers absent from the submission bibliography. Composition cases additionally score Minimal Prior Set recall, bridge classification, temporal leakage, and evidence-supported claim rate.

Gold records must validate against `annotation.schema.json`; system outputs must validate against `prediction.schema.json`. Join them with `metrics.metric_case(annotation, prediction)` before passing the normalized record to retrieval metrics. This keeps gold field names and prediction field names explicit instead of relying on an undocumented adapter.
