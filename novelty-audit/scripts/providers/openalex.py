"""OpenAlex Works adapter."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from normalize_paper import normalize_paper
from providers.base import ScholarProvider, SearchResult, request_json


class OpenAlexProvider(ScholarProvider):
    name = "openalex"
    endpoint = "https://api.openalex.org/works"

    def __init__(self, corpus: str | None = None):
        self.corpus = corpus or os.getenv("OPENALEX_CORPUS", "all")
        if self.corpus not in {"core", "expansion", "all"}:
            raise ValueError("OPENALEX_CORPUS must be core, expansion, or all")

    def _params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if os.getenv("OPENALEX_API_KEY"):
            params["api_key"] = os.environ["OPENALEX_API_KEY"]
        return params

    @staticmethod
    def _abstract(index: dict[str, list[int]] | None) -> str | None:
        if not index:
            return None
        positions = [(position, word) for word, values in index.items() for position in values]
        return " ".join(word for _, word in sorted(positions))

    def _convert(self, work: dict[str, Any]) -> dict[str, Any]:
        primary = work.get("primary_location") or {}
        source = primary.get("source") or {}
        ids = work.get("ids") or {}
        date_value = work.get("publication_date")
        record = {
            "id": work.get("id", "").rsplit("/", 1)[-1],
            "title": work.get("display_name") or work.get("title"),
            "abstract": self._abstract(work.get("abstract_inverted_index")),
            "authors": [{"name": (item.get("author") or {}).get("display_name", ""), "id": (item.get("author") or {}).get("id")} for item in work.get("authorships") or []],
            "year": work.get("publication_year"),
            "venue": source.get("display_name"),
            "doi": ids.get("doi"),
            "url": primary.get("landing_page_url") or work.get("id"),
            "citation_count": work.get("cited_by_count"),
            "open_access": work.get("open_access"),
            "references": [value.rsplit("/", 1)[-1] for value in work.get("referenced_works") or []],
            "dates": ([{"value": date_value, "source": "publication", "url": primary.get("landing_page_url"), "verified": True}] if date_value else []),
            "raw_provenance": [{"provider": self.name, "provider_id": work.get("id")}],
        }
        return normalize_paper(record, self.name)

    def search_with_metadata(self, query: str, *, before: str | None = None, limit: int = 100, page_token: Any | None = None) -> SearchResult:
        per_page = min(max(limit, 1), 100)
        page_number = int(page_token or 1)
        params = self._params() | {"search": query, "per_page": per_page, "page": page_number, "corpus": self.corpus, "select": "id,display_name,abstract_inverted_index,authorships,publication_year,publication_date,primary_location,ids,cited_by_count,open_access,referenced_works"}
        if before:
            params["filter"] = f"to_publication_date:{before}"
        data = request_json(self.endpoint, params=params)
        meta = data.get("meta") or {}
        papers = [self._convert(work) for work in (data.get("results") or [])[:limit]]
        return SearchResult(
            papers=papers,
            total_count=meta.get("count"),
            pagination={"page": meta.get("page", page_number), "per_page": meta.get("per_page", per_page), "next": page_number + 1 if meta.get("count", 0) > page_number * per_page else None},
            corpus=self.corpus,
        )

    def get_by_id(self, identifier: str) -> dict[str, Any]:
        data = request_json(f"{self.endpoint}/{quote(identifier)}", params=self._params())
        return self._convert(data)

    def citations(self, paper_id: str, *, before: str | None = None) -> list[dict[str, Any]]:
        params = self._params() | {"filter": f"cites:{paper_id}", "per_page": 100, "corpus": self.corpus}
        data = request_json(self.endpoint, params=params)
        return [self._convert(work) for work in data.get("results") or []]
