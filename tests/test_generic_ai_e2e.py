"""End-to-end tests.

1. Local: start the real `misp-modules` server with this repository as custom module directory
   and POST every fixture event from `fixtures/output/` to `/query`.
2. Live: fetch the same events (uuids from `fixtures/output/hashes.csv`) from the MISP instance
   configured in `.env` and run them through the module. Skipped when `.env` is missing, the
   host is unreachable, or the API key is rejected. Set MISP_VERIFY_SSL=false (in .env or the
   environment) for instances with self-signed certificates.
"""

# pytest fixtures are injected by name, which pylint reads as shadowing:
# pylint: disable=redefined-outer-name

import csv
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path
from urllib import error, request

import pytest
from conftest import FIXTURE_DIR, FIXTURE_FILES, WITH_REPORT, load_fixture

from expansion import generic_ai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PROJECT_ROOT / "logs" / "test_e2e_server.log"
ENV_PATH = PROJECT_ROOT / ".env"


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


def _load_env() -> dict[str, str]:
    """Shell semantics: a later line in .env overrides an earlier one; os.environ wins over both."""
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ)
    return values


def _fixture_uuids() -> list[str]:
    with (FIXTURE_DIR / "hashes.csv").open(encoding="utf-8") as handle:
        return sorted({row[1] for row in csv.reader(handle) if len(row) == 2})


@pytest.fixture(scope="module")
def misp_fetch():
    env = _load_env()
    base_url = env.get("MISP_BASE_URL") or (
        f"https://{env['MISP_HOST']}" if env.get("MISP_HOST") else ""
    )
    api_key = env.get("MISP_API_KEY", "")
    if not base_url or not api_key:
        pytest.skip("MISP_BASE_URL / MISP_API_KEY not configured in .env")
    context = ssl.create_default_context()
    if env.get("MISP_VERIFY_SSL", "true").lower() in {"0", "false", "no"}:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    def fetch(uuid: str) -> dict:
        req = request.Request(
            f"{base_url.rstrip('/')}/events/view/{uuid}",
            headers={"Authorization": api_key, "Accept": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=30, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if exc.code in (401, 403):
                pytest.skip(f"MISP API key rejected by {base_url} (HTTP {exc.code})")
            if exc.code == 404:
                pytest.skip(f"event {uuid} does not exist on {base_url}")
            raise
        except error.URLError as exc:
            pytest.skip(f"MISP instance {base_url} unreachable: {exc.reason}")
        raise AssertionError("unreachable")  # pytest.skip() raises; keeps pylint happy

    fetch(WITH_REPORT)  # probe once so auth/network problems skip the whole module
    return fetch


@pytest.mark.parametrize("uuid", _fixture_uuids())
def test_live_misp_events_validate(misp_fetch, uuid) -> None:
    live = misp_fetch(uuid)
    result = generic_ai.dict_handler({"module": "generic_ai", "event": live})
    assert "error" not in result, result
    assert result["results"]["Event"]["Event"]["uuid"] == uuid
    fixture = load_fixture(uuid)
    expected_report = "\n\n".join(
        r["content"] for r in fixture["Event"].get("EventReport", []) if not r.get("deleted")
    )
    assert result["event_report"] == expected_report
