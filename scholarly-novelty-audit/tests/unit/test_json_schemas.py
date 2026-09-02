import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[2]


def test_all_machine_schemas_are_versioned_and_valid(valid_report):
    paths = list((ROOT / "schemas").glob("*.schema.json")) + list((ROOT / "benchmark").glob("*.schema.json"))
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
        assert schema["x-schema-version"] == "0.3.2"
        assert "/v0.3.2/" in schema["$id"]

    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
    )
    report_schema = next(schema for schema in schemas if schema.get("title") == "NoveltyAudit Report")
    errors = list(Draft202012Validator(report_schema, registry=registry).iter_errors(valid_report))
    assert errors == []
