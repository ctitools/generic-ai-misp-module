"""UC3 — tag suggestion via misp-tag-suggest, with the HTTP call replaced by a fake."""

# pylint: disable=redefined-outer-name,unused-argument

import pytest
from pymisp import MISPEvent

from expansion import generic_ai
from genai import llm, prompts, suggest

AI_TAGS = set(prompts.AI_TAGS)
ANSWER = {
    "suggestions": [
        {"tag": 'rsit:fraud="phishing"', "score": 0.91},
        {"tag": "tlp:amber", "score": 0.6},  # already on the dummy event
        {"tag": 'misp-galaxy:threat-actor="APT-X"', "score": 0.2},
    ],
    "abstained": False,
    "model_version": "BAAI/bge-base-en-v1.5@abc123def456",
    "dataset_manifest_sha256": "manifest",
}
ABSTAINED = {
    "suggestions": [],
    "abstained": True,
    "model_version": "m",
    "dataset_manifest_sha256": "x",
}


def _tags(event: MISPEvent) -> set[str]:
    return {t.name for t in event.tags}


@pytest.fixture
def event(dummy_event) -> MISPEvent:
    return generic_ai.validate_event(dummy_event["Event"])


@pytest.fixture
def settings(monkeypatch) -> suggest.SuggestSettings:
    monkeypatch.setenv("MISP_TAG_SUGGEST_URL", "http://suggest.example:8000/")
    monkeypatch.setenv("MISP_TAG_SUGGEST_API_KEY", "s3cret")
    return suggest.SuggestSettings.from_env()


@pytest.fixture
def fake_http(monkeypatch):
    """Make llm.http_json return a fixed answer and record every call."""
    calls: list[dict] = []

    def install(answer, error: str | None = None):
        def fake(url, payload=None, *, headers=None, timeout=0):
            calls.append({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
            if error:
                raise llm.LLMError(error)
            return answer

        monkeypatch.setattr(llm, "http_json", fake)
        return calls

    return install


def test_settings_come_from_env_only(settings) -> None:
    assert settings.base_url == "http://suggest.example:8000"  # trailing slash stripped
    assert settings.api_key == "s3cret" and "s3cret" not in repr(settings)
    assert "suggest_url" not in generic_ai.moduleconfig


def test_missing_url_is_a_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("MISP_TAG_SUGGEST_URL", raising=False)
    monkeypatch.setattr(llm, "env", dict)  # ignore the repo's .env
    with pytest.raises(suggest.SuggestError, match="MISP_TAG_SUGGEST_URL"):
        suggest.SuggestSettings.from_env()


def test_tags_are_added_filtered_and_ai_tagged(event, settings, fake_http) -> None:
    calls = fake_http(ANSWER)
    before = _tags(event)
    result = suggest.suggest_tags(event, settings, limit=3, min_score=0.5)
    assert _tags(event) == before | {'rsit:fraud="phishing"'} | AI_TAGS
    assert result["added"] == [{"tag": 'rsit:fraud="phishing"', "score": 0.91}]
    assert result["skipped_existing"] == ["tlp:amber"]
    assert result["below_min_score"] == ['misp-galaxy:threat-actor="APT-X"']
    assert result["abstained"] is False and result["model_version"] == ANSWER["model_version"]
    (call,) = calls
    assert call["url"] == "http://suggest.example:8000/suggest"
    assert call["headers"] == {"X-Api-Key": "s3cret"}
    assert call["payload"]["limit"] == 3 and call["payload"]["event"]["Event"]["uuid"] == event.uuid


def test_abstention_adds_nothing_and_no_ai_tags(event, settings, fake_http) -> None:
    fake_http(ABSTAINED)
    before = _tags(event)
    result = suggest.suggest_tags(event, settings)
    assert _tags(event) == before and result["abstained"] is True and not result["added"]


def test_nothing_new_means_no_ai_tags(event, settings, fake_http) -> None:
    fake_http({**ANSWER, "suggestions": [{"tag": "tlp:amber", "score": 0.9}]})
    before = _tags(event)
    suggest.suggest_tags(event, settings)
    assert _tags(event) == before  # only existing tags came back: the event is unchanged


@pytest.mark.parametrize(
    "answer, fragment",
    [
        ({"abstained": False}, "no suggestions list"),
        ({"suggestions": [{"score": 1}]}, "malformed suggestion"),
        ({"suggestions": [{"tag": "x", "score": "high"}]}, "malformed suggestion"),
    ],
)
def test_malformed_answers_are_errors(event, settings, fake_http, answer, fragment) -> None:
    fake_http(answer)
    with pytest.raises(suggest.SuggestError, match=fragment):
        suggest.suggest_tags(event, settings)
    assert not _tags(event) & AI_TAGS


def test_http_failures_become_suggest_errors(event, settings, fake_http) -> None:
    fake_http(None, error="endpoint returned HTTP 503: index not built")
    with pytest.raises(suggest.SuggestError, match="misp-tag-suggest.*HTTP 503"):
        suggest.suggest_tags(event, settings)


def test_is_reachable(settings, fake_http) -> None:
    fake_http({"status": "ok", "artifacts_ready": True})
    assert suggest.is_reachable(settings)
    fake_http({"status": "setup-required", "artifacts_ready": False})
    assert not suggest.is_reachable(settings)
    fake_http(None, error="unreachable")
    assert not suggest.is_reachable(settings)


def test_dict_handler_dispatches_tag_suggestion(dummy_event, settings, fake_http, monkeypatch):
    fake_http(ANSWER)
    monkeypatch.setattr(llm, "llm_chat", lambda *a, **k: pytest.fail("LLM called"))
    result = generic_ai.dict_handler(
        {"event": dummy_event, "use_case": "tag_suggestion", "suggest_min_score": "0.5"}
    )
    assert "error" not in result, result
    tags = {t["name"] for t in result["results"]["Event"]["Event"]["Tag"]}
    assert 'rsit:fraud="phishing"' in tags and AI_TAGS <= tags
    assert result["metadata"]["use_case"] == "tag_suggestion"
    assert result["metadata"]["model"]["name"] == ANSWER["model_version"]
    assert result["metadata"]["below_min_score"] == ['misp-galaxy:threat-actor="APT-X"']


def test_dict_handler_reports_suggest_errors(dummy_event, settings, fake_http) -> None:
    fake_http(None, error="endpoint unreachable")
    result = generic_ai.dict_handler({"event": dummy_event, "use_case": "tag_suggestion"})
    assert result == {"error": "misp-tag-suggest: endpoint unreachable"}


def test_use_case_is_known(dummy_event) -> None:
    assert "tag_suggestion" in generic_ai.USE_CASES
    assert generic_ai.resolve_settings({})["suggest_limit"] == 5
    assert generic_ai.resolve_settings({"suggest_limit": "7"})["suggest_limit"] == 7
