"""Summarization benchmark report: gate pass rate, length, indicator coverage, determinism.

    python -m benchmarks.compare_summary [--results-dir R] [--second-dir R2] [--data-dir D]
                                         [--out docs/BENCHMARKS_summary.md] [--csv ...]

Reads <id>.summary.json from --results-dir (and, for determinism, the same ids from a second
pass in --second-dir), plus <id>.classic.json for the indicator coverage. No reference
summaries exist, so this measures what can be measured without one (docs/BENCHMARKS.md).
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import statistics
from collections import Counter
from datetime import date
from pathlib import Path

from benchmarks.compare import pie, table, xychart
from benchmarks.metrics import normalise_value, values
from genai import prompts

CSV_COLUMNS = ["id", "title", "status", "words", "coverage", "seconds", "identical", "similarity"]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def gate_problems(error: str) -> list[str]:
    """The structural-check reasons in a module error, reduced to their kind."""
    if "structural check" not in error:
        return [error[:40]]
    kinds = []
    for problem in error.split(": ", 1)[1].split("; "):
        kinds.append(re.sub(r"'.*'|\d+|: .*", "", problem).strip())
    return kinds


def coverage(summary: str, classic: list) -> float | None:
    """Share of the regex baseline's hashes, IPs and URLs that the summary mentions."""
    reference = values(p for p in classic if p[0] in ("md5", "sha1", "sha256", "ip-dst", "url"))
    if not reference:
        return None
    text = normalise_value(summary)
    return sum(v in text for v in reference) / len(reference)


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.split(), b.split()).ratio()


def event_indicators(entry: dict) -> list:
    """(type, value) of a MISP event's attributes, incl. objects: the coverage reference for
    the event kind (there is no regex baseline for an event)."""
    event = entry.get("Event", {})
    attributes = list(event.get("Attribute", []))
    for obj in event.get("Object", []):
        attributes.extend(obj.get("Attribute", []))
    return [[a["type"], str(a["value"])] for a in attributes]


def load(data_dir: Path, results_dir: Path, second_dir: Path | None, ext: str) -> list[dict]:
    rows = []
    for path in sorted(results_dir.glob(f"*.{ext}.json")):
        uid = path.name.removesuffix(f".{ext}.json")
        entry_path, classic_path = data_dir / f"{uid}.json", results_dir / f"{uid}.classic.json"
        entry = _read(entry_path) if entry_path.exists() else {}
        row = {"id": uid, "result": _read(path), "classic": []}
        row["title"] = entry.get("title") or entry.get("Event", {}).get("info") or ""
        if "Event" in entry:
            row["classic"] = event_indicators(entry)
        elif classic_path.exists():
            row["classic"] = _read(classic_path)["indicators"]
        second = second_dir / path.name if second_dir else None
        row["second"] = _read(second) if second and second.exists() else None
        rows.append(row)
    return rows


def per_report(row: dict) -> list:
    result, second = row["result"], row["second"]
    if "error" in result:
        return [row["id"][:8], row["title"][:40], "error", 0, "", result["seconds"], "", ""]
    identical = same = ""
    if second and "summary" in second:
        identical = result["summary"] == second["summary"]
        same = similarity(result["summary"], second["summary"])
    cov = coverage(result["summary"], row["classic"])
    return [
        row["id"][:8],
        row["title"][:40],
        "ok",
        result["words"],
        "" if cov is None else cov,
        result["seconds"],
        identical,
        same,
    ]


def report(  # one table per metric family; pylint: disable=too-many-locals
    rows: list[dict], prompt: prompts.Prompt, kind: str = "report"
) -> str:
    run = "GENERIC_AI_REQUEST_TIMEOUT=900 python -m benchmarks.run_llm --use-case summarization"
    ok = [r for r in rows if "summary" in r["result"]]
    errors = Counter(
        k for r in rows if "error" in r["result"] for k in gate_problems(r["result"]["error"])
    )
    words = [r["result"]["words"] for r in ok]
    secs = [r["result"]["seconds"] for r in rows]
    covs = [
        c for c in (coverage(r["result"]["summary"], r["classic"]) for r in ok) if c is not None
    ]
    paired = [r for r in ok if r["second"] and "summary" in r["second"]]
    identical = sum(r["result"]["summary"] == r["second"]["summary"] for r in paired)
    sims = [similarity(r["result"]["summary"], r["second"]["summary"]) for r in paired]
    first = ok[0]["result"] if ok else {}
    model = first.get("model", {})
    bins = [sum(1 for w in words if lo <= w < lo + 25) for lo in range(0, 250, 25)]
    heading_hits = {h: sum(h in r["result"]["summary"] for r in ok) for h in prompt.headings}
    lines = [
        f"# Summarization benchmark: summary_kind={kind}",
        "",
        f"Date: {date.today()}. Reports: {len(rows)}, summaries: {len(ok)}, "
        f"errors: {len(rows) - len(ok)}.",
        "",
        f"- Model: `{model.get('name')}` digest `{model.get('digest')}` "
        f"server `{model.get('server')}`",
        f"- Prompt: `{prompt.value}` v{prompt.version} sha256 `{prompt.sha256}`; headings "
        f"{list(prompt.headings)}; max words {prompt.max_words}",
        "",
        "**Method.** No reference summaries exist, so this measures the module's own gate "
        "(headings, length, no indicator that is not in the input), length, how much of the "
        + ("event's own hashes/IPs/URLs" if kind == "event" else "regex baseline's hashes/IPs/URLs")
        + " the summary mentions (coverage, informational: a good summary need not list every "
        "hash), timing, and determinism between two passes with the same seed (byte-identical, "
        "and word-level similarity otherwise).",
        "",
        "## Gate",
        "",
        table(
            ["outcome / gate problem (one error can carry several)", "count"],
            [["summary produced", len(ok)], *sorted(errors.items())],
        ),
        pie("Gate outcome", {"ok": len(ok), **errors}),
        "## Length (words, headings excluded by the gate; limit " + str(prompt.max_words) + ")",
        "",
        table(
            ["min", "median", "p90", "max"],
            [
                [
                    min(words),
                    statistics.median(words),
                    sorted(words)[int(0.9 * len(words))],
                    max(words),
                ]
            ]
            if words
            else [[0, 0, 0, 0]],
        ),
        xychart("Words per summary", [str(lo) for lo in range(0, 250, 25)], {"summaries": bins}),
        "## Headings present",
        "",
        table(["heading", "summaries"], [[h, n] for h, n in heading_hits.items()]),
        "## Indicator coverage (share of the reference md5/sha1/sha256/ip-dst/url mentioned)",
        "",
        table(
            ["reports with indicators", "mean coverage", "median"],
            [
                [
                    len(covs),
                    statistics.fmean(covs) if covs else 0.0,
                    statistics.median(covs) if covs else 0.0,
                ]
            ],
        ),
        "## Timing",
        "",
        table(
            ["median s", "p90 s", "max s", "total min"],
            [
                [
                    statistics.median(secs),
                    sorted(secs)[int(0.9 * len(secs))],
                    max(secs),
                    sum(secs) / 60,
                ]
            ]
            if secs
            else [[0, 0, 0, 0]],
        ),
        "## Determinism (second pass, same seed and temperature 0)",
        "",
        table(
            ["paired", "byte-identical", "mean word similarity", "min similarity"],
            [
                [
                    len(paired),
                    identical,
                    statistics.fmean(sims) if sims else 0.0,
                    min(sims) if sims else 0.0,
                ]
            ],
        ),
        "## Per report",
        "",
        table(CSV_COLUMNS, [per_report(r) for r in rows]),
        "## Reproduce",
        "",
        "```bash",
        f"{run} --kind {kind}",
        f"{run} --kind {kind} --results-dir benchmarks/results-pass2",
        f"python -m benchmarks.compare_summary --kind {kind} --second-dir benchmarks/results-pass2",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=Path("benchmarks/data/orkl"))
    ap.add_argument("--results-dir", type=Path, default=Path("benchmarks/results"))
    ap.add_argument("--second-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("docs/BENCHMARKS_summary.md"))
    ap.add_argument("--csv", type=Path, default=Path("benchmarks/results/summary.csv"))
    ap.add_argument("--kind", choices=("report", "event"), default="report")
    args = ap.parse_args(argv)
    ext = "summary-event" if args.kind == "event" else "summary"
    rows = load(args.data_dir, args.results_dir, args.second_dir, ext)
    used = next((r["result"]["prompt"].get("uuid") for r in rows if "summary" in r["result"]), "")
    prompt = prompts.resolve_prompt(f"summary-{args.kind}", used)  # the cluster the run used
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(rows, prompt, args.kind), encoding="utf-8")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([CSV_COLUMNS, *(per_report(r) for r in rows)])
    print(f"wrote {args.out} and {args.csv} ({len(rows)} reports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
