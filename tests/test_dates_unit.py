"""Unit tests for genai/dates.py: only unambiguous spellings become ISO dates."""

import pytest

from genai.dates import to_iso

ISO = "2026-03-12T00:00:00+00:00"


@pytest.mark.parametrize(
    "spelling",
    [
        "2026-03-12",
        "2026-03-12T14:05:00Z",
        "2026-03-12 14:05",
        "12 March 2026",
        "12th March 2026",
        "12 Mar 2026",
        "12 Mar. 2026",
        "March 12, 2026",
        "March 12 2026",
        "Mar 12, 2026",
        "  march   12,  2026 ",
    ],
)
def test_accepted_spellings(spelling: str) -> None:
    assert to_iso(spelling) == ISO


@pytest.mark.parametrize(
    "spelling",
    [
        "03/04/2026",  # day/month order ambiguous
        "12.03.2026",
        "March 2026",  # no day
        "last week",
        "2026",
        "31 February 2026",  # not a date
        "12 Marsh 2026",  # not a month
        "",
    ],
)
def test_rejected_spellings(spelling: str) -> None:
    assert to_iso(spelling) is None
