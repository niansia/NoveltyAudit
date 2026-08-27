#!/usr/bin/env python3
"""Fail when repository or run artifacts contain common credential material."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable


PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "openai-style-token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "assigned-secret": re.compile(
        r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[\"'][A-Za-z0-9_./+\-=]{16,}[\"']"
    ),
}
IGNORED_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "tmp"}
TEXT_SUFFIXES = {"", ".json", ".jsonl", ".md", ".txt", ".toml", ".yaml", ".yml", ".py", ".html", ".csv", ".tsv"}


def files_under(paths: Iterable[str | Path]) -> Iterable[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            yield path
            continue
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and not (set(candidate.parts) & IGNORED_PARTS):
                    yield candidate


def scan_paths(paths: Iterable[str | Path]) -> list[str]:
    findings = []
    for path in files_under(paths):
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path}:{line_number}: possible {label}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan repository or run artifacts for credentials")
    parser.add_argument("paths", nargs="+", help="files or directories to scan")
    args = parser.parse_args()
    findings = scan_paths(args.paths)
    for finding in findings:
        print(f"ERROR: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
