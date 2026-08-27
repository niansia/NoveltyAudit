import importlib.util
from pathlib import Path


path = Path(__file__).resolve().parents[2] / "scripts" / "verify_citations.py"
spec = importlib.util.spec_from_file_location("verify_citations", path)
verify_citations = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(verify_citations)


class FakeCrossref:
    def get_by_id(self, identifier):
        return {"doi": f"https://doi.org/{identifier.upper()}"}


class FakeArxiv:
    def get_by_id(self, identifier):
        return {"arxiv_id": f"{identifier}v4"}


def test_independent_identifier_validation_normalizes_resolved_ids():
    checks = verify_citations.verify_paper_identifiers(
        {"doi": "DOI:10.1000/ABC.", "arxiv_id": "2401.01234v2"},
        crossref=FakeCrossref(), arxiv=FakeArxiv(),
    )
    assert [item["valid"] for item in checks] == [True, True]
    assert {item["provider"] for item in checks} == {"crossref", "arxiv"}
