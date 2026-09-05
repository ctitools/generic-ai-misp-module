"""Run the module's LLM use-cases over the sampled orkl reports.

    .venv/bin/python -m benchmarks.run_llm [--use-case extraction|summarization] [--ids a,b]
                                           [--data-dir D] [--results-dir R] [--force]

Options: --log-file (default logs/benchmark-llm.log), --prompt (cluster uuid or value).

Reads benchmarks/data/orkl/sample.json + <id>.json, calls expansion.generic_ai.dict_handler
(the module as deployed) and writes one result per report: <id>.llm.json for extraction,
<id>.summary.json for summarization (kind "report"). Resumable. A second summarization pass
into another --results-dir gives the determinism measurement for benchmarks.compare_summary.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from expansion import generic_ai
from genai import llm

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "benchmarks" / "data" / "orkl"
RESULTS_DIR = REPO_ROOT / "benchmarks" / "results"
LOG_FILE = REPO_ROOT / "logs" / "benchmark-llm.log"
log = logging.getLogger("benchmark-llm")


def indicators(event: dict) -> list[list[str]]:
    """Sorted (type, value) pairs of all event and object attributes."""
    attributes = list(event.get("Attribute", []))
    for obj in event.get("Object", []):
        attributes.extend(obj.get("Attribute", []))
    return sorted([a["type"], str(a["value"])] for a in attributes)


SUFFIX = {"extraction": "llm", "summarization": "summary"}


def run_one(entry: dict, prompt: str = "", use_case: str = "extraction") -> dict:
    """One report through the real module entry point; never raises on LLM/validation errors."""
    title = entry.get("title") or entry["id"]
    report = {"name": title, "content": entry.get("plain_text", "")}
    event = {"info": title, "EventReport": [report]}
    request = {"module": "generic_ai", "event": {"Event": event}, "use_case": use_case}
    if prompt:  # prompt cluster uuid or value
        request["prompt_extraction" if use_case == "extraction" else "prompt_summary_report"] = (
            prompt
        )
    start = time.perf_counter()
    response = generic_ai.dict_handler(request)
    seconds = round(time.perf_counter() - start, 3)
    if "error" in response:
        return {"error": response["error"], "seconds": seconds}
    meta = response["metadata"]
    result = {"model": meta["model"], "prompt": meta["prompt"], "seconds": seconds}
    processed = response["results"]["Event"]["Event"]
    if use_case == "extraction":
        return result | {"indicators": indicators(processed), "rejected": meta["rejected"]}
    return result | {"summary": processed["EventReport"][-1]["content"], "words": meta["words"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", help="comma-separated orkl ids (default: sample.json)")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--force", action="store_true", help="re-run ids with a result file")
    parser.add_argument("--log-file", type=Path, default=LOG_FILE)
    parser.add_argument("--prompt", default="", help="prompt cluster uuid or value (default v1)")
    parser.add_argument("--use-case", choices=list(SUFFIX), default="extraction")
    args = parser.parse_args(argv)

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.log_file), logging.StreamHandler(sys.stderr)],
        force=True,
    )
    settings = llm.LLMSettings.from_env()
    if not settings.model or not llm.is_reachable(settings):
        log.error("LLM endpoint %s not reachable or OPENAI_MODEL unset", settings.base_url)
        return 2

    if args.ids:
        ids = args.ids.split(",")
    else:
        ids = json.loads((args.data_dir / "sample.json").read_text(encoding="utf-8"))["ids"]
    args.results_dir.mkdir(parents=True, exist_ok=True)
    suffix = SUFFIX[args.use_case]
    todo = [i for i in ids if args.force or not (args.results_dir / f"{i}.{suffix}.json").exists()]
    log.info("%s model=%s reports=%d todo=%d", args.use_case, settings.model, len(ids), len(todo))
    started, fail = time.perf_counter(), 0
    for done, uid in enumerate(todo, 1):
        entry = json.loads((args.data_dir / f"{uid}.json").read_text(encoding="utf-8"))
        result = run_one(entry, args.prompt, args.use_case)
        fail += "error" in result
        (args.results_dir / f"{uid}.{suffix}.json").write_text(json.dumps(result, indent=2))
        _progress(uid, result, (done, fail, len(todo)), time.perf_counter() - started)
    return 0


def _progress(uid: str, result: dict, counts: tuple[int, int, int], elapsed: float) -> None:
    done, fail, total = counts
    rate = done / elapsed if elapsed else 0.0
    eta = (total - done) / rate if rate else 0.0
    if "error" in result:
        outcome = result["error"][:80]
    else:
        outcome = result["words"] if "summary" in result else len(result["indicators"])
    log.info(
        "%s done=%d/%d ok=%d fail=%d elapsed=%.0fs %.3f reports/s eta=%.0fs result=%s",
        uid,
        done,
        total,
        done - fail,
        fail,
        elapsed,
        rate,
        eta,
        outcome,
    )


if __name__ == "__main__":
    sys.exit(main())
