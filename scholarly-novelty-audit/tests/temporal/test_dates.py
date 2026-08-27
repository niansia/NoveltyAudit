import pytest

from resolve_dates import apply_cutoff, resolve_earliest_public_date


def test_arxiv_v1_beats_later_publisher_date():
    paper = {"year": 2025, "dates": [
        {"value": "2025-08-01", "source": "publisher_online"},
        {"value": "2024-12-15", "source": "arxiv_v1"},
    ]}
    resolved = resolve_earliest_public_date(paper)
    assert resolved["earliest_public_date"] == "2024-12-15"
    assert resolved["date_provenance"]["source"] == "arxiv_v1"


def test_year_only_is_uncertain_and_never_january_first():
    result = apply_cutoff({"year": 2024, "dates": []}, "2024-06-01")
    assert result["earliest_public_date"] is None
    assert result["cutoff_status"] == "DATE_UNCERTAIN"


def test_post_cutoff_isolated():
    result = apply_cutoff({"dates": [{"value": "2025-10-01", "source": "arxiv_v1"}]}, "2025-09-18")
    assert result["cutoff_status"] == "POST_CUTOFF"


def test_cutoff_requires_day_precision():
    with pytest.raises(ValueError):
        apply_cutoff({"dates": []}, "2025")


def test_month_precision_prevents_later_exact_date_from_becoming_earliest():
    paper = {"dates": [
        {"value": "2025-01", "source": "crossref_published_online"},
        {"value": "2025-03-15", "source": "crossref_issued"},
    ]}
    result = apply_cutoff(paper, "2025-02-01")
    assert result["earliest_public_date"] is None
    assert result["cutoff_status"] == "DATE_UNCERTAIN"
    assert result["date_provenance"]["precision"] == "month"
