import hashlib
import json
import re
from typing import Any

misperrors = {"error": "Error"}
mispattributes = {
    "input": ["text", "comment"],
    "output": ["text"],
}
moduleinfo = {
    "version": "0.1",
    "author": "OpenCode",
    "description": (
        "Generic AI MISP expansion scaffold with a deterministic summarization fallback."
    ),
    "module-type": ["expansion"],
    "name": "Generic AI",
    "logo": "",
    "requirements": [],
    "features": (
        "This scaffold accepts free text or a text-like MISP attribute and "
        "returns a short deterministic summary. It is intended as the "
        "thinnest runnable Generic AI module before wiring a real model "
        "backend."
    ),
    "references": [],
    "input": "Raw text or a MISP attribute of type text/comment.",
    "output": "A text summary in MISP expansion format plus execution metadata.",
}
moduleconfig = [
    "summary_sentences",
    "summary_chars",
    "default_model_id",
    "default_use_case_category",
]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE_RE = re.compile(r"\s+")
_MARKDOWN_HEADING_RE = re.compile(r"(?m)^\s{0,3}#+\s*")


def _normalise_text(text: str) -> str:
    without_headings = _MARKDOWN_HEADING_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", without_headings).strip()


def _coerce_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, coerced))


def _extract_input_text(request: dict[str, Any]) -> str:
    if request.get("text"):
        return str(request["text"])

    attribute = request.get("attribute")
    if attribute:
        attribute_type = attribute.get("type")
        if attribute_type not in mispattributes["input"]:
            raise ValueError("Unsupported attribute type.")
        value = attribute.get("value")
        if not value:
            raise ValueError('This module requires an "attribute" with a non-empty value.')
        return str(value)

    raise ValueError('This module requires either a "text" field or a supported "attribute" field.')


def _summarise(text: str, sentence_limit: int, char_limit: int) -> str:
    normalised = _normalise_text(text)
    if not normalised:
        raise ValueError("The provided text is empty after normalisation.")

    sentences = [
        sentence.strip() for sentence in _SENTENCE_SPLIT_RE.split(normalised) if sentence.strip()
    ]
    if len(sentences) == 1:
        if len(normalised) <= char_limit:
            return normalised
        return f"{normalised[: char_limit - 3].rstrip()}..."

    selected: list[str] = []
    current_length = 0
    for sentence in sentences:
        projected_length = current_length + len(sentence) + (1 if selected else 0)
        if projected_length > char_limit and selected:
            break
        if projected_length > char_limit:
            return f"{sentence[: char_limit - 3].rstrip()}..."
        selected.append(sentence)
        current_length = projected_length
        if len(selected) >= sentence_limit:
            break
    return " ".join(selected)


def dict_handler(request: dict[str, Any]) -> dict[str, Any]:
    config = request.get("config") or {}

    try:
        source_text = _extract_input_text(request)
    except ValueError as error:
        return {"error": str(error)}

    sentence_limit = _coerce_int(config.get("summary_sentences"), default=3, minimum=1, maximum=10)
    char_limit = _coerce_int(config.get("summary_chars"), default=500, minimum=80, maximum=4000)

    try:
        summary = _summarise(source_text, sentence_limit=sentence_limit, char_limit=char_limit)
    except ValueError as error:
        return {"error": str(error)}

    normalised = _normalise_text(source_text)
    model_id = request.get("model_id") or config.get("default_model_id") or "deterministic-fallback"
    use_case = (
        request.get("use_case_category")
        or config.get("default_use_case_category")
        or "summarization"
    )

    metadata = {
        "status_code": 200,
        "model_id": model_id,
        "model_parameters": request.get("model_parameters") or {},
        "mode": "deterministic-fallback",
        "use_case_category": use_case,
        "content_hash": hashlib.sha256(normalised.encode("utf-8")).hexdigest(),
        "source_characters": len(normalised),
        "summary_characters": len(summary),
        "summary_sentences": len(_SENTENCE_SPLIT_RE.split(summary)) if summary else 0,
        "tlp_level": request.get("tlp_level"),
        "reference_uploaded_file": request.get("reference_uploaded_file"),
    }

    return {
        "results": [
            {
                "types": mispattributes["output"],
                "values": [summary],
                "comment": f"Generic AI summary ({use_case}, model={model_id})",
            }
        ],
        "answer": {"summary": summary},
        "metadata": metadata,
        "tags": ["workflow:ai-generated", f"use-case:{use_case}"],
    }


def handler(q: str | bool = False) -> dict[str, Any] | bool:  # pylint: disable=invalid-name
    if q is False:
        return False
    return dict_handler(json.loads(q))


def introspection() -> dict[str, list[str]]:
    return mispattributes


def version() -> dict[str, Any]:
    moduleinfo["config"] = moduleconfig
    return moduleinfo
