"""Offline tests for the two use-cases: the LLM is replaced by a canned answer."""

# pylint: disable=redefined-outer-name,unused-argument

import json

import pytest
from conftest import load_fixture
from pymisp import MISPEvent

from expansion import generic_ai
from genai import extract, llm, prompts, summarize

AI_TAGS = set(prompts.AI_TAGS)
REPORT_UUID = "9c8b7a6f-5e4d-4c3b-8a29-18f7e6d5c4b3"


def _tags(element) -> set[str]:
    return {t.name for t in element.tags}


@pytest.fixture
def event(dummy_event) -> MISPEvent:
    return generic_ai.validate_event(dummy_event["Event"])


@pytest.fixture
def fake_llm(monkeypatch):
    """Make llm.llm_chat return a fixed answer and record the request."""
    calls: list[dict] = []

    def install(answer: str):
        def fake(messages, params, settings, json_mode=False):
            calls.append({"messages": messages, "params": params, "json_mode": json_mode})
            return answer

        monkeypatch.setattr(llm, "llm_chat", fake)
        return calls

    return install


def _candidate(kind, value, quote=None, confidence=0.99, category=None):
    return {
        "type": kind,
        "value": value,
        "quote": quote or value,
        "confidence": confidence,
        "category": category,
    }


# --- UC1 extraction ------------------------------------------------------------------------------


def test_extraction_adds_tagged_attributes(event, fake_llm) -> None:
    # the dummy report mentions an IP that is already on the event and two new-looking strings
    answer = json.dumps(
        {
            "indicators": [
                _candidate(
                    "domain",
                    "acme-bank-secure.example",
                    "e-mails from alerts@acme-bank-secure.example",
                ),
                _candidate(
                    "filename", "Invoice_2026.xlsm", "Excel attachment Invoice_2026.xlsm (MD5"
                ),
            ]
        }
    )
    calls = fake_llm(answer)
    before = len(event.attributes)
    settings = {"use_case": "extraction"}
    metadata: dict = {}
    generic_ai.process_event(event, settings=settings, metadata=metadata)
    assert calls[0]["json_mode"] is True
    assert "{{" not in calls[0]["messages"][0]["content"]  # placeholders rendered
    added = [a for a in event.attributes if a.value == "acme-bank-secure.example"]
    assert len(added) == 1 and _tags(added[0]) == AI_TAGS
    assert added[0].comment == f"extracted by generic_ai from EventReport {REPORT_UUID}"
    assert len(event.attributes) == before + 1  # the filename already exists inside the file object
    assert metadata["added"] == 1 and [r["reason"] for r in metadata["rejected"]] == ["duplicate"]
    assert not _tags(event) & AI_TAGS  # attributes were suggested, not event-level content
    assert event.event_reports[0].content.startswith("## Summary")  # source untouched


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        (_candidate("ip-dst", "198.51.100.9"), "not-in-source"),
        (_candidate("ip-dst", "203.0.113.42", quote="something else"), "quote-mismatch"),
        (_candidate("ipv4", "203.0.113.42"), "unknown-type"),
        (_candidate("sha256", "d41d8cd98f00b204e9800998ecf8427"), "format"),  # 31 hex chars
        (_candidate("ip-dst", "203.0.113.42"), "duplicate"),
        (_candidate("domain", "acme-bank-secure.example", confidence=0.5), "confidence"),
    ],
)
def test_extraction_filters(event, fake_llm, candidate, reason) -> None:
    fake_llm(json.dumps({"indicators": [candidate]}))
    metadata: dict = {}
    generic_ai.process_event(event, settings={"use_case": "extraction"}, metadata=metadata)
    assert metadata["added"] == 0
    assert metadata["rejected"][0]["reason"] == reason


DEFANGED_REPORT = (
    "C2 at 198.51.100[.]7, listening on 198.51.100[.]7:443 and 198.51.100[.]7:x, "
    "download from hxxps://evil[.]example/p, pipe \\\\.\\pipe\\ntsvcs, "
    "MD5 2615f7aa2141cc1cb5d0c687bc3396981c2c68dc"
)


def _defanged_event() -> MISPEvent:
    return generic_ai.validate_event(
        {"info": "defanged", "EventReport": [{"name": "r", "content": DEFANGED_REPORT}]}
    )


def test_extraction_refangs_and_records_the_original(fake_llm) -> None:
    fake_llm(
        json.dumps(
            {
                "indicators": [
                    _candidate("ip-dst", "198.51.100[.]7"),
                    _candidate("url", "hxxps://evil[.]example/p"),
                    _candidate("ip-dst|port", "198.51.100[.]7:443"),
                    _candidate("ip-dst|port", "198.51.100[.]7:x"),
                    _candidate("named pipe", "\\\\.\\pipe\\ntsvcs"),
                    _candidate("ip-dst", "10.0.0[.]1"),
                ]
            }
        )
    )
    event = _defanged_event()
    metadata: dict = {}
    generic_ai.process_event(event, settings={"use_case": "extraction"}, metadata=metadata)
    stored = {a.type: (a.value, a.comment) for a in event.attributes}
    assert stored["ip-dst"][0] == "198.51.100.7"
    assert stored["ip-dst"][1].endswith("; defanged in source as 198.51.100[.]7")
    assert stored["url"][0] == "https://evil.example/p"
    assert stored["ip-dst|port"][0] == "198.51.100.7:443"
    assert stored["named pipe"] == ("\\\\.\\pipe\\ntsvcs", stored["named pipe"][1])
    assert "defanged" not in stored["named pipe"][1]
    assert [(r["value"], r["reason"]) for r in metadata["rejected"]] == [
        ("198.51.100[.]7:x", "format"),
        ("10.0.0[.]1", "not-in-source"),
    ]
    assert metadata["refanged"] == 3 and metadata["retyped"] == 0


def test_extraction_retypes_hashes_by_length(fake_llm) -> None:
    digest = "2615f7aa2141cc1cb5d0c687bc3396981c2c68dc"  # the report calls it MD5; 40 hex = sha1
    fake_llm(json.dumps({"indicators": [_candidate("md5", digest)]}))
    event = _defanged_event()
    metadata: dict = {}
    generic_ai.process_event(event, settings={"use_case": "extraction"}, metadata=metadata)
    (attribute,) = event.attributes
    assert attribute.type == "sha1" and attribute.comment.endswith("; typed md5 by the model")
    assert metadata["retyped"] == 1 and metadata["added"] == 1


def test_extraction_rejects_non_json(event, fake_llm) -> None:
    fake_llm("Here are the indicators: 203.0.113.42")
    before = event.to_json()
    with pytest.raises(llm.LLMError, match="not JSON"):
        generic_ai.process_event(event, settings={"use_case": "extraction"})
    assert event.to_json() == before


def test_extraction_builds_objects(fake_llm) -> None:
    raw = {
        "Event": {
            "info": "x",
            "EventReport": [
                {
                    "name": "r",
                    "content": "Dropper evil.exe (sha256 " + "a" * 64 + ") exploits CVE-2025-1234.",
                }
            ],
        }
    }
    event = generic_ai.validate_event(raw["Event"])
    quote = "evil.exe (sha256 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)"
    fake_llm(
        json.dumps(
            {
                "indicators": [
                    _candidate("filename", "evil.exe", quote),
                    _candidate("sha256", "a" * 64, quote),
                    _candidate("vulnerability", "CVE-2025-1234", "exploits CVE-2025-1234"),
                ]
            }
        )
    )
    metadata: dict = {}
    generic_ai.process_event(event, settings={"use_case": "extraction"}, metadata=metadata)
    assert metadata == {**metadata, "added": 3, "objects": 2}
    assert sorted(o.name for o in event.objects) == ["file", "vulnerability"]
    for misp_object in event.objects:
        assert all(_tags(a) == AI_TAGS for a in misp_object.attributes)
    assert not event.attributes


def test_extraction_needs_a_report(fake_llm) -> None:
    event = generic_ai.validate_event({"info": "no report"})
    fake_llm("{}")
    with pytest.raises(ValueError, match="no EventReport"):
        generic_ai.process_event(event, settings={"use_case": "extraction"})


def test_extraction_only_adds(event, fake_llm, dummy_event) -> None:
    from misp_compare import misp_event_diff  # pylint: disable=import-outside-toplevel

    fake_llm(
        json.dumps(
            {
                "indicators": [
                    _candidate(
                        "domain", "acme-bank-secure.example", "alerts@acme-bank-secure.example"
                    )
                ]
            }
        )
    )
    generic_ai.process_event(event, settings={"use_case": "extraction"})
    differences = misp_event_diff(dummy_event["Event"], json.loads(event.to_json()))
    assert all("added by processing" in d or "items ->" in d for d in differences), differences


# --- UC2 summarization ---------------------------------------------------------------------------

SUMMARY = (
    "## Threat\nPhishing against ACME Bank via login-acme-bank.example.\n"
    "## Targets\nCustomers.\n## Indicators\n203.0.113.42\n## Recommended actions\nBlock it."
)
EVENT_SUMMARY = (
    "## What happened\nPhishing.\n## Key indicators\n203.0.113.42\n"
    "## Context and attribution\nLow confidence.\n"
    "## Related events\n1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9"
)


def test_summary_of_report_is_attached_and_event_tagged(event, fake_llm) -> None:
    calls = fake_llm(SUMMARY)
    metadata: dict = {}
    generic_ai.process_event(event, settings={"use_case": "summarization"}, metadata=metadata)
    assert "## Summary" in calls[0]["messages"][0]["content"]  # the report was the input
    assert calls[0]["params"]["temperature"] == 0 and calls[0]["params"]["seed"] == 42
    assert [r.name for r in event.event_reports][
        1
    ] == "AI summary of Phishing campaign against ACME Bank customers"
    assert event.event_reports[1].content == SUMMARY
    assert event.event_reports[0].content.startswith("## Summary")
    assert AI_TAGS <= _tags(event)
    assert all(not _tags(a) & AI_TAGS for a in event.attributes)
    assert (
        metadata["kind"] == "report"
        and metadata["prompt"]["cluster"] == "summary-report/qwen3.8-v2"
    )


def test_summary_of_event_uses_rendering(event, fake_llm) -> None:
    calls = fake_llm(EVENT_SUMMARY)
    generic_ai.process_event(event, settings={"use_case": "summarization", "summary_kind": "event"})
    sent = calls[0]["messages"][0]["content"]
    assert "## Attributes" in sent and "1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9" in sent
    assert "## Summary" not in sent  # report content is not the input for kind=event
    assert event.event_reports[1].name == f"AI summary of event {event.uuid}"


def test_event_rendering_is_deterministic_and_sorted(dummy_event) -> None:
    first = summarize.render_event(generic_ai.validate_event(dummy_event["Event"]))
    dummy_event["Event"]["Attribute"].reverse()
    dummy_event["Event"]["Tag"].reverse()
    second = summarize.render_event(generic_ai.validate_event(dummy_event["Event"]))
    assert first == second
    assert "timestamp" not in first
    for attribute in dummy_event["Event"]["Attribute"]:
        assert attribute["value"] in first


@pytest.mark.parametrize(
    ("answer", "fragment"),
    [
        (
            "## Threat\nx\n## Targets\nx\n## Indicators\nx",
            "missing heading '## Recommended actions'",
        ),
        (
            SUMMARY + "\nAlso 198.51.100.77 and evil-other.example.com.",
            "indicator not in input: 198.51.100.77",
        ),
        (
            "## Threat\n" + "word " * 250 + "\n## Targets\n## Indicators\n## Recommended actions",
            "words > 200",
        ),
    ],
)
def test_summary_structural_gate(event, fake_llm, answer, fragment) -> None:
    fake_llm(answer)
    with pytest.raises(llm.LLMError, match="structural check") as excinfo:
        generic_ai.process_event(event, settings={"use_case": "summarization"})
    assert fragment in str(excinfo.value)
    assert len(event.event_reports) == 1 and not _tags(event) & AI_TAGS


def test_unknown_kind_and_use_case(event, fake_llm) -> None:
    fake_llm(SUMMARY)
    with pytest.raises(ValueError, match="summary_kind"):
        generic_ai.process_event(
            event, settings={"use_case": "summarization", "summary_kind": "nope"}
        )
    with pytest.raises(ValueError, match="use_case"):
        generic_ai.process_event(event, settings={"use_case": "translate"})


# --- cross-cutting -------------------------------------------------------------------------------


def test_settings_precedence(monkeypatch) -> None:
    monkeypatch.setenv("GENERIC_AI_SUMMARY_KIND", "event")
    monkeypatch.setenv("GENERIC_AI_REQUEST_TIMEOUT", "7")
    settings = generic_ai.resolve_settings(
        {
            "use_case": "extraction",
            "config": {"use_case": "summarization", "min_confidence": "0.5"},
            "request_timeout": 1,
        }
    )
    assert settings["use_case"] == "extraction"  # request beats config
    assert settings["min_confidence"] == 0.5  # config beats default, coerced to float
    assert settings["summary_kind"] == "event"  # env beats default
    assert settings["request_timeout"] == 7  # request may not set it
    assert generic_ai.resolve_settings({})["use_case"] == "none"


def test_request_cannot_set_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://from-env.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    settings = llm.LLMSettings.from_env()
    assert settings.base_url == "http://from-env.example/v1" and settings.api_key == "env-key"
    assert "api_base" not in generic_ai.moduleconfig and "api_key" not in generic_ai.moduleconfig


def test_dict_handler_reports_llm_errors(dummy_event, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise llm.LLMError("LLM endpoint unreachable or timed out (120s)")

    monkeypatch.setattr(llm, "llm_chat", boom)
    result = generic_ai.dict_handler({"event": dummy_event, "use_case": "summarization"})
    assert result == {"error": "LLM endpoint unreachable or timed out (120s)"}


def test_passthrough_default_makes_no_llm_call(dummy_event, monkeypatch) -> None:
    monkeypatch.setattr(llm, "llm_chat", lambda *a, **k: pytest.fail("LLM called"))
    result = generic_ai.dict_handler({"event": dummy_event})
    assert result["metadata"] == {}


def test_prompt_resolution() -> None:
    default = prompts.resolve_prompt("summary-report")
    assert default.value == "summary-report/qwen3.8-v2" and default.params["seed"] == 42
    assert prompts.resolve_prompt("summary-report", default.uuid) == default
    inline = prompts.resolve_prompt("summary-report", "Summarise: {{input}}")
    assert inline.value == "inline" and inline.headings == default.headings
    with pytest.raises(ValueError):
        prompts.resolve_prompt("nope")


def test_pinned_tags_cover_the_ai_tags() -> None:
    assert set(prompts.AI_TAGS) <= set(prompts.pinned_tags())


def test_describe_types_matches_rfc_scale() -> None:
    assert len(extract.MISP_TYPES) > 150 and "ip-dst" in extract.MISP_TYPES


def test_fixture_event_extraction_keeps_round_trip(fake_llm) -> None:
    raw = load_fixture("10a94632-a0a1-4062-a3a5-95fe321ae045")
    fake_llm(json.dumps({"indicators": []}))
    event = generic_ai.validate_event(raw["Event"])
    generic_ai.process_event(event, settings={"use_case": "extraction"})
    assert json.loads(event.to_json())["uuid"] == raw["Event"]["uuid"]


def test_check_summary_ignores_markdown_around_urls() -> None:
    prompt = prompts.resolve_prompt("summary-report")
    source = "Phishing at https://login-acme-bank.example/verify seen."
    summary = "\n".join(f"## {h}" for h in prompt.headings)
    url = "https://login-acme-bank.example/verify"
    summary += f"\nVictims visit `{url}`. Then ({url})."
    assert not [p for p in summarize.check_summary(summary, source, prompt) if "indicator" in p]


def test_check_summary_refangs_before_comparing() -> None:
    prompt = prompts.resolve_prompt("summary-report")
    source = "Beacons to 203.0.113[.]42 and hxxps://evil[.]example/x were seen."
    summary = "\n".join(f"## {h}" for h in prompt.headings)
    summary += "\nBeacons to 203.0.113.42 and https://evil.example/x; also 198.51.100[.]9."
    problems = summarize.check_summary(summary, source, prompt)
    assert problems == ["indicator not in input: 198.51.100.9"]


def test_summary_v2_cluster_is_the_default_and_v1_stays_selectable() -> None:
    v2 = prompts.resolve_prompt("summary-report", "summary-report/qwen3.8-v2")
    assert v2.version == 2 and v2.params["max_tokens"] == 1000 and v2.max_words == 200
    assert (
        "150 words" in v2.text and v2.headings == prompts.resolve_prompt("summary-report").headings
    )


def test_check_summary_accepts_values_broken_across_lines_in_the_source() -> None:
    prompt = prompts.resolve_prompt("summary-report")
    source = "driver {5AE3F37E-4EAE-41AE-8240-\r\n35465B5E81EB}"
    source += " and hash d41d8cd98f00b204\ne9800998ecf8427e"
    summary = "\n".join(f"## {h}" for h in prompt.headings)
    summary += "\nGUID 5AE3F37E-4EAE-41AE-8240-35465B5E81EB, hash d41d8cd98f00b204e9800998ecf8427e."
    assert not [p for p in summarize.check_summary(summary, source, prompt) if "indicator" in p]
