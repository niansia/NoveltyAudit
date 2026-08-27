from search_coverage import derive_search_coverage


def run(provider, family, *, corpus="not_applicable", truncated=False):
    return {
        "query_id": f"{provider}:{family}", "provider": provider, "family": family,
        "status": "ok", "returned_count": 0, "total_count": 0,
        "truncated": truncated, "pagination": {}, "corpus": corpus,
    }


def test_broad_is_derived_only_from_complete_primary_search_runs():
    families = ["literal", "mechanism", "problem_function", "ancestor", "composition_bridge"]
    runs = [run("openalex", family, corpus="all") for family in families]
    runs.append(run("semantic-scholar", "mechanism"))
    derived = derive_search_coverage({"query_runs": runs})
    assert derived["level"] == "BROAD"
    assert derived["reasons"] == []


def test_fake_provider_core_corpus_and_truncation_cannot_inflate_coverage():
    families = ["literal", "mechanism", "problem_function", "ancestor", "composition_bridge"]
    runs = [run("openalex", family, corpus="core") for family in families]
    runs.append(run("fake-provider", "mechanism", truncated=True))
    derived = derive_search_coverage({"query_runs": runs})
    assert derived["level"] != "BROAD"
    assert any("unsupported primary" in reason for reason in derived["reasons"])
    assert any("corpus=all" in reason for reason in derived["reasons"])
    assert any("truncated" in reason for reason in derived["reasons"])
