"""Provider contract and resilient HTTP helpers."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    pass


class ScholarProvider(ABC):
    name = "base"

    @abstractmethod
    def search(self, query: str, *, before: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_by_id(self, identifier: str) -> dict[str, Any]:
        raise NotImplementedError(f"{self.name} does not implement get_by_id")

    def references(self, paper_id: str, *, before: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError(f"{self.name} does not implement references")

    def citations(self, paper_id: str, *, before: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError(f"{self.name} does not implement citations")

    def fulltext_or_snippets(self, paper_id: str) -> list[dict[str, Any]]:
        return []

    def healthcheck(self) -> dict[str, Any]:
        try:
            self.search("scientific method", limit=1)
            return {"provider": self.name, "ok": True}
        except Exception as error:  # healthchecks must disclose, not crash a full audit
            return {"provider": self.name, "ok": False, "error": str(error)}


def request_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 3,
) -> dict[str, Any]:
    if params:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        url = f"{url}{'&' if '?' in url else '?'}{query}"
    request_headers = {"Accept": "application/json", "User-Agent": "NoveltyAudit/0.2 (+https://github.com/)"}
    request_headers.update(headers or {})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers=request_headers), timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            last_error = error
            if error.code not in {429, 500, 502, 503, 504}:
                break
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
        if attempt + 1 < retries:
            time.sleep(0.5 * (2 ** attempt))
    parsed = urlsplit(url)
    safe_endpoint = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    if isinstance(last_error, HTTPError):
        detail = f"HTTP {last_error.code}"
    else:
        detail = type(last_error).__name__ if last_error else "unknown error"
    raise ProviderError(f"request failed for {safe_endpoint}: {detail}")
