import sys
import types
from pathlib import Path

import fulltext
import pytest
from fulltext import (
    FullTextError,
    _extract,
    _PinnedHTTPConnection,
    _PinnedHTTPSConnection,
    acquire_fulltexts,
    source_candidates,
)


def test_acquires_html_with_hashes_and_auditable_text(tmp_path):
    papers = [{"id": "P1", "fulltext_urls": ["https://example.org/paper.html"]}]

    def fetcher(url, max_bytes):
        assert url == "https://example.org/paper.html"
        assert max_bytes == 12345
        return b"<html><style>hidden</style><body><h1>Method</h1><p>Adaptive memory.</p></body></html>", "text/html", url

    result = acquire_fulltexts(papers, tmp_path, fetcher=fetcher, max_bytes=12345)
    assert result["status"] == "COMPLETE"
    acquisition = result["fulltext_acquisitions"][0]
    assert acquisition["source_kind"] == "HTML"
    assert acquisition["extraction_method"] == "html.parser"
    assert acquisition["content_sha256"].startswith("sha256:")
    text = Path(acquisition["text_path"]).read_text(encoding="utf-8")
    assert "Adaptive memory" in text
    assert "hidden" not in text


def test_pdf_extraction_uses_declared_runtime_dependency(monkeypatch):
    class Page:
        def extract_text(self):
            return "Evidence from methods."

    fake = types.SimpleNamespace(PdfReader=lambda stream: types.SimpleNamespace(pages=[Page()]))
    monkeypatch.setitem(sys.modules, "pypdf", fake)
    text, kind, method = _extract(b"%PDF-fake", "application/pdf")
    assert (text, kind, method) == ("Evidence from methods.", "PDF", "pypdf")


def test_partial_result_discloses_missing_public_fulltext(tmp_path):
    papers = [
        {"id": "P1", "arxiv_id": "2401.01234"},
        {"id": "P2"},
    ]

    def fetcher(url, max_bytes):
        return b"full scholarly text", "text/plain", url

    result = acquire_fulltexts(papers, tmp_path, fetcher=fetcher)
    assert result["status"] == "PARTIAL"
    assert result["fulltext_acquisitions"][0]["paper_id"] == "P1"
    assert result["failures"] == [{
        "paper_id": "P2",
        "error_code": "NO_PUBLIC_FULLTEXT_URL",
        "detail": "No provider-derived public full-text URL was available.",
    }]


def test_source_candidates_reject_local_or_credentialed_urls():
    paper = {"id": "P", "fulltext_urls": [
        "http://127.0.0.1/private",
        "https://user:pass@example.org/private",
        "https://example.org/public.pdf",
    ]}
    assert source_candidates(paper) == ["https://example.org/public.pdf"]


class _FakeSocket:
    def __init__(self, peer="93.184.216.34"):
        self.peer = peer
        self.connected_to = None
        self.closed = False

    def settimeout(self, _timeout):
        pass

    def bind(self, _source):
        pass

    def connect(self, address):
        self.connected_to = address

    def getpeername(self):
        return self.peer, 443

    def setsockopt(self, *_args):
        pass

    def close(self):
        self.closed = True


def test_pinned_connection_defeats_dns_rebinding_between_check_and_connect(monkeypatch):
    resolutions = []
    public_record = (
        fulltext.socket.AF_INET,
        fulltext.socket.SOCK_STREAM,
        fulltext.socket.IPPROTO_TCP,
        "",
        ("93.184.216.34", 80),
    )
    private_record = (
        fulltext.socket.AF_INET,
        fulltext.socket.SOCK_STREAM,
        fulltext.socket.IPPROTO_TCP,
        "",
        ("127.0.0.1", 80),
    )

    def rebinding_resolver(*_args, **_kwargs):
        resolutions.append(True)
        return [public_record] if len(resolutions) == 1 else [private_record]

    fake = _FakeSocket()
    monkeypatch.setattr(fulltext.socket, "getaddrinfo", rebinding_resolver)
    monkeypatch.setattr(fulltext.socket, "socket", lambda *_args, **_kwargs: fake)
    connection = _PinnedHTTPConnection("papers.example", 80)
    connection.connect()
    assert len(resolutions) == 1
    assert fake.connected_to == ("93.184.216.34", 80)


def test_pinned_connection_rejects_any_private_dns_answer(monkeypatch):
    records = [
        (fulltext.socket.AF_INET, fulltext.socket.SOCK_STREAM, 0, "", ("93.184.216.34", 80)),
        (fulltext.socket.AF_INET, fulltext.socket.SOCK_STREAM, 0, "", ("169.254.169.254", 80)),
    ]
    monkeypatch.setattr(fulltext.socket, "getaddrinfo", lambda *_args, **_kwargs: records)
    with pytest.raises(FullTextError, match="non-public"):
        _PinnedHTTPConnection("mixed.example", 80)


def test_pinned_connection_rejects_unvalidated_private_peer(monkeypatch):
    records = [
        (fulltext.socket.AF_INET, fulltext.socket.SOCK_STREAM, 0, "", ("93.184.216.34", 80)),
    ]
    fake = _FakeSocket(peer="127.0.0.1")
    monkeypatch.setattr(fulltext.socket, "getaddrinfo", lambda *_args, **_kwargs: records)
    monkeypatch.setattr(fulltext.socket, "socket", lambda *_args, **_kwargs: fake)
    connection = _PinnedHTTPConnection("papers.example", 80)
    with pytest.raises(FullTextError, match="unvalidated or non-public peer"):
        connection.connect()
    assert fake.closed is True


def test_pinned_https_preserves_original_hostname_for_tls_sni(monkeypatch):
    records = [
        (fulltext.socket.AF_INET, fulltext.socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443)),
    ]
    fake = _FakeSocket()
    captured = {}

    class Context:
        def wrap_socket(self, sock, *, server_hostname):
            captured["server_hostname"] = server_hostname
            return sock

    monkeypatch.setattr(fulltext.socket, "getaddrinfo", lambda *_args, **_kwargs: records)
    monkeypatch.setattr(fulltext.socket, "socket", lambda *_args, **_kwargs: fake)
    connection = _PinnedHTTPSConnection("papers.example", 443)
    connection._context = Context()
    connection.connect()
    assert fake.connected_to == ("93.184.216.34", 443)
    assert captured["server_hostname"] == "papers.example"


def test_pdf_dependency_failure_is_explicit(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(FullTextError, match="install pypdf"):
        _extract(b"%PDF-fake", "application/pdf")
