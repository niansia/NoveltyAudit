"""Acquire public scholarly full text with auditable hashes and safe extraction."""

from __future__ import annotations

import http.client
import ipaddress
import re
import socket
from collections.abc import Callable
from datetime import date, datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import (
    HTTPHandler,
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from normalize_paper import normalize_arxiv_id, split_arxiv_id
from providers.arxiv import ArxivProvider


USER_AGENT = "NoveltyAudit/0.3.1"
ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
ARXIV_VERSION_LOCK = "LATEST_VERIFIED_VERSION_AT_OR_BEFORE_CUTOFF"
ArxivVersionResolver = Callable[[str, int | None], list[dict[str, Any]]]


class FullTextError(RuntimeError):
    pass


def _public_address_records(hostname: str, port: int) -> tuple[tuple[Any, Any, int, tuple[Any, ...], str], ...]:
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise FullTextError(f"full-text host resolution failed: {type(error).__name__}") from error
    approved: list[tuple[Any, Any, int, tuple[Any, ...], str]] = []
    seen: set[tuple[Any, str, int]] = set()
    for family, socktype, proto, _canonical_name, sockaddr in records:
        address = str(sockaddr[0]).split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as error:
            raise FullTextError("full-text resolver returned an invalid address") from error
        if not ip.is_global:
            raise FullTextError("full-text URL resolves to a non-public address")
        key = (family, str(ip), int(sockaddr[1]))
        if key not in seen:
            approved.append((family, socktype, proto, sockaddr, str(ip)))
            seen.add(key)
    if not approved:
        raise FullTextError("full-text host resolution returned no public addresses")
    return tuple(approved)


class _PinnedConnectionMixin:
    _pinned_records: tuple[tuple[Any, Any, int, tuple[Any, ...], str], ...]

    def _pin_public_peer(self) -> None:
        self._pinned_records = _public_address_records(self.host, self.port or self.default_port)

    def _create_pinned_connection(  # type: ignore[no-untyped-def]
        self, _address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None
    ):
        approved = {record[4] for record in self._pinned_records}
        last_error: OSError | None = None
        for family, socktype, proto, sockaddr, _validated_address in self._pinned_records:
            connection = None
            try:
                connection = socket.socket(family, socktype, proto)
                if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                    connection.settimeout(timeout)
                if source_address:
                    connection.bind(source_address)
                connection.connect(sockaddr)
                peer = str(ipaddress.ip_address(str(connection.getpeername()[0]).split("%", 1)[0]))
                if peer not in approved or not ipaddress.ip_address(peer).is_global:
                    raise FullTextError("full-text connection reached an unvalidated or non-public peer")
                return connection
            except FullTextError:
                if connection is not None:
                    connection.close()
                raise
            except OSError as error:
                last_error = error
                if connection is not None:
                    connection.close()
        if last_error is not None:
            raise last_error
        raise FullTextError("full-text connection had no validated public peer")


class _PinnedHTTPConnection(_PinnedConnectionMixin, http.client.HTTPConnection):
    def __init__(self, host, port=None, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(host, port, **kwargs)
        self._pin_public_peer()
        self._create_connection = self._create_pinned_connection


class _PinnedHTTPSConnection(_PinnedConnectionMixin, http.client.HTTPSConnection):
    def __init__(self, host, port=None, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(host, port, **kwargs)
        self._pin_public_peer()
        self._create_connection = self._create_pinned_connection


class _PinnedHTTPHandler(HTTPHandler):
    def http_open(self, req):  # type: ignore[no-untyped-def]
        return self.do_open(_PinnedHTTPConnection, req)


class _PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, req):  # type: ignore[no-untyped-def]
        return self.do_open(
            _PinnedHTTPSConnection,
            req,
            context=self._context,
            check_hostname=self._check_hostname,
        )


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
        target = _validate_public_url(urljoin(req.full_url, newurl), resolve=False)
        return super().redirect_request(req, fp, code, msg, headers, target)


def fetch_url(url: str, max_bytes: int = 25_000_000) -> tuple[bytes, str, str]:
    url = _validate_public_url(url, resolve=False)
    opener = build_opener(
        ProxyHandler({}),
        _SafeRedirectHandler(),
        _PinnedHTTPHandler(),
        _PinnedHTTPSHandler(),
    )
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
    if content_type in {"text/html", "application/xhtml+xml"} or re.search(r"<html\b", decoded[:1000], re.IGNORECASE):
        parser = _TextExtractor()
        parser.feed(decoded)
        return parser.text(), "HTML", "html.parser"
    return decoded, "TEXT", "utf-8"


def _date_value(value: Any) -> date | None:
    text = str(value or "").strip()
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _arxiv_identity(url: str) -> tuple[str, int | None] | None:
    parsed = urlsplit(url)
    if (parsed.hostname or "").casefold() not in ARXIV_HOSTS:
        return None
    path = parsed.path
    if path.startswith("/pdf/"):
        identifier = path.removeprefix("/pdf/")
    elif path.startswith("/abs/"):
        identifier = path.removeprefix("/abs/")
    else:
        return None
    if identifier.casefold().endswith(".pdf"):
        identifier = identifier[:-4]
    base_id, version = split_arxiv_id(identifier)
    return (base_id, version) if base_id else None


def _exact_arxiv_pdf(url: Any, base_id: str, version: int) -> str | None:
    if not url:
        return None
    candidate = str(url)
    identity = _arxiv_identity(candidate)
    if identity != (base_id, version):
        return None
    try:
        _validate_public_url(candidate, resolve=False)
    except FullTextError:
        return None
    return f"https://arxiv.org/pdf/{base_id}v{version}"


def _version_entries_from_record(paper: dict[str, Any], base_id: str) -> dict[int, dict[str, Any]]:
    records = [paper, *(item for item in (paper.get("versions") or []) if isinstance(item, dict))]
    entries: dict[int, dict[str, Any]] = {}
    for record in records:
        for raw in record.get("arxiv_versions") or []:
            if not isinstance(raw, dict) or raw.get("verified") is not True:
                continue
            version = raw.get("version")
            submitted_at = _date_value(raw.get("submitted_at"))
            if not isinstance(version, int) or isinstance(version, bool) or version < 1 or submitted_at is None:
                continue
            identifier_base, identifier_version = split_arxiv_id(raw.get("identifier"))
            if identifier_base != base_id or identifier_version != version:
                continue
            pdf_url = _exact_arxiv_pdf(raw.get("pdf_url"), base_id, version)
            candidate = {
                "version": version,
                "identifier": f"{base_id}v{version}",
                "submitted_at": submitted_at.isoformat(),
                "pdf_url": pdf_url,
                "verified": True,
            }
            previous = entries.get(version)
            if previous:
                if previous["submitted_at"] != candidate["submitted_at"]:
                    raise FullTextError(f"conflicting arXiv metadata for version v{version}")
                if previous.get("pdf_url") and candidate.get("pdf_url") and previous["pdf_url"] != candidate["pdf_url"]:
                    raise FullTextError(f"conflicting arXiv PDF metadata for version v{version}")
                if not previous.get("pdf_url") and candidate.get("pdf_url"):
                    entries[version] = candidate
            else:
                entries[version] = candidate

    for record in records:
        record_version = record.get("arxiv_version")
        if (
            not isinstance(record_version, int)
            or isinstance(record_version, bool)
            or record_version < 1
            or record_version in entries
        ):
            continue
        source = "arxiv_v1" if record_version == 1 else f"arxiv_v{record_version}"
        submitted_at = next(
            (
                _date_value(item.get("value"))
                for item in record.get("dates") or []
                if isinstance(item, dict)
                and item.get("source") == source
                and item.get("verified", True) is True
            ),
            None,
        )
        pdf_url = next(
            (
                exact
                for value in record.get("fulltext_urls") or []
                if (exact := _exact_arxiv_pdf(value, base_id, record_version))
            ),
            None,
        )
        if submitted_at is not None:
            entries[record_version] = {
                "version": record_version,
                "identifier": f"{base_id}v{record_version}",
                "submitted_at": submitted_at.isoformat(),
                "pdf_url": pdf_url,
                "verified": True,
            }
    return entries


def _latest_verified_arxiv_version(
    paper: dict[str, Any], entries: dict[int, dict[str, Any]]
) -> int | None:
    records = [paper, *(item for item in (paper.get("versions") or []) if isinstance(item, dict))]
    verified = []
    for record in records:
        if record.get("arxiv_latest_version_verified") is not True:
            continue
        value = record.get("arxiv_version")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
            verified.append(value)
    if not verified:
        return None
    latest = max(verified)
    return latest if latest in entries else None


def _validate_version_entries(
    entries: dict[int, dict[str, Any]], *, latest_version: int, require_complete: bool
) -> None:
    if require_complete and set(entries) != set(range(1, latest_version + 1)):
        missing = sorted(set(range(1, latest_version + 1)) - set(entries))
        raise FullTextError(f"arXiv version history is incomplete; missing versions: {missing}")
    previous_date: date | None = None
    for version in sorted(entries):
        entry = entries[version]
        submitted_at = _date_value(entry.get("submitted_at"))
        if submitted_at is None or entry.get("verified") is not True:
            raise FullTextError(f"arXiv version v{version} lacks verified submission metadata")
        if previous_date is not None and submitted_at < previous_date:
            raise FullTextError("arXiv version dates are not monotonic")
        previous_date = submitted_at


def _select_version_entry(
    entries: dict[int, dict[str, Any]],
    *,
    cutoff: date,
    latest_version: int | None,
    require_complete_history: bool,
) -> dict[str, Any] | None:
    if latest_version is None:
        return None
    _validate_version_entries(
        entries, latest_version=latest_version, require_complete=require_complete_history
    )
    eligible = [
        entry for version, entry in entries.items()
        if version <= latest_version
        and _date_value(entry.get("submitted_at")) is not None
        and _date_value(entry.get("submitted_at")) <= cutoff
        and entry.get("pdf_url")
    ]
    return max(eligible, key=lambda item: int(item["version"])) if eligible else None


def _default_arxiv_version_resolver(base_id: str, latest_version: int | None) -> list[dict[str, Any]]:
    return ArxivProvider().version_history(base_id, latest_version=latest_version)


def _historical_arxiv_source(
    paper: dict[str, Any],
    resolver: ArxivVersionResolver,
) -> dict[str, Any] | None:
    base_id = normalize_arxiv_id(paper.get("arxiv_id"))
    if not base_id or paper.get("cutoff_status") != "ELIGIBLE":
        return None
    cutoff = _date_value(paper.get("cutoff"))
    if cutoff is None:
        raise FullTextError("strict historical arXiv acquisition requires paper.cutoff as YYYY-MM-DD")

    local_entries = _version_entries_from_record(paper, base_id)
    latest_version = _latest_verified_arxiv_version(paper, local_entries)
    latest_entry = local_entries.get(latest_version) if latest_version is not None else None
    if latest_entry and _date_value(latest_entry.get("submitted_at")) <= cutoff and latest_entry.get("pdf_url"):
        _validate_version_entries(local_entries, latest_version=latest_version, require_complete=False)
        selected = latest_entry
        selection_entries = local_entries
        history_complete = set(local_entries) == set(range(1, latest_version + 1))
        method = "LOCAL_LATEST_VERSION_METADATA"
    else:
        try:
            history = resolver(base_id, latest_version)
        except Exception as error:  # noqa: BLE001 - fail closed on provider/version-resolution errors
            raise FullTextError(f"arXiv version history resolution failed: {error}") from error
        resolved_entries: dict[int, dict[str, Any]] = {}
        for record in history:
            if not isinstance(record, dict):
                raise FullTextError("arXiv version resolver returned a malformed record")
            record_base = normalize_arxiv_id(record.get("arxiv_id"))
            version = record.get("arxiv_version")
            if record_base != base_id or not isinstance(version, int) or isinstance(version, bool):
                raise FullTextError("arXiv version resolver returned mismatched metadata")
            record_entries = _version_entries_from_record(record, base_id)
            entry = record_entries.get(version)
            if entry is None:
                raise FullTextError(f"arXiv version resolver omitted verified metadata for v{version}")
            if version in resolved_entries and resolved_entries[version] != entry:
                raise FullTextError(f"arXiv version resolver returned conflicting metadata for v{version}")
            resolved_entries[version] = entry
        resolved_latest = max(resolved_entries) if resolved_entries else None
        if latest_version is not None and resolved_latest != latest_version:
            raise FullTextError(
                f"arXiv version history disagrees with the known latest version v{latest_version}"
            )
        latest_version = resolved_latest
        selected = _select_version_entry(
            resolved_entries,
            cutoff=cutoff,
            latest_version=latest_version,
            require_complete_history=True,
        )
        selection_entries = resolved_entries
        history_complete = True
        method = "ARXIV_API_COMPLETE_VERSION_HISTORY"
    if selected is None:
        raise FullTextError("no verified downloadable arXiv version existed at or before the cutoff")
    return {
        **selected,
        "cutoff": cutoff.isoformat(),
        "version_lock": ARXIV_VERSION_LOCK,
        "selection_method": method,
        "version_history": [selection_entries[version] for version in sorted(selection_entries)],
        "version_history_complete": history_complete,
    }


def _require_same_arxiv_version(requested_url: str, final_url: str) -> None:
    requested = _arxiv_identity(requested_url)
    if requested is None or requested[1] is None:
        raise FullTextError("historical arXiv request was not pinned to an explicit version")
    final = _arxiv_identity(final_url)
    if final != requested:
        raise FullTextError("historical arXiv download did not preserve the explicitly requested version")


def source_candidates(paper: dict[str, Any]) -> list[str]:
    candidates = list(paper.get("fulltext_urls") or [])
    open_access = paper.get("open_access")
    if isinstance(open_access, str):
        candidates.append(open_access)
    elif isinstance(open_access, dict):
        for key in ("url", "oa_url", "pdf_url", "landing_page_url"):
            if open_access.get(key):
                candidates.append(str(open_access[key]))
    arxiv_id = normalize_arxiv_id(paper.get("arxiv_id"))
    arxiv_version = paper.get("arxiv_version")
    if arxiv_id:
        suffix = (
            f"v{arxiv_version}"
            if isinstance(arxiv_version, int) and not isinstance(arxiv_version, bool) and arxiv_version >= 1
            else ""
        )
        candidates.append(f"https://arxiv.org/pdf/{arxiv_id}{suffix}")
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
    arxiv_version_resolver: ArxivVersionResolver = _default_arxiv_version_resolver,
) -> dict[str, Any]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    acquisitions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for paper in papers:
        paper_id = str(paper.get("id") or "")
        if not paper_id:
            failures.append({
                "paper_id": "<missing>",
                "error_code": "NO_PUBLIC_FULLTEXT_URL",
                "detail": "No provider-derived public full-text URL was available.",
            })
            continue
        try:
            historical_arxiv = _historical_arxiv_source(paper, arxiv_version_resolver)
        except FullTextError as error:
            failures.append({
                "paper_id": paper_id,
                "error_code": "ARXIV_VERSION_RESOLUTION_FAILED",
                "detail": str(error),
            })
            continue
        urls = [historical_arxiv["pdf_url"]] if historical_arxiv else source_candidates(paper)
        if not urls:
            failures.append({
                "paper_id": paper_id,
                "error_code": "NO_PUBLIC_FULLTEXT_URL",
                "detail": "No provider-derived public full-text URL was available.",
            })
            continue
        errors: list[str] = []
        for url in urls:
            try:
                payload, content_type, final_url = fetcher(url, max_bytes)
                if historical_arxiv:
                    _require_same_arxiv_version(url, final_url)
                text, source_kind, extraction_method = _extract(payload, content_type)
                text = text.replace("\x00", "").strip()
                if not text:
                    raise FullTextError("full-text extraction produced no text")
                content_hash = sha256(payload).hexdigest()
                text_hash = sha256(text.encode("utf-8")).hexdigest()
                text_path = target / f"{_safe_stem(paper_id)}-{text_hash[:12]}.txt"
                text_path.write_text(text + "\n", encoding="utf-8")
                acquisition_id = f"FT:{paper_id}:{text_hash[:16]}"
                acquisition = {
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
                }
                if historical_arxiv:
                    acquisition.update({
                        "historical_cutoff": historical_arxiv["cutoff"],
                        "arxiv_version": historical_arxiv["version"],
                        "arxiv_version_date": historical_arxiv["submitted_at"],
                        "version_lock": historical_arxiv["version_lock"],
                        "version_selection_method": historical_arxiv["selection_method"],
                        "arxiv_version_history": historical_arxiv["version_history"],
                        "arxiv_version_history_complete": historical_arxiv["version_history_complete"],
                    })
                acquisitions.append(acquisition)
                break
            except Exception as error:  # noqa: BLE001 - isolate one failed candidate URL
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
