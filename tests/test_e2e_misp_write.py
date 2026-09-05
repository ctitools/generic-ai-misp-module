"""Live write-path e2e (the AGENTS.md loop): create an event on the dev MISP with an orkl.eu
report as EventReport, run the module, push the result back with PyMISP, verify on the
instance, delete the event.

Every event is created with distribution 0 ("your organisation only") and is never published;
set E2E_KEEP=1 to leave the events on the instance for inspection.
"""

# llm_settings is used as a gate only; pylint: disable=redefined-outer-name,unused-argument

import os
import time
import warnings
from pathlib import Path

import pytest
from conftest import PROJECT_ROOT, load_env
from pymisp import MISPEvent, PyMISP

from expansion import generic_ai
from genai import prompts

ORKL_DIR = PROJECT_ROOT / "tests" / "fixtures" / "orkl"
REPORTS = sorted(ORKL_DIR.glob("*.txt"))
AI_TAGS = set(prompts.AI_TAGS)
YOUR_ORG_ONLY = 0
SEED_ATTRIBUTES = (
    ("ip-dst", "203.0.113.42"),
    ("domain", "login-acme-bank.example"),
    ("md5", "d41d8cd98f00b204e9800998ecf8427e"),
)


@pytest.fixture(scope="session")
def misp_write(misp_api) -> PyMISP:  # misp_api: the read-only probe gates on reachability/auth
    env = load_env()
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    return PyMISP(misp_api.base_url, env["MISP_API_KEY"], ssl=misp_api.context.verify_mode != 0)


@pytest.fixture
def created_event(misp_write: PyMISP, request):
    """A fresh unpublished org-only event carrying one orkl report; deleted after the test."""
    report: Path = request.param
    event = MISPEvent()
    event.info = f"generic-ai e2e {report.stem[:8]} {int(time.time())}"
    event.distribution = YOUR_ORG_ONLY
    event.published = False
    event.analysis = 0
    event.threat_level_id = 4
    event.add_event_report(name=report.stem, content=report.read_text(encoding="utf-8"))
    for kind, value in SEED_ATTRIBUTES:  # so the event kind has attributes to tell a story from
        event.add_attribute(kind, value, comment="e2e seed attribute")
    created = misp_write.add_event(event, pythonify=True)
    assert created.distribution == YOUR_ORG_ONLY and not created.published
    try:
        yield created.uuid
    finally:
        if not os.environ.get("E2E_KEEP"):
            misp_write.delete_event(created.uuid)


def _run_and_push(
    misp_write: PyMISP, uuid: str, settings: dict, metadata: dict | None = None
) -> tuple[dict, dict]:
    """Fetch the event from MISP, run the module on it, push the processed event back.

    Returns (the event as the module produced it, the event as MISP stores it afterwards)."""
    live = misp_write.get_event(uuid, pythonify=False)
    response = generic_ai.dict_handler({"module": "generic_ai", "event": live, **settings})
    assert "error" not in response, response.get("error")
    if metadata is not None:
        metadata.update(response["metadata"])
    processed = MISPEvent()
    processed.load(response["results"]["Event"])
    processed.distribution = YOUR_ORG_ONLY
    processed.published = False
    result = misp_write.update_event(processed, pythonify=False)
    assert not result.get("errors"), result
    produced = response["results"]["Event"]["Event"]
    return produced, misp_write.get_event(uuid, pythonify=False)["Event"]


def _tags(element: dict) -> set[str]:
    return {t["name"] for t in element.get("Tag", [])}


@pytest.mark.parametrize("created_event", REPORTS, indirect=True, ids=[p.stem[:8] for p in REPORTS])
def test_extraction_lands_in_misp(misp_write, llm_settings, created_event) -> None:
    produced, after = _run_and_push(misp_write, created_event, {"use_case": "extraction"})
    attributes = list(after["Attribute"]) + [a for o in after["Object"] for a in o["Attribute"]]
    added = [a for a in attributes if a.get("comment", "").startswith("extracted by generic_ai")]
    assert added, "the module added no attribute to the event"
    for attribute in added:
        assert AI_TAGS <= _tags(attribute), (attribute["type"], attribute["value"])
    sent = {
        a["uuid"]: a
        for a in produced["Attribute"]
        + [x for o in produced.get("Object", []) for x in o["Attribute"]]
    }
    for attribute in added:  # to_ids and dates arrive in MISP exactly as the module set them
        expected = sent[attribute["uuid"]]
        assert attribute["to_ids"] == expected["to_ids"], attribute["value"]
        for field in ("first_seen", "last_seen"):
            assert (attribute.get(field) or "")[:10] == (expected.get(field) or "")[:10], field
    assert not _tags(after) & AI_TAGS  # attributes were suggested, the event stays untagged
    assert after["distribution"] == str(YOUR_ORG_ONLY) and after["published"] is False
    (report,) = [r for r in after["EventReport"] if not r["deleted"]]  # source report untouched
    assert report["content"] == (ORKL_DIR / f"{report['name']}.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("created_event", REPORTS[:1], indirect=True, ids=[REPORTS[0].stem[:8]])
def test_summary_lands_in_misp(misp_write, llm_settings, created_event) -> None:
    _, after = _run_and_push(misp_write, created_event, {"use_case": "summarization"})
    reports = {r["name"]: r["content"] for r in after["EventReport"] if not r["deleted"]}
    summaries = [n for n in reports if n.startswith("AI summary of ")]
    assert len(summaries) == 1 and reports[summaries[0]].startswith("## Threat")
    assert reports[REPORTS[0].stem] == REPORTS[0].read_text(encoding="utf-8")  # source untouched
    assert AI_TAGS <= _tags(after)  # event-level content: the event carries the AI tags
    assert after["distribution"] == str(YOUR_ORG_ONLY) and after["published"] is False


@pytest.mark.parametrize("created_event", REPORTS[1:2], indirect=True, ids=[REPORTS[1].stem[:8]])
def test_event_summary_lands_in_misp(misp_write, llm_settings, created_event) -> None:
    settings = {"use_case": "summarization", "summary_kind": "event"}
    _, after = _run_and_push(misp_write, created_event, settings)
    reports = {r["name"]: r["content"] for r in after["EventReport"] if not r["deleted"]}
    summaries = [n for n in reports if n == f"AI summary of event {after['uuid']}"]
    assert len(summaries) == 1 and reports[summaries[0]].startswith("## What happened")
    assert reports[REPORTS[1].stem] == REPORTS[1].read_text(encoding="utf-8")  # source untouched
    assert AI_TAGS <= _tags(after)
    seeded = {a["value"] for a in after["Attribute"] if a.get("comment") == "e2e seed attribute"}
    assert seeded == {v for _, v in SEED_ATTRIBUTES}  # nothing added or lost on the event
    assert after["distribution"] == str(YOUR_ORG_ONLY) and after["published"] is False


@pytest.mark.parametrize("created_event", REPORTS[:1], indirect=True, ids=[REPORTS[0].stem[:8]])
def test_tag_suggestion_lands_in_misp(misp_write, suggest_settings, created_event) -> None:
    metadata: dict = {}
    _, after = _run_and_push(misp_write, created_event, {"use_case": "tag_suggestion"}, metadata)
    added = {s["tag"] for s in metadata["added"]}
    if added:
        assert added <= _tags(after) and AI_TAGS <= _tags(after)
    else:  # the service abstained or only returned tags the event already had
        assert metadata["abstained"] or metadata["skipped_existing"]
        assert not _tags(after) & AI_TAGS
    assert after["distribution"] == str(YOUR_ORG_ONLY) and after["published"] is False
