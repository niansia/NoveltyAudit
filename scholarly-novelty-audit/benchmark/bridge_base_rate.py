#!/usr/bin/env python3
"""Measure reviewer-named prior-work and co-citation bridge base rates.

This is a benchmark utility, not part of the runtime Agent Skill. It reads the
licensed TUdatalib release directly from its ZIP, links explicit reviewer
mentions to the release's Semantic Scholar records without an LLM, resolves
those records to OpenAlex, and measures pre-cutoff co-citation bridges.

The detailed output remains subject to the source dataset's license. Commit
only aggregate output unless redistribution rights have been reviewed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from hashlib import md5
from itertools import combinations
from pathlib import Path
from statistics import median
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DATASET_ID = "tudatalib/4988"
DATASET_LICENSE = "CC BY-NC 4.0"
EXPECTED_MD5 = "67d9e82abe79ed69ea5b5a3e4537ca3b"
OPENALEX = "https://api.openalex.org/works"
S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch"
SELECT = (
    "id,display_name,publication_date,publication_year,ids,primary_location,"
    "referenced_works_count,referenced_works,cited_by_count"
)
BRIDGE_SELECT = "id,display_name,publication_date,ids"

ARXIV_RE = re.compile(
    r"(?:arxiv(?:\.org/(?:abs|pdf)/|\s*(?::|preprint\s+arxiv:)?\s*))"
    r"(?P<id>\d{4}\.\d{4,5}(?:v\d+)?)",
    re.IGNORECASE,
)
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]{2,200})\]\((https?://[^)]+)\)")
PRIOR_CUE_RE = re.compile(
    r"\b(prior|previous|existing|earlier|already|et\s+al|arxiv|doi|"
    r"not\s+novel|lack(?:s|ing)?\s+(?:of\s+)?novelty)\b|https?://",
    re.IGNORECASE,
)


def normalized_title(value: str | None) -> str:
    value = (value or "").casefold()
    value = re.sub(r"under review as a conference paper at \S+ \d{4}", "", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def author_surnames(authors: Any) -> list[str]:
    if not isinstance(authors, list):
        return []
    result: list[str] = []
    for author in authors:
        name = author.get("name") if isinstance(author, dict) else author
        if isinstance(name, str) and name.strip():
            tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", name)
            if tokens:
                result.append(tokens[-1])
    return result


def candidate_records(structured: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect and merge paper-like records embedded anywhere in a case."""
    merged: dict[str, dict[str, Any]] = {}
    for node in iter_dicts(structured):
        title = node.get("title")
        if not isinstance(title, str) or len(normalized_title(title).split()) < 2:
            continue
        paper_id = node.get("paperId") or node.get("paper_id")
        if not isinstance(paper_id, str):
            paper_id = None
        external = node.get("externalIds") or node.get("external_ids") or {}
        if not isinstance(external, dict):
            external = {}
        record = {
            "title": title.strip(),
            "s2_id": paper_id,
            "publication_date": node.get("publicationDate") or node.get("publication_date"),
            "year": node.get("year"),
            "authors": author_surnames(node.get("authors")),
            "external_ids": external,
            "s2_reference_count": node.get("referenceCount") or node.get("reference_count"),
        }
        key = normalized_title(title)
        current = merged.get(key)
        if current is None:
            merged[key] = record
            continue
        for field in ("s2_id", "publication_date", "year", "s2_reference_count"):
            if current.get(field) in (None, "") and record.get(field) not in (None, ""):
                current[field] = record[field]
        if not current["authors"] and record["authors"]:
            current["authors"] = record["authors"]
        current["external_ids"].update(record["external_ids"])
    return list(merged.values())


def novelty_payload(annotation: dict[str, Any]) -> tuple[str, str]:
    statements: list[str] = []
    reviews: list[str] = []
    for output in annotation.get("output") or []:
        statements.extend(str(item) for item in (output.get("novelty_statements") or []) if item)
        if output.get("review"):
            reviews.append(str(output["review"]))
    return "\n".join(statements), "\n".join(reviews)


def cited_reference_numbers(text: str) -> set[int]:
    numbers: set[int] = set()
    for match in re.finditer(r"\[([0-9,\-\s]+)\]", text):
        group = match.group(1)
        for start, end in re.findall(r"(\d+)\s*-\s*(\d+)", group):
            low, high = sorted((int(start), int(end)))
            if high - low <= 25:
                numbers.update(range(low, high + 1))
        without_ranges = re.sub(r"\d+\s*-\s*\d+", "", group)
        numbers.update(int(value) for value in re.findall(r"\d+", without_ranges))
    return numbers


def numbered_reference_blocks(review: str) -> dict[int, str]:
    blocks: dict[int, str] = {}
    pattern = re.compile(
        r"(?:^|\n)\s*\[(\d+)\]\s*(.*?)"
        r"(?=(?:\n\s*\[\d+\])|\Z)",
        re.DOTALL,
    )
    for match in pattern.finditer(review):
        blocks[int(match.group(1))] = match.group(2).strip()
    return blocks


def title_aliases(title: str) -> set[str]:
    aliases: set[str] = set()
    prefix = title.split(":", 1)[0].strip()
    if re.fullmatch(r"[A-Z][A-Z0-9-]{1,14}", prefix):
        aliases.add(prefix)
    return aliases


def _identifier_values(record: dict[str, Any]) -> tuple[str | None, str | None]:
    external = record.get("external_ids") or {}
    doi = external.get("DOI") or external.get("doi")
    arxiv = external.get("ArXiv") or external.get("arxiv")
    return (str(doi) if doi else None, str(arxiv).removesuffix(".pdf") if arxiv else None)


def merge_prior_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge duplicate mentions by scholarly ID, resolved work ID, or title."""
    groups: list[tuple[set[str], dict[str, Any]]] = []
    for source in items:
        item = dict(source)
        doi, arxiv = _identifier_values(item)
        keys = {
            value for value in (
                f"oa:{item.get('openalex_id')}" if item.get("openalex_id") else None,
                f"s2:{item.get('s2_id')}" if item.get("s2_id") else None,
                f"doi:{doi.casefold()}" if doi else None,
                f"arxiv:{arxiv.split('v', 1)[0].casefold()}" if arxiv else None,
                f"title:{normalized_title(item.get('title'))}" if item.get("title") else None,
            ) if value
        }
        match = next(((known, target) for known, target in groups if known & keys), None)
        if match is None:
            groups.append((keys, item))
            continue
        known, target = match
        known.update(keys)
        for field, value in item.items():
            if field == "link_methods":
                target[field] = sorted(set(target.get(field) or []) | set(value or []))
            elif field == "external_ids":
                target.setdefault(field, {}).update(value or {})
            elif target.get(field) in (None, "", [], {}):
                target[field] = value
        if str(target.get("title", "")).startswith(("arXiv:", "DOI:")) and not str(item.get("title", "")).startswith(("arXiv:", "DOI:")):
            target["title"] = item["title"]
    return sorted((item for _, item in groups), key=lambda item: normalized_title(item.get("title")))


def extract_named_priors(
    annotation: dict[str, Any], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    """Conservatively link reviewer novelty statements to known paper records."""
    novelty, review = novelty_payload(annotation)
    novelty_norm = normalized_title(novelty)
    review_norm = normalized_title(review)
    target_norm = normalized_title((annotation.get("input") or {}).get("title"))
    selected: dict[str, dict[str, Any]] = {}
    cited_blocks = {
        number: block
        for number, block in numbered_reference_blocks(review).items()
        if number in cited_reference_numbers(novelty)
    }
    cited_blocks_norm = {number: normalized_title(block) for number, block in cited_blocks.items()}

    def add(record: dict[str, Any], method: str) -> None:
        key = record.get("s2_id") or normalized_title(record.get("title"))
        if not key or normalized_title(record.get("title")) == target_norm:
            return
        item = selected.setdefault(str(key), dict(record) | {"link_methods": []})
        item.setdefault("external_ids", {}).update(record.get("external_ids") or {})
        if method not in item["link_methods"]:
            item["link_methods"].append(method)

    novelty_arxiv = {match.group("id").split("v", 1)[0] for match in ARXIV_RE.finditer(novelty)}
    novelty_dois = {match.group(0).rstrip(".,;)").casefold() for match in DOI_RE.finditer(novelty)}
    surname_candidates: dict[str, list[dict[str, Any]]] = {}
    for record in candidates:
        title = record["title"]
        title_norm = normalized_title(title)
        if not title_norm or SequenceMatcher(None, title_norm, target_norm).ratio() >= 0.92:
            continue
        doi, arxiv = _identifier_values(record)
        if arxiv and arxiv.split("v", 1)[0] in novelty_arxiv:
            add(record, "IDENTIFIER_ARXIV")
        if doi and doi.casefold() in novelty_dois:
            add(record, "IDENTIFIER_DOI")
        if len(title_norm.split()) >= 4 and title_norm in novelty_norm:
            add(record, "EXACT_TITLE")
        if len(title_norm.split()) >= 3:
            for number, block_norm in cited_blocks_norm.items():
                if title_norm not in block_norm:
                    continue
                linked = dict(record)
                linked["external_ids"] = dict(record.get("external_ids") or {})
                block = cited_blocks[number]
                arxiv_matches = [match.group("id").split("v", 1)[0] for match in ARXIV_RE.finditer(block)]
                doi_matches = [match.group(0).rstrip(".,;)") for match in DOI_RE.finditer(block)]
                if len(arxiv_matches) == 1:
                    linked["external_ids"].setdefault("ArXiv", arxiv_matches[0])
                if len(doi_matches) == 1:
                    linked["external_ids"].setdefault("DOI", doi_matches[0])
                add(linked, "NUMBERED_REFERENCE")
        for alias in title_aliases(title):
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", novelty, re.IGNORECASE):
                add(record, "DISTINCTIVE_TITLE_ALIAS")
        surnames = record.get("authors") or []
        if surnames:
            surname_candidates.setdefault(surnames[0].casefold(), []).append(record)

    for surname, records in surname_candidates.items():
        if not re.search(rf"\b{re.escape(surname)}\b(?:\s+et\s+al\.?)?", novelty, re.IGNORECASE):
            continue
        for record in records:
            title_norm = normalized_title(record["title"])
            # A surname alone can be ambiguous. Require uniqueness in the case
            # corpus or the paper's full title in the review bibliography.
            if len(records) == 1 or title_norm in review_norm:
                add(record, "REVIEWER_AUTHOR_LINK")

    # Preserve explicit identifiers even if the release has no matching paper
    # record; resolution may still succeed through DOI/arXiv.
    for arxiv in sorted(novelty_arxiv):
        if not any((_identifier_values(item)[1] or "").split("v", 1)[0] == arxiv for item in selected.values()):
            add({"title": f"arXiv:{arxiv}", "s2_id": None, "publication_date": None,
                 "year": None, "authors": [], "external_ids": {"ArXiv": arxiv},
                 "s2_reference_count": None}, "IDENTIFIER_ARXIV")
    for doi in sorted(novelty_dois):
        if not any((_identifier_values(item)[0] or "").casefold() == doi for item in selected.values()):
            add({"title": f"DOI:{doi}", "s2_id": None, "publication_date": None,
                 "year": None, "authors": [], "external_ids": {"DOI": doi},
                 "s2_reference_count": None}, "IDENTIFIER_DOI")
    for number, block in cited_blocks.items():
        for match in ARXIV_RE.finditer(block):
            arxiv = match.group("id").split("v", 1)[0]
            add({"title": f"arXiv:{arxiv}", "s2_id": None, "publication_date": None,
                 "year": None, "authors": [], "external_ids": {"ArXiv": arxiv},
                 "s2_reference_count": None}, "NUMBERED_REFERENCE_IDENTIFIER")
        for match in DOI_RE.finditer(block):
            doi = match.group(0).rstrip(".,;)")
            add({"title": f"DOI:{doi}", "s2_id": None, "publication_date": None,
                 "year": None, "authors": [], "external_ids": {"DOI": doi},
                 "s2_reference_count": None}, "NUMBERED_REFERENCE_IDENTIFIER")
        quoted_titles = [
            value.strip().rstrip(".") for value in re.findall(r'["\u201c]([^"\u201d]{8,240})["\u201d]', block)
        ]
        if quoted_titles and not any(
            normalized_title(item.get("title")) in normalized_title(block)
            for item in selected.values()
        ):
            add({"title": quoted_titles[0], "s2_id": None, "publication_date": None,
                 "year": None, "authors": [], "external_ids": {},
                 "s2_reference_count": None}, f"NUMBERED_REFERENCE_TITLE_{number}")
    for label, url in MARKDOWN_LINK_RE.findall(novelty):
        arxiv_match = ARXIV_RE.search(url)
        doi_match = DOI_RE.search(url)
        if arxiv_match or doi_match:
            external: dict[str, str] = {}
            if arxiv_match:
                external["ArXiv"] = arxiv_match.group("id").split("v", 1)[0]
            if doi_match:
                external["DOI"] = doi_match.group(0).rstrip(".,;)")
            add({"title": label, "s2_id": None, "publication_date": None,
                 "year": None, "authors": [], "external_ids": external,
                 "s2_reference_count": None}, "MARKDOWN_IDENTIFIER")

    priors = merge_prior_records(list(selected.values()))
    if priors:
        status = "EXTRACTED"
    elif PRIOR_CUE_RE.search(novelty):
        status = "POTENTIAL_MISSED_MENTIONS"
    else:
        status = "NO_EXPLICIT_WORK_DETECTED"
    return priors, status


class DatasetZip:
    def __init__(self, path: Path):
        self.path = path
        self.archive = zipfile.ZipFile(path)
        self.names = set(self.archive.namelist())

    def cases(self) -> list[str]:
        return sorted(
            name.split("/")[1]
            for name in self.names
            if re.fullmatch(r"data_for_release/[^/]+/annotation\.json", name)
        )

    def json(self, name: str) -> dict[str, Any]:
        return json.loads(self.archive.read(name).decode("utf-8"))

    def annotation(self, case_id: str) -> dict[str, Any]:
        return self.json(f"data_for_release/{case_id}/annotation.json")

    def structured(self, case_id: str) -> dict[str, Any]:
        return self.json(f"data_for_release/{case_id}/ours/structured_representation.json")


def file_md5(path: Path) -> str:
    digest = md5()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class ApiBudget:
    maximum: int
    used: int = 0

    def consume(self) -> None:
        if self.used >= self.maximum:
            raise RuntimeError("PAID_CALL_BUDGET_EXHAUSTED")
        self.used += 1


class ApiCache:
    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self.data.get(key)

    def put(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def request_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
) -> Any:
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"User-Agent": "NoveltyAudit/0.3.1 bridge-base-rate"} | (headers or {})
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, data=payload, headers=request_headers), timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                raise
            delay = min(float(error.headers.get("Retry-After", 2 ** attempt)), 30.0)
        except (URLError, TimeoutError):
            if attempt + 1 == attempts:
                raise
            delay = min(2 ** attempt, 10)
        time.sleep(delay)
    raise AssertionError("unreachable")


class Resolver:
    def __init__(self, cache: ApiCache, budget: ApiBudget):
        self.cache = cache
        self.budget = budget
        self.openalex_key = os.getenv("OPENALEX_API_KEY")
        self.s2_key = os.getenv("S2_API_KEY") or os.getenv("SEMANTIC_SCHOLAR_API_KEY")

    def enrich_s2(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for paper_id in sorted(set(ids)):
            cached = self.cache.get(f"s2:{paper_id}")
            if cached is None:
                missing.append(paper_id)
            elif isinstance(cached, dict):
                result[paper_id] = cached
        for start in range(0, len(missing), 100):
            batch = missing[start:start + 100]
            headers = {"x-api-key": self.s2_key} if self.s2_key else {}
            data = request_json(
                S2_BATCH,
                params={"fields": "paperId,title,publicationDate,year,externalIds,referenceCount"},
                body={"ids": batch},
                headers=headers,
            )
            for paper_id, record in zip(batch, data):
                self.cache.put(f"s2:{paper_id}", record)
                if isinstance(record, dict):
                    result[paper_id] = record
            time.sleep(1.0 if not self.s2_key else 0.1)
        return result

    def _openalex(self, key: str, *, identifier: str | None = None,
                  params: dict[str, Any] | None = None, paid: bool = False) -> Any:
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        if paid:
            self.budget.consume()
        api_params = dict(params or {})
        if self.openalex_key:
            api_params["api_key"] = self.openalex_key
        url = OPENALEX + (f"/{quote(identifier, safe=':/')}" if identifier else "")
        data = request_json(url, params=api_params)
        self.cache.put(key, data)
        time.sleep(0.1)
        return data

    def resolve(self, prior: dict[str, Any], s2: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(prior)
        external = dict(prior.get("external_ids") or {})
        if s2:
            external.update(s2.get("externalIds") or {})
            merged["s2_reference_count"] = s2.get("referenceCount")
            merged["s2_publication_date"] = s2.get("publicationDate")
            merged["s2_id"] = s2.get("paperId") or merged.get("s2_id")
            if normalized_title(merged.get("title")) in {"", normalized_title(f"arXiv:{external.get('ArXiv', '')}")}:
                merged["title"] = s2.get("title") or merged.get("title")
        merged["external_ids"] = external
        doi = external.get("DOI") or external.get("doi")
        arxiv = external.get("ArXiv") or external.get("arxiv")
        identifiers: list[tuple[str, str]] = []
        if doi:
            identifiers.append(("DOI", f"doi:{str(doi).removeprefix('https://doi.org/')}"))
        if arxiv:
            arxiv_id = str(arxiv).removesuffix(".pdf").split("v", 1)[0]
            identifiers.append(("ARXIV_DOI", f"doi:10.48550/arXiv.{arxiv_id}"))
        if external.get("MAG"):
            identifiers.append(("MAG", f"mag:{external['MAG']}"))
        if external.get("PubMed") or external.get("PMID"):
            identifiers.append(("PMID", f"pmid:{external.get('PubMed') or external.get('PMID')}"))
        openalex: dict[str, Any] | None = None
        method: str | None = None
        errors: list[str] = []
        for label, identifier in identifiers:
            try:
                data = self._openalex(f"openalex:singleton:{identifier.casefold()}", identifier=identifier)
                if isinstance(data, dict) and data.get("id"):
                    openalex, method = data, label
                    break
            except HTTPError as error:
                if error.code != 404:
                    errors.append(f"{label}:{error.code}")
        if openalex is None and merged.get("title") and not str(merged["title"]).startswith(("DOI:", "arXiv:")):
            query = str(merged["title"])
            try:
                data = self._openalex(
                    f"openalex:search:{normalized_title(query)}",
                    params={"search": query, "per-page": 5, "select": SELECT},
                    paid=True,
                )
                scored = sorted(
                    ((SequenceMatcher(None, normalized_title(query), normalized_title(item.get("display_name"))).ratio(), item)
                     for item in data.get("results") or []),
                    reverse=True,
                    key=lambda pair: pair[0],
                )
                if scored and scored[0][0] >= 0.88:
                    merged["title_resolution_score"] = round(scored[0][0], 4)
                    openalex, method = scored[0][1], "TITLE_SEARCH"
                else:
                    errors.append("TITLE_SEARCH_NO_CONFIDENT_MATCH")
            except (HTTPError, RuntimeError) as error:
                errors.append(str(error))
        if openalex:
            merged.update({
                "openalex_id": str(openalex["id"]).rsplit("/", 1)[-1],
                "openalex_title": openalex.get("display_name"),
                "openalex_publication_date": openalex.get("publication_date"),
                "openalex_referenced_works_count": openalex.get("referenced_works_count"),
                "openalex_referenced_works_nonempty": bool(openalex.get("referenced_works")),
                "openalex_cited_by_count": openalex.get("cited_by_count"),
                "resolution_method": method,
            })
        else:
            merged["resolution_method"] = "UNRESOLVED"
        dates: list[tuple[date, str]] = []
        for field, source in (("publication_date", "DATASET_RECORD"),
                              ("s2_publication_date", "SEMANTIC_SCHOLAR"),
                              ("openalex_publication_date", "OPENALEX")):
            parsed = parse_date(merged.get(field))
            if parsed:
                dates.append((parsed, source))
        if dates:
            earliest = min(item[0] for item in dates)
            merged["earliest_public_date"] = earliest.isoformat()
            merged["earliest_date_sources"] = sorted(source for value, source in dates if value == earliest)
        else:
            merged["earliest_public_date"] = None
            merged["earliest_date_sources"] = []
        oa_count = merged.get("openalex_referenced_works_count")
        s2_count = merged.get("s2_reference_count")
        if isinstance(oa_count, int) and oa_count > 0:
            coverage = "NONEMPTY"
        elif oa_count == 0 and isinstance(s2_count, int) and s2_count > 0:
            coverage = "CONFIRMED_CROSS_PROVIDER_GAP"
        elif oa_count == 0:
            coverage = "EMPTY_UNCONFIRMED"
        else:
            coverage = "UNRESOLVED"
        merged["openalex_reference_coverage_status"] = coverage
        merged["resolution_errors"] = errors
        return merged

    def bridges(self, paper_a: str, paper_b: str, *, max_results: int) -> dict[str, Any]:
        pair = sorted((paper_a, paper_b))
        filter_value = f"cites:{pair[0]},cites:{pair[1]}"
        results: list[dict[str, Any]] = []
        page = 1
        total: int | None = None
        status = "COMPLETE"
        errors: list[str] = []
        try:
            while True:
                key = f"openalex:bridge:{pair[0]}:{pair[1]}:page:{page}:per-page:100"
                data = self._openalex(
                    key,
                    params={"filter": filter_value, "per-page": 100, "page": page,
                            "select": BRIDGE_SELECT},
                    paid=True,
                )
                meta = data.get("meta") or {}
                total = int(meta.get("count") or 0)
                results.extend(data.get("results") or [])
                if len(results) >= total:
                    break
                if len(results) >= max_results:
                    status = "PARTIAL"
                    errors.append("PAIR_RESULT_LIMIT_REACHED")
                    break
                page += 1
        except (HTTPError, RuntimeError, URLError) as error:
            status = "PARTIAL"
            errors.append(str(error))
        return {
            "paper_ids": pair,
            "status": status,
            "provider_total": total,
            "retrieved_count": len(results),
            "provider_cutoff_applied": False,
            "works": [
                {"id": str(item.get("id", "")).rsplit("/", 1)[-1],
                 "publication_date": item.get("publication_date")}
                for item in results
            ],
            "errors": errors,
        }


def target_date(
    annotation: dict[str, Any], candidates: list[dict[str, Any]],
    submission_date: date | None = None,
) -> tuple[date | None, list[str]]:
    target = normalized_title((annotation.get("input") or {}).get("title"))
    dates: list[tuple[date, str]] = []
    annotated = parse_date(annotation.get("publicationDate"))
    if annotated:
        dates.append((annotated, "ANNOTATION_CONFERENCE_RECORD"))
    if submission_date:
        dates.append((submission_date, "ICLR_2025_SUBMISSION_DEADLINE"))
    for record in candidates:
        record_title = normalized_title(record.get("title"))
        if target and SequenceMatcher(None, target, record_title).ratio() >= 0.90:
            parsed = parse_date(record.get("publication_date"))
            if parsed:
                dates.append((parsed, "MATCHED_DATASET_PAPER_RECORD"))
    if not dates:
        return None, []
    earliest = min(item[0] for item in dates)
    return earliest, sorted(source for value, source in dates if value == earliest)


def maturity_bin(days: int | None) -> str:
    if days is None:
        return "UNKNOWN"
    if days < 0:
        return "POST_CUTOFF_PRIOR"
    if days <= 180:
        return "0_TO_6_MONTHS"
    if days <= 365:
        return "6_TO_12_MONTHS"
    if days <= 548:
        return "12_TO_18_MONTHS"
    if days <= 1095:
        return "18_TO_36_MONTHS"
    return "OVER_36_MONTHS"


def zero_interpretation(pair: dict[str, Any], priors: list[dict[str, Any]]) -> str:
    if pair["status"] != "COMPLETE":
        return "UNINTERPRETABLE_INCOMPLETE_QUERY"
    if pair.get("pre_cutoff_bridge_count", 0) > 0:
        return "BRIDGE_PRESENT"
    if pair.get("date_uncertain_count", 0) > 0:
        return "UNINTERPRETABLE_BRIDGE_DATE_MISSING"
    opportunity_days = pair.get("opportunity_days")
    if opportunity_days is None:
        return "UNINTERPRETABLE_ENDPOINT_DATE_MISSING"
    if opportunity_days < 0:
        return "UNINTERPRETABLE_POST_CUTOFF_ENDPOINT"
    by_id = {item.get("openalex_id"): item for item in priors}
    coverage_gap = any(
        (by_id.get(paper_id) or {}).get("openalex_reference_coverage_status")
        in {"CONFIRMED_CROSS_PROVIDER_GAP", "EMPTY_UNCONFIRMED", "UNRESOLVED"}
        for paper_id in pair["paper_ids"]
    )
    short_window = opportunity_days < 548
    if coverage_gap and short_window:
        return "ZERO_WITH_SHORT_WINDOW_AND_COVERAGE_CAVEAT"
    if coverage_gap:
        return "ZERO_WITH_PROVIDER_COVERAGE_CAVEAT"
    if short_window:
        return "ZERO_WITH_SHORT_OBSERVATION_WINDOW"
    return "ZERO_UNDER_MEASURED_PROVIDER_SNAPSHOT"


def summarize(cases: list[dict[str, Any]], *, archive_md5: str, paid_calls: int) -> dict[str, Any]:
    all_priors = [prior for case in cases for prior in case["priors"]]
    all_pairs = [pair for case in cases for pair in case["pairs"]]
    complete_pairs = [pair for pair in all_pairs if pair["status"] == "COMPLETE"]
    dated_priors = [prior["age_at_cutoff_days"] for prior in all_priors if prior.get("age_at_cutoff_days") is not None]
    dated_pairs = [pair["opportunity_days"] for pair in complete_pairs if pair.get("opportunity_days") is not None]
    multi_cases = [case for case in cases if case["named_prior_count"] >= 2]
    complete_multi_cases = [
        case for case in multi_cases
        if case.get("pair_coverage_status") == "COMPLETE"
        and case["pairs"] and all(pair["status"] == "COMPLETE" for pair in case["pairs"])
    ]
    bridge_cases = [case for case in complete_multi_cases if case["pre_cutoff_distinct_bridge_count"] > 0]
    bridge_pairs = [pair for pair in complete_pairs if pair["pre_cutoff_bridge_count"] > 0]
    ref_counts = Counter(prior["openalex_reference_coverage_status"] for prior in all_priors)
    extraction_counts = Counter(case["extraction_status"] for case in cases)
    zero_counts = Counter(pair["negative_interpretation"] for pair in all_pairs)
    maturity_counts = Counter(maturity_bin(value) for value in dated_pairs)

    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    citation_sensitivity: dict[str, Any] = {}
    for threshold in (50, 100, 250, 500, 1000):
        eligible = [
            pair for pair in complete_pairs
            if len(pair.get("endpoint_cited_by_counts") or []) == 2
            and all(isinstance(value, int) and value < threshold for value in pair["endpoint_cited_by_counts"])
        ]
        positive = sum(pair["pre_cutoff_bridge_count"] > 0 for pair in eligible)
        citation_sensitivity[str(threshold)] = {
            "eligible_pairs": len(eligible),
            "pairs_with_bridge": positive,
            "pair_bridge_base_rate": ratio(positive, len(eligible)),
        }

    case_rate = ratio(len(bridge_cases), len(complete_multi_cases))
    if case_rate is None:
        signal = "INSUFFICIENT_COMPLETE_CASES"
    elif case_rate >= 0.30:
        signal = "BRIDGE_MATERIAL_SUBSET"
    elif case_rate <= 0.05:
        signal = "BRIDGE_LOW_BASE_RATE"
    else:
        signal = "BRIDGE_CONDITIONAL_SUBSET"
    return {
        "schema_version": "1.0",
        "snapshot_date": datetime.now(timezone.utc).date().isoformat(),
        "source": {"dataset_id": DATASET_ID, "license": DATASET_LICENSE,
                   "archive_md5": archive_md5},
        "method": {
            "llm_used": False,
            "provider_cutoff_applied_to_bridge_queries": False,
            "cutoff_rule": "day before the earlier of a matched target public date and the 2024-10-01 ICLR submission deadline",
            "bridge_definition": "distinct OpenAlex works citing both endpoints and dated on/before cutoff",
            "short_observation_window_days": 548,
            "openalex_paid_queries_made_or_reused": paid_calls,
        },
        "case_coverage": {
            "annotated_cases": len(cases),
            "all_cases_represented": len(cases) == 82,
            "extraction_status_counts": dict(sorted(extraction_counts.items())),
            "cases_with_detected_named_priors": sum(case["named_prior_count"] > 0 for case in cases),
            "cases_with_two_or_more_named_priors": len(multi_cases),
            "composition_case_prevalence_lower_bound": ratio(len(multi_cases), len(cases)),
        },
        "prior_resolution": {
            "named_priors": len(all_priors),
            "openalex_resolved": sum(bool(prior.get("openalex_id")) for prior in all_priors),
            "openalex_resolution_rate": ratio(sum(bool(prior.get("openalex_id")) for prior in all_priors), len(all_priors)),
            "openalex_reference_coverage_status_counts": dict(sorted(ref_counts.items())),
            "openalex_nonempty_reference_rate": ratio(ref_counts["NONEMPTY"], len(all_priors)),
            "confirmed_cross_provider_gap_rate": ratio(ref_counts["CONFIRMED_CROSS_PROVIDER_GAP"], len(all_priors)),
        },
        "age": {
            "dated_priors": len(dated_priors),
            "median_prior_age_at_cutoff_days": median(dated_priors) if dated_priors else None,
            "dated_complete_pairs": len(dated_pairs),
            "median_pair_opportunity_days": median(dated_pairs) if dated_pairs else None,
            "pair_opportunity_bins": dict(sorted(maturity_counts.items())),
            "pairs_under_18_months": sum(0 <= value < 548 for value in dated_pairs),
            "pairs_under_18_months_rate": ratio(sum(0 <= value < 548 for value in dated_pairs), len(dated_pairs)),
        },
        "bridges": {
            "measured_pairs": len(all_pairs),
            "complete_pairs": len(complete_pairs),
            "pairs_with_pre_cutoff_bridge": len(bridge_pairs),
            "pair_bridge_base_rate": ratio(len(bridge_pairs), len(complete_pairs)),
            "complete_multi_prior_cases": len(complete_multi_cases),
            "cases_with_pre_cutoff_bridge": len(bridge_cases),
            "case_bridge_base_rate": case_rate,
            "distinct_pre_cutoff_bridges_across_cases": sum(case["pre_cutoff_distinct_bridge_count"] for case in complete_multi_cases),
            "negative_interpretation_counts": dict(sorted(zero_counts.items())),
            "citation_base_rate_sensitivity": citation_sensitivity,
            "product_signal": signal,
        },
        "limitations": [
            "Composition prevalence is a conservative lower bound from deterministic explicit-mention linking.",
            "OpenAlex reference coverage is a provider observation, not a claim that a paper lacks a bibliography.",
            "Bridge dates use OpenAlex work publication_date; unresolved version history can undercount historical bridges.",
            "A zero is never pooled with partial queries, unresolved endpoints or dates, or unreported observation-window caveats.",
        ],
    }


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    archive_path = Path(args.dataset_zip)
    archive_md5 = file_md5(archive_path)
    if not args.skip_checksum and archive_md5 != EXPECTED_MD5:
        raise ValueError(f"dataset MD5 mismatch: expected {EXPECTED_MD5}, got {archive_md5}")
    dataset = DatasetZip(archive_path)
    submission_date = parse_date(args.submission_date)
    if args.submission_date and submission_date is None:
        raise ValueError("--submission-date must use YYYY-MM-DD")
    cases: list[dict[str, Any]] = []
    for case_id in dataset.cases():
        annotation = dataset.annotation(case_id)
        candidates = candidate_records(dataset.structured(case_id))
        priors, extraction_status = extract_named_priors(annotation, candidates)
        target_public_date, target_sources = target_date(annotation, candidates, submission_date)
        cutoff = target_public_date - timedelta(days=1) if target_public_date else None
        cases.append({
            "case_id": case_id,
            "human_classes": [output.get("class") for output in annotation.get("output") or []],
            "target_first_public_date": target_public_date.isoformat() if target_public_date else None,
            "target_date_sources": target_sources,
            "cutoff": cutoff.isoformat() if cutoff else None,
            "extraction_status": extraction_status,
            "named_prior_count": len(priors),
            "priors": priors,
            "pairs": [],
        })
    cache = ApiCache(Path(args.cache))
    resolver = Resolver(cache, ApiBudget(args.max_paid_calls))
    s2_ids = [prior["s2_id"] for case in cases for prior in case["priors"] if prior.get("s2_id")]
    s2_records = resolver.enrich_s2(s2_ids)
    for case in cases:
        cutoff = parse_date(case["cutoff"])
        resolved: list[dict[str, Any]] = []
        for prior in case["priors"]:
            item = resolver.resolve(prior, s2_records.get(prior.get("s2_id")))
            prior_date = parse_date(item.get("earliest_public_date"))
            item["age_at_cutoff_days"] = (cutoff - prior_date).days if cutoff and prior_date else None
            resolved.append(item)
        resolved = merge_prior_records(resolved)
        case["priors"] = resolved
        case["named_prior_count"] = len(resolved)
        for left, right in combinations([item for item in resolved if item.get("openalex_id")], 2):
            pair = resolver.bridges(left["openalex_id"], right["openalex_id"], max_results=args.max_pair_results)
            left_date = parse_date(left.get("earliest_public_date"))
            right_date = parse_date(right.get("earliest_public_date"))
            newer = max(left_date, right_date) if left_date and right_date else None
            pair["opportunity_days"] = (cutoff - newer).days if cutoff and newer else None
            pair["endpoint_cited_by_counts"] = [
                left.get("openalex_cited_by_count"), right.get("openalex_cited_by_count")
            ]
            eligible = {
                work["id"] for work in pair["works"]
                if parse_date(work.get("publication_date")) is not None
                and cutoff is not None and parse_date(work["publication_date"]) <= cutoff
                and work["id"] not in pair["paper_ids"]
            }
            uncertain = sum(parse_date(work.get("publication_date")) is None for work in pair["works"])
            pair["pre_cutoff_bridge_ids"] = sorted(eligible)
            pair["pre_cutoff_bridge_count"] = len(eligible)
            pair["date_uncertain_count"] = uncertain
            pair["negative_interpretation"] = zero_interpretation(pair, resolved)
            case["pairs"].append(pair)
        if case["named_prior_count"] >= 2 and len(case["pairs"]) < case["named_prior_count"] * (case["named_prior_count"] - 1) // 2:
            case["pair_coverage_status"] = "PARTIAL_UNRESOLVED_ENDPOINTS"
        elif all(pair["status"] == "COMPLETE" for pair in case["pairs"]):
            case["pair_coverage_status"] = "COMPLETE"
        else:
            case["pair_coverage_status"] = "PARTIAL_QUERY_FAILURE"
        case["pre_cutoff_distinct_bridge_count"] = len({
            bridge_id for pair in case["pairs"] for bridge_id in pair["pre_cutoff_bridge_ids"]
        })
    paid_query_count = sum(
        key.startswith(("openalex:search:", "openalex:bridge:"))
        for key in cache.data
    )
    summary = summarize(cases, archive_md5=archive_md5, paid_calls=paid_query_count)
    return cases, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-zip", required=True, help="Official data_novelty_assessment.zip")
    parser.add_argument("--output", required=True, help="Detailed case-level JSON (keep under source license)")
    parser.add_argument("--summary-output", required=True, help="Aggregate JSON safe for public reporting")
    parser.add_argument("--cache", required=True, help="Resumable provider response cache")
    parser.add_argument("--max-paid-calls", type=int, default=100)
    parser.add_argument("--max-pair-results", type=int, default=1000)
    parser.add_argument(
        "--submission-date", default="2024-10-01",
        help="Dataset-wide submission deadline used as a target-date ceiling (YYYY-MM-DD)",
    )
    parser.add_argument("--skip-checksum", action="store_true")
    args = parser.parse_args()
    cases, summary = run(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"source_license": DATASET_LICENSE, "cases": cases}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary_output = Path(args.summary_output)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
