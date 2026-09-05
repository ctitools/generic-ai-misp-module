"""Tag-suggestion benchmark: how well does misp-tag-suggest recover the tags analysts set?

For every sampled live event (benchmarks/misp_sample.py) the existing tags are the gold set;
the event is sent without them, and the suggested tags are scored against the gold set
(precision@k, recall@k, hit@1). Results: benchmarks/results-suggest/<timestamp>.json;
progress and rows/sec in logs/benchmark-suggest.log.

    .venv/bin/python -m benchmarks.run_suggest --n 20 --k 5
"""

import argparse
import copy
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks import misp_sample
from expansion import generic_ai
from genai import suggest

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "benchmarks" / "results-suggest"
LOG_FILE = REPO_ROOT / "logs" / "benchmark-suggest.log"
log = logging.getLogger("benchmark.suggest")


def gold_tags(event: dict[str, Any]) -> set[str]:
    """Namespaced tags on the event (taxonomy / galaxy); local flags like 'tlp:white' count too."""
    return {t["name"] for t in event.get("Tag", []) if ":" in t.get("name", "")}


def score(gold: set[str], suggested: list[str]) -> dict[str, float]:
    hits = [t for t in suggested if t in gold]
    return {
        "precision": len(hits) / len(suggested) if suggested else 0.0,
        "recall": len(hits) / len(gold) if gold else 0.0,
        "hit_at_1": float(bool(suggested) and suggested[0] in gold),
    }


def run_one(raw: dict[str, Any], settings: suggest.SuggestSettings, k: int) -> dict[str, Any]:
    event_dict = copy.deepcopy(raw.get("Event", raw))
    gold = gold_tags(event_dict)
    event_dict["Tag"] = []  # the service ignores existing tags, but do not even send them
    event = generic_ai.validate_event(event_dict)
    started = time.perf_counter()
    result = suggest.suggest_tags(event, settings, limit=k)
    suggested = [s["tag"] for s in result["added"]]
    return {
        "uuid": event.uuid,
        "gold": sorted(gold),
        "suggested": suggested,
        "abstained": result["abstained"],
        "model_version": result.get("model_version", ""),
        "seconds": round(time.perf_counter() - started, 3),
        **score(gold, suggested),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    scored = [r for r in rows if r["gold"]]
    keys = ("precision", "recall", "hit_at_1")
    out = {k: sum(r[k] for r in scored) / len(scored) if scored else 0.0 for k in keys}
    out["abstained"] = sum(r["abstained"] for r in rows) / len(rows) if rows else 0.0
    out["events"] = len(rows)
    out["events_with_gold"] = len(scored)
    return out


def run(
    ids: list[str], data_dir: Path, settings: suggest.SuggestSettings, k: int
) -> dict[str, Any]:
    rows, failures = [], []
    started = time.perf_counter()
    for done, uid in enumerate(ids, 1):
        raw = json.loads((data_dir / f"{uid}.json").read_text(encoding="utf-8"))
        try:
            rows.append(run_one(raw, settings, k))
        except (suggest.SuggestError, ValueError) as error:
            failures.append({"uuid": uid, "error": str(error)})
            log.warning("%s failed: %s", uid, error)
        rate = done / (time.perf_counter() - started)
        log.info(
            "%d/%d ok=%d failed=%d (%.2f events/s)", done, len(ids), len(rows), len(failures), rate
        )
    return {
        "k": k,
        "service": settings.base_url,
        "model_version": rows[0]["model_version"] if rows else "",
        "summary": aggregate(rows),
        "failures": failures,
        "events": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--k", type=int, default=5, help="tags requested per event (1..10)")
    parser.add_argument("--data-dir", type=Path, default=misp_sample.DATA_DIR)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    misp_sample.setup_logging(LOG_FILE)
    settings = suggest.SuggestSettings.from_env()
    if not suggest.is_reachable(settings):
        raise SystemExit(f"misp-tag-suggest at {settings.base_url} is not reachable or not indexed")
    ids = misp_sample.sample(
        misp_sample.client(),
        args.n,
        args.seed,
        min_attributes=1,
        max_attributes=300,
        data_dir=args.data_dir,
    )
    result = run(ids, args.data_dir, settings, args.k)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    out = args.results_dir / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    log.info("summary %s -> %s", result["summary"], out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
