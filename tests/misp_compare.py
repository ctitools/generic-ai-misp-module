"""Semantic comparison of two MISP event dicts (original vs. processed).

A PyMISP load -> to_json round trip is not byte-identical, so the round-trip quality gate
compares meaning, not bytes. Tolerated on purpose (each rule is deliberate, see
docs/DEVELOPER_GUIDE.md section 6):

1. keys whose value is None, "", whitespace-only, [] or {} are ignored on both sides
   (PyMISP serialises a whitespace-only EventReport content as "");
2. numbers and numeric strings compare as strings ("1" == 1); booleans stay booleans;
3. strings compare after whitespace collapsing;
4. ISO-8601 date-time strings compare by value (+0000 == +00:00, .000000 dropped, naive = UTC);
5. the paths in ALLOWLIST (known PyMISP normalisations).

Everything else is reported as a difference and fails the gate.
"""

import re
from datetime import datetime, timezone
from typing import Any

_EMPTY = (None, "", [], {})
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")

# path regex -> why the difference is tolerated
ALLOWLIST = {
    r"/GalaxyCluster\[\d+\]/(distribution|sharing_group_id)$": (
        "MISP sets these on default galaxy clusters, PyMISP refuses them; "
        "the module drops them (generic_ai._normalise_for_pymisp)"
    ),
    r"/ObjectReference\[\d+\]/object_uuid$": "PyMISP fills in the referencing object's uuid",
    r"/Opinion\[\d+\]/_canEdit$": "MISP UI permission flag, not event data",
    r"/RelatedEvent\[\d+\]/Opinion$": "PyMISP does not model opinions on related events",
}


def _is_empty(value: Any) -> bool:
    return value in _EMPTY or (isinstance(value, str) and not value.strip())


def _normalise(value: Any) -> Any:  # pylint: disable=too-many-return-statements
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items() if not _is_empty(v)}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = " ".join(value.split())
        if _DATETIME_RE.match(text):
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return text
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        return text
    return value


def _walk(a: Any, b: Any, path: str, out: list[tuple[str, str]]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(a.keys() | b.keys()):
            if key not in b:
                out.append((f"{path}/{key}", "missing after processing"))
            elif key not in a:
                out.append((f"{path}/{key}", "added by processing"))
            else:
                _walk(a[key], b[key], f"{path}/{key}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, f"{len(a)} items -> {len(b)} items"))
        for index, (x, y) in enumerate(zip(a, b, strict=False)):
            _walk(x, y, f"{path}[{index}]", out)
    elif a != b:
        out.append((path, f"{str(a)[:60]!r} -> {str(b)[:60]!r}"))


def misp_event_diff(original: dict, processed: dict) -> list[str]:
    """Return human-readable differences; an empty list means semantically equal."""
    found: list[tuple[str, str]] = []
    _walk(_normalise(original), _normalise(processed), "", found)
    return [
        f"{path}: {message}"
        for path, message in found
        if not any(re.search(pattern, path) for pattern in ALLOWLIST)
    ]
