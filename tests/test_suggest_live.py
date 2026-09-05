"""UC3 against the running misp-tag-suggest service (skips unless MISP_TAG_SUGGEST_URL is up).

The service abstains when the event is unlike its index, so the assertions cover both
outcomes: added tags exist on the dev MISP and the event is AI-tagged, or nothing changed.
"""

import pytest
from conftest import WITH_REPORT, load_fixture

from expansion import generic_ai
from genai import prompts, suggest

AI_TAGS = set(prompts.AI_TAGS)


def _tags(event) -> set[str]:
    return {t.name for t in event.tags}


@pytest.mark.parametrize("uuid", [WITH_REPORT])
def test_suggested_tags_exist_on_the_instance(suggest_settings, misp_api, uuid) -> None:
    event = generic_ai.validate_event(load_fixture(uuid)["Event"])
    before = _tags(event)
    result = suggest.suggest_tags(event, suggest_settings, limit=5)
    assert result["model_version"] and result["dataset_manifest_sha256"]
    if result["abstained"]:
        assert not result["added"] and _tags(event) == before
        return
    added = {s["tag"] for s in result["added"]}
    assert _tags(event) == before | added | AI_TAGS
    for tag in added:
        assert ":" in tag, f"{tag!r} is not a namespaced taxonomy/galaxy tag"
        assert misp_api.tag_exists(tag), f"{tag!r} suggested but not known to the dev MISP"


def test_handler_round_trip_through_the_service(suggest_settings) -> None:
    result = generic_ai.dict_handler(
        {"event": load_fixture(WITH_REPORT), "use_case": "tag_suggestion", "suggest_limit": 3}
    )
    assert "error" not in result, result
    assert result["metadata"]["model"]["server"] == suggest_settings.base_url
    assert len(result["metadata"]["added"]) <= 3
