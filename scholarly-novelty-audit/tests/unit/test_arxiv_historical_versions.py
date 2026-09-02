import xml.etree.ElementTree as ET

import pytest
from deduplicate import deduplicate
from fulltext import ARXIV_VERSION_LOCK, acquire_fulltexts, source_candidates
from providers.arxiv import ArxivProvider
from providers.base import ProviderError



def version_entry(version, submitted_at, *, pdf=True):
    base_id = "1706.03762"
    return {
        "id": f"{base_id}v{version}",
        "arxiv_id": f"{base_id}v{version}",
        "arxiv_version": version,
        "arxiv_versions": [{
            "version": version,
            "identifier": f"{base_id}v{version}",
            "submitted_at": submitted_at,
            "pdf_url": f"https://arxiv.org/pdf/{base_id}v{version}" if pdf else None,
            "verified": True,
        }],
        "dates": [{
            "value": submitted_at,
            "source": "arxiv_v1" if version == 1 else f"arxiv_v{version}",
            "verified": True,
        }],
        "fulltext_urls": [f"https://arxiv.org/pdf/{base_id}v{version}"] if pdf else [],
    }


def historical_paper(*, latest_version=3, latest_date="2020-01-01", cutoff="2019-06-01"):
    paper = version_entry(latest_version, latest_date)
    paper.update({
        "id": "P1",
        "cutoff": cutoff,
        "cutoff_status": "ELIGIBLE",
        "earliest_public_date": "2017-06-12",
        "arxiv_latest_version_verified": True,
    })
    return paper


def atom_entry(version, submitted_at):
    published = "2017-06-12" if version > 1 else submitted_at
    return f"""
      <entry>
        <id>https://arxiv.org/abs/1706.03762v{version}</id>
        <title>Attention Is All You Need</title>
        <summary>Version {version}</summary>
        <published>{published}T00:00:00Z</published>
        <updated>{submitted_at}T00:00:00Z</updated>
        <author><name>Ashish Vaswani</name></author>
        <link href="https://arxiv.org/abs/1706.03762v{version}" rel="alternate" type="text/html"/>
        <link href="https://arxiv.org/pdf/1706.03762v{version}" rel="related" title="pdf" type="application/pdf"/>
      </entry>
    """


def atom_feed(*entries):
    return ET.fromstring(
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" '
        'xmlns:arxiv="http://arxiv.org/schemas/atom">'
        + "".join(entries)
        + "</feed>"
    )


def complete_history(_base_id, _latest_version):
    return [
        version_entry(1, "2017-06-12"),
        version_entry(2, "2019-01-15"),
        version_entry(3, "2020-01-01"),
    ]


def test_arxiv_provider_records_exact_version_date_and_pdf():
    paper = ArxivProvider()._convert(
        atom_feed(atom_entry(7, "2023-08-02")).find("{http://www.w3.org/2005/Atom}entry"),
        latest_version_verified=True,
    )

    assert paper["arxiv_id"] == "1706.03762"
    assert paper["arxiv_version"] == 7
    assert paper["arxiv_latest_version_verified"] is True
    assert paper["fulltext_urls"] == ["https://arxiv.org/pdf/1706.03762v7"]
    assert paper["arxiv_versions"] == [{
        "version": 7,
        "identifier": "1706.03762v7",
        "submitted_at": "2023-08-02",
        "pdf_url": "https://arxiv.org/pdf/1706.03762v7",
        "verified": True,
    }]
    assert {item["source"] for item in paper["dates"]} == {"arxiv_v1", "arxiv_v7"}


def test_arxiv_provider_version_history_requires_every_exact_version(monkeypatch):
    provider = ArxivProvider()
    monkeypatch.setattr(
        provider,
        "_fetch",
        lambda params: atom_feed(
            atom_entry(1, "2017-06-12"),
            atom_entry(2, "2019-01-15"),
            atom_entry(3, "2020-01-01"),
        ),
    )

    history = provider.version_history("1706.03762", latest_version=3)

    assert [paper["arxiv_version"] for paper in history] == [1, 2, 3]


def test_arxiv_provider_rejects_incomplete_version_history(monkeypatch):
    provider = ArxivProvider()
    monkeypatch.setattr(
        provider,
        "_fetch",
        lambda params: atom_feed(
            atom_entry(1, "2017-06-12"),
            atom_entry(3, "2020-01-01"),
        ),
    )

    with pytest.raises(ProviderError, match="missing versions"):
        provider.version_history("1706.03762", latest_version=3)


def test_dedup_preserves_arxiv_version_metadata_and_urls():
    records = [
        {
            "id": "W1",
            "title": "Attention Is All You Need",
            "year": 2017,
            "authors": ["Ashish Vaswani"],
            "providers": ["openalex"],
        },
        {
            **version_entry(3, "2020-01-01"),
            "title": "Attention Is All You Need",
            "year": 2017,
            "authors": ["Ashish Vaswani"],
            "providers": ["arxiv"],
        },
    ]

    result = deduplicate(records)[0]

    assert result["arxiv_id"] == "1706.03762"
    assert result["arxiv_version"] == 3
    assert result["arxiv_latest_version_verified"] is False
    assert result["fulltext_urls"] == ["https://arxiv.org/pdf/1706.03762v3"]
    assert result["arxiv_versions"][0]["version"] == 3
    assert result["versions"][1]["arxiv_version"] == 3



def test_dedup_does_not_transfer_latest_verification_to_a_newer_unverified_version():
    records = [
        {
            **version_entry(2, "2019-01-15"),
            "title": "Attention Is All You Need",
            "year": 2017,
            "authors": ["Ashish Vaswani"],
            "providers": ["arxiv"],
            "arxiv_latest_version_verified": True,
        },
        {
            **version_entry(3, "2020-01-01"),
            "title": "Attention Is All You Need",
            "year": 2017,
            "authors": ["Ashish Vaswani"],
            "providers": ["other"],
            "arxiv_latest_version_verified": False,
        },
    ]

    result = deduplicate(records)[0]

    assert result["arxiv_version"] == 3
    assert result["arxiv_latest_version_verified"] is False


def test_historical_acquisition_selects_latest_version_before_cutoff(tmp_path):
    requested = []

    def fetcher(url, max_bytes):
        requested.append(url)
        return b"historical version two", "text/plain", url

    result = acquire_fulltexts(
        [historical_paper()],
        tmp_path,
        fetcher=fetcher,
        arxiv_version_resolver=complete_history,
    )

    assert requested == ["https://arxiv.org/pdf/1706.03762v2"]
    assert result["status"] == "COMPLETE"
    acquisition = result["fulltext_acquisitions"][0]
    assert acquisition["arxiv_version"] == 2
    assert acquisition["arxiv_version_date"] == "2019-01-15"
    assert acquisition["historical_cutoff"] == "2019-06-01"
    assert acquisition["version_lock"] == ARXIV_VERSION_LOCK
    assert acquisition["version_selection_method"] == "ARXIV_API_COMPLETE_VERSION_HISTORY"
    assert acquisition["arxiv_version_history_complete"] is True
    assert [entry["version"] for entry in acquisition["arxiv_version_history"]] == [1, 2, 3]


def test_historical_acquisition_uses_local_latest_when_it_predates_cutoff(tmp_path):
    requested = []

    def resolver(_base_id, _latest_version):
        raise AssertionError("resolver should not be called")

    def fetcher(url, max_bytes):
        requested.append(url)
        return b"latest existed before cutoff", "text/plain", url

    result = acquire_fulltexts(
        [historical_paper(latest_date="2019-01-01", cutoff="2019-06-01")],
        tmp_path,
        fetcher=fetcher,
        arxiv_version_resolver=resolver,
    )

    assert requested == ["https://arxiv.org/pdf/1706.03762v3"]
    assert result["status"] == "COMPLETE"
    acquisition = result["fulltext_acquisitions"][0]
    assert acquisition["version_selection_method"] == "LOCAL_LATEST_VERSION_METADATA"
    assert acquisition["arxiv_version_history_complete"] is False
    assert [entry["version"] for entry in acquisition["arxiv_version_history"]] == [3]


def test_incomplete_history_fails_closed_without_current_revision_fallback(tmp_path):
    requested = []

    def incomplete_history(_base_id, _latest_version):
        return [version_entry(1, "2017-06-12"), version_entry(3, "2020-01-01")]

    def fetcher(url, max_bytes):
        requested.append(url)
        return b"should not be fetched", "text/plain", url

    result = acquire_fulltexts(
        [historical_paper()],
        tmp_path,
        fetcher=fetcher,
        arxiv_version_resolver=incomplete_history,
    )

    assert requested == []
    assert result["status"] == "FAILED"
    assert result["failures"][0]["error_code"] == "ARXIV_VERSION_RESOLUTION_FAILED"


def test_unverified_explicit_version_does_not_skip_complete_history(tmp_path):
    requested = []
    paper = historical_paper()
    paper["arxiv_latest_version_verified"] = False

    def resolver(base_id, latest_version):
        assert base_id == "1706.03762"
        assert latest_version is None
        return complete_history(base_id, latest_version)

    def fetcher(url, max_bytes):
        requested.append(url)
        return b"historical version two", "text/plain", url

    result = acquire_fulltexts(
        [paper],
        tmp_path,
        fetcher=fetcher,
        arxiv_version_resolver=resolver,
    )

    assert result["status"] == "COMPLETE"
    assert requested == ["https://arxiv.org/pdf/1706.03762v2"]
    assert result["fulltext_acquisitions"][0]["version_selection_method"] == "ARXIV_API_COMPLETE_VERSION_HISTORY"


def test_historical_acquisition_rejects_redirect_to_unversioned_pdf(tmp_path):
    def fetcher(url, max_bytes):
        return b"historical version", "text/plain", "https://arxiv.org/pdf/1706.03762"

    result = acquire_fulltexts(
        [historical_paper()],
        tmp_path,
        fetcher=fetcher,
        arxiv_version_resolver=complete_history,
    )

    assert result["status"] == "FAILED"
    assert "did not preserve" in result["failures"][0]["detail"]


def test_nonhistorical_arxiv_prefers_known_explicit_latest_version():
    paper = {"id": "P1", "arxiv_id": "1706.03762", "arxiv_version": 3}
    assert source_candidates(paper) == ["https://arxiv.org/pdf/1706.03762v3"]


def historical_report_acquisition(**overrides):
    history = [
        {
            "version": 1,
            "identifier": "1706.03762v1",
            "submitted_at": "2017-06-12",
            "pdf_url": "https://arxiv.org/pdf/1706.03762v1",
            "verified": True,
        },
        {
            "version": 2,
            "identifier": "1706.03762v2",
            "submitted_at": "2019-01-15",
            "pdf_url": "https://arxiv.org/pdf/1706.03762v2",
            "verified": True,
        },
        {
            "version": 3,
            "identifier": "1706.03762v3",
            "submitted_at": "2020-01-01",
            "pdf_url": "https://arxiv.org/pdf/1706.03762v3",
            "verified": True,
        },
    ]
    acquisition = {
        "paper_id": "P1",
        "source_url": "https://arxiv.org/pdf/1706.03762v2",
        "historical_cutoff": "2019-06-01",
        "arxiv_version": 2,
        "arxiv_version_date": "2019-01-15",
        "version_lock": ARXIV_VERSION_LOCK,
        "version_selection_method": "ARXIV_API_COMPLETE_VERSION_HISTORY",
        "arxiv_version_history": history,
        "arxiv_version_history_complete": True,
    }
    acquisition.update(overrides)
    return {
        "input": {"cutoff": "2019-06-01", "strict_date": True},
        "papers": [{
            "id": "P1",
            "arxiv_id": "1706.03762",
            "arxiv_version": 3,
            "arxiv_latest_version_verified": True,
            "cutoff": "2019-06-01",
            "cutoff_status": "ELIGIBLE",
        }],
        "fulltext_acquisitions": [acquisition],
    }


def test_schema_guard_accepts_cutoff_pinned_arxiv_acquisition():
    from schema_validation import validate_historical_arxiv_acquisitions

    assert validate_historical_arxiv_acquisitions(historical_report_acquisition()) == []


def test_schema_guard_rejects_unversioned_arxiv_acquisition():
    from schema_validation import validate_historical_arxiv_acquisitions

    errors = validate_historical_arxiv_acquisitions(historical_report_acquisition(
        source_url="https://arxiv.org/pdf/1706.03762",
        arxiv_version=None,
    ))

    assert any("requires an explicit vN" in error for error in errors)


def test_schema_guard_rejects_post_cutoff_arxiv_acquisition():
    from schema_validation import validate_historical_arxiv_acquisitions

    errors = validate_historical_arxiv_acquisitions(historical_report_acquisition(
        source_url="https://arxiv.org/pdf/1706.03762v3",
        arxiv_version=3,
        arxiv_version_date="2020-01-01",
    ))

    assert any("post-dates the cutoff" in error for error in errors)


def test_arxiv_provider_preserves_legacy_identifier_namespace():
    entry = ET.fromstring("""
      <entry xmlns="http://www.w3.org/2005/Atom">
        <id>https://arxiv.org/abs/hep-th/9901001v2</id>
        <title>Legacy identifier</title>
        <summary>Version two</summary>
        <published>1999-01-01T00:00:00Z</published>
        <updated>1999-02-01T00:00:00Z</updated>
        <author><name>A. Author</name></author>
        <link href="https://arxiv.org/abs/hep-th/9901001v2" rel="alternate" type="text/html"/>
        <link href="https://arxiv.org/pdf/hep-th/9901001v2" rel="related" title="pdf" type="application/pdf"/>
      </entry>
    """)

    paper = ArxivProvider()._convert(entry, latest_version_verified=True)

    assert paper["arxiv_id"] == "hep-th/9901001"
    assert paper["arxiv_version"] == 2
    assert paper["fulltext_urls"] == ["https://arxiv.org/pdf/hep-th/9901001v2"]


def test_schema_guard_rejects_nonlatest_cutoff_eligible_version():
    from schema_validation import validate_historical_arxiv_acquisitions

    report = historical_report_acquisition(
        source_url="https://arxiv.org/pdf/1706.03762v1",
        arxiv_version=1,
        arxiv_version_date="2017-06-12",
    )
    errors = validate_historical_arxiv_acquisitions(report)

    assert any("not the latest verified version" in error for error in errors)


def test_schema_guard_requires_verified_latest_for_local_selection():
    from schema_validation import validate_historical_arxiv_acquisitions

    report = historical_report_acquisition(
        source_url="https://arxiv.org/pdf/1706.03762v3",
        historical_cutoff="2020-06-01",
        arxiv_version=3,
        arxiv_version_date="2020-01-01",
        version_selection_method="LOCAL_LATEST_VERSION_METADATA",
        arxiv_version_history=[{
            "version": 3,
            "identifier": "1706.03762v3",
            "submitted_at": "2020-01-01",
            "pdf_url": "https://arxiv.org/pdf/1706.03762v3",
            "verified": True,
        }],
        arxiv_version_history_complete=False,
    )
    report["input"]["cutoff"] = "2020-06-01"
    report["papers"][0]["cutoff"] = "2020-06-01"
    report["papers"][0]["arxiv_latest_version_verified"] = False
    errors = validate_historical_arxiv_acquisitions(report)

    assert any("was not independently verified" in error for error in errors)


def test_schema_guard_leaves_non_strict_reports_unchanged():
    from schema_validation import validate_historical_arxiv_acquisitions

    report = historical_report_acquisition(
        source_url="https://arxiv.org/pdf/1706.03762",
        arxiv_version=None,
    )
    report["input"]["strict_date"] = False

    assert validate_historical_arxiv_acquisitions(report) == []
