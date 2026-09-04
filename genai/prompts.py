"""Prompt clusters (the generic-ai-prompts MISP galaxy) and the pinned AI taxonomy tags."""

import hashlib
import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from pymisp import AbstractMISP

from genai.llm import DEFAULT_PARAMS, REPO_ROOT

CLUSTERS_FILE = REPO_ROOT / "clusters" / "generic-ai-prompts.json"
PINNED_TAGS_FILE = Path(__file__).with_name("ai_taxonomy_pinned.json")
USE_CASES = ("cti-info-extraction", "summary-report", "summary-event")

# Every LLM-suggested element gets exactly these two tags (docs/USE-CASES.md, "Rule").
AI_TAGS = (
    'ai-computer-assisted:assistance-level="ai-generated"',
    'ai-computer-assisted:review-level="unreviewed"',
)


@dataclass(frozen=True)
class Prompt:
    value: str
    uuid: str
    use_case: str
    text: str
    params: dict[str, Any] = field(default_factory=dict)
    version: int = 0
    sha256: str = ""
    headings: tuple[str, ...] = ()
    max_words: int = 0

    def render(self, **fields: str) -> str:
        text = self.text
        for key, value in fields.items():
            text = text.replace("{{" + key + "}}", value)
        return text

    def describe(self) -> dict[str, Any]:
        return {
            "cluster": self.value,
            "uuid": self.uuid,
            "version": self.version,
            "sha256": self.sha256,
        }


@cache
def load_clusters() -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(CLUSTERS_FILE.read_text(encoding="utf-8"))["values"])


def _from_cluster(cluster: dict[str, Any]) -> Prompt:
    meta = cluster["meta"]
    return Prompt(
        value=cluster["value"],
        uuid=cluster["uuid"],
        use_case=meta["use_case"],
        text=meta["prompt"],
        params={**DEFAULT_PARAMS, **meta.get("model_parameters", {})},
        version=int(meta.get("version", 0)),
        sha256=meta.get("prompt_sha256") or hashlib.sha256(meta["prompt"].encode()).hexdigest(),
        headings=tuple(meta.get("headings", ())),
        max_words=int(meta.get("max_words", 0)),
    )


def resolve_prompt(use_case: str, setting: str | None = None) -> Prompt:
    """Cluster uuid or value -> that cluster; other text -> inline prompt; empty -> default."""
    if use_case not in USE_CASES:
        raise ValueError(f"unknown prompt use-case {use_case!r}, expected one of {USE_CASES}")
    clusters = [c for c in load_clusters() if c["meta"]["use_case"] == use_case]
    if setting:
        for cluster in clusters:
            if setting in (cluster["uuid"], cluster["value"]):
                return _from_cluster(cluster)
        default = _from_cluster(clusters[0])
        return Prompt(
            value="inline",
            uuid="",
            use_case=use_case,
            text=setting,
            params=default.params,
            sha256=hashlib.sha256(setting.encode()).hexdigest(),
            headings=default.headings,
            max_words=default.max_words,
        )
    return _from_cluster(clusters[0])


@cache
def pinned_tags() -> tuple[str, ...]:
    return tuple(json.loads(PINNED_TAGS_FILE.read_text(encoding="utf-8"))["tags"])


def tag_ai_generated(element: AbstractMISP) -> None:
    """Attach the two AI tags (verbatim from the pinned list) to an attribute, object or event."""
    for name in AI_TAGS:
        if name not in pinned_tags():
            raise ValueError(f"{name} is not in the pinned ai-computer-assisted tag list")
        element.add_tag(name)
