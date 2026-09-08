"""Unit tests for genai/refang.py."""

import pytest

from genai.refang import is_defanged, refang


@pytest.mark.parametrize(
    "defanged, clean",
    [
        ("hxxp://evil[.]com/x", "http://evil.com/x"),
        ("hXXps://a[.]b[:]443/p", "https://a.b:443/p"),
        ("hxxp[:]//evil.com", "http://evil.com"),
        ("1[.]2[.]3[.]4:8080", "1.2.3.4:8080"),
        ("evil(.)com", "evil.com"),
        ("evil{.}com", "evil.com"),
        ("evil[dot]com and evil(DOT)org", "evil.com and evil.org"),
        ("bad[at]evil[.]com", "bad@evil.com"),
        ("bad[@]evil.com", "bad@evil.com"),
        ("https://pastebin\\.com/raw/q81X", "https://pastebin.com/raw/q81X"),
        ("see api.ipify\\.org and go", "see api.ipify.org and go"),
        ("1.2.3.4 already clean", "1.2.3.4 already clean"),
    ],
)
def test_refang(defanged: str, clean: str) -> None:
    assert refang(defanged) == clean
    assert refang(clean) == clean  # idempotent


@pytest.mark.parametrize(
    "text",
    [
        "\\\\.\\pipe\\ntsvcs",
        "'%TEMP%\\\\..\\\\..\\\\Roaming'",
        "[a-z0-9]{16}\\.dll",  # a regex in the report, not a domain
        "evil dot com",  # too ambiguous, left alone
    ],
)
def test_refang_leaves_paths_and_prose_alone(text: str) -> None:
    assert refang(text) == text
    assert not is_defanged(text)


def test_is_defanged() -> None:
    assert is_defanged("131.226.2[.]6")
    assert not is_defanged("131.226.2.6")
