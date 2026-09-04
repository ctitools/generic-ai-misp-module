"""Read-only orkl.eu client and reproducible report sampler (stdlib only).

Data flow: orkl.eu API -> benchmarks/data/orkl/<id>.json (raw entry) + sample.json (the draw).
"""

import argparse
import json
import logging
import random
import time
import urllib.request
from pathlib import Path

BASE = "https://orkl.eu/api/v1"
DATA_DIR = Path(__file__).resolve().parent / "data" / "orkl"
LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "benchmark-orkl.log"
UA = "generic-ai-misp-module benchmarks (https://github.com/CIRCL/generic-ai-misp-module)"
log = logging.getLogger("benchmark.orkl")


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec: fixed https base URL
        return json.load(resp)


def info() -> dict:
    return _get(f"{BASE}/library/info")["data"]


def entry(uuid: str) -> dict:
    return _get(f"{BASE}/library/entry/{uuid}")["data"]


def entries(limit: int, offset: int) -> list[dict]:
    url = f"{BASE}/library/entries?limit={limit}&offset={offset}&order_by=created_at&order=asc"
    return _get(url)["data"]


def sample(  # filters are user knobs; pylint: disable=too-many-arguments,too-many-locals
    n: int = 100,
    seed: int = 42,
    *,
    min_chars: int = 2000,
    max_chars: int = 40000,
    language: str = "en",
    data_dir: Path = DATA_DIR,
) -> list[str]:
    """Draw n random orkl entries matching the filters, save them to data_dir, return the ids.

    A finished draw (sample.json with the same parameters) is reused without any network call.
    """
    data_dir = Path(data_dir)
    meta_file = data_dir / "sample.json"
    meta = {
        "seed": seed,
        "n": n,
        "min_chars": min_chars,
        "max_chars": max_chars,
        "language": language,
    }
    if meta_file.exists():
        old = json.loads(meta_file.read_text())
        if {k: old.get(k) for k in meta} == meta:
            log.info("reusing %s (%d ids)", meta_file, len(old["ids"]))
            return old["ids"]
    data_dir.mkdir(parents=True, exist_ok=True)
    meta["library_entries"] = total = info()["library_entries"]
    ids, skipped, start = [], 0, time.monotonic()
    for offset in random.Random(seed).sample(range(total), total):
        if len(ids) >= n:
            break
        item = (entries(1, offset) or [{}])[0]
        text = item.get("plain_text") or ""
        lang = (item.get("language") or "").lower()  # orkl returns "EN"
        if lang == language.lower() and min_chars <= len(text) <= max_chars:
            (data_dir / f"{item['id']}.json").write_text(json.dumps(item, indent=1))
            ids.append(item["id"])
        else:
            skipped += 1
        if (len(ids) + skipped) % 10 == 0:
            rate = (len(ids) + skipped) / (time.monotonic() - start)
            log.info("kept %d/%d skipped %d (%.2f entries/s)", len(ids), n, skipped, rate)
    if len(ids) < n:
        raise RuntimeError(f"only {len(ids)} of {n} entries matched the filters")
    meta_file.write_text(json.dumps({**meta, "ids": ids}, indent=1))
    rate = (len(ids) + skipped) / (time.monotonic() - start)
    log.info("done: kept %d skipped %d (%.2f entries/s) -> %s", len(ids), skipped, rate, meta_file)
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-chars", type=int, default=2000)
    parser.add_argument("--max-chars", type=int, default=40000)
    parser.add_argument("--language", default="en")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    LOG_FILE.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)],
    )
    print(json.dumps(sample(**vars(args))))


if __name__ == "__main__":
    main()
