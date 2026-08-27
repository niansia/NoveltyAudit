"""arXiv Atom API adapter."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from normalize_paper import normalize_paper
from providers.base import ProviderError, ScholarProvider


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


class ArxivProvider(ScholarProvider):
    name = "arxiv"
    endpoint = "https://export.arxiv.org/api/query"

    def _fetch(self, params: dict[str, Any]) -> ET.Element:
        url = f"{self.endpoint}?{urlencode(params)}"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                request = Request(url, headers={"User-Agent": "NoveltyAudit/0.2"})
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

    def search(self, query: str, *, before: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        root = self._fetch({"search_query": f"all:{query}", "start": 0, "max_results": min(max(limit, 1), 100), "sortBy": "relevance"})
        papers = [self._convert(entry) for entry in root.findall(f"{ATOM}entry")]
        if before:
            cutoff = date.fromisoformat(before)
            papers = [paper for paper in papers if paper.get("dates") and date.fromisoformat(paper["dates"][0]["value"]) <= cutoff]
        return papers[:limit]

    def get_by_id(self, identifier: str) -> dict[str, Any]:
        root = self._fetch({"id_list": identifier, "max_results": 1})
        entry = root.find(f"{ATOM}entry")
        if entry is None:
            raise ProviderError(f"arXiv paper not found: {identifier}")
        return self._convert(entry)
