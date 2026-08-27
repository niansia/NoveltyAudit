import importlib.util
import sys
from pathlib import Path

path = Path(__file__).resolve().parents[2] / "benchmark" / "bridge_base_rate.py"
spec = importlib.util.spec_from_file_location("bridge_base_rate", path)
bridge = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)


def candidate(title, paper_id, author, publication_date="2023-01-01", external=None):
    return {
        "title": title,
        "s2_id": paper_id,
        "publication_date": publication_date,
        "year": int(publication_date[:4]),
        "authors": [author],
        "external_ids": external or {},
        "s2_reference_count": None,
    }


def test_reviewer_author_and_distinctive_alias_link_only_named_priors():
    annotation = {
        "input": {"title": "Safety Patching"},
        "output": [{
            "novelty_statements": [
                "The method relies on the SNIP score proposed by Lee et al. and merging methods by Yu et al. and Hui et al."
            ],
            "review": (
                'Yu, Le, et al. "Language Models are Super Mario: Absorbing Abilities."\n'
                'Hui, Tingfeng, et al. "HFT: Half Fine-Tuning for Large Language Models."\n'
                'Wang et al. "An unrelated evaluator dataset."'
            ),
        }],
    }
    candidates = [
        candidate("SNIP: Single-shot Network Pruning", "S1", "Lee"),
        candidate("Language Models are Super Mario: Absorbing Abilities", "S2", "Yu"),
        candidate("HFT: Half Fine-Tuning for Large Language Models", "S3", "Hui"),
        candidate("An unrelated evaluator dataset", "S4", "Wang"),
    ]
    priors, status = bridge.extract_named_priors(annotation, candidates)
    assert status == "EXTRACTED"
    assert {item["s2_id"] for item in priors} == {"S1", "S2", "S3"}


def test_generic_uppercase_token_does_not_select_entire_field():
    annotation = {
        "input": {"title": "A New Text-to-SQL Method"},
        "output": [{"novelty_statements": ["Text-to-SQL has extensive prior work."], "review": ""}],
    }
    candidates = [
        candidate("DIN-SQL: Decomposed Text-to-SQL", "S1", "Pourreza"),
        candidate("Spider: A Text-to-SQL Dataset", "S2", "Yu"),
    ]
    priors, status = bridge.extract_named_priors(annotation, candidates)
    assert priors == []
    assert status == "POTENTIAL_MISSED_MENTIONS"


def test_explicit_arxiv_and_markdown_label_merge_to_one_prior():
    annotation = {
        "input": {"title": "Tool Work"},
        "output": [{
            "novelty_statements": ["See [Domino](https://arxiv.org/abs/2403.06988)."],
            "review": "",
        }],
    }
    priors, status = bridge.extract_named_priors(annotation, [])
    assert status == "EXTRACTED"
    assert len(priors) == 1
    assert priors[0]["external_ids"]["ArXiv"] == "2403.06988"


def test_numbered_reference_range_links_only_cited_review_blocks():
    annotation = {
        "input": {"title": "Bias Transfer"},
        "output": [{
            "novelty_statements": ["Closely related work [1-2] was omitted."],
            "review": (
                "[1] Smith et al. The First Prior. arXiv preprint arXiv:2301.00001.\n\n"
                "[2] Jones et al. The Second Prior. arXiv preprint arXiv:2302.00002.\n\n"
                "[3] Doe et al. An Unrelated Paper. arXiv preprint arXiv:2303.00003."
            ),
        }],
    }
    candidates = [
        candidate("The First Prior", "S1", "Smith"),
        candidate("The Second Prior", "S2", "Jones"),
        candidate("An Unrelated Paper", "S3", "Doe"),
    ]
    priors, status = bridge.extract_named_priors(annotation, candidates)
    assert status == "EXTRACTED"
    assert {item["s2_id"] for item in priors} == {"S1", "S2"}


def test_target_cutoff_uses_earliest_matching_public_record():
    annotation = {
        "input": {"title": "A New Paper"},
        "publicationDate": "2024-12-10",
    }
    candidates = [candidate("A New Paper", "S1", "Author", "2024-05-22")]
    value, sources = bridge.target_date(annotation, candidates)
    assert value.isoformat() == "2024-05-22"
    assert sources == ["MATCHED_DATASET_PAPER_RECORD"]


def test_zero_bridge_interpretation_separates_short_window_and_coverage():
    pair = {
        "status": "COMPLETE",
        "paper_ids": ["W1", "W2"],
        "pre_cutoff_bridge_count": 0,
        "opportunity_days": 100,
    }
    priors = [
        {"openalex_id": "W1", "openalex_reference_coverage_status": "NONEMPTY"},
        {"openalex_id": "W2", "openalex_reference_coverage_status": "CONFIRMED_CROSS_PROVIDER_GAP"},
    ]
    assert bridge.zero_interpretation(pair, priors) == "ZERO_WITH_SHORT_WINDOW_AND_COVERAGE_CAVEAT"
    pair["status"] = "PARTIAL"
    assert bridge.zero_interpretation(pair, priors) == "UNINTERPRETABLE_INCOMPLETE_QUERY"


def test_zero_bridge_interpretation_rejects_unknown_or_impossible_dates():
    pair = {
        "status": "COMPLETE", "paper_ids": ["W1", "W2"],
        "pre_cutoff_bridge_count": 0, "opportunity_days": 600,
        "date_uncertain_count": 1,
    }
    priors = [
        {"openalex_id": "W1", "openalex_reference_coverage_status": "NONEMPTY"},
        {"openalex_id": "W2", "openalex_reference_coverage_status": "NONEMPTY"},
    ]
    assert bridge.zero_interpretation(pair, priors) == "UNINTERPRETABLE_BRIDGE_DATE_MISSING"
    pair["date_uncertain_count"] = 0
    pair["opportunity_days"] = None
    assert bridge.zero_interpretation(pair, priors) == "UNINTERPRETABLE_ENDPOINT_DATE_MISSING"
    pair["opportunity_days"] = -1
    assert bridge.zero_interpretation(pair, priors) == "UNINTERPRETABLE_POST_CUTOFF_ENDPOINT"


def test_summary_does_not_put_partial_pairs_in_zero_denominator():
    cases = [{
        "named_prior_count": 2,
        "extraction_status": "EXTRACTED",
        "priors": [
            {"openalex_id": "W1", "openalex_reference_coverage_status": "NONEMPTY", "age_at_cutoff_days": 800},
            {"openalex_id": "W2", "openalex_reference_coverage_status": "NONEMPTY", "age_at_cutoff_days": 700},
        ],
        "pairs": [
            {"status": "PARTIAL", "pre_cutoff_bridge_count": 0, "opportunity_days": 700,
             "negative_interpretation": "UNINTERPRETABLE_INCOMPLETE_QUERY"}
        ],
        "pre_cutoff_distinct_bridge_count": 0,
    }]
    summary = bridge.summarize(cases, archive_md5="x", paid_calls=1)
    assert summary["bridges"]["complete_pairs"] == 0
    assert summary["bridges"]["pair_bridge_base_rate"] is None
    assert summary["bridges"]["complete_multi_prior_cases"] == 0
