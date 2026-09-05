"""Shared fixtures: local fixture events and read-only access to the live MISP instance."""

import json
import ssl
import sys
import urllib.request
from pathlib import Path
from urllib import error

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = PROJECT_ROOT / "fixtures" / "output"
sys.path.insert(0, str(PROJECT_ROOT))

from genai import llm  # noqa: E402  # pylint: disable=wrong-import-position

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


def load_env() -> dict[str, str]:
    """.env (last line wins) overlaid by os.environ — the same loader the module uses."""
    return llm.env()


LIVE_HELP = "see README.md, section 'Live systems (MISP and LLM server)'"


def pytest_addoption(parser):
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="re-record tests/golden/*.md from the live LLM (review the diff before committing)",
    )
    parser.addoption(
        "--require-live",
        action="store_true",
        default=False,
        help="fail instead of skip when the live MISP or LLM is unavailable (pre-tag run)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "live_llm: needs the LLM endpoint from .env")
    config.addinivalue_line("markers", "live_misp: needs the MISP instance from .env")
    config.live_gates = {}  # gate name -> "ran" | "skipped: reason" | "FAILED: reason"


def pytest_collection_modifyitems(items):
    """Mark every test by the live fixture it uses, so `-m 'not live_llm'` and the summary work."""
    for item in items:
        for fixture, marker in (("llm_settings", "live_llm"), ("misp_api", "live_misp")):
            if fixture in getattr(item, "fixturenames", ()):
                item.add_marker(getattr(pytest.mark, marker))


def live_gate(config, gate: str, reason: str) -> None:
    """A live system is unavailable: skip by default, fail with --require-live."""
    if config.getoption("--require-live"):
        config.live_gates[gate] = f"FAILED: {reason}"
        pytest.fail(f"{gate}: {reason} ({LIVE_HELP})", pytrace=False)
    config.live_gates[gate] = f"skipped: {reason}"
    pytest.skip(f"{reason} ({LIVE_HELP})")


def pytest_terminal_summary(terminalreporter, config):
    gates = dict(config.live_gates)
    for marker in ("live_llm", "live_misp"):
        skipped = sum(
            1
            for report in terminalreporter.stats.get("skipped", [])
            if marker in getattr(report, "keywords", {})
        )
        gates.setdefault(marker.replace("live_", ""), "not requested")
        if skipped:
            gates[marker.replace("live_", "")] += f" ({skipped} tests skipped)"
    terminalreporter.write_sep("-", "live gates")
    for gate, status in sorted(gates.items()):
        terminalreporter.write_line(f"{gate}: {status}")
    if any(status.startswith("skipped") for status in gates.values()):
        terminalreporter.write_line(
            f"a green run without live gates proves nothing live; {LIVE_HELP}"
        )


@pytest.fixture(scope="session")
def llm_settings(request) -> llm.LLMSettings:
    """LLM endpoint from .env; skips (or fails with --require-live) when it is unreachable."""
    settings = llm.LLMSettings.from_env()
    if not settings.model or not llm.is_reachable(settings):
        live_gate(
            request.config,
            "llm",
            f"LLM endpoint {settings.base_url} unreachable or OPENAI_MODEL unset",
        )
    request.config.live_gates["llm"] = f"ran ({settings.model} at {settings.base_url})"
    return settings


@pytest.fixture
def dummy_event() -> dict:
    return json.loads((PROJECT_ROOT / "fixtures" / "summary" / "dummy-event.json").read_text())


class MispApi:
    """Minimal read-only MISP client. Auth/network problems go through live_gate (skip or fail);
    a missing event (404) is always a skip: it is a data problem, not a missing live system."""

    def __init__(self, base_url: str, api_key: str, verify_ssl: bool, config=None) -> None:
        self.base_url = base_url.rstrip("/")
        self.config = config
        self.headers = {
            "Authorization": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.context = ssl.create_default_context()
        if not verify_ssl:  # tests only: the dev instance has a self-signed certificate
            self.context.check_hostname = False
            self.context.verify_mode = ssl.CERT_NONE

    def _call(self, path: str, body: dict | None = None) -> dict | list:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers=self.headers,
            method="POST" if body is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=60, context=self.context) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if exc.code in (401, 403):
                self._gate(f"MISP API key rejected by {self.base_url} (HTTP {exc.code})")
            if exc.code == 404:
                pytest.skip(f"{path} does not exist on {self.base_url}")
            raise
        except error.URLError as exc:
            self._gate(f"MISP instance {self.base_url} unreachable: {exc.reason}")
        raise AssertionError("unreachable")  # pytest.skip() raises; keeps pylint happy

    def _gate(self, reason: str) -> None:
        if self.config is not None:
            live_gate(self.config, "misp", reason)
        pytest.skip(reason)

    def fetch(self, uuid: str) -> dict:
        """GET /events/view/<uuid> -> {"Event": {...}}"""
        return self._call(f"/events/view/{uuid}")

    def index(self, limit: int = 500) -> list[dict]:
        """POST /events/index -> [{"id", "uuid", "timestamp", "published", "orgc_uuid"}, ...]"""
        return self._call("/events/index", {"limit": limit, "page": 1, "minimal": 1})


@pytest.fixture(scope="session")
def misp_api(request) -> MispApi:
    env = load_env()
    base_url = env.get("MISP_BASE_URL") or (
        f"https://{env['MISP_HOST']}" if env.get("MISP_HOST") else ""
    )
    api_key = env.get("MISP_API_KEY", "")
    if not base_url or not api_key:
        live_gate(request.config, "misp", "MISP_BASE_URL / MISP_API_KEY not configured in .env")
    verify_ssl = env.get("MISP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
    api = MispApi(base_url, api_key, verify_ssl, request.config)
    api.index(limit=1)  # probe once so auth/network problems gate everything that needs MISP
    request.config.live_gates["misp"] = f"ran ({base_url})"
    return api
