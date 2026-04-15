import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib import error, request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PROJECT_ROOT / "logs" / "test_e2e_server.log"


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


def test_service_exposes_generic_ai_module_and_summarises_fixture() -> None:
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
                assert any(module["name"] == "generic_ai" for module in modules)

                fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "sample_cti_report.md"
                query = {
                    "module": "generic_ai",
                    "text": fixture_path.read_text(encoding="utf-8"),
                    "use_case_category": "summarization",
                }
                query_request = request.Request(
                    f"http://127.0.0.1:{port}/query",
                    data=json.dumps(query).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with request.urlopen(query_request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                assert payload["metadata"]["status_code"] == 200
                assert not payload["answer"]["summary"].startswith("# Incident Report")
                assert "Analysts observed a phishing campaign" in payload["answer"]["summary"]
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
