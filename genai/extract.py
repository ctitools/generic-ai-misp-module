"""UC1 — CTI info extraction: high-confidence MISP attributes from an EventReport.

The LLM proposes candidates as JSON; five deterministic filters decide what is added
(docs/USE-CASES.md). Every added attribute is AI-tagged.
"""

import ipaddress
import json
import re
from typing import Any

from pymisp import MISPAttribute, MISPEvent, MISPObject

from genai import llm, prompts
from genai.refang import is_defanged, refang

DESCRIBE_TYPES = MISPAttribute().describe_types
MISP_TYPES: frozenset[str] = frozenset(DESCRIBE_TYPES["types"])
HASH_TYPES = ("md5", "sha1", "sha256")
HASH_BY_LENGTH = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I
)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.I)


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _hex(length: int):
    return lambda value: re.fullmatch(rf"[a-f0-9]{{{length}}}", value, re.I) is not None


FORMAT_CHECKS = {
    "ip-src": _is_ip,
    "ip-dst": _is_ip,
    "domain": _DOMAIN_RE.match,
    "hostname": _DOMAIN_RE.match,
    "md5": _hex(32),
    "sha1": _hex(40),
    "sha256": _hex(64),
    "url": lambda value: value.lower().startswith(("http://", "https://")),
    "email": _EMAIL_RE.match,
    "email-src": _EMAIL_RE.match,
    "email-dst": _EMAIL_RE.match,
    "vulnerability": _CVE_RE.match,
}


def _ip_port(value: str) -> bool:
    host, sep, port = value.rpartition(":")
    return bool(sep) and port.isdigit() and _is_ip(host.strip("[]"))


FORMAT_CHECKS |= {
    "ip-src|port": _ip_port,
    "ip-dst|port": _ip_port,
    "hostname|port": lambda value: (
        _DOMAIN_RE.match(value.rpartition(":")[0]) is not None
        and value.rpartition(":")[2].isdigit()
    ),
}


def normalise(text: str) -> str:
    return " ".join(text.split()).lower()


def existing_values(event: MISPEvent) -> set[tuple[str, str]]:
    attributes = list(event.attributes) + [a for o in event.objects for a in o.attributes]
    return {(a.type, normalise(str(a.value))) for a in attributes}


def parse_candidates(answer: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(answer)
    except json.JSONDecodeError as error:
        raise llm.LLMError("extraction answer is not JSON") from error
    candidates = data.get("indicators") if isinstance(data, dict) else data
    if not isinstance(candidates, list) or not all(isinstance(c, dict) for c in candidates):
        raise llm.LLMError('extraction answer must be {"indicators": [...]}')
    return candidates


def reject_reason(  # one return per filter; pylint: disable=too-many-return-statements
    candidate: dict[str, Any], source: str, existing: set[tuple[str, str]], min_confidence: float
) -> str | None:
    """The first filter the candidate fails, or None if it may be added.

    Two normalisations happen here and are recorded on the candidate (`_provenance`): defanged
    values are refanged (`1.2.3[.]4` -> `1.2.3.4`) and a hash labelled with the wrong hash type
    is re-typed by its length. Everything else is compared literally against the report.
    """
    raw = str(candidate.get("value", "")).strip()
    value = refang(raw)
    kind = str(candidate.get("type", ""))
    if not value or normalise(value) not in source:
        return "not-in-source"
    if normalise(value) not in normalise(refang(str(candidate.get("quote", "")))):
        return "quote-mismatch"
    if kind not in MISP_TYPES:
        return "unknown-type"
    if kind in HASH_BY_LENGTH.values() and re.fullmatch(r"[a-f0-9]+", value, re.I):
        if (retyped := HASH_BY_LENGTH.get(len(value))) and retyped != kind:
            candidate["_provenance"] = f"typed {kind} by the model"
            kind = candidate["type"] = retyped
    if is_defanged(raw):
        candidate["_provenance"] = f"defanged in source as {raw}"
    candidate["value"] = value
    check = FORMAT_CHECKS.get(kind)
    if check and not check(value):
        return "format"
    if (kind, normalise(value)) in existing:
        return "duplicate"
    try:
        if float(candidate.get("confidence", 0)) < min_confidence:
            return "confidence"
    except TypeError, ValueError:
        return "confidence"
    return None


def _category(candidate: dict[str, Any]) -> str:
    kind = candidate["type"]
    category = candidate.get("category")
    if category in DESCRIBE_TYPES["category_type_mappings"] and kind in DESCRIBE_TYPES[
        "category_type_mappings"
    ].get(category, []):
        return str(category)
    return str(DESCRIBE_TYPES["sane_defaults"][kind]["default_category"])


def _add(event: MISPEvent, accepted: list[dict[str, Any]], comment: str) -> int:
    """Add accepted candidates: CVEs as vulnerability objects, filename+hash pairs sharing a
    quote as file objects, everything else as plain attributes. Returns the object count."""
    objects = 0

    def note(candidate: dict[str, Any]) -> str:
        return comment + (f"; {candidate['_provenance']}" if "_provenance" in candidate else "")

    by_quote: dict[str, list[dict[str, Any]]] = {}
    for candidate in accepted:
        by_quote.setdefault(normalise(str(candidate.get("quote", ""))), []).append(candidate)
    for group in by_quote.values():
        types = {c["type"] for c in group}
        if "filename" in types and types & set(HASH_TYPES):
            misp_object = MISPObject("file")
            misp_object.comment = comment
            for candidate in group:
                if candidate["type"] in ("filename", *HASH_TYPES):
                    attribute = misp_object.add_attribute(
                        candidate["type"], value=candidate["value"], comment=note(candidate)
                    )
                    prompts.tag_ai_generated(attribute)
            event.add_object(misp_object)
            objects += 1
            group = [c for c in group if c["type"] not in ("filename", *HASH_TYPES)]
        for candidate in group:
            if candidate["type"] == "vulnerability":
                misp_object = MISPObject("vulnerability")
                misp_object.comment = comment
                attribute = misp_object.add_attribute(
                    "id", value=candidate["value"], comment=note(candidate)
                )
                prompts.tag_ai_generated(attribute)
                event.add_object(misp_object)
                objects += 1
            else:
                attribute = event.add_attribute(
                    candidate["type"],
                    candidate["value"],
                    category=_category(candidate),
                    comment=note(candidate),
                )
                prompts.tag_ai_generated(attribute)
    return objects


def _count(accepted: list[dict[str, Any]], prefix: str) -> int:
    return sum(c.get("_provenance", "").startswith(prefix) for c in accepted)


def extract_iocs(  # filters, counts and provenance in one pass; pylint: disable=too-many-locals
    event: MISPEvent,
    report: str,
    settings: llm.LLMSettings,
    prompt: prompts.Prompt,
    min_confidence: float = 0.9,
) -> dict[str, Any]:
    """Add high-confidence indicators found in `report` to `event`; returns metadata."""
    if not report.strip():
        raise ValueError("the event has no EventReport to extract from")
    content = prompt.render(misp_types=", ".join(sorted(MISP_TYPES)), input=report)
    answer = llm.llm_chat([{"role": "user", "content": content}], prompt.params, settings, True)
    source = normalise(refang(report))
    existing = existing_values(event)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in parse_candidates(answer):
        given = {"type": candidate.get("type"), "value": candidate.get("value")}  # model's words
        if reason := reject_reason(candidate, source, existing, min_confidence):
            rejected.append(given | {"reason": reason})
            continue
        existing.add((candidate["type"], normalise(candidate["value"])))
        accepted.append(candidate)
    report_uuids = ", ".join(
        r.uuid for r in event.event_reports if not getattr(r, "deleted", False)
    )
    objects = _add(event, accepted, f"extracted by generic_ai from EventReport {report_uuids}")
    return {
        "use_case": "extraction",
        "added": len(accepted),
        "objects": objects,
        "rejected": rejected,
        "refanged": _count(accepted, "defanged"),
        "retyped": _count(accepted, "typed"),
        "prompt": prompt.describe(),
    }
