"""Draw a reproducible sample of real events from the MISP instance in .env (read-only).

    python -m benchmarks.misp_sample --n 100 --seed 42 [--min-attributes 5] [--max-attributes 300]

Writes benchmarks/data/misp/<uuid>.json (the event as MISP serves it, {"Event": {...}}) and
sample.json ({"seed", "n", "ids", ...}). Input for the event-kind summarization benchmark.
MISP_VERIFY_SSL=false accepts the dev instance's self-signed certificate (benchmark tooling and
tests only; the module never talks to MISP).
"""

import argparse
import json
import logging
import random
import sys
import time
import warnings
from pathlib import Path

from pymisp import PyMISP

from genai import llm

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "benchmarks" / "data" / "misp"
LOG_FILE = REPO_ROOT / "logs" / "benchmark-misp-sample.log"
log = logging.getLogger("benchmark.misp_sample")


def client() -> PyMISP:
    env = llm.env()
    verify = env.get("MISP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
    if not verify:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    return PyMISP(env["MISP_BASE_URL"], env["MISP_API_KEY"], ssl=verify)


def sample(  # sampler knobs; pylint: disable=too-many-arguments,too-many-locals
    misp: PyMISP,
    n: int,
    seed: int,
    *,
    min_attributes: int,
    max_attributes: int,
    data_dir: Path = DATA_DIR,
) -> list[str]:
    """Seeded draw of n events whose attribute count is within bounds; resumable."""
    params = {
        "seed": seed,
        "n": n,
        "min_attributes": min_attributes,
        "max_attributes": max_attributes,
    }
    sample_file = data_dir / "sample.json"
    if sample_file.exists():
        previous = json.loads(sample_file.read_text(encoding="utf-8"))
        if all(previous.get(k) == v for k, v in params.items()):
            log.info("reusing %s (%d ids)", sample_file, len(previous["ids"]))
            return previous["ids"]
    index = misp.search_index(pythonify=False)
    eligible = sorted(
        e["uuid"]
        for e in index
        if min_attributes <= int(e.get("attribute_count", 0)) <= max_attributes
    )
    if len(eligible) < n:
        raise SystemExit(f"only {len(eligible)} eligible events on the instance, asked for {n}")
    ids = random.Random(seed).sample(eligible, n)
    data_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    for done, uid in enumerate(ids, 1):
        event = misp.get_event(uid, pythonify=False)
        (data_dir / f"{uid}.json").write_text(json.dumps(event, indent=2), encoding="utf-8")
        log.info("fetched %d/%d (%.2f events/s)", done, n, done / (time.perf_counter() - started))
    sample_file.write_text(
        json.dumps(
            params | {"library_events": len(index), "eligible": len(eligible), "ids": ids}, indent=2
        ),
        encoding="utf-8",
    )
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-attributes", type=int, default=5)
    parser.add_argument("--max-attributes", type=int, default=300)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args(argv)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
        force=True,
    )
    ids = sample(
        client(),
        args.n,
        args.seed,
        min_attributes=args.min_attributes,
        max_attributes=args.max_attributes,
        data_dir=args.data_dir,
    )
    log.info("done: %d events -> %s", len(ids), args.data_dir / "sample.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
