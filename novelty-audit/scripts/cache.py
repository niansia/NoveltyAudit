"""Small, atomic, schema-aware JSON cache."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class JsonCache:
    def __init__(self, directory: str | Path, ttl_seconds: int = 86400, schema_version: str = "1") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.schema_version = schema_version

    def _path(self, namespace: str, key: Any) -> Path:
        payload = json.dumps([self.schema_version, namespace, key], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, namespace: str, key: Any) -> Any | None:
        path = self._path(namespace, key)
        if not path.exists() or time.time() - path.stat().st_mtime > self.ttl_seconds:
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if record.get("schema_version") != self.schema_version:
            return None
        return record.get("value")

    def set(self, namespace: str, key: Any, value: Any) -> Path:
        path = self._path(namespace, key)
        record = {"schema_version": self.schema_version, "stored_at": time.time(), "value": value}
        handle, temp_name = tempfile.mkstemp(prefix="novelty-audit-", suffix=".json", dir=self.directory)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path

