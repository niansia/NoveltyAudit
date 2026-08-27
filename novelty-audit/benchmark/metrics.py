"""Reference metrics for reviewer-grounded novelty benchmarks."""

from __future__ import annotations

from typing import Iterable, Sequence


def metric_case(annotation: dict, prediction: dict) -> dict:
    """Join schema-valid gold annotation and prediction records for metrics."""
    if annotation.get("case_id") != prediction.get("case_id"):
        raise ValueError("annotation and prediction case_id values must match")
    return {
        "case_id": annotation["case_id"],
        "overlooked_gold": list(annotation.get("overlooked_by_author") or []),
        "gold": list(annotation.get("gold_prior_set") or []),
        "gold_prior_sets": [list(annotation.get("gold_prior_set") or [])],
        "ranked_papers": list(prediction.get("ranked_papers") or []),
        "predicted_prior_sets": list(prediction.get("predicted_prior_sets") or []),
        "verdict_paper_ids": list(prediction.get("verdict_paper_ids") or []),
        "report_claims": list(prediction.get("report_claims") or []),
    }


def overlooked_killer_recall_at_k(cases: Iterable[dict], k: int = 5) -> float:
    numerator = 0
    denominator = 0
    for case in cases:
        gold = set(case.get("overlooked_gold") or [])
        retrieved = set((case.get("ranked_papers") or [])[:k])
        numerator += len(gold & retrieved)
        denominator += len(gold)
    return numerator / denominator if denominator else 0.0


def mean_reciprocal_rank(cases: Iterable[dict]) -> float:
    scores = []
    for case in cases:
        gold = set(case.get("gold") or [])
        score = 0.0
        for rank, paper_id in enumerate(case.get("ranked_papers") or [], start=1):
            if paper_id in gold:
                score = 1.0 / rank
                break
        scores.append(score)
    return sum(scores) / len(scores) if scores else 0.0


def temporal_leakage_rate(verdict_papers: Sequence[dict]) -> float:
    if not verdict_papers:
        return 0.0
    leaked = sum(paper.get("cutoff_status") != "ELIGIBLE" for paper in verdict_papers)
    return leaked / len(verdict_papers)


def minimal_prior_set_recall(predicted_sets: Iterable[Iterable[str]], gold_sets: Iterable[Iterable[str]]) -> float:
    predicted = {frozenset(item) for item in predicted_sets}
    gold = {frozenset(item) for item in gold_sets}
    return len(predicted & gold) / len(gold) if gold else 0.0


def evidence_supported_claim_rate(report_claims: Sequence[dict]) -> float:
    if not report_claims:
        return 0.0
    supported = sum(bool(claim.get("evidence_ids")) for claim in report_claims)
    return supported / len(report_claims)
