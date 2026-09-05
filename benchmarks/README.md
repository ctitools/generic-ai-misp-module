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
GENERIC_AI_REQUEST_TIMEOUT=900 $V/python -m benchmarks.run_llm   # 3. LLM extraction (needs OPENAI_* in .env)
$V/python -m benchmarks.compare                       # 4. metrics -> docs + csv
GENERIC_AI_REQUEST_TIMEOUT=900 $V/python -m benchmarks.run_llm --use-case summarization   # 5. summaries (pass 1)
GENERIC_AI_REQUEST_TIMEOUT=900 $V/python -m benchmarks.run_llm --use-case summarization --results-dir benchmarks/results-pass2   # 6. pass 2 (determinism)
$V/python -m benchmarks.compare_summary --second-dir benchmarks/results-pass2   # 7. -> docs/BENCHMARKS_summary.md + csv
MISP_VERIFY_SSL=false $V/python -m benchmarks.misp_sample --n 100 --seed 42   # 8. 100 real events (5-300 attributes) from the dev MISP
GENERIC_AI_REQUEST_TIMEOUT=900 $V/python -m benchmarks.run_llm --use-case summarization --kind event --data-dir benchmarks/data/misp   # 9. event ("story-telling") summaries
$V/python -m benchmarks.compare_summary --kind event --data-dir benchmarks/data/misp --second-dir <pass 2 dir> --out docs/BENCHMARKS_summary-event.md --csv benchmarks/results/summary-event.csv
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
| `benchmarks/data/misp/<uuid>.json`, `sample.json` | real events from the dev MISP as served (`{"Event": …}`), the seeded draw |
| `benchmarks/results/<id>.summary-event.json` | same contract as `.summary.json`, `summary_kind=event` |
| `benchmarks/results/<id>.summary.json` | `{"model", "prompt", "summary", "words", "seconds"}` or `{"error", "seconds"}` |
| `benchmarks/results/<id>.llm.json` | `{"model": {...}, "prompt": {...}, "indicators": [[type, value], ...], "rejected": [...], "seconds": float}` |
| `benchmarks/results/extraction.csv` | per-report metrics (committed) |
| `docs/BENCHMARKS_extraction.md` | the written-up comparison (committed) |

`benchmarks/data/` and `benchmarks/results/*.json` are gitignored (downloaded / regenerable);
the csv and the docs are committed. orkl.eu exposes no IoC field, so there is no ground truth
from orkl: the comparison is between the two extractors, judged against the report text.
