import json

from expansion import generic_ai


def test_introspection_declares_supported_types() -> None:
    assert generic_ai.introspection() == {"input": ["text", "comment"], "output": ["text"]}


def test_version_exposes_expected_configuration() -> None:
    version = generic_ai.version()
    assert version["name"] == "Generic AI"
    assert version["module-type"] == ["expansion"]
    assert "summary_sentences" in version["config"]


def test_dict_handler_summarises_raw_text() -> None:
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "text": (
                "Sentence one explains the intrusion. "
                "Sentence two explains containment. "
                "Sentence three explains the remaining risk."
            ),
        }
    )

    assert response["results"][0]["types"] == ["text"]
    assert response["answer"]["summary"].startswith("Sentence one explains the intrusion.")
    assert response["metadata"]["mode"] == "deterministic-fallback"


def test_dict_handler_supports_text_attribute_requests() -> None:
    response = generic_ai.dict_handler(
        {
            "module": "generic_ai",
            "attribute": {
                "type": "text",
                "value": (
                    "This is a CTI report. It contains several observations. "
                    "It should be summarised."
                ),
                "uuid": "1c6152e4-61f0-4cc9-a4e0-2f96f0e2167c",
            },
        }
    )

    assert response["results"][0]["values"][0].startswith("This is a CTI report.")


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
            "text": "First sentence. Second sentence. Third sentence.",
        }
    )
    response = generic_ai.handler(payload)
    assert response["results"][0]["values"][0] == "First sentence. Second sentence. Third sentence."
