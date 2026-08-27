import pytest

from export_report import export, to_html, to_markdown, validate_user_output
from validate_output import validate_report


def test_markdown_contains_three_axes_and_mps(valid_report):
    output = to_markdown(valid_report)
    assert "Novelty Risk:** HIGH" in output
    assert "Search Protocol Coverage:** BROAD" in output
    assert "not demonstrated recall" in output
    assert "MPS search bound: K ≤ 3" in output
    assert "Adaptive Memory Systems + Compression-aware Selection" in output


def test_html_escapes_untrusted_claim(valid_report):
    valid_report["input"]["claim"] = "<script>alert(1)</script>"
    output = to_html(valid_report)
    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;" in output
    assert "<table>" in output
    assert "**Novelty Risk:**" not in output


def test_markdown_collapses_untrusted_newlines(valid_report):
    valid_report["input"]["claim"] = "claim\n# Forged section"
    valid_report["papers"][0]["title"] = "paper\n## Forged paper section"
    output = to_markdown(valid_report)
    assert "\n# Forged section" not in output
    assert "\n## Forged paper section" not in output


def test_markdown_escapes_raw_html_and_heading_syntax(valid_report):
    valid_report["residual_novelty"] = "# FORGED SAFE VERDICT <img src=x onerror=alert(1)>"
    output = to_markdown(valid_report)
    assert "\n# FORGED SAFE VERDICT" not in output
    assert "<img" not in output
    assert "&lt;img" in output


def test_rejects_novelty_percentage_in_user_facing_output(valid_report, tmp_path):
    valid_report["residual_novelty"] = "Estimated novelty 99.99%"
    assert validate_user_output(to_html(valid_report), "html")
    assert any("novelty percentage" in error for error in validate_report(valid_report))
    with pytest.raises(ValueError):
        export(valid_report, tmp_path / "report.html", "html")


def test_html_does_not_embed_machine_json_or_internal_features(valid_report):
    valid_report["papers"][0]["embedding_score"] = 0.91
    output = to_html(valid_report)
    assert "Structured JSON" not in output
    assert "embedding_score" not in output
