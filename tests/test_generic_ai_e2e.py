import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib import error, request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PROJECT_ROOT / "logs" / "test_e2e_server.log"
ORKL_SAMPLE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "orkl-sample.txt"
EXPECTED_AI_TAG_NAMES = [
    'ai-computer-assisted:assistance-level="ai-generated"',
    'ai-computer-assisted:review-level="unreviewed"',
]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_service(url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except error.URLError:
            time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {url}")


def _load_orkl_sample_markdown() -> str:
    return (
        "# ORKL CTI Report\n\n"
        "- Source fixture: tests/fixtures/orkl-sample.txt\n\n"
        + ORKL_SAMPLE_PATH.read_text(encoding="utf-8")
    )


def test_service_exposes_generic_ai_module_and_returns_event_report() -> None:
    port = _free_port()
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

                with request.urlopen(f"http://127.0.0.1:{port}/modules", timeout=5) as response:
                    modules = json.loads(response.read().decode("utf-8"))
                generic_ai_module = next(
                    module for module in modules if module["name"] == "generic_ai"
                )
                assert generic_ai_module["mispattributes"]["format"] == "misp_standard"

                query = {
                    "module": "generic_ai",
                    "attribute": {
                        "type": "text",
                        "uuid": "6ad612d9-5db0-487d-8253-1e55afca1f63",
                        "value": _load_orkl_sample_markdown(),
                    },
                    "use_case_category": "summarization",
                    "event_id": 1,
                }
                query_request = request.Request(
                    f"http://127.0.0.1:{port}/query",
                    data=json.dumps(query).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with request.urlopen(query_request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                report = payload["results"]["EventReport"][0]
                assert payload["metadata"]["status_code"] == 200
                assert payload["metadata"]["mode"] == "deterministic-fallback"
                assert report["name"] == "Generic AI Summary (summarization)"
                assert "Emotet Is Not Dead (Yet)" in report["content"]
                assert "## Metadata" in report["content"]
                assert [tag["name"] for tag in payload["results"]["Tag"]] == EXPECTED_AI_TAG_NAMES
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
