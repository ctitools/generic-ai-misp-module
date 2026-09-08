"""End-to-end tests.

1. Local: start the real `misp-modules` server with this repository as custom module directory
   and POST every fixture event from `fixtures/output/` to `/query`.
2. Live: fetch the same events (uuids from `fixtures/output/hashes.csv`) from the MISP instance
   configured in `.env` and run them through the module. Skipped when `.env` is missing, the
   host is unreachable, or the API key is rejected (see conftest.MispApi). Set
   MISP_VERIFY_SSL=false (in .env or the environment) for self-signed certificates.
"""

# pytest fixtures are injected by name, which pylint reads as shadowing:
# pylint: disable=redefined-outer-name

import csv
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib import error, request

import pytest
from conftest import FIXTURE_DIR, FIXTURE_FILES, load_fixture

from expansion import generic_ai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PROJECT_ROOT / "logs" / "test_e2e_server.log"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_service(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except error.URLError:
            time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {url}; see {LOG_PATH}")


def _post_json(url: str, body: dict, timeout: float = 30.0) -> dict:
    req = request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@pytest.fixture(scope="module")
def misp_modules_url():
    pytest.importorskip("misp_modules")
    port = _free_port()
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("w", encoding="utf-8") as log_handle:
        with subprocess.Popen(
            [
                sys.executable,
                "-m",
                "misp_modules",
                "-c",
                str(PROJECT_ROOT),
                "-l",
                "127.0.0.1",
                "-p",
                str(port),
            ],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=PROJECT_ROOT,
        ) as process:
            try:
                _wait_for_service(f"http://127.0.0.1:{port}/healthcheck")
                yield f"http://127.0.0.1:{port}"
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def test_service_lists_generic_ai_module(misp_modules_url) -> None:
    with request.urlopen(f"{misp_modules_url}/modules", timeout=5) as response:
        modules = json.loads(response.read().decode("utf-8"))
    module = next(m for m in modules if m["name"] == "generic_ai")
    assert module["mispattributes"] == generic_ai.mispattributes
    assert module["meta"]["version"] == generic_ai.moduleinfo["version"]


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_service_round_trips_every_fixture_event(misp_modules_url, path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = _post_json(f"{misp_modules_url}/query", {"module": "generic_ai", "event": raw})
    assert "error" not in payload, payload
    assert payload["results"]["Event"]["Event"]["uuid"] == raw["Event"]["uuid"]
    expected_report = "\n\n".join(
        r["content"] for r in raw["Event"].get("EventReport", []) if not r.get("deleted")
    )
    assert payload["event_report"] == expected_report


def test_service_rejects_invalid_event(misp_modules_url) -> None:
    payload = _post_json(f"{misp_modules_url}/query", {"module": "generic_ai", "event": {}})
    assert payload["error"].startswith("Invalid MISP Event")


# --- live MISP instance -------------------------------------------------------------------------


def _fixture_uuids() -> list[str]:
    with (FIXTURE_DIR / "hashes.csv").open(encoding="utf-8") as handle:
        return sorted({row[1] for row in csv.reader(handle) if len(row) == 2})


@pytest.mark.parametrize("uuid", _fixture_uuids())
def test_live_misp_events_validate(misp_api, uuid) -> None:
    live = misp_api.fetch(uuid)
    result = generic_ai.dict_handler({"module": "generic_ai", "event": live})
    assert "error" not in result, result
    assert result["results"]["Event"]["Event"]["uuid"] == uuid
    fixture = load_fixture(uuid)
    expected_report = "\n\n".join(
        r["content"] for r in fixture["Event"].get("EventReport", []) if not r.get("deleted")
    )
    assert result["event_report"] == expected_report


# --- use-cases through the real misp-modules server (live LLM; skips when it is down) ---


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"use_case": "summarization", "summary_kind": "report"}, "kind"),
        ({"use_case": "extraction"}, "added"),
    ],
)
def test_service_runs_use_cases(
    misp_modules_url, llm_settings, dummy_event, body, expected
) -> None:
    payload = _post_json(
        f"{misp_modules_url}/query",
        {"module": "generic_ai", "event": dummy_event, **body},
        timeout=300,
    )
    assert "error" not in payload, payload
    assert expected in payload["metadata"]
    assert payload["metadata"]["model"]["name"] == llm_settings.model
    event = payload["results"]["Event"]["Event"]
    tagged = {t["name"] for t in event.get("Tag", [])} | {
        t["name"] for a in event.get("Attribute", []) for t in a.get("Tag", [])
    }
    assert (
        'ai-computer-assisted:assistance-level="ai-generated"' in tagged
        or body["use_case"] == "extraction"
    )
