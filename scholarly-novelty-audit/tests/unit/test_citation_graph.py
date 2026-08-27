import pytest

from citation_graph import find_bridges, promote_bridge, relation_route_exists
from deduplicate import deduplicate


def test_discovers_direct_and_co_citation_without_textual_promotion():
    papers = [
        {"id": "A", "references": [], "cutoff_status": "ELIGIBLE"},
        {"id": "B", "references": ["A"], "cutoff_status": "ELIGIBLE"},
        {"id": "C", "references": ["A", "B"], "cutoff_status": "ELIGIBLE"},
    ]
    result = find_bridges("A", "B", papers)
    assert {item["type"] for item in result} == {"DIRECT_CITATION", "CO_CITATION"}
    assert all(item["graph_verified"] is True for item in result)
    assert all(item["text_verified"] is False for item in result)


def test_textual_promotion_requires_evidence():
    with pytest.raises(ValueError):
        promote_bridge({"paper_ids": ["A", "B"]}, "EXPLICIT_EXTENSION", [])


def test_resolves_cross_provider_and_doi_aliases():
    papers = [
        {"id": "S2-A", "doi": "10.1000/a", "provider_ids": {"openalex": "W1"}, "references": [], "cutoff_status": "ELIGIBLE"},
        {"id": "B", "references": ["https://openalex.org/W1"], "cutoff_status": "ELIGIBLE"},
        {"id": "C", "references": ["https://doi.org/10.1000/A", "B"], "cutoff_status": "ELIGIBLE"},
    ]
    result = find_bridges("10.1000/A", "B", papers)
    assert {item["type"] for item in result} == {"DIRECT_CITATION", "CO_CITATION"}
    assert all(item["paper_ids"] == ["S2-A", "B"] for item in result)
    assert relation_route_exists({"paper_ids": ["10.1000/A", "B"], "source_paper_id": "C"}, papers)


def test_high_citation_endpoint_blocks_co_citation_promotion():
    papers = [
        {"id": "A", "references": [], "citation_count": 10000, "cutoff_status": "ELIGIBLE"},
        {"id": "B", "references": [], "citation_count": 4, "cutoff_status": "ELIGIBLE"},
        {"id": "C", "references": ["A", "B"], "cutoff_status": "ELIGIBLE"},
    ]
    bridge = next(item for item in find_bridges("A", "B", papers, high_citation_threshold=100) if item["type"] == "CO_CITATION")
    assert bridge["base_rate_status"] == "HIGH_BASE_RATE"


def test_post_cutoff_connection_is_retained_as_landscape_bridge():
    papers = [
        {"id": "A", "references": [], "cutoff_status": "ELIGIBLE"},
        {"id": "B", "references": [], "cutoff_status": "ELIGIBLE"},
        {"id": "L", "references": ["A", "B"], "cutoff_status": "POST_CUTOFF"},
    ]
    bridge = next(item for item in find_bridges("A", "B", papers, cutoff="2025-01-01") if item["source_paper_id"] == "L")
    assert bridge["type"] == "LANDSCAPE_BRIDGE"
    assert bridge["underlying_type"] == "CO_CITATION"
    assert bridge["affects_historical_verdict"] is False


def test_deduplication_keeps_conservative_maximum_citation_count():
    records = [
        {"id": "A1", "doi": "10.1000/a", "title": "A", "citation_count": 20, "providers": ["one"]},
        {"id": "A2", "doi": "10.1000/a", "title": "A", "citation_count": 10000, "providers": ["two"]},
    ]
    assert deduplicate(records)[0]["citation_count"] == 10000
