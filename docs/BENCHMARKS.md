# Benchmarks

## Running: LLM extraction over the orkl sample

Data flow: `benchmarks/data/orkl/sample.json` (`{"seed", "n", "ids": [...]}`) and one
`benchmarks/data/orkl/<id>.json` per report (`id`, `title`, `plain_text`, ...) are produced by
the sampler; `benchmarks/run_llm.py` wraps each report as a MISP event with one EventReport,
sends it through `expansion.generic_ai.dict_handler` with `use_case=extraction` (the module as
deployed, LLM from `.env`) and writes one result per report.

```bash
.venv/bin/python -m benchmarks.run_llm                 # all ids in sample.json, resumable
.venv/bin/python -m benchmarks.run_llm --ids a,b --force
```

- artifact: `benchmarks/results/<id>.llm.json` = `{"model", "prompt", "indicators": [[type, value], ...], "rejected", "seconds"}`, or `{"error", "seconds"}` (a report is never dropped)
- progress: `logs/benchmark-llm.log` (ok/fail counts, reports/s, ETA); exit code 2 when the LLM is unreachable
- verification: `.venv/bin/pytest -q tests/test_run_llm_unit.py` (offline, mocked LLM)

Benchmarks exist per use-case and per community profile.
The first benchmark measures the **CTI info extraction** use-case: the module's LLM extraction
against a classical regex extractor and against hand-labelled gold lists. The measured result is
in [BENCHMARKS_extraction.md](BENCHMARKS_extraction.md) (generated, do not edit by hand).

## Method

- Sample: 100 random orkl.eu reports (seeded draw, `benchmarks/data/orkl/sample.json`).
- Classic reference: `iocextract` 1.16.1, a deliberate *superset* extractor (it also catches
  defanged values). Run per report through `genai/classic.py`.
- LLM: the module's extraction use-case (`benchmarks/run_llm.py`), one result file per report
  with model digest, prompt sha256 and timing, so every number is traceable.
- Gold: three hand-labelled lists in `fixtures/gold/*.iocs.json` (two MISP EventReports from
  `fixtures/output/`, one ORKL sample). The coordinator places the classic and LLM results for
  them under `benchmarks/results/gold/`.
- Comparison: `benchmarks/compare.py` matches by normalised **value only** (lower-case,
  whitespace collapsed, trailing `/` and `.` stripped); indicator types are ignored on purpose.

## Commands

python -m benchmarks.orkl --n 100 --seed 42          # draw the sample -> benchmarks/data/orkl/
for f in benchmarks/data/orkl/*.txt; do              # classic extractor, one file per report
  python -m genai.classic "$f" -o "benchmarks/results/$(basename "$f" .txt).classic.json"
done
python -m benchmarks.run_llm                         # LLM extraction -> benchmarks/results/<id>.llm.json
python -m benchmarks.compare                         # -> docs/BENCHMARKS_extraction.md + results/extraction.csv
.venv/bin/pytest -q tests/test_compare_unit.py       # offline check of the comparison on synthetic data

## Artifacts

| path | content |
|---|---|
| `benchmarks/data/orkl/sample.json`, `<id>.json` | the drawn ids and the raw ORKL entries |
| `benchmarks/results/<id>.classic.json` | `{"tool", "indicators": [[type, value]]}` |
| `benchmarks/results/<id>.llm.json` | `{"model", "prompt", "indicators", "rejected", "seconds"}` or `{"error"}` |
| `benchmarks/results/gold/<name>.{classic,llm}.json` | same, for the three gold reports |
| `benchmarks/results/extraction.csv` | one row per report (counts, precision, recall, F1, kappa, seconds) |
| `docs/BENCHMARKS_extraction.md` | the report: tables, Mermaid charts, confusion matrices, deviations |

Data and result json files are gitignored (`benchmarks/data/`, `benchmarks/results/`). Only
`benchmarks/compare.py` is in this tree yet; `benchmarks/orkl.py`, `genai/classic.py`
(`iocextract`, a benchmark-only dependency) and `benchmarks/run_llm.py` are separate units.

## Metric definitions

For one report, `got` = LLM values, `ref` = reference values (classic or gold), `universe` =
the set over which "no" answers are counted (default `got ∪ ref`, so `tn = 0`; in the gold view
`classic ∪ llm ∪ gold`).

- tp = `got ∩ ref`, fp = `got − ref`, fn = `ref − got`, tn = `universe − got − ref`
- precision = tp / (tp + fp); recall = sensitivity = tp / (tp + fn)
- specificity = tn / (tn + fp); accuracy = (tp + tn) / |universe|
- F1 = 2 tp / (2 tp + fp + fn); Jaccard overlap = tp / (tp + fp + fn)
- Cohen's kappa = (p_o − p_e) / (1 − p_e) with p_o the observed agreement on the universe and
  p_e the chance agreement of the two "yes" rates; 1 = perfect, 0 = chance, < 0 = worse than chance
- micro = computed on the summed counts; macro = mean of the per-report values
- degenerate cases: empty `got` and `ref` → precision, recall, F1, Jaccard = 1.0; other empty
  denominators → 0.0

## The superset caveat

The classic extractor is intentionally over-inclusive, so against it an LLM "false positive" is a
value the regexes missed (a regex gap) and an LLM "false negative" may be a correct omission, e.g.
the reporting vendor's own site. The report flags classic-only values whose host appears in the
entry's `sources`/`references`/first text line as `reporter-domain`. Specificity and accuracy
need a universe wider than `got ∪ ref` and are only meaningful in the gold view.

## Future

- Benchmarks per community profile (law enforcement, CERT, ...): different MISPs value different things.
- More models (on-prem and SaaS: qwen, gemma, DeepSeek, gpt-oss, mistral) and prompt versions
  with pinned sampling parameters, as galaxy clusters.
- The other use-cases: summarization goldens, story-telling from the event graph, NER/tagging,
  quality review as a recommendation engine over similar events.
- A curated set of mature MISP events (objects, galaxies, taxonomies) instead of simplistic old data.
- Hand-crafted knowledge-graph fixtures in a simple JSON format for the story-telling use-case.
