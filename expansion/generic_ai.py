"""Generic AI MISP module: takes a full MISP Event, validates it, runs a use-case on it.

Data flow (see docs/DEVELOPER_GUIDE.md / docs/ARCHITECTURE.md):

    request -> _extract_event -> validate_event -> event (MISPEvent)
        -> get_event_report(event) -> event_report (markdown string)
        -> process_event(event, settings)    -> MISPEvent
           (use_case none|extraction|summarization|tag_suggestion)
        -> process_eventReport(event_report) -> MISPEvent
        -> response {"results": {"Event": ..., "ReportEvent": ...}, "event_report", "metadata"}
"""

import copy
import json
import sys
from pathlib import Path
from typing import Any

from pymisp import MISPEvent, PyMISPError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # misp-modules imports this file by path, not as a package
    sys.path.insert(0, str(REPO_ROOT))

from genai import (  # noqa: E402  # pylint: disable=wrong-import-position
    extract,
    llm,
    prompts,
    suggest,
    summarize,
)

misperrors = {"error": "Error"}
mispattributes = {"input": [], "output": ["Event"], "format": "misp_standard"}
moduleinfo = {
    "version": "0.4",
    "author": "Aaron Kaplan / ctitools",
    "description": "Generic AI MISP module operating on a full MISP Event.",
    "module-type": ["expansion"],
    "name": "Generic AI MISP module",
    "logo": "",
    "requirements": ["pymisp"],
    "features": (
        "Accepts a full MISP Event (MISP core format), validates it with PyMISP and runs a "
        "use-case on it: CTI info extraction (high-confidence attributes from the EventReport) "
        "or summarization (of the EventReport or of the event), or tag suggestion through the "
        "misp-tag-suggest service. Prompts and sampling parameters come from the "
        "generic-ai-prompts galaxy; all AI output is ai-computer-assisted tagged."
    ),
    "references": ["https://www.misp-standard.org/rfc/misp-standard-core.html"],
    "input": 'A full MISP Event under "event" ({"Event": {...}} or bare) or under "data": [...].',
    "output": "The processed MISP Event plus a MISP Event built from the EventReport.",
}
# key -> default. Settable in MISP's module settings; the request body may override all but
# request_timeout. Endpoint and API key come from .env only (never from the request).
DEFAULTS: dict[str, Any] = {
    "use_case": "none",
    "summary_kind": "report",
    "prompt_extraction": "",
    "prompt_summary_report": "",
    "prompt_summary_event": "",
    "model_id": "",
    "min_confidence": 0.9,
    "suggest_limit": 5,
    "suggest_min_score": 0.0,
    "request_timeout": llm.DEFAULT_TIMEOUT,
}
moduleconfig = list(DEFAULTS)
REQUEST_KEYS = frozenset(moduleconfig) - {"request_timeout"}
USE_CASES = ("none", "extraction", "summarization", "tag_suggestion")

# process_event(..., e2etest=True) writes the processed event here as <uuid>.json
E2E_DIR = REPO_ROOT / "tests" / "e2etests"


def _extract_event(request: dict[str, Any]) -> dict[str, Any]:
    """Return the raw event dict from either request shape, unwrapping {"Event": ...}."""
    data = request.get("event")
    if data is None and isinstance(request.get("data"), list) and request["data"]:
        data = request["data"][0]
    if not isinstance(data, dict) or not data:
        raise ValueError('This module requires a MISP Event under "event" or "data".')
    return data["Event"] if isinstance(data.get("Event"), dict) else data


def resolve_settings(request: dict[str, Any]) -> dict[str, Any]:
    """Precedence: request body (allowed keys) > module config > .env GENERIC_AI_<KEY> > default."""
    config = request.get("config") if isinstance(request.get("config"), dict) else {}
    env = llm.env()
    settings = {}
    for key, default in DEFAULTS.items():
        sources = [
            request.get(key) if key in REQUEST_KEYS else None,
            config.get(key),
            env.get(f"GENERIC_AI_{key.upper()}"),
        ]
        value = next((v for v in sources if v not in (None, "")), default)
        settings[key] = type(default)(value) if isinstance(default, (int, float)) else value
    return settings


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


def _run_use_case(event: MISPEvent, settings: dict[str, Any]) -> dict[str, Any]:
    if settings["use_case"] == "tag_suggestion":  # no LLM: the misp-tag-suggest service
        suggest_settings = suggest.SuggestSettings.from_env(settings["request_timeout"])
        result = suggest.suggest_tags(
            event,
            suggest_settings,
            int(settings["suggest_limit"]),
            float(settings["suggest_min_score"]),
        )
        result["model"] = {"name": result["model_version"], "server": suggest_settings.base_url}
        return result
    llm_settings = llm.LLMSettings.from_env(
        settings["model_id"] or None, settings["request_timeout"]
    )
    report = get_event_report(event)
    if settings["use_case"] == "extraction":
        prompt = prompts.resolve_prompt("cti-info-extraction", settings["prompt_extraction"])
        result = extract.extract_iocs(
            event, report, llm_settings, prompt, float(settings["min_confidence"])
        )
    else:
        kind = settings["summary_kind"]
        if kind not in summarize.KINDS:
            raise ValueError(f"unknown summary_kind {kind!r}, expected one of {summarize.KINDS}")
        prompt = prompts.resolve_prompt(f"summary-{kind}", settings[f"prompt_summary_{kind}"])
        result = summarize.summarize(event, report, kind, llm_settings, prompt)
    result["model"] = llm.model_info(llm_settings)
    return result


def process_event(
    event: MISPEvent,
    e2etest: bool = False,
    settings: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MISPEvent:
    """Run the configured use-case on the event (default "none": pass-through).

    `metadata`, if given, is filled with what the use-case did. With e2etest=True the
    processed event is also written to E2E_DIR/<uuid>.json for the round-trip quality gate.
    """
    settings = {**DEFAULTS, **(settings or {})}
    if settings["use_case"] not in USE_CASES:
        raise ValueError(f"unknown use_case {settings['use_case']!r}, expected one of {USE_CASES}")
    if settings["use_case"] != "none":
        result = _run_use_case(event, settings)
        if metadata is not None:
            metadata.update(result)
    if e2etest:
        E2E_DIR.mkdir(parents=True, exist_ok=True)
        (E2E_DIR / f"{event.uuid}.json").write_text(
            json.dumps(_to_dict(event), indent=2), encoding="utf-8"
        )
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
    metadata: dict[str, Any] = {}
    try:
        processed = process_event(event, settings=resolve_settings(request), metadata=metadata)
    except (ValueError, llm.LLMError, suggest.SuggestError, PyMISPError) as error:
        # PyMISPError: an accepted candidate PyMISP still refuses (e.g. an unparsable datetime)
        return {"error": str(error)}
    return {
        "results": {
            "Event": _to_dict(processed),
            "ReportEvent": _to_dict(process_eventReport(event_report)),
        },
        "event_report": event_report,
        "metadata": metadata,
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
