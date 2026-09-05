"""UC3 — Tag suggestion: ask the misp-tag-suggest service for taxonomy tags, add them, AI-tag.

The service (https://github.com/ctitools/misp-tag-suggest) is a separate process because it
needs torch/faiss/sentence-transformers; this repo allows only pymisp. Its contract:

    POST /suggest {"event": {"Event": {...}}, "limit": 1..10}
      -> {"suggestions": [{"tag", "score"}], "abstained", "model_version",
          "dataset_manifest_sha256"}
    GET  /health -> {"artifacts_ready": bool, ...}

URL and key come from .env only (MISP_TAG_SUGGEST_URL, MISP_TAG_SUGGEST_API_KEY), never from a
request. Abstention is not an error: nothing is added and the metadata says so.
"""

import json
from dataclasses import dataclass
from typing import Any

from pymisp import MISPEvent

from genai import llm, prompts

DEFAULT_TIMEOUT = 60


class SuggestError(RuntimeError):
    pass


@dataclass(frozen=True)
class SuggestSettings:
    base_url: str
    api_key: str = ""
    timeout: int = DEFAULT_TIMEOUT

    def __repr__(self) -> str:  # never leak the key into logs or test output
        key = "***" if self.api_key else ""
        return f"SuggestSettings(base_url={self.base_url!r}, api_key={key!r})"

    @classmethod
    def from_env(cls, timeout: int | None = None) -> "SuggestSettings":
        values = llm.env()
        url = values.get("MISP_TAG_SUGGEST_URL", "").rstrip("/")
        if not url:
            raise SuggestError("MISP_TAG_SUGGEST_URL is not set in .env (misp-tag-suggest service)")
        return cls(url, values.get("MISP_TAG_SUGGEST_API_KEY", ""), int(timeout or DEFAULT_TIMEOUT))


def _call(settings: SuggestSettings, path: str, payload: dict | None = None) -> Any:
    headers = {"X-Api-Key": settings.api_key} if settings.api_key else {}
    try:
        return llm.http_json(
            settings.base_url + path, payload, headers=headers, timeout=settings.timeout
        )
    except llm.LLMError as error:
        raise SuggestError(f"misp-tag-suggest: {error}") from error


def is_reachable(settings: SuggestSettings) -> bool:
    try:
        return bool(_call(settings, "/health").get("artifacts_ready"))
    except SuggestError, AttributeError:
        return False


def _suggestions(data: Any) -> list[tuple[str, float]]:
    if not isinstance(data, dict) or not isinstance(data.get("suggestions"), list):
        raise SuggestError("misp-tag-suggest answer had no suggestions list")
    out = []
    for item in data["suggestions"]:
        try:
            out.append((str(item["tag"]), float(item["score"])))
        except (KeyError, TypeError, ValueError) as error:
            raise SuggestError(
                f"misp-tag-suggest returned a malformed suggestion: {item!r}"
            ) from error
    return out


def suggest_tags(
    event: MISPEvent, settings: SuggestSettings, limit: int = 5, min_score: float = 0.0
) -> dict[str, Any]:
    """Add the suggested tags (score >= min_score, not already present) to the event; metadata."""
    payload = {"event": {"Event": json.loads(event.to_json())}, "limit": limit}
    data = _call(settings, "/suggest", payload)
    existing = {t.name for t in event.tags}
    added, skipped, below = [], [], []
    for tag, score in _suggestions(data):
        if score < min_score:
            below.append(tag)
        elif tag in existing:
            skipped.append(tag)
        else:
            event.add_tag(tag)
            added.append({"tag": tag, "score": score})
    if added:  # event-level content: the event carries the AI tags (USE-CASES.md)
        prompts.tag_ai_generated(event)
    return {
        "use_case": "tag_suggestion",
        "added": added,
        "skipped_existing": skipped,
        "below_min_score": below,
        "abstained": bool(data.get("abstained")),
        "model_version": str(data.get("model_version", "")),
        "dataset_manifest_sha256": str(data.get("dataset_manifest_sha256", "")),
    }
