"""Shared fixtures: local fixture events and read-only access to the live MISP instance."""

import json
import ssl
import sys
from pathlib import Path
from urllib import error, request

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


def pytest_addoption(parser):
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="re-record tests/golden/*.md from the live LLM (review the diff before committing)",
    )


@pytest.fixture(scope="session")
def llm_settings() -> llm.LLMSettings:
    """LLM endpoint from .env; skips every LLM test when it is unreachable."""
    settings = llm.LLMSettings.from_env()
    if not settings.model or not llm.is_reachable(settings):
        pytest.skip(f"LLM endpoint {settings.base_url} not reachable or OPENAI_MODEL unset")
    return settings


@pytest.fixture
def dummy_event() -> dict:
    return json.loads((PROJECT_ROOT / "fixtures" / "summary" / "dummy-event.json").read_text())


class MispApi:
    """Minimal read-only MISP client. Network/auth problems turn into pytest skips."""

    def __init__(self, base_url: str, api_key: str, verify_ssl: bool) -> None:
        self.base_url = base_url.rstrip("/")
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
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers=self.headers,
            method="POST" if body is not None else "GET",
        )
        try:
            with request.urlopen(req, timeout=60, context=self.context) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if exc.code in (401, 403):
                pytest.skip(f"MISP API key rejected by {self.base_url} (HTTP {exc.code})")
            if exc.code == 404:
                pytest.skip(f"{path} does not exist on {self.base_url}")
            raise
        except error.URLError as exc:
            pytest.skip(f"MISP instance {self.base_url} unreachable: {exc.reason}")
        raise AssertionError("unreachable")  # pytest.skip() raises; keeps pylint happy

    def fetch(self, uuid: str) -> dict:
        """GET /events/view/<uuid> -> {"Event": {...}}"""
        return self._call(f"/events/view/{uuid}")

    def index(self, limit: int = 500) -> list[dict]:
        """POST /events/index -> [{"id", "uuid", "timestamp", "published", "orgc_uuid"}, ...]"""
        return self._call("/events/index", {"limit": limit, "page": 1, "minimal": 1})


@pytest.fixture(scope="session")
def misp_api() -> MispApi:
    env = load_env()
    base_url = env.get("MISP_BASE_URL") or (
        f"https://{env['MISP_HOST']}" if env.get("MISP_HOST") else ""
    )
    api_key = env.get("MISP_API_KEY", "")
    if not base_url or not api_key:
        pytest.skip("MISP_BASE_URL / MISP_API_KEY not configured in .env")
    verify_ssl = env.get("MISP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
    api = MispApi(base_url, api_key, verify_ssl)
    api.index(limit=1)  # probe once so auth/network problems skip everything that needs MISP
    return api
