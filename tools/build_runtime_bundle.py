#!/usr/bin/env python3
"""Build a deterministic, development-file-free Agent Skill ZIP."""

from __future__ import annotations

import argparse
import zipfile
from hashlib import sha256
from pathlib import Path, PurePosixPath

RUNTIME_ROOTS = {"SKILL.md", "agents", "assets", "references", "schemas", "scripts", "requirements.txt"}
FORBIDDEN_PARTS = {"tests", "benchmark", "__pycache__", ".pytest_cache", "tmp", ".git"}


def runtime_files(skill: Path) -> list[Path]:
    files: list[Path] = []
    for root_name in sorted(RUNTIME_ROOTS):
        root = skill / root_name
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    clean = []
    for path in files:
        relative = path.relative_to(skill)
        if FORBIDDEN_PARTS & set(relative.parts) or path.suffix in {".pyc", ".pyo"}:
            continue
        clean.append(path)
    required = {"SKILL.md", "requirements.txt"}
    present = {path.relative_to(skill).as_posix() for path in clean}
    missing = sorted(required - present)
    if missing:
        raise ValueError(f"runtime skill is missing required files: {missing}")
    return sorted(clean, key=lambda path: path.relative_to(skill).as_posix())


def runtime_entries(skill: Path) -> list[tuple[Path, PurePosixPath]]:
    entries = [(path, PurePosixPath(path.relative_to(skill).as_posix())) for path in runtime_files(skill)]
    license_path = skill.parent / "LICENSE"
    if not license_path.is_file():
        raise ValueError("runtime distribution requires the repository-root LICENSE")
    entries.append((license_path, PurePosixPath("LICENSE")))
    return sorted(entries, key=lambda item: str(item[1]))


def build(skill: Path, output: Path) -> str:
    skill = skill.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = skill.name
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, skill_relative in runtime_entries(skill):
            relative = PurePosixPath(prefix) / skill_relative
            info = zipfile.ZipInfo(str(relative), date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    digest = sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", default="scholarly-novelty-audit")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    digest = build(Path(args.skill), Path(args.output))
    print(f"Runtime bundle: {args.output}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
