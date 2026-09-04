"""Generic AI MISP module: takes a full MISP Event, validates it, runs two (dummy) hooks.

Data flow (see README.md / docs/ARCHITECTURE.md):

    request -> _extract_event -> validate_event -> event (MISPEvent)
        -> get_event_report(event) -> event_report (markdown string)
        -> process_event(event)            -> MISPEvent
        or...
        -> process_eventReport(event_report) -> MISPEvent
        -> response {"results": {"Event": ..., "ReportEvent": ...}, "event_report": ...}
"""

import copy
import json
from pathlib import Path
from typing import Any

from pymisp import MISPEvent, PyMISPError

misperrors = {"error": "Error"}
mispattributes = {"input": [], "output": ["Event"], "format": "misp_standard"}
moduleinfo = {
    "version": "0.3",
    "author": "Aaron Kaplan / ctitools",
    "description": "Generic AI MISP module operating on a full MISP Event.",
    "module-type": ["expansion"],
    "name": "Generic AI MISP module",
    "logo": "",
    "requirements": ["pymisp"],
    "features": (
        "Accepts a full MISP Event (MISP core format), validates it with PyMISP, extracts the "
        "EventReport markdown and passes both through process_event() and "
        "process_eventReport(). Both hooks are dummies for now and return a MISP Event."
    ),
    "references": ["https://www.misp-standard.org/rfc/misp-standard-core.html"],
    "input": 'A full MISP Event under "event" ({"Event": {...}} or bare) or under "data": [...].',
    "output": "Two MISP Events: the processed event and the event built from the EventReport.",
}
moduleconfig: list[str] = []

# process_event(..., e2etest=True) writes the processed event here as <uuid>.json
E2E_DIR = Path(__file__).resolve().parents[1] / "tests" / "e2etests"


def _extract_event(request: dict[str, Any]) -> dict[str, Any]:
    """Return the raw event dict from either request shape, unwrapping {"Event": ...}."""
    data = request.get("event")
    if data is None and isinstance(request.get("data"), list) and request["data"]:
        data = request["data"][0]
    if not isinstance(data, dict) or not data:
        raise ValueError('This module requires a MISP Event under "event" or "data".')
    return data["Event"] if isinstance(data.get("Event"), dict) else data


def _normalise_for_pymisp(data: dict[str, Any]) -> dict[str, Any]:
    """Work around a PyMISP-vs-MISP mismatch.

    MISP's /events/view output sets "distribution" / "sharing_group_id" on default galaxy
    clusters, but PyMISP (MISPGalaxyCluster.from_dict) refuses default clusters carrying them.
    """
    data = copy.deepcopy(data)  # PyMISP also pops keys from nested dicts while loading

    def strip(node: Any) -> None:  # galaxies sit on the event, its attributes and its objects
        if isinstance(node, list):
            for item in node:
                strip(item)
        elif isinstance(node, dict):
            for cluster in node.get("GalaxyCluster", []):
                if cluster.get("default"):
                    cluster.pop("distribution", None)
                    cluster.pop("sharing_group_id", None)
            for value in node.values():
                strip(value)

    strip(data)
    return data


def validate_event(data: dict[str, Any]) -> MISPEvent:
    """Validate the raw event dict with PyMISP; raises PyMISPError on invalid input."""
    if not data.get("info"):
        raise PyMISPError('"info" is required.')
    # force_timestamps: PyMISP otherwise drops "timestamp" from events it considers edited
    event = MISPEvent(force_timestamps=True)
    event.load(_normalise_for_pymisp(data))
    return event


def get_event_report(event: MISPEvent) -> str:
    """Markdown of all non-deleted EventReports of the event, joined; "" if there are none."""
    contents = [
        report.content
        for report in event.event_reports
        if report.content and not getattr(report, "deleted", False)
    ]
    return "\n\n".join(contents)


def process_event(event: MISPEvent, e2etest: bool = False) -> MISPEvent:
    """Dummy hook acting on the whole event. Replace with real AI logic.

    With e2etest=True the (processed) event is also written to E2E_DIR/<uuid>.json so the
    round-trip quality gate (tests/test_e2e_roundtrip.py) can compare it with the original.
    """
    if e2etest:
        E2E_DIR.mkdir(parents=True, exist_ok=True)
        path = E2E_DIR / f"{event.uuid}.json"
        path.write_text(json.dumps(_to_dict(event), indent=2), encoding="utf-8")
    return event


def process_eventReport(event_report: str) -> MISPEvent:  # pylint: disable=invalid-name
    """Dummy hook acting only on the EventReport markdown. Replace with real AI logic."""
    event = MISPEvent()
    event.info = "Generic AI: dummy result from process_eventReport"
    event.add_event_report(name="Generic AI dummy report", content=event_report)
    return event


def _to_dict(event: MISPEvent) -> dict[str, Any]:
    return {"Event": json.loads(event.to_json())}


def dict_handler(request: dict[str, Any]) -> dict[str, Any]:
    try:
        event = validate_event(_extract_event(request))
    except (ValueError, TypeError, KeyError, PyMISPError) as error:
        # PyMISP raises TypeError/KeyError (not PyMISPError) for some missing fields
        return {"error": f"Invalid MISP Event: {error}"}

    event_report = get_event_report(event)
    return {
        "results": {
            "Event": _to_dict(process_event(event)),
            "ReportEvent": _to_dict(process_eventReport(event_report)),
        },
        "event_report": event_report,
    }


def handler(q: str | bool = False) -> dict[str, Any] | bool:  # pylint: disable=invalid-name
    if q is False:
        return False
    try:
        request = json.loads(q)
    except json.JSONDecodeError as error:
        return {"error": f"Invalid JSON request: {error}"}
    return dict_handler(request)


def introspection() -> dict[str, Any]:
    return mispattributes


def version() -> dict[str, Any]:
    return {**moduleinfo, "config": moduleconfig}
