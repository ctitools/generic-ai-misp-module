"""LLM extraction results for the three hand-labelled gold reports (fixtures/gold/*.iocs.json).

Each gold source becomes a synthetic event holding only its report, so the report text is the
only source of indicators (an event's existing attributes would be counted as output). Writes
<results-dir>/gold/<name>.llm.json next to the classic baseline files; benchmarks.compare then
renders the gold view.

    .venv/bin/python -m benchmarks.gold --results-dir benchmarks/results-v4
"""

import argparse
import json
import sys
from pathlib import Path

from benchmarks.run_llm import run_one

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = REPO_ROOT / "fixtures" / "gold"


def gold_events(gold_dir: Path = GOLD_DIR) -> dict[str, dict]:
    """name -> run_one() entry: report-only MISP fixture event, or the orkl sample as text."""
    entries = {}
    for gold_file in sorted(gold_dir.glob("*.iocs.json")):
        name = gold_file.name.removesuffix(".iocs.json")
        fixture = REPO_ROOT / "fixtures" / "output" / f"{name}.json"
        if fixture.exists():
            event = json.loads(fixture.read_text(encoding="utf-8"))["Event"]
            reports = [r for r in event.get("EventReport", []) if not r.get("deleted")]
            entries[name] = {"Event": {"info": event["info"], "EventReport": reports}}
        else:
            text = (REPO_ROOT / "tests" / "fixtures" / f"{name}.txt").read_text(encoding="utf-8")
            entries[name] = {"id": name, "title": name, "plain_text": text}
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results-dir", type=Path, default=Path("benchmarks/results"))
    args = parser.parse_args(argv)
    out = args.results_dir / "gold"
    out.mkdir(parents=True, exist_ok=True)
    for name, entry in gold_events().items():
        result = run_one(entry)
        (out / f"{name}.llm.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        status = result.get("error") or f"{len(result['indicators'])} indicators"
        print(f"{name}: {status} ({result['seconds']}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
