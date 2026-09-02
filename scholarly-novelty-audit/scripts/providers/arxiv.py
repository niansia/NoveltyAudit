"""arXiv Atom API adapter."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from normalize_paper import normalize_arxiv_id, normalize_paper, split_arxiv_id
from providers.base import ProviderError, ScholarProvider, SearchResult


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
MAX_VERSION_HISTORY = 100


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
                request = Request(url, headers={"User-Agent": "NoveltyAudit/0.3.1"})
                with urlopen(request, timeout=30) as response:
                    return ET.fromstring(response.read())
            except Exception as error:
                last_error = error
                if attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
        raise ProviderError(f"arXiv request failed: {last_error}")

    @staticmethod
    def _entry_links(entry: ET.Element) -> tuple[str | None, str | None]:
        alternate = None
        pdf = None
        for link in entry.findall(f"{ATOM}link"):
            href = link.attrib.get("href")
            if not href:
                continue
            if link.attrib.get("rel") == "alternate":
                alternate = href
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf = href
        return alternate, pdf

    def _convert(
        self, entry: ET.Element, *, latest_version_verified: bool = False
    ) -> dict[str, Any]:
        raw_identifier = entry.findtext(f"{ATOM}id") or ""
        alternate, pdf_url = self._entry_links(entry)
        base_id, version = split_arxiv_id(raw_identifier)
        if version is None and pdf_url:
            pdf_base_id, pdf_version = split_arxiv_id(pdf_url)
            if pdf_base_id == base_id:
                version = pdf_version
        versioned_identifier = f"{base_id}v{version}" if base_id and version else base_id or raw_identifier
        published = entry.findtext(f"{ATOM}published")
        updated = entry.findtext(f"{ATOM}updated")
        doi = entry.findtext(f"{ARXIV}doi")
        dates = []
        if published:
            dates.append({
                "value": published[:10],
                "source": "arxiv_v1",
                "url": f"https://arxiv.org/abs/{base_id}v1" if base_id else alternate,
                "verified": True,
            })
        if updated and version and version > 1:
            dates.append({
                "value": updated[:10],
                "source": f"arxiv_v{version}",
                "url": f"https://arxiv.org/abs/{versioned_identifier}",
                "verified": True,
            })
        exact_pdf_url = None
        if pdf_url and base_id and version:
            exact_pdf_url = f"https://arxiv.org/pdf/{versioned_identifier}"
        elif pdf_url:
            exact_pdf_url = pdf_url
        arxiv_versions = []
        if version and updated:
            arxiv_versions.append({
                "version": version,
                "identifier": versioned_identifier,
                "submitted_at": updated[:10],
                "pdf_url": exact_pdf_url,
                "verified": True,
            })
        record = {
            "id": versioned_identifier,
            "arxiv_id": versioned_identifier,
            "arxiv_version": version,
            "arxiv_latest_version_verified": latest_version_verified,
            "arxiv_versions": arxiv_versions,
            "doi": doi,
            "title": " ".join((entry.findtext(f"{ATOM}title") or "").split()),
            "abstract": " ".join((entry.findtext(f"{ATOM}summary") or "").split()),
            "authors": [{"name": author.findtext(f"{ATOM}name") or ""} for author in entry.findall(f"{ATOM}author")],
            "year": int(published[:4]) if published else None,
            "venue": entry.findtext(f"{ARXIV}journal_ref"),
            "url": alternate or (f"https://arxiv.org/abs/{versioned_identifier}" if versioned_identifier else None),
            "fulltext_urls": [exact_pdf_url] if exact_pdf_url else [],
            "dates": dates,
            "raw_provenance": [{"provider": self.name, "provider_id": versioned_identifier}],
        }
        return normalize_paper(record, self.name)

    def search_with_metadata(self, query: str, *, before: str | None = None, limit: int = 100, page_token: Any | None = None) -> SearchResult:
        requested = min(max(limit, 1), 100)
        root = self._fetch({"search_query": build_arxiv_query(query), "start": int(page_token or 0), "max_results": requested, "sortBy": "relevance"})
        entries = root.findall(f"{ATOM}entry")
        raw_returned_count = len(entries)
        papers = [self._convert(entry, latest_version_verified=True) for entry in entries]
        if before:
            cutoff = date.fromisoformat(before)
            papers = [paper for paper in papers if paper.get("dates") and date.fromisoformat(paper["dates"][0]["value"]) <= cutoff]

        def integer(name: str, default: int | None = None) -> int | None:
            value = root.findtext(f"{OPENSEARCH}{name}")
            return int(value) if value not in (None, "") else default

        start = integer("startIndex", int(page_token or 0)) or 0
        total_count = integer("totalResults")
        next_offset = (
            start + raw_returned_count
            if raw_returned_count > 0 and total_count is not None and start + raw_returned_count < total_count
            else None
        )
        return SearchResult(
            papers=papers[:limit],
            total_count=total_count,
            pagination={
                "start": start,
                "items_per_page": integer("itemsPerPage", requested),
                "raw_returned_count": raw_returned_count,
                "eligible_returned_count": len(papers[:limit]),
                "next": next_offset,
            },
        )

    def get_by_id(self, identifier: str) -> dict[str, Any]:
        root = self._fetch({"id_list": identifier, "max_results": 1})
        entry = root.find(f"{ATOM}entry")
        if entry is None:
            raise ProviderError(f"arXiv paper not found: {identifier}")
        _, requested_version = split_arxiv_id(identifier)
        return self._convert(entry, latest_version_verified=requested_version is None)

    def version_history(
        self,
        identifier: str,
        *,
        latest_version: int | None = None,
        max_versions: int = MAX_VERSION_HISTORY,
    ) -> list[dict[str, Any]]:
        """Return complete, exact-version metadata or fail closed.

        The arXiv API accepts versioned IDs in ``id_list`` and reports the
        retrieved version's submission date in ``updated``. A complete history
        lets the full-text stage pin evidence to the latest version that existed
        at the historical cutoff instead of following an unversioned current PDF.
        """
        base_id = normalize_arxiv_id(identifier)
        if not base_id:
            raise ProviderError("arXiv version history requires a valid identifier")
        latest_record = None
        if latest_version is None:
            latest_record = self.get_by_id(base_id)
            latest_version = latest_record.get("arxiv_version")
        if not isinstance(latest_version, int) or isinstance(latest_version, bool) or latest_version < 1:
            raise ProviderError("arXiv latest version number could not be verified")
        if latest_version > max_versions:
            raise ProviderError(
                f"arXiv version history exceeds the safety limit of {max_versions} versions"
            )
        if latest_record is not None and latest_version == 1:
            return [latest_record]

        requested_versions = list(range(1, latest_version + 1))
        if latest_record is not None:
            requested_versions = requested_versions[:-1]
            if requested_versions:
                time.sleep(3)
        records = []
        if requested_versions:
            ids = ",".join(f"{base_id}v{version}" for version in requested_versions)
            root = self._fetch({"id_list": ids, "max_results": len(requested_versions)})
            records.extend(self._convert(entry) for entry in root.findall(f"{ATOM}entry"))
        if latest_record is not None:
            records.append(latest_record)

        by_version: dict[int, dict[str, Any]] = {}
        for record in records:
            record_base_id = normalize_arxiv_id(record.get("arxiv_id"))
            version = record.get("arxiv_version")
            if record_base_id != base_id or not isinstance(version, int) or isinstance(version, bool):
                raise ProviderError("arXiv returned mismatched version-history metadata")
            if version in by_version:
                raise ProviderError("arXiv returned a duplicate version-history entry")
            by_version[version] = record
        missing = sorted(set(range(1, latest_version + 1)) - set(by_version))
        if missing:
            raise ProviderError(f"arXiv version history is incomplete; missing versions: {missing}")
        return [by_version[version] for version in range(1, latest_version + 1)]
