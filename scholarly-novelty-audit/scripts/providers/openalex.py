"""OpenAlex Works adapter."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from normalize_paper import normalize_paper
from providers.base import (
    GraphResult,
    ProviderError,
    ScholarProvider,
    SearchResult,
    request_json,
)


class OpenAlexProvider(ScholarProvider):
    name = "openalex"
    endpoint = "https://api.openalex.org/works"
    select_fields = "id,display_name,abstract_inverted_index,authorships,publication_year,publication_date,primary_location,ids,cited_by_count,open_access,referenced_works"

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
        params = self._params() | {"search": query, "per_page": per_page, "page": page_number, "corpus": self.corpus, "select": self.select_fields}
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

    def references_with_metadata(
        self, paper_id: str, *, before: str | None = None, limit: int = 100
    ) -> GraphResult:
        reference_ids = self.get_by_id(paper_id).get("references") or []
        results: list[dict[str, Any]] = []
        raw_examined = 0
        # Provider-side date filtering can make a raw-ID batch underfull. Keep
        # scanning the known reference list until the eligible result budget is
        # full or every raw reference ID has actually been examined.
        for start in range(0, len(reference_ids), 100):
            if len(results) >= limit:
                break
            batch = reference_ids[start:start + 100]
            raw_examined += len(batch)
            filter_value = f"openalex:{'|'.join(batch)}"
            if before:
                filter_value += f",to_publication_date:{before}"
            data = request_json(self.endpoint, params=self._params() | {
                "filter": filter_value, "per_page": len(batch), "corpus": self.corpus,
                "select": self.select_fields,
            })
            results.extend(self._convert(work) for work in data.get("results") or [])
        returned = results[:limit]
        exhausted = raw_examined >= len(reference_ids) and len(results) <= limit
        return GraphResult(
            papers=returned,
            exhausted=exhausted,
            provider_total=len(reference_ids),
            raw_examined_count=raw_examined,
        )

    def references(self, paper_id: str, *, before: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self.references_with_metadata(paper_id, before=before, limit=limit).papers

    def citations_with_metadata(
        self, paper_id: str, *, before: str | None = None, limit: int = 100
    ) -> GraphResult:
        results: list[dict[str, Any]] = []
        cursor: str | None = "*"
        seen_cursors: set[str] = set()
        page_budget = max(limit + 1, 2)
        provider_total: int | None = None
        for _ in range(page_budget):
            if cursor is None or len(results) >= limit:
                break
            if cursor in seen_cursors:
                raise ProviderError("OpenAlex citation pagination repeated a cursor")
            seen_cursors.add(cursor)
            filter_value = f"cites:{paper_id}"
            if before:
                filter_value += f",to_publication_date:{before}"
            data = request_json(self.endpoint, params=self._params() | {
                "filter": filter_value, "per_page": min(100, limit - len(results)),
                "cursor": cursor, "corpus": self.corpus, "select": self.select_fields,
            })
            results.extend(self._convert(work) for work in data.get("results") or [])
            meta = data.get("meta") or {}
            if provider_total is None and isinstance(meta.get("count"), int):
                provider_total = meta["count"]
            next_cursor = meta.get("next_cursor")
            cursor = str(next_cursor) if next_cursor else None
        if cursor is not None and len(results) < limit:
            raise ProviderError("OpenAlex citation pagination exceeded its safety budget")
        return GraphResult(
            papers=results[:limit],
            exhausted=cursor is None,
            next_token=cursor,
            provider_total=provider_total,
            raw_examined_count=len(results),
        )

    def citations(self, paper_id: str, *, before: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self.citations_with_metadata(paper_id, before=before, limit=limit).papers
