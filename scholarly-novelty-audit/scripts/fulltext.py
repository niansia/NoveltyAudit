"""Acquire public scholarly full text with auditable hashes and safe extraction."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import ipaddress
from pathlib import Path
import re
import socket
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


USER_AGENT = "NoveltyAudit/0.3.1 (+https://github.com/)"


class FullTextError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "\n".join(line for line in (" ".join(self.parts).splitlines()) if line.strip())


def _validate_public_url(url: str, *, resolve: bool) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise FullTextError("full-text URL must be public HTTP(S) without embedded credentials")
    hostname = parsed.hostname.casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise FullTextError("full-text URL resolves to a local address")
    addresses: list[str] = []
    try:
        addresses.append(str(ipaddress.ip_address(hostname)))
    except ValueError:
        if resolve:
            try:
                addresses.extend(item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443))
            except OSError as error:
                raise FullTextError(f"full-text host resolution failed: {type(error).__name__}") from error
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise FullTextError("full-text URL resolves to a non-public address")
    return url


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        target = _validate_public_url(urljoin(req.full_url, newurl), resolve=True)
        return super().redirect_request(req, fp, code, msg, headers, target)


def fetch_url(url: str, max_bytes: int = 25_000_000) -> tuple[bytes, str, str]:
    url = _validate_public_url(url, resolve=True)
    opener = build_opener(_SafeRedirectHandler())
    request = Request(url, headers={"Accept": "application/pdf,text/html,text/plain;q=0.9,*/*;q=0.1", "User-Agent": USER_AGENT})
    with opener.open(request, timeout=45) as response:
        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise FullTextError(f"full text exceeds the {max_bytes}-byte safety limit")
        content_type = (response.headers.get_content_type() or "application/octet-stream").casefold()
        final_url = _validate_public_url(response.geturl(), resolve=False)
        return payload, content_type, final_url


def _extract(payload: bytes, content_type: str) -> tuple[str, str, str]:
    if payload.startswith(b"%PDF") or content_type == "application/pdf":
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise FullTextError("PDF extraction unavailable: install pypdf from requirements.txt") from error
        try:
            pages = [(page.extract_text() or "").strip() for page in PdfReader(BytesIO(payload)).pages]
        except Exception as error:
            raise FullTextError(f"PDF extraction failed: {type(error).__name__}") from error
        text = "\n\n".join(page for page in pages if page)
        return text, "PDF", "pypdf"
    decoded = payload.decode("utf-8", errors="replace")
    if content_type in {"text/html", "application/xhtml+xml"} or re.search(r"<html\b", decoded[:1000], re.I):
        parser = _TextExtractor()
        parser.feed(decoded)
        return parser.text(), "HTML", "html.parser"
    return decoded, "TEXT", "utf-8"


def source_candidates(paper: dict[str, Any]) -> list[str]:
    candidates = list(paper.get("fulltext_urls") or [])
    open_access = paper.get("open_access")
    if isinstance(open_access, str):
        candidates.append(open_access)
    elif isinstance(open_access, dict):
        for key in ("url", "oa_url", "pdf_url", "landing_page_url"):
            if open_access.get(key):
                candidates.append(str(open_access[key]))
    if paper.get("arxiv_id"):
        candidates.append(f"https://arxiv.org/pdf/{paper['arxiv_id']}")
    unique: list[str] = []
    for candidate in candidates:
        try:
            validated = _validate_public_url(str(candidate), resolve=False)
        except FullTextError:
            continue
        if validated not in unique:
            unique.append(validated)
    return unique


def _safe_stem(value: Any) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    return stem[:80] or "paper"


def acquire_fulltexts(
    papers: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    fetcher: Callable[[str, int], tuple[bytes, str, str]] = fetch_url,
    max_bytes: int = 25_000_000,
) -> dict[str, Any]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    acquisitions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for paper in papers:
        paper_id = str(paper.get("id") or "")
        urls = source_candidates(paper)
        if not paper_id or not urls:
            failures.append({"paper_id": paper_id or "<missing>", "error_code": "NO_PUBLIC_FULLTEXT_URL", "detail": "No provider-derived public full-text URL was available."})
            continue
        errors: list[str] = []
        for url in urls:
            try:
                payload, content_type, final_url = fetcher(url, max_bytes)
                text, source_kind, extraction_method = _extract(payload, content_type)
                text = text.replace("\x00", "").strip()
                if not text:
                    raise FullTextError("full-text extraction produced no text")
                content_hash = sha256(payload).hexdigest()
                text_hash = sha256(text.encode("utf-8")).hexdigest()
                text_path = target / f"{_safe_stem(paper_id)}-{text_hash[:12]}.txt"
                text_path.write_text(text + "\n", encoding="utf-8")
                acquisition_id = f"FT:{paper_id}:{text_hash[:16]}"
                acquisitions.append({
                    "id": acquisition_id,
                    "paper_id": paper_id,
                    "status": "COMPLETE",
                    "source_url": final_url,
                    "source_kind": source_kind,
                    "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "content_sha256": f"sha256:{content_hash}",
                    "text_sha256": f"sha256:{text_hash}",
                    "text_path": str(text_path),
                    "extraction_method": extraction_method,
                    "char_count": len(text),
                })
                break
            except Exception as error:
                errors.append(f"{url}: {error}")
        else:
            failures.append({"paper_id": paper_id, "error_code": "ACQUISITION_FAILED", "detail": " | ".join(errors)})
    if acquisitions and not failures:
        status = "COMPLETE"
    elif acquisitions:
        status = "PARTIAL"
    else:
        status = "FAILED"
    return {"status": status, "fulltext_acquisitions": acquisitions, "failures": failures}
