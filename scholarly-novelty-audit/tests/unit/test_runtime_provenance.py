import json
from types import SimpleNamespace

import cli
from report_assembly import runtime_environment


def test_runtime_environment_records_evidence_processing_versions():
    runtime = runtime_environment()
    assert runtime["python_version"]
    assert runtime["dependencies"]["jsonschema"]
    assert runtime["dependencies"]["pypdf"]


def test_runtime_info_cli_writes_manifest_ready_payload(tmp_path):
    output = tmp_path / "runtime.json"
    assert cli.command_runtime_info(SimpleNamespace(output=str(output))) == cli.EXIT_COMPLETE
    assert json.loads(output.read_text(encoding="utf-8")) == runtime_environment()
