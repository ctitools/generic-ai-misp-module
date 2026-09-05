"""Live LLM tests (skip when the endpoint in .env is unreachable). See docs/TESTING.md.

Order matters: the determinism test runs first; if the endpoint does not honour seed and
temperature, nothing else here is meaningful.
"""

# pylint: disable=redefined-outer-name,unused-argument

import json
import re

import pytest
from conftest import PROJECT_ROOT, live_gate, load_fixture

from expansion import generic_ai
from genai import extract, llm, prompts, summarize
from genai.refang import refang

GOLD_DIR = PROJECT_ROOT / "fixtures" / "gold"
GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden"
ORKL = PROJECT_ROOT / "tests" / "fixtures" / "orkl-sample.txt"


def test_llm_is_deterministic(llm_settings) -> None:
    messages = [
        {"role": "user", "content": "Name three indicators of compromise types, one per line."}
    ]
    answers = {llm.llm_chat(messages, {"max_tokens": 80}, llm_settings) for _ in range(3)}
    assert len(answers) == 1, answers


def test_model_info_is_pinned(llm_settings) -> None:
    info = llm.model_info(llm_settings)
    assert info["name"] == llm_settings.model
    if "digest" in info:
        assert re.fullmatch(r"[0-9a-f]{12}", info["digest"])


def _precision(event, report, gold, llm_settings):
    prompt = prompts.resolve_prompt("cti-info-extraction")
    metadata = extract.extract_iocs(event, report, llm_settings, prompt)
    got = {(a.type, a.value.lower()) for a in event.attributes} | {
        (a.type, a.value.lower())  # values are stored refanged
        for o in event.objects
        for a in o.attributes
        if getattr(o, "comment", "")
    }
    gold_set = {(t, refang(v).lower()) for t, v in gold["indicators"]}
    gold_values = {v for _, v in gold_set}
    true_positive = {g for g in got if g in gold_set or g[1] in gold_values}
    precision = len(true_positive) / len(got) if got else 1.0
    recall = len({v for _, v in true_positive}) / len(gold_values) if gold_values else 1.0
    print(
        f"\n  extracted={len(got)} gold={len(gold_set)} "
        f"precision={precision:.2f} recall={recall:.2f} "
        f"rejected={[(r['value'], r['reason']) for r in metadata['rejected']][:8]}"
    )
    print("  false positives:", sorted(got - true_positive)[:10])
    return precision, recall


@pytest.mark.parametrize(
    "uuid", ["10a94632-a0a1-4062-a3a5-95fe321ae045", "59ed4725-5f2a-4844-8dc4-e6926dbcb5ce"]
)
def test_extraction_precision_gate(llm_settings, uuid) -> None:
    raw = load_fixture(uuid)
    for key in ("Attribute", "Object"):  # start from the report alone, gold is report-derived
        raw["Event"][key] = []
    event = generic_ai.validate_event(raw["Event"])
    gold = json.loads((GOLD_DIR / f"{uuid}.iocs.json").read_text())
    precision, _recall = _precision(event, generic_ai.get_event_report(event), gold, llm_settings)
    assert precision >= 0.95


def test_extraction_recall_report(llm_settings) -> None:
    """Informational: how much of the Emotet sample's hashes the high-confidence policy keeps."""
    event = generic_ai.validate_event(
        {"info": "orkl sample", "EventReport": [{"name": "orkl", "content": ORKL.read_text()}]}
    )
    gold = json.loads((GOLD_DIR / "orkl-sample.iocs.json").read_text())
    precision, recall = _precision(event, generic_ai.get_event_report(event), gold, llm_settings)
    assert precision >= 0.95
    assert recall >= 0.0  # reported, not gated


def test_extraction_is_deterministic(llm_settings, dummy_event) -> None:
    results = []
    for _ in range(2):
        event = generic_ai.validate_event(dummy_event["Event"])
        generic_ai.process_event(event, settings={"use_case": "extraction"})
        results.append(sorted((a.type, a.value) for a in event.attributes))
    assert results[0] == results[1]


@pytest.mark.parametrize("kind", summarize.KINDS)
def test_summary_structural_gate_and_golden(llm_settings, dummy_event, kind, request) -> None:
    event = generic_ai.validate_event(dummy_event["Event"])
    metadata: dict = {}
    generic_ai.process_event(
        event, settings={"use_case": "summarization", "summary_kind": kind}, metadata=metadata
    )
    summary = event.event_reports[-1].content
    assert set(prompts.AI_TAGS) <= {t.name for t in event.tags}
    assert metadata["kind"] == kind and metadata["words"] <= 200 + 30  # headings are not counted
    # L1/L2 golden comparison, only when model digest + server + prompt hash match the header
    info = metadata["model"]
    header = {
        "model": info.get("name"),
        "digest": info.get("digest"),
        "server": info.get("server"),
        "prompt_sha256": metadata["prompt"]["sha256"],
    }
    golden = GOLDEN_DIR / f"summary-{kind}.md"
    if request.config.getoption("--update-goldens"):
        golden.write_text(json.dumps(header) + "\n---\n" + summary + "\n", encoding="utf-8")
        print(f"\n  recorded {golden}")
        return
    if not golden.exists():
        pytest.skip(f"no golden yet: run with --update-goldens to record {golden.name}")
    recorded_header, _, recorded = golden.read_text(encoding="utf-8").partition("\n---\n")
    if json.loads(recorded_header) != header:
        live_gate(
            request.config,
            f"golden-{kind}",
            f"golden header {recorded_header} does not match live {header}; re-record and review",
        )
    same_l2 = " ".join(recorded.split()).rstrip(".") == " ".join(summary.split()).rstrip(".")
    if not same_l2:  # documented: L2 drift is a warning, not a failure
        print(
            f"\n  WARNING L2 drift for {golden.name}; re-record with --update-goldens after review"
        )
    if request.config.getoption("-v"):
        print(summary)
