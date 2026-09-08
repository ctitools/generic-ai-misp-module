#!/bin/sh
# Benchmark round v4: the whole suite on the pre-seeded samples (100 orkl.eu reports, 100 dev-MISP
# events), each summarisation kind twice for the determinism check, plus tag suggestion.
# Results in benchmarks/results-v4* (gitignored) and benchmarks/results-suggest/; the generated
# reports in docs/BENCHMARKS_*.md and the csv files are committed. One command:
#     sh benchmarks/run_v4.sh > logs/benchmark-v4.log 2>&1
# Do not run live tests while this runs: Ollama serialises requests.
set -e
cd "$(dirname "$0")/.."
V=.venv/bin
export GENERIC_AI_REQUEST_TIMEOUT=900 MISP_VERIFY_SSL=false
echo "== v4 start $(date -u +%FT%TZ)"
$V/python -m genai.classic benchmarks/data/orkl/*.json -o benchmarks/results-v4
$V/python -m benchmarks.run_llm --results-dir benchmarks/results-v4
$V/python -m benchmarks.gold --results-dir benchmarks/results-v4
$V/python -m benchmarks.compare --results-dir benchmarks/results-v4 --csv benchmarks/results/extraction.csv
$V/python -m benchmarks.run_llm --use-case summarization --results-dir benchmarks/results-v4
$V/python -m benchmarks.run_llm --use-case summarization --results-dir benchmarks/results-v4-pass2
$V/python -m benchmarks.compare_summary --results-dir benchmarks/results-v4 --second-dir benchmarks/results-v4-pass2 --csv benchmarks/results/summary.csv
$V/python -m benchmarks.run_llm --use-case summarization --kind event --data-dir benchmarks/data/misp --results-dir benchmarks/results-event-v4
$V/python -m benchmarks.run_llm --use-case summarization --kind event --data-dir benchmarks/data/misp --results-dir benchmarks/results-event-v4-pass2
$V/python -m benchmarks.compare_summary --kind event --data-dir benchmarks/data/misp --results-dir benchmarks/results-event-v4 --second-dir benchmarks/results-event-v4-pass2 --out docs/BENCHMARKS_summary-event.md --csv benchmarks/results/summary-event.csv
$V/python -m benchmarks.run_suggest --n 100 --seed 42 --k 5
echo "== v4 done $(date -u +%FT%TZ)"
