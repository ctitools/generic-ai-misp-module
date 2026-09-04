import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = PROJECT_ROOT / "fixtures" / "output"
sys.path.insert(0, str(PROJECT_ROOT))

# Real MISP events exported from the MISP instance in .env (see fixtures/output/hashes.csv).
FIXTURE_FILES = sorted(p for p in FIXTURE_DIR.glob("*.json") if p.name != "manifest.json")
WITH_REPORT = "10a94632-a0a1-4062-a3a5-95fe321ae045"  # one EventReport
TWO_REPORTS = "83a7add9-76d7-47ef-9f4b-ebd07fbe880d"  # two EventReports
NO_REPORT = "7cc5850c-a9bf-4b8f-8230-4229a6d4109e"  # no EventReport


def load_fixture(uuid: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{uuid}.json").read_text(encoding="utf-8"))


@pytest.fixture
def event_with_report() -> dict:
    return load_fixture(WITH_REPORT)
