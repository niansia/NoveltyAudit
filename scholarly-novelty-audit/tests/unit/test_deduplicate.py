from deduplicate import deduplicate


def test_merges_preprint_and_publisher_version_by_doi():
    records = [
        {"id": "arxiv", "title": "A Composition Aware Audit", "doi": "10.1000/X", "year": 2024, "authors": ["A. Lee"], "providers": ["arxiv"]},
        {"id": "publisher", "title": "A Composition-Aware Audit", "doi": "https://doi.org/10.1000/x", "year": 2025, "authors": ["Alice Lee"], "providers": ["crossref"]},
    ]
    result = deduplicate(records)
    assert len(result) == 1
    assert set(result[0]["providers"]) == {"arxiv", "crossref"}
    assert len(result[0]["versions"]) == 2


def test_does_not_merge_similar_titles_without_author_overlap():
    records = [
        {"id": "a", "title": "Adaptive Memory for Video", "year": 2024, "authors": ["Alice Lee"]},
        {"id": "b", "title": "Adaptive Memory for Videos", "year": 2024, "authors": ["Bob Chen"]},
    ]
    assert len(deduplicate(records)) == 2


def test_does_not_merge_distinct_dois_even_with_same_title_and_author():
    records = [
        {"id": "a", "title": "Same title", "doi": "10.1000/a", "year": 2024, "authors": ["Alice Lee"]},
        {"id": "b", "title": "Same title", "doi": "10.1000/b", "year": 2024, "authors": ["Alice Lee"]},
    ]
    assert len(deduplicate(records)) == 2


def test_merge_keeps_provider_id_of_canonical_first_version():
    records = [
        {
            "id": "W1", "title": "Exact Work", "doi": "10.1000/work", "year": 2024,
            "authors": ["Alice Lee"], "providers": ["openalex"],
            "provider_ids": {"openalex": "W1"}, "references": ["R1"],
        },
        {
            "id": "W2", "title": "Exact Work", "doi": "10.1000/work", "year": 2024,
            "authors": ["Alice Lee"], "providers": ["openalex"],
            "provider_ids": {"openalex": "W2"}, "references": [],
        },
    ]
    result = deduplicate(records)[0]
    assert result["id"] == "W1"
    assert result["provider_ids"]["openalex"] == "W1"
    assert [version["id"] for version in result["versions"]] == ["W1", "W2"]
