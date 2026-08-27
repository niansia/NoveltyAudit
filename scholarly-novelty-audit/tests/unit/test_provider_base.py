from urllib.error import HTTPError

import providers.arxiv as arxiv_module
import providers.openalex as openalex_module
import providers.semantic_scholar as s2_module
import pytest
from providers import base
from providers.arxiv import build_arxiv_query
from providers.crossref import CrossrefProvider
from providers.openalex import OpenAlexProvider
from providers.semantic_scholar import SemanticScholarProvider


def openalex_work(identifier):
    return {
        "id": f"https://openalex.org/{identifier}",
        "display_name": f"Paper {identifier}",
        "authorships": [],
        "ids": {},
        "referenced_works": [],
    }


def test_provider_error_redacts_query_and_api_key(monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPError("https://api.example.test/works", 401, "bad", {}, None)

    monkeypatch.setattr(base, "urlopen", fail)
    with pytest.raises(base.ProviderError) as caught:
        base.request_json("https://api.example.test/works", params={"query": "private claim", "api_key": "secret"}, retries=1)
    message = str(caught.value)
    assert "secret" not in message
    assert "private claim" not in message
    assert message == "request failed for https://api.example.test/works: HTTP 401"


def test_openalex_uses_api_key_and_ignores_retired_mailto(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
    monkeypatch.setenv("OPENALEX_MAILTO", "legacy@example.org")
    params = OpenAlexProvider()._params()
    assert params == {"api_key": "test-key"}


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (HTTPError("https://api.example.test/works", 429, "rate", {}, None), "HTTP 429"),
        (HTTPError("https://api.example.test/works", 503, "down", {}, None), "HTTP 503"),
        (TimeoutError(), "TimeoutError"),
    ],
)
def test_retryable_provider_failures_degrade_to_typed_provider_error(monkeypatch, failure, expected):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(base, "urlopen", fail)
    monkeypatch.setattr(base.time, "sleep", lambda _: None)
    with pytest.raises(base.ProviderError) as caught:
        base.request_json("https://api.example.test/works", retries=2)
    assert expected in str(caught.value)


def test_search_result_exposes_auditable_counts_and_truncation():
    page = base.SearchResult(papers=[{"id": "A"}], total_count=10, pagination={"offset": 0, "limit": 1})
    assert page.audit_fields() == {
        "returned_count": 1, "total_count": 10, "truncated": True,
        "pagination": {"offset": 0, "limit": 1}, "corpus": "not_applicable",
    }


def test_search_result_paginates_by_raw_count_after_local_filtering():
    page = base.SearchResult(
        papers=[], total_count=1000,
        pagination={"start": 0, "raw_returned_count": 100, "eligible_returned_count": 0},
    )
    assert page.returned_count == 0
    assert page.raw_returned_count == 100
    assert page.next_token == 100
    assert page.truncated is True


def test_graph_result_exposes_explicit_provider_exhaustion():
    result = base.GraphResult(
        papers=[{"id": "A"}], exhausted=True, next_token=None,
        provider_total=1, raw_examined_count=1,
    )
    assert result.returned_count == 1
    assert result.exhausted is True


def test_arxiv_pagination_advances_by_raw_entries_not_cutoff_eligible_entries(monkeypatch):
    xml = """<feed xmlns="http://www.w3.org/2005/Atom"
        xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
      <opensearch:totalResults>1000</opensearch:totalResults>
      <opensearch:startIndex>0</opensearch:startIndex>
      <opensearch:itemsPerPage>2</opensearch:itemsPerPage>
      <entry><id>https://arxiv.org/abs/2601.00001</id><title>Late A</title><summary>A</summary><published>2026-01-01T00:00:00Z</published></entry>
      <entry><id>https://arxiv.org/abs/2601.00002</id><title>Late B</title><summary>B</summary><published>2026-01-02T00:00:00Z</published></entry>
    </feed>"""
    monkeypatch.setattr(arxiv_module.ArxivProvider, "_fetch", lambda self, params: arxiv_module.ET.fromstring(xml))
    page = arxiv_module.ArxivProvider().search_with_metadata("late work", before="2025-01-01", limit=2)
    assert page.papers == []
    assert page.pagination["raw_returned_count"] == 2
    assert page.pagination["eligible_returned_count"] == 0
    assert page.next_token == 2


def test_openalex_uses_canonical_pagination_and_explicit_all_corpus(monkeypatch):
    captured = {}
    def fake_request(url, *, params=None, **kwargs):
        captured.update(params or {})
        return {"meta": {"count": 0, "page": 1, "per_page": 17, "next_cursor": None}, "results": []}
    monkeypatch.setattr(openalex_module, "request_json", fake_request)
    page = OpenAlexProvider().search_with_metadata("novel mechanism", limit=17)
    assert captured["per_page"] == 17
    assert "per-page" not in captured
    assert captured["corpus"] == "all"
    assert page.total_count == 0
    assert page.corpus == "all"


def test_historical_cutoff_is_pushed_into_provider_queries(monkeypatch):
    openalex_params = {}
    s2_params = {}
    monkeypatch.setattr(openalex_module, "request_json", lambda *args, **kwargs: openalex_params.update(kwargs.get("params") or {}) or {"meta": {"count": 0}, "results": []})
    monkeypatch.setattr(s2_module, "request_json", lambda *args, **kwargs: s2_params.update(kwargs.get("params") or {}) or {"total": 0, "data": []})
    OpenAlexProvider().search_with_metadata("mechanism", before="2025-09-18", limit=10)
    SemanticScholarProvider().search_with_metadata("mechanism", before="2025-09-18", limit=10)
    assert openalex_params["filter"] == "to_publication_date:2025-09-18"
    assert s2_params["publicationDateOrYear"] == ":2025-09-18"


def test_semantic_scholar_preserves_total_and_next(monkeypatch):
    monkeypatch.setattr(s2_module, "request_json", lambda *args, **kwargs: {"total": 12, "offset": 0, "next": 1, "data": []})
    page = SemanticScholarProvider().search_with_metadata("novel mechanism", limit=1)
    assert page.total_count == 12
    assert page.truncated is True


def test_semantic_scholar_citation_expansion_requests_local_references(monkeypatch):
    captured = {}
    def fake_request(*args, **kwargs):
        captured.update(kwargs.get("params") or {})
        return {"data": [{"citingPaper": {"paperId": "C", "title": "C", "references": [{"paperId": "A"}, {"paperId": "B"}]}}]}
    monkeypatch.setattr(s2_module, "request_json", fake_request)
    papers = SemanticScholarProvider().citations("A", before="2025-01-01", limit=20)
    assert "references" in captured["fields"]
    assert captured["publicationDateOrYear"] == ":2025-01-01"
    assert papers[0]["references"] == ["A", "B"]


def test_openalex_references_scans_past_underfull_cutoff_batch(monkeypatch):
    provider = OpenAlexProvider()
    reference_ids = [f"W{index}" for index in range(1, 151)]
    monkeypatch.setattr(provider, "get_by_id", lambda _: {"references": reference_ids})
    requests = []

    def fake_request(*args, **kwargs):
        params = kwargs["params"]
        requests.append(params)
        ids = params["filter"].split(",", 1)[0].removeprefix("openalex:").split("|")
        eligible = ids[:-1] if len(requests) == 1 else ids
        return {"results": [openalex_work(identifier) for identifier in eligible]}

    monkeypatch.setattr(openalex_module, "request_json", fake_request)
    papers = provider.references("W-ANCHOR", before="2025-01-01", limit=100)
    assert len(papers) == 100
    assert len(requests) == 2
    assert "W101" in requests[1]["filter"]
    assert all("to_publication_date:2025-01-01" in request["filter"] for request in requests)


def test_openalex_references_exhausts_raw_ids_before_claiming_under_limit(monkeypatch):
    provider = OpenAlexProvider()
    reference_ids = [f"W{index}" for index in range(1, 151)]
    monkeypatch.setattr(provider, "get_by_id", lambda _: {"references": reference_ids})
    requests = []

    def fake_request(*args, **kwargs):
        requests.append(kwargs["params"])
        results = [openalex_work(f"W{index}") for index in range(1, 100)] if len(requests) == 1 else []
        return {"results": results}

    monkeypatch.setattr(openalex_module, "request_json", fake_request)
    papers = provider.references("W-ANCHOR", before="2025-01-01", limit=100)
    assert len(papers) == 99
    assert len(requests) == 2


def test_openalex_exact_reference_limit_can_be_explicitly_exhausted(monkeypatch):
    provider = OpenAlexProvider()
    reference_ids = [f"W{index}" for index in range(1, 101)]
    monkeypatch.setattr(provider, "get_by_id", lambda _: {"references": reference_ids})
    monkeypatch.setattr(openalex_module, "request_json", lambda *args, **kwargs: {
        "results": [openalex_work(identifier) for identifier in reference_ids],
    })
    result = provider.references_with_metadata("W-ANCHOR", limit=100)
    assert result.returned_count == 100
    assert result.exhausted is True
    assert result.provider_total == 100
    assert result.raw_examined_count == 100


def test_openalex_citations_follow_cursor_until_exhausted(monkeypatch):
    requests = []

    def fake_request(*args, **kwargs):
        cursor = kwargs["params"]["cursor"]
        requests.append(cursor)
        if cursor == "*":
            return {"meta": {"next_cursor": "next-1"}, "results": [openalex_work("C1")]}
        return {"meta": {"next_cursor": None}, "results": [openalex_work("C2")]}

    monkeypatch.setattr(openalex_module, "request_json", fake_request)
    papers = OpenAlexProvider().citations("W-A", limit=3)
    assert [paper["id"] for paper in papers] == ["C1", "C2"]
    assert requests == ["*", "next-1"]


def test_openalex_exact_citation_limit_uses_provider_end_signal(monkeypatch):
    monkeypatch.setattr(openalex_module, "request_json", lambda *args, **kwargs: {
        "meta": {"count": 2, "next_cursor": None},
        "results": [openalex_work("C1"), openalex_work("C2")],
    })
    result = OpenAlexProvider().citations_with_metadata("W-A", limit=2)
    assert result.returned_count == 2
    assert result.exhausted is True
    assert result.next_token is None


def test_openalex_repeated_citation_cursor_is_a_provider_failure(monkeypatch):
    monkeypatch.setattr(openalex_module, "request_json", lambda *args, **kwargs: {
        "meta": {"next_cursor": "*"}, "results": [],
    })
    with pytest.raises(base.ProviderError, match="repeated a cursor"):
        OpenAlexProvider().citations("W-A", limit=2)


def test_semantic_scholar_graph_edges_follow_next_offset(monkeypatch):
    requests = []

    def fake_request(*args, **kwargs):
        params = kwargs["params"]
        requests.append(params)
        if params["offset"] == 0:
            return {"next": 1, "data": [{"citedPaper": {"paperId": "R1", "title": "R1"}}]}
        return {"data": [{"citedPaper": {"paperId": "R2", "title": "R2"}}]}

    monkeypatch.setattr(s2_module, "request_json", fake_request)
    papers = SemanticScholarProvider().references("A", before="2025-01-01", limit=3)
    assert [paper["id"] for paper in papers] == ["R1", "R2"]
    assert [request["offset"] for request in requests] == [0, 1]
    assert all(request["publicationDateOrYear"] == ":2025-01-01" for request in requests)


def test_semantic_scholar_exact_graph_limit_uses_provider_end_signal(monkeypatch):
    monkeypatch.setattr(s2_module, "request_json", lambda *args, **kwargs: {
        "next": None,
        "data": [
            {"citedPaper": {"paperId": "R1", "title": "R1"}},
            {"citedPaper": {"paperId": "R2", "title": "R2"}},
        ],
    })
    result = SemanticScholarProvider().references_with_metadata("A", limit=2)
    assert result.returned_count == 2
    assert result.exhausted is True
    assert result.next_token is None


def test_semantic_scholar_repeated_graph_offset_is_a_provider_failure(monkeypatch):
    monkeypatch.setattr(s2_module, "request_json", lambda *args, **kwargs: {"next": 0, "data": []})
    with pytest.raises(base.ProviderError, match="repeated an offset"):
        SemanticScholarProvider().citations("A", limit=2)


def test_semantic_scholar_negative_graph_offset_is_a_provider_failure(monkeypatch):
    monkeypatch.setattr(s2_module, "request_json", lambda *args, **kwargs: {"next": -1, "data": []})
    with pytest.raises(base.ProviderError, match="negative graph pagination offset"):
        SemanticScholarProvider().citations("A", limit=2)


def test_crossref_preserves_month_precision():
    value, source = CrossrefProvider._date_parts({"published-online": {"date-parts": [[2025, 1]]}, "issued": {"date-parts": [[2025, 3, 15]]}})
    assert value == "2025-01"
    assert source == "crossref_published_online"


def test_arxiv_plain_multiword_query_becomes_boolean_fields():
    assert build_arxiv_query("scholarly novelty assessment") == "all:scholarly AND all:novelty AND all:assessment"
    assert build_arxiv_query("ti:novelty AND abs:audit") == "ti:novelty AND abs:audit"
