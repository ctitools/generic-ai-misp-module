"""Turn a date spelling copied from a report into ISO-8601 (UTC midnight), or None.

Only unambiguous spellings are accepted; anything else (numeric day/month order, relative
dates, months without a day) returns None and the caller drops the date. Nothing is guessed.
"""

import re
from datetime import date

_MONTHS = {
    m: i
    for i, names in enumerate(
        (
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ),
        start=1,
    )
    for m in names
}
_MONTH = r"(?P<month>[a-z]+)\.?"
_PATTERNS = (
    re.compile(r"^(?P<year>\d{4})-(?P<mon>\d{2})-(?P<day>\d{2})(?:[t ]\d{2}:\d{2}(?::\d{2})?z?)?$"),
    re.compile(rf"^(?P<day>\d{{1,2}})(?:st|nd|rd|th)? {_MONTH},? (?P<year>\d{{4}})$"),
    re.compile(rf"^{_MONTH} (?P<day>\d{{1,2}})(?:st|nd|rd|th)?,? (?P<year>\d{{4}})$"),
)


def to_iso(spelling: str) -> str | None:
    """'12 March 2026', 'March 12, 2026', '2026-03-12' -> '2026-03-12T00:00:00+00:00'."""
    text = " ".join(spelling.lower().split())
    for pattern in _PATTERNS:
        if match := pattern.match(text):
            parts = match.groupdict()
            month = int(parts["mon"]) if "mon" in parts else _MONTHS.get(parts["month"], 0)
            try:
                day = date(int(parts["year"]), month, int(parts["day"]))
            except ValueError:
                return None
            return day.isoformat() + "T00:00:00+00:00"
    return None
