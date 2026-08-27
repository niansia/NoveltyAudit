"""Draft 2020-12 validation for NoveltyAudit machine reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas"


def validate_report_schema(report: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from referencing import Registry, Resource
    except ImportError:
        return ["schema validation unavailable: install jsonschema>=4.23"]

    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in SCHEMA_ROOT.glob("*.schema.json")]
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
    )
    report_schema = next(schema for schema in schemas if schema.get("title") == "NoveltyAudit Report")
    validator = Draft202012Validator(report_schema, registry=registry, format_checker=FormatChecker())
    errors = []
    for error in sorted(validator.iter_errors(report), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(value) for value in error.absolute_path) or "$"
        if error.validator == "format" and error.validator_value == "date-time":
            message = "must be an ISO 8601 date-time"
        elif error.validator == "format" and error.validator_value == "date":
            message = "must be a complete ISO 8601 date"
        else:
            message = error.message
        errors.append(f"schema {path}: {message}")
    return errors
