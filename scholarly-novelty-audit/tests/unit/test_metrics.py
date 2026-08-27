import importlib.util
from pathlib import Path


path = Path(__file__).resolve().parents[2] / "benchmark" / "metrics.py"
spec = importlib.util.spec_from_file_location("novelty_metrics", path)
metrics = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(metrics)


def test_retrieval_metrics():
    cases = [
        {"bibliography_absent_gold": ["A", "B"], "gold": ["A", "B"], "ranked_papers": ["X", "A", "B"]},
        {"bibliography_absent_gold": ["C"], "gold": ["C"], "ranked_papers": ["Y", "Z"]},
    ]
    assert metrics.bibliography_absent_killer_recall_at_k(cases, 2) == 1 / 3
    assert metrics.mean_reciprocal_rank(cases) == 0.25


def test_safety_and_mps_metrics():
    assert metrics.temporal_leakage_rate([{"cutoff_status": "ELIGIBLE"}, {"cutoff_status": "POST_CUTOFF"}]) == 0.5
    assert metrics.minimal_prior_set_recall([["A", "B"]], [["B", "A"], ["C"]]) == 0.5
    assert metrics.evidence_supported_claim_rate([{"evidence_ids": ["E"]}, {"evidence_ids": []}]) == 0.5


def test_schema_records_wire_directly_into_metrics_adapter():
    annotation = {"case_id": "C1", "not_in_supplied_bibliography": ["A"], "gold_prior_set": ["A", "B"]}
    prediction = {"case_id": "C1", "ranked_papers": ["A", "X"], "predicted_prior_sets": [["A", "B"]], "verdict_paper_ids": ["A", "B"], "report_claims": [{"text": "covered", "evidence_ids": ["E1"]}]}
    case = metrics.metric_case(annotation, prediction)
    assert metrics.bibliography_absent_killer_recall_at_k([case], 1) == 1.0
    assert metrics.mean_reciprocal_rank([case]) == 1.0
    assert metrics.minimal_prior_set_recall(case["predicted_prior_sets"], case["gold_prior_sets"]) == 1.0
