import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


REPO_ROOT = Path(__file__).resolve().parents[3]
CASE_ROOT = REPO_ROOT / "case-studies"


def test_public_case_studies_validate_against_schema():
    schema = json.loads((CASE_ROOT / "case.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    cases = sorted(CASE_ROOT.glob("*/*/case.json"))
    assert len(cases) == 3

    for path in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(case), key=lambda error: list(error.path))
        assert not errors, f"{path}: {[error.message for error in errors]}"


def test_case_types_are_explicit_and_distinct():
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(CASE_ROOT.glob("*/*/case.json"))]
    assert {case["case_type"] for case in cases} == {
        "SYNTHETIC",
        "REVIEWER_GROUNDED",
        "PUBLIC_CASE_STUDY",
    }
    assert all(case["limitations"] for case in cases)
    assert all(case["provenance"]["sources"] for case in cases)
