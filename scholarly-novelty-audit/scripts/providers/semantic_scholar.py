"""Semantic Scholar Graph API adapter."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from normalize_paper import normalize_paper
from providers.base import ProviderError, ScholarProvider, SearchResult, request_json


FIELDS = "paperId,title,abstract,authors,year,venue,url,externalIds,citationCount,publicationDate,openAccessPdf,referenceCount"
EDGE_FIELDS = f"{FIELDS},references"


class SemanticScholarProvider(ScholarProvider):
    name = "semantic-scholar"
    endpoint = "https://api.semanticscholar.org/graph/v1"

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": os.environ["S2_API_KEY"]} if os.getenv("S2_API_KEY") else {}

    def _convert(self, paper: dict[str, Any]) -> dict[str, Any]:
        date_value = paper.get("publicationDate")
        record = {
            "id": paper.get("paperId"),
            "title": paper.get("title"),
            "abstract": paper.get("abstract"),
            "authors": [{"name": author.get("name", ""), "id": author.get("authorId")} for author in paper.get("authors") or []],
            "year": paper.get("year"),
            "venue": paper.get("venue"),
            "url": paper.get("url"),
            "external_ids": paper.get("externalIds") or {},
            "citation_count": paper.get("citationCount"),
            "open_access": paper.get("openAccessPdf"),
            "references": [item.get("paperId") for item in paper.get("references") or [] if item.get("paperId")],
            "dates": ([{"value": date_value, "source": "publication", "url": paper.get("url"), "verified": True}] if date_value else []),
            "raw_provenance": [{"provider": self.name, "provider_id": paper.get("paperId")}],
        }
        return normalize_paper(record, self.name)

    def search_with_metadata(self, query: str, *, before: str | None = None, limit: int = 100, page_token: Any | None = None) -> SearchResult:
        params: dict[str, Any] = {"query": query, "limit": min(max(limit, 1), 100), "offset": int(page_token or 0), "fields": FIELDS}
        if before:
            params["publicationDateOrYear"] = f":{before}"
        data = request_json(f"{self.endpoint}/paper/search", params=params, headers=self._headers())
        papers = [self._convert(paper) for paper in (data.get("data") or [])[:limit]]
        return SearchResult(
            papers=papers,
            total_count=data.get("total"),
            pagination={"offset": data.get("offset", 0), "limit": params["limit"], "next": data.get("next")},
        )

    def get_by_id(self, identifier: str) -> dict[str, Any]:
        data = request_json(f"{self.endpoint}/paper/{quote(identifier, safe='')}", params={"fields": FIELDS}, headers=self._headers())
        return self._convert(data)

    def _edges(self, identifier: str, kind: str, before: str | None, limit: int) -> list[dict[str, Any]]:
        key = "citingPaper" if kind == "citations" else "citedPaper"
        papers: list[dict[str, Any]] = []
        offset = 0
        seen_offsets: set[int] = set()
        page_budget = max(limit + 1, 2)
        next_offset: Any | None = 0
        for _ in range(page_budget):
            if next_offset is None or len(papers) >= limit:
                break
            try:
                offset = int(next_offset)
            except (TypeError, ValueError) as error:
                raise ProviderError("Semantic Scholar returned an invalid graph pagination offset") from error
            if offset < 0:
                raise ProviderError("Semantic Scholar returned a negative graph pagination offset")
            if offset in seen_offsets:
                raise ProviderError("Semantic Scholar graph pagination repeated an offset")
            seen_offsets.add(offset)
            params: dict[str, Any] = {
                "fields": EDGE_FIELDS if kind == "citations" else FIELDS,
                "limit": min(max(limit - len(papers), 1), 1000),
                "offset": offset,
            }
            if before:
                params["publicationDateOrYear"] = f":{before}"
            data = request_json(
                f"{self.endpoint}/paper/{quote(identifier, safe='')}/{kind}",
                params=params,
                headers=self._headers(),
            )
            papers.extend(self._convert(edge[key]) for edge in data.get("data") or [] if edge.get(key))
            next_offset = data.get("next")
        if next_offset is not None and len(papers) < limit:
            raise ProviderError("Semantic Scholar graph pagination exceeded its safety budget")
        return papers[:limit]

    def references(self, paper_id: str, *, before: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self._edges(paper_id, "references", before, limit)

    def citations(self, paper_id: str, *, before: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self._edges(paper_id, "citations", before, limit)
