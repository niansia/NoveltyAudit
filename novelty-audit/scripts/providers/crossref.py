"""Crossref Works adapter for DOI and publication metadata."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from normalize_paper import normalize_paper
from providers.base import ScholarProvider, request_json


class CrossrefProvider(ScholarProvider):
    name = "crossref"
    endpoint = "https://api.crossref.org/works"

    @staticmethod
    def _date_parts(message: dict[str, Any]) -> tuple[str | None, str | None]:
        for key, source in (("published-online", "crossref_published_online"), ("issued", "crossref_issued"), ("published-print", "proceedings")):
            parts = ((message.get(key) or {}).get("date-parts") or [[]])[0]
            if len(parts) >= 3:
                return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}", source
            if len(parts) == 1:
                return str(parts[0]), "year_only"
        return None, None

    def _convert(self, message: dict[str, Any]) -> dict[str, Any]:
        date_value, source = self._date_parts(message)
        title = (message.get("title") or [""])[0]
        record = {
            "id": message.get("DOI"),
            "doi": message.get("DOI"),
            "title": title,
            "abstract": message.get("abstract"),
            "authors": [{"name": " ".join(filter(None, [author.get("given"), author.get("family")])), "orcid": author.get("ORCID")} for author in message.get("author") or []],
            "year": int(str(date_value)[:4]) if date_value else None,
            "venue": (message.get("container-title") or [None])[0],
            "url": message.get("URL"),
            "citation_count": message.get("is-referenced-by-count"),
            "references": [item.get("DOI") for item in message.get("reference") or [] if item.get("DOI")],
            "dates": ([{"value": date_value, "source": source, "url": message.get("URL"), "verified": True}] if date_value else []),
            "raw_provenance": [{"provider": self.name, "provider_id": message.get("DOI")}],
        }
        return normalize_paper(record, self.name)

    def search(self, query: str, *, before: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"query.bibliographic": query, "rows": min(max(limit, 1), 100), "select": "DOI,title,abstract,author,published-online,published-print,issued,container-title,URL,is-referenced-by-count,reference"}
        data = request_json(self.endpoint, params=params)
        return [self._convert(item) for item in (data.get("message") or {}).get("items") or []]

    def get_by_id(self, identifier: str) -> dict[str, Any]:
        data = request_json(f"{self.endpoint}/{quote(identifier, safe='')}")
        return self._convert(data["message"])
