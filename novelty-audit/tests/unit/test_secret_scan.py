import importlib.util
from pathlib import Path


path = Path(__file__).resolve().parents[2] / "scripts" / "secret_scan.py"
spec = importlib.util.spec_from_file_location("secret_scan", path)
secret_scan = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(secret_scan)


def test_secret_scan_detects_credentials_and_allows_variable_names(tmp_path):
    safe = tmp_path / "safe.md"
    unsafe = tmp_path / "unsafe.txt"
    safe.write_text("Set OPENALEX_API_KEY in your environment.", encoding="utf-8")
    unsafe.write_text("client_secret='" + ("abcdef" * 5) + "'", encoding="utf-8")
    assert secret_scan.scan_paths([safe]) == []
    assert any("assigned-secret" in item for item in secret_scan.scan_paths([unsafe]))
