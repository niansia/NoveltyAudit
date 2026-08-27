from urllib.error import HTTPError

import pytest

import providers.base as base
from providers.openalex import OpenAlexProvider


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
