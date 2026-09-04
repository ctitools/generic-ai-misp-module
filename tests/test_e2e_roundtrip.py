"""Round-trip quality gate for process_event().

Fetch 10 random events from the MISP instance in .env, run each through validate_event() and
process_event(..., e2etest=True) — which writes tests/e2etests/<uuid>.json — and prove that the
file is semantically identical to the original (see misp_compare.py for what "semantically"
tolerates). Skipped when the instance is not configured or unreachable.

Reproduce a run with the seed from tests/e2etests/last_run.json:
    E2E_SEED=<seed> pytest tests/test_e2e_roundtrip.py
"""

# pytest fixtures are injected by name, which pylint reads as shadowing:
# pylint: disable=redefined-outer-name

import json
import os
import random
import secrets
import sys

import pytest
from misp_compare import misp_event_diff

from expansion import generic_ai

SAMPLE_SIZE = 10


@pytest.fixture(scope="module")
def random_uuids(misp_api) -> list[str]:
    seed = int(os.environ.get("E2E_SEED") or secrets.randbelow(10**9))
    uuids = sorted(entry["uuid"] for entry in misp_api.index(limit=500))
    chosen = random.Random(seed).sample(uuids, min(SAMPLE_SIZE, len(uuids)))
    generic_ai.E2E_DIR.mkdir(parents=True, exist_ok=True)
    (generic_ai.E2E_DIR / "last_run.json").write_text(
        json.dumps({"seed": seed, "uuids": chosen}, indent=2), encoding="utf-8"
    )
    print(f"\nE2E_SEED={seed} events={chosen}")
    return chosen


def test_process_event_round_trip(misp_api, random_uuids) -> None:
    failures: list[str] = []
    for uuid in random_uuids:
        original = misp_api.fetch(uuid)
        event = generic_ai.validate_event(original["Event"])
        generic_ai.process_event(event, e2etest=True)
        saved = json.loads((generic_ai.E2E_DIR / f"{uuid}.json").read_text(encoding="utf-8"))
        differences = misp_event_diff(original["Event"], saved["Event"])
        print(f"{uuid}: {'OK' if not differences else f'{len(differences)} differences'}")
        failures.extend(f"{uuid}{difference}" for difference in differences)
    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    sys.exit(pytest.main(["-q", "-s", __file__]))
