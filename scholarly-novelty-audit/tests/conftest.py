from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def valid_report() -> dict:
    return json.loads((Path(__file__).parent / "fixtures" / "composition-report.json").read_text(encoding="utf-8"))

