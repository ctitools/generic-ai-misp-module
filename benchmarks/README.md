# Benchmarks: LLM IoC extraction vs. a classical regex extractor

Goal: measure `genai/extract.py` (the module's LLM extraction use-case) against a classical
regex extractor on 100 random CTI reports from [orkl.eu](https://orkl.eu).

## Data flow

```
orkl.eu API (read-only GET, no auth)
   │  python -m benchmarks.orkl --n 100 --seed 42
   ▼
benchmarks/data/orkl/<id>.json      raw orkl entry (title, plain_text, references, ...)
benchmarks/data/orkl/sample.json    the draw: seed, n, filters, library size, ids
   │                                   │
   │  python -m genai.classic          │  python -m benchmarks.run_llm
   ▼                                   ▼
benchmarks/results/<id>.classic.json   benchmarks/results/<id>.llm.json
   │                                   │
   └──────── python -m benchmarks.compare ─────────┐
                                                   ▼
                          docs/BENCHMARKS_extraction.md + benchmarks/results/extraction.csv
```

## Commands

```bash
V=.venv/bin
$V/python -m benchmarks.orkl --n 100 --seed 42        # 1. sample 100 English reports
$V/python -m genai.classic benchmarks/data/orkl/*.json -o benchmarks/results   # 2. classical extractor
$V/python -m benchmarks.run_llm                       # 3. LLM extraction (needs OPENAI_* in .env)
$V/python -m benchmarks.compare                       # 4. metrics -> docs + csv
$V/pytest -q tests/test_orkl_unit.py                  # verification of step 1 (offline, fake API)
```

`benchmarks.orkl` options: `--n --seed --min-chars 2000 --max-chars 40000 --language en --data-dir`.
It draws offsets in `[0, library_entries)` with `random.Random(seed)` (no replacement), fetches one
entry per offset with `order_by=created_at&order=asc` (stable offsets), keeps an entry only if the
language matches (case-insensitive; orkl returns `"EN"`) and the `plain_text` length is within bounds, and redraws until `n` are kept.
If `sample.json` already exists with the same parameters the finished draw is reused without any
network call (an interrupted draw is redone from scratch; the seed makes it the same draw).
Progress (kept/skipped, entries/s) goes to stderr and `logs/benchmark-orkl.log`.

## Artifacts and file contracts

| Path | Contract |
|---|---|
| `benchmarks/data/orkl/<id>.json` | the raw orkl `data` object of one library entry |
| `benchmarks/data/orkl/sample.json` | `{"seed", "n", "min_chars", "max_chars", "language", "library_entries", "ids": [...]}` |
| `benchmarks/results/<id>.classic.json` | `{"tool": "iocextract 1.16.1", "indicators": [[type, value], ...]}` |
| `benchmarks/results/<id>.llm.json` | `{"model": {...}, "prompt": {...}, "indicators": [[type, value], ...], "rejected": [...], "seconds": float}` |
| `benchmarks/results/extraction.csv` | per-report metrics (committed) |
| `docs/BENCHMARKS_extraction.md` | the written-up comparison (committed) |

`benchmarks/data/` and `benchmarks/results/*.json` are gitignored (downloaded / regenerable);
the csv and the docs are committed. orkl.eu exposes no IoC field, so there is no ground truth
from orkl: the comparison is between the two extractors, judged against the report text.
