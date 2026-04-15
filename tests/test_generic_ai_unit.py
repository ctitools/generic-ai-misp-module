import json
from pathlib import Path

import pytest

from expansion import generic_ai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORKL_SAMPLE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "orkl-sample.txt"
ORKL_SAMPLE_TEXT = ORKL_SAMPLE_PATH.read_text(encoding="utf-8")
EXPECTED_AI_TAG_NAMES = [
    'ai-computer-assisted:assistance-level="ai-generated"',
    'ai-computer-assisted:review-level="unreviewed"',
]


def test_introspection_declares_misp_standard_text_support() -> None:
    assert generic_ai.introspection() == {
        "input": ["text", "comment"],
        "output": ["EventReport"],
        "format": "misp_standard",
    }


def test_version_exposes_expected_configuration() -> None:
    version = generic_ai.version()
    assert version["name"] == "Generic AI"
    assert version["module-type"] == ["expansion"]
    assert "backend" in version["config"]
    assert "event_report_name" in version["config"]


def test_dict_handler_returns_event_report_for_raw_text() -> None:
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "text": ORKL_SAMPLE_TEXT,
        }
    )

    report = response["results"]["EventReport"][0]
    assert report["name"] == "Generic AI Summary (summarization)"
    assert "Emotet Is Not Dead (Yet)" in report["content"]
    assert "Emotet Is Not Dead (Yet)" in response["answer"]["summary"]
    assert response["metadata"]["mode"] == "deterministic-fallback"
    assert response["results"]["Tag"] == [
        {"name": EXPECTED_AI_TAG_NAMES[0], "local": False},
        {"name": EXPECTED_AI_TAG_NAMES[1], "local": False},
    ]
    assert response["tags"] == EXPECTED_AI_TAG_NAMES


def test_dict_handler_supports_text_attribute_requests() -> None:
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "attribute": {
                "type": "text",
                "value": ORKL_SAMPLE_TEXT,
                "uuid": "1c6152e4-61f0-4cc9-a4e0-2f96f0e2167c",
            },
        }
    )

    report = response["results"]["EventReport"][0]
    assert report["distribution"] == "0"
    assert "Emotet attacks leveraging malicious macros" in response["answer"]["summary"]
    assert "## Metadata" in report["content"]


def test_dict_handler_rejects_unsupported_attribute_types() -> None:
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "attribute": {
                "type": "ip-src",
                "value": "8.8.8.8",
                "uuid": "1c6152e4-61f0-4cc9-a4e0-2f96f0e2167c",
            },
        }
    )

    assert response == {"error": "Unsupported attribute type."}


def test_dict_handler_requires_text_input() -> None:
    response = generic_ai.dict_handler({"module": "generic_ai"})
    assert response == {
        "error": 'This module requires either a "text" field or a supported "attribute" field.'
    }


def test_live_backend_uses_ollama_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(url: str, payload: dict[str, object], **_: object) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        return {"model": "gemma4:latest", "message": {"content": "Backend summary"}}

    monkeypatch.setattr(generic_ai, "_request_json", fake_request_json)
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "text": "A CTI report that should go through the live backend.",
            "config": {"backend": "ollama", "default_model_id": "gemma4:latest"},
        }
    )

    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert response["answer"]["summary"] == "Backend summary"
    assert response["metadata"]["backend"] == "ollama"
    assert response["metadata"]["mode"] == "live-backend"


def test_openai_compatible_backend_allows_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(
        url: str,
        _payload: dict[str, object],
        *,
        headers: dict[str, str],
        timeout: int,
        verify_ssl: bool,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["verify_ssl"] = verify_ssl
        return {
            "model": "gemma4:latest",
            "choices": [{"message": {"content": "OpenAI compatible summary"}}],
        }

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(generic_ai, "_request_json", fake_request_json)
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "text": "A CTI report that should go through the OpenAI compatible path.",
            "config": {
                "backend": "openai",
                "api_base": "http://10.72.0.4:11434/v1",
                "default_model_id": "gemma4:latest",
                "verify_ssl": False,
            },
        }
    )

    assert captured["url"] == "http://10.72.0.4:11434/v1/chat/completions"
    assert captured["headers"] == {"Content-Type": "application/json"}
    assert response["answer"]["summary"] == "OpenAI compatible summary"
    assert response["metadata"]["backend"] == "openai"
    assert response["metadata"]["mode"] == "live-backend"


def test_request_json_rejects_non_http_urls() -> None:
    # pylint: disable=protected-access
    with pytest.raises(generic_ai.BackendError, match=r"Only http\(s\) backend URLs are allowed"):
        generic_ai._request_json(
            "file:///tmp/evil",
            {},
            headers={"Content-Type": "application/json"},
            timeout=1,
            verify_ssl=False,
        )


def test_backend_failure_falls_back_deterministically(monkeypatch: pytest.MonkeyPatch) -> None:
    def raising_request_json(*_: object, **__: object) -> dict[str, object]:
        raise generic_ai.BackendError("boom")

    monkeypatch.setattr(generic_ai, "_request_json", raising_request_json)
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "text": "First sentence. Second sentence. Third sentence.",
            "config": {"backend": "ollama", "default_model_id": "gemma4:latest"},
        }
    )

    assert response["metadata"]["mode"] == "fallback-after-backend-error"
    assert response["metadata"]["backend_error"] == "boom"
    assert response["answer"]["summary"] == "First sentence. Second sentence. Third sentence."


def test_config_can_override_sentence_and_character_limits() -> None:
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "text": (
                "Sentence one is intentionally long to consume the available "
                "characters quickly while describing multiple artifacts, "
                "infrastructure details, and response actions in a single "
                "breath. "
                "Sentence two should not appear in the summary when the character budget is tight."
            ),
            "config": {"summary_sentences": 1, "summary_chars": 80},
        }
    )

    assert response["answer"]["summary"].endswith("...")
    assert len(response["answer"]["summary"]) <= 80


def test_handler_wraps_json_requests() -> None:
    payload = json.dumps(
        {
            "module": "generic_ai",
            "text": ORKL_SAMPLE_TEXT,
        }
    )
    response = generic_ai.handler(payload)
    assert response["results"]["EventReport"][0]["name"] == "Generic AI Summary (summarization)"
    assert "Emotet Is Not Dead (Yet)" in response["answer"]["summary"]
