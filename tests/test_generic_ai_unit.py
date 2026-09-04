import copy
import json

import pytest
from conftest import FIXTURE_FILES, NO_REPORT, TWO_REPORTS, load_fixture
from pymisp import MISPEvent

from expansion import generic_ai


def test_introspection_and_version() -> None:
    assert generic_ai.introspection() == {
        "input": [],
        "output": ["Event"],
        "format": "misp_standard",
    }
    info = generic_ai.version()
    assert info["name"] == "Generic AI MISP module"
    assert info["module-type"] == ["expansion"]
    assert info["config"] == generic_ai.moduleconfig
    assert "config" not in generic_ai.moduleinfo  # version() must not mutate the global


def test_handler_without_query_returns_false() -> None:
    assert generic_ai.handler() is False


def test_handler_rejects_invalid_json() -> None:
    assert generic_ai.handler("{not json")["error"].startswith("Invalid JSON request")


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_every_fixture_event_validates_and_round_trips(path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    result = generic_ai.dict_handler({"module": "generic_ai", "event": raw})
    assert "error" not in result
    event = result["results"]["Event"]["Event"]
    assert event["uuid"] == raw["Event"]["uuid"]
    assert event["info"] == raw["Event"]["info"]
    assert len(event.get("Attribute", [])) == len(raw["Event"].get("Attribute", []))
    assert len(event.get("Object", [])) == len(raw["Event"].get("Object", []))


def test_wrapped_bare_and_export_style_inputs_are_equivalent(event_with_report) -> None:
    wrapped = generic_ai.dict_handler({"event": event_with_report})
    bare = generic_ai.dict_handler({"event": event_with_report["Event"]})
    export_style = generic_ai.dict_handler({"data": [event_with_report]})
    assert wrapped["event_report"] == bare["event_report"] == export_style["event_report"]
    assert (
        wrapped["results"]["Event"]["Event"]["uuid"]
        == bare["results"]["Event"]["Event"]["uuid"]
        == export_style["results"]["Event"]["Event"]["uuid"]
    )


def test_input_dict_is_not_mutated(event_with_report) -> None:
    before = copy.deepcopy(event_with_report)
    generic_ai.dict_handler({"event": event_with_report})
    assert event_with_report == before


def test_event_report_is_the_report_markdown(event_with_report) -> None:
    result = generic_ai.dict_handler({"event": event_with_report})
    reports = event_with_report["Event"]["EventReport"]
    assert len(reports) == 1
    assert result["event_report"] == reports[0]["content"]
    # process_eventReport() dummy wraps the markdown into a new event's EventReport
    report_event = result["results"]["ReportEvent"]["Event"]
    # PyMISP strips surrounding whitespace when it stores report content
    assert report_event["EventReport"][0]["content"] == reports[0]["content"].strip()
    assert report_event["uuid"] != event_with_report["Event"]["uuid"]


def test_multiple_reports_are_joined() -> None:
    raw = load_fixture(TWO_REPORTS)
    contents = [r["content"] for r in raw["Event"]["EventReport"]]
    assert len(contents) == 2
    assert generic_ai.dict_handler({"event": raw})["event_report"] == "\n\n".join(contents)


def test_deleted_reports_are_skipped(event_with_report) -> None:
    event_with_report["Event"]["EventReport"][0]["deleted"] = True
    assert generic_ai.dict_handler({"event": event_with_report})["event_report"] == ""


def test_event_without_report_gives_empty_string() -> None:
    result = generic_ai.dict_handler({"event": load_fixture(NO_REPORT)})
    assert "error" not in result
    assert result["event_report"] == ""


@pytest.mark.parametrize(
    ("request_body", "fragment"),
    [
        ({}, 'under "event" or "data"'),
        ({"event": "not a dict"}, 'under "event" or "data"'),
        ({"data": []}, 'under "event" or "data"'),
        ({"event": {"Event": {"date": "2024-01-01"}}}, '"info" is required'),
        ({"event": {"Event": {"info": "x", "date": "not-a-date"}}}, "date"),
        ({"event": {"Event": {"info": "x", "distribution": 9}}}, "distribution"),
        ({"event": {"Event": {"info": "x", "EventReport": [{"content": "c"}]}}}, "name"),
        (
            {"event": {"Event": {"info": "x", "Attribute": [{"type": "nope", "value": "v"}]}}},
            "nope",
        ),
    ],
)
def test_invalid_events_are_rejected(request_body, fragment) -> None:
    result = generic_ai.dict_handler(request_body)
    assert result["error"].startswith("Invalid MISP Event: ")
    assert fragment in result["error"]


def test_default_galaxy_cluster_with_distribution_is_accepted() -> None:
    # MISP's /events/view output looks like this; PyMISP alone would reject it.
    cluster = {
        "uuid": "b7a2c8a4-0a17-4c0a-9d5d-3d5f7a5f1c11",
        "value": "x",
        "default": True,
        "distribution": "3",
        "sharing_group_id": "0",
    }
    galaxy = {
        "uuid": "c5f6f4c6-9d68-4b6f-9d3a-0c4b3d5a2f22",
        "name": "g",
        "type": "g",
        "GalaxyCluster": [copy.deepcopy(cluster)],
    }
    event = {
        "info": "x",
        "Galaxy": [copy.deepcopy(galaxy)],
        "Attribute": [{"type": "text", "value": "v", "Galaxy": [copy.deepcopy(galaxy)]}],
    }
    result = generic_ai.dict_handler({"event": event})
    assert "error" not in result, result
    assert len(result["results"]["Event"]["Event"]["Galaxy"]) == 1


def test_process_event_is_identity(event_with_report) -> None:
    event = generic_ai.validate_event(event_with_report["Event"])
    assert generic_ai.process_event(event) is event


def test_process_event_report_returns_misp_event() -> None:
    result = generic_ai.process_eventReport("# Title\n\nbody")
    assert isinstance(result, MISPEvent)
    assert result.event_reports[0].content == "# Title\n\nbody"


def test_process_event_e2etest_writes_event_file(event_with_report, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(generic_ai, "E2E_DIR", tmp_path / "e2etests")
    event = generic_ai.validate_event(event_with_report["Event"])
    assert generic_ai.process_event(event) is event
    assert not (tmp_path / "e2etests").exists()  # default: nothing written
    generic_ai.process_event(event, e2etest=True)
    saved = json.loads((tmp_path / "e2etests" / f"{event.uuid}.json").read_text(encoding="utf-8"))
    assert saved["Event"]["uuid"] == event_with_report["Event"]["uuid"]
    assert saved["Event"]["timestamp"] == event_with_report["Event"]["timestamp"]
