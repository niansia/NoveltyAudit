import sys
import types
from pathlib import Path

import pytest

from fulltext import FullTextError, _extract, acquire_fulltexts, source_candidates


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


def test_pdf_dependency_failure_is_explicit(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(FullTextError, match="install pypdf"):
        _extract(b"%PDF-fake", "application/pdf")
