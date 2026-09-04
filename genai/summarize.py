"""UC2 — Summarization of an EventReport (kind="report") or of the event itself (kind="event").

The summary is attached as a new EventReport and the event is AI-tagged (docs/USE-CASES.md).
"""

import re
from typing import Any

from pymisp import MISPEvent

from genai import llm, prompts

KINDS = ("report", "event")
_INDICATOR_RES = (
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),  # IPv4
    re.compile(r"\b[a-f0-9]{32}\b|\b[a-f0-9]{40}\b|\b[a-f0-9]{64}\b", re.I),  # hashes
    re.compile(r"https?://[^\s)\]>\"']+"),  # urls
    re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I),
    re.compile(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", re.I),  # uuids
    re.compile(  # domains with a common TLD
        r"\b(?:[a-z0-9-]+\.)+"
        r"(?:com|net|org|io|lu|eu|ru|cn|info|biz|xyz|top|click|live|help|site|online)\b",
        re.I,
    ),
)


def render_event(event: MISPEvent) -> str:
    """Deterministic markdown of the event's content (no timestamps, everything sorted)."""
    lines = [f"# Event {event.uuid}", f"info: {event.info}", f"date: {event.date}"]
    lines.append("tags: " + ", ".join(sorted(t.name for t in event.tags)))
    lines += ["", "## Attributes", "| category | type | value | comment |", "|---|---|---|---|"]
    for a in sorted(event.attributes, key=lambda a: (a.category, a.type, str(a.value))):
        lines.append(f"| {a.category} | {a.type} | {a.value} | {getattr(a, 'comment', '') or ''} |")
    lines += ["", "## Objects"]
    for o in sorted(event.objects, key=lambda o: (o.name, o.uuid)):
        lines.append(f"- {o.name} ({o.uuid})")
        for a in sorted(o.attributes, key=lambda a: (a.object_relation or "", str(a.value))):
            lines.append(f"  - {a.object_relation}: {a.value}")
    galaxies = sorted(
        f"{g.name}: {c.value}" for g in getattr(event, "galaxies", []) for c in g.clusters
    )
    lines += ["", "## Galaxies", *(f"- {g}" for g in galaxies)]
    related = sorted(
        f"- {r['Event'].get('uuid', '')}: {r['Event'].get('info', '')}"
        for r in getattr(event, "RelatedEvent", [])
        if isinstance(r, dict) and "Event" in r
    )
    lines += ["", "## Related events", *related]
    lines += ["", "## Reports", *(f"- {r.name}" for r in event.event_reports)]
    return "\n".join(lines) + "\n"


def check_summary(summary: str, source: str, prompt: prompts.Prompt) -> list[str]:
    """Structural gate (TESTING.md L3): headings, length, no indicator that is not in the input."""
    problems = [f"missing heading {h!r}" for h in prompt.headings if h not in summary]
    words = len(re.findall(r"\S+", re.sub(r"^#.*$", "", summary, flags=re.M)))
    if prompt.max_words and words > prompt.max_words:
        problems.append(f"{words} words > {prompt.max_words}")
    source_lower = source.lower()
    foreign = {
        m.group(0)
        for rx in _INDICATOR_RES
        for m in rx.finditer(summary)
        if m.group(0).lower() not in source_lower
    }
    problems += [f"indicator not in input: {f}" for f in sorted(foreign)]
    return problems


def summarize(
    event: MISPEvent,
    report: str,
    kind: str,
    settings: llm.LLMSettings,
    prompt: prompts.Prompt,
) -> dict[str, Any]:
    """Attach an AI summary of the report or of the event as a new EventReport; returns metadata."""
    if kind not in KINDS:
        raise ValueError(f"unknown summary kind {kind!r}, expected one of {KINDS}")
    if kind == "report":
        source = report
        name = "AI summary of " + ", ".join(
            r.name for r in event.event_reports if not getattr(r, "deleted", False)
        )
    else:
        source = render_event(event)
        name = f"AI summary of event {event.uuid}"
    if not source.strip():
        raise ValueError(f"nothing to summarise for kind={kind!r}")
    messages = [{"role": "user", "content": prompt.render(input=source)}]
    summary = llm.llm_chat(messages, prompt.params, settings)
    problems = check_summary(summary, source, prompt)
    if problems:
        raise llm.LLMError("summary failed the structural check: " + "; ".join(problems))
    event.add_event_report(name=name, content=summary)
    prompts.tag_ai_generated(event)
    return {
        "use_case": "summarization",
        "kind": kind,
        "report_name": name,
        "words": len(summary.split()),
        "input_chars": len(source),
        "prompt": prompt.describe(),
    }
