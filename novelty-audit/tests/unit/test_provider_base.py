from urllib.error import HTTPError

import pytest

import providers.base as base
import providers.openalex as openalex_module
import providers.semantic_scholar as s2_module
from providers.arxiv import build_arxiv_query
from providers.crossref import CrossrefProvider
from providers.openalex import OpenAlexProvider
from providers.semantic_scholar import SemanticScholarProvider


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


def test_crossref_preserves_month_precision():
    value, source = CrossrefProvider._date_parts({"published-online": {"date-parts": [[2025, 1]]}, "issued": {"date-parts": [[2025, 3, 15]]}})
    assert value == "2025-01"
    assert source == "crossref_published_online"


def test_arxiv_plain_multiword_query_becomes_boolean_fields():
    assert build_arxiv_query("scholarly novelty assessment") == "all:scholarly AND all:novelty AND all:assessment"
    assert build_arxiv_query("ti:novelty AND abs:audit") == "ti:novelty AND abs:audit"
