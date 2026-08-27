from urllib.error import HTTPError

import pytest

import providers.base as base


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
