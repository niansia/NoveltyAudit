"""arXiv Atom API adapter."""

from __future__ import annotations

import time
import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from normalize_paper import normalize_paper
from providers.base import ProviderError, ScholarProvider, SearchResult


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"


def build_arxiv_query(query: str) -> str:
    """Turn an ordinary multiword query into explicit arXiv boolean syntax."""
    query = " ".join(query.split())
    if re.search(r"\b(?:all|ti|au|abs|co|jr|cat|rn|id):", query, re.IGNORECASE) or re.search(r"\b(?:AND|OR|ANDNOT)\b", query):
        return query
    terms = re.findall(r"[\w.-]+", query, flags=re.UNICODE)
    if not terms:
        raise ValueError("arXiv query contains no searchable terms")
    return " AND ".join(f"all:{term}" for term in terms)


class ArxivProvider(ScholarProvider):
    name = "arxiv"
    endpoint = "https://export.arxiv.org/api/query"

    def _fetch(self, params: dict[str, Any]) -> ET.Element:
        url = f"{self.endpoint}?{urlencode(params)}"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                request = Request(url, headers={"User-Agent": "NoveltyAudit/0.3"})
                with urlopen(request, timeout=30) as response:
                    return ET.fromstring(response.read())
            except Exception as error:
                last_error = error
                if attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
        raise ProviderError(f"arXiv request failed: {last_error}")

    def _convert(self, entry: ET.Element) -> dict[str, Any]:
        identifier = (entry.findtext(f"{ATOM}id") or "").rsplit("/", 1)[-1]
        published = entry.findtext(f"{ATOM}published")
        doi = entry.findtext(f"{ARXIV}doi")
        links = {link.attrib.get("rel"): link.attrib.get("href") for link in entry.findall(f"{ATOM}link")}
        record = {
            "id": identifier,
            "arxiv_id": identifier,
            "doi": doi,
            "title": " ".join((entry.findtext(f"{ATOM}title") or "").split()),
            "abstract": " ".join((entry.findtext(f"{ATOM}summary") or "").split()),
            "authors": [{"name": author.findtext(f"{ATOM}name") or ""} for author in entry.findall(f"{ATOM}author")],
            "year": int(published[:4]) if published else None,
            "venue": entry.findtext(f"{ARXIV}journal_ref"),
            "url": links.get("alternate") or entry.findtext(f"{ATOM}id"),
            "dates": ([{"value": published[:10], "source": "arxiv_v1", "url": entry.findtext(f"{ATOM}id"), "verified": True}] if published else []),
            "raw_provenance": [{"provider": self.name, "provider_id": identifier}],
        }
        return normalize_paper(record, self.name)

    def search_with_metadata(self, query: str, *, before: str | None = None, limit: int = 100, page_token: Any | None = None) -> SearchResult:
        requested = min(max(limit, 1), 100)
        root = self._fetch({"search_query": build_arxiv_query(query), "start": int(page_token or 0), "max_results": requested, "sortBy": "relevance"})
        papers = [self._convert(entry) for entry in root.findall(f"{ATOM}entry")]
        if before:
            cutoff = date.fromisoformat(before)
            papers = [paper for paper in papers if paper.get("dates") and date.fromisoformat(paper["dates"][0]["value"]) <= cutoff]
        def integer(name: str, default: int | None = None) -> int | None:
            value = root.findtext(f"{OPENSEARCH}{name}")
            return int(value) if value not in (None, "") else default
        return SearchResult(
            papers=papers[:limit],
            total_count=integer("totalResults"),
            pagination={"start": integer("startIndex", 0), "items_per_page": integer("itemsPerPage", requested)},
        )

    def get_by_id(self, identifier: str) -> dict[str, Any]:
        root = self._fetch({"id_list": identifier, "max_results": 1})
        entry = root.find(f"{ATOM}entry")
        if entry is None:
            raise ProviderError(f"arXiv paper not found: {identifier}")
        return self._convert(entry)
