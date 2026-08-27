import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("build_runtime_bundle", ROOT / "tools" / "build_runtime_bundle.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_runtime_bundle_is_deterministic_and_excludes_development_files(tmp_path):
    skill = ROOT / "scholarly-novelty-audit"
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    assert MODULE.build(skill, first) == MODULE.build(skill, second)
    assert first.read_bytes() == second.read_bytes()
    sidecar = first.with_suffix(first.suffix + ".sha256").read_bytes()
    assert sidecar.endswith(b"\n")
    assert b"\r\n" not in sidecar
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        infos = archive.infolist()
    assert "scholarly-novelty-audit/SKILL.md" in names
    assert "scholarly-novelty-audit/LICENSE" in names
    assert "scholarly-novelty-audit/requirements.txt" in names
    with zipfile.ZipFile(first) as archive:
        assert archive.read("scholarly-novelty-audit/LICENSE") == (ROOT / "LICENSE").read_bytes()
    assert infos and all(info.create_system == 3 for info in infos)
    assert not any("/tests/" in name or "/benchmark/" in name or "__pycache__" in name for name in names)
