"""Semantic Scholar Graph API adapter."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from normalize_paper import normalize_paper
from providers.base import ScholarProvider, SearchResult, request_json


FIELDS = "paperId,title,abstract,authors,year,venue,url,externalIds,citationCount,publicationDate,openAccessPdf,referenceCount"


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

    def _edges(self, identifier: str, kind: str, before: str | None) -> list[dict[str, Any]]:
        data = request_json(f"{self.endpoint}/paper/{quote(identifier, safe='')}/{kind}", params={"fields": FIELDS, "limit": 100}, headers=self._headers())
        key = "citingPaper" if kind == "citations" else "citedPaper"
        papers = [self._convert(edge[key]) for edge in data.get("data") or [] if edge.get(key)]
        if before:
            year = int(before[:4])
            papers = [paper for paper in papers if paper.get("year") and int(paper["year"]) <= year]
        return papers

    def references(self, paper_id: str, *, before: str | None = None) -> list[dict[str, Any]]:
        return self._edges(paper_id, "references", before)

    def citations(self, paper_id: str, *, before: str | None = None) -> list[dict[str, Any]]:
        return self._edges(paper_id, "citations", before)
