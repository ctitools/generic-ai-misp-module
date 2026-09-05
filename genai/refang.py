"""Refang defanged indicators (`hxxp://evil[.]com`, `1.2.3[.]4`, `bad[at]evil[.]com`).

The one normalisation the module performs (docs/USE-CASES.md). Used by the extraction
use-case, the classic baseline and the benchmark metrics, so all three agree on a value.
"""

import re

_BRACKETED = re.compile(r"\[\.\]|\(\.\)|\{\.\}|\[dot\]|\(dot\)", re.I)
_PATTERNS = (
    (re.compile(r"hxxp(s?)(?:\[:\]|:)//", re.I), r"http\1://"),
    (_BRACKETED, "."),
    (re.compile(r"\[:\]"), ":"),
    (re.compile(r"\[@\]|\[at\]|\(at\)", re.I), "@"),
)
_ESCAPED_DOT = re.compile(r"\\\.")
_NETWORK_TOKEN = re.compile(  # url, email, domain(:port|/path) or IPv4(:port) after refanging
    r"^(?:https?://\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+|(?:[a-z0-9-]+\.)+[a-z]{2,63}(?:[/:]\S*)?"
    r"|\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?)$",
    re.I,
)


def _unescape_dots(token: str) -> str:
    """Markdown-escaped dots (`pastebin\\.com`) only in network tokens, never in pipe paths."""
    if token.startswith("\\\\") or "\\." not in token:
        return token
    candidate = _ESCAPED_DOT.sub(".", token)
    return candidate if _NETWORK_TOKEN.match(candidate.rstrip(".,;:)")) else token


def refang(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    if "\\." in text:
        text = " ".join(_unescape_dots(token) for token in text.split(" "))
    return text


def is_defanged(text: str) -> bool:
    return refang(text) != text
