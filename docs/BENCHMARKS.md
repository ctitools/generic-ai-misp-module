# Benchmarks

The first benchmark measures the **CTI info extraction** use-case: the module's LLM extraction
against a classical regex extractor and against hand-labelled gold lists. The measured result is
in [BENCHMARKS_extraction.md](BENCHMARKS_extraction.md) (generated, do not edit by hand).

## Current results (v3 test run, 2026-09-05)

Model `qwen3.8:latest` digest `22130167c4c2`, Ollama 0.33.2, seed 42 / temperature 0. Extraction
prompt `cti-info-extraction/qwen3.8-v1` at schema version 3 (`actionable`, `first_seen`,
`last_seen`, `published`), `max_tokens` 10000, `GENERIC_AI_REQUEST_TIMEOUT=900`. Summary clusters
`summary-report/qwen3.8-v2` and `summary-event/qwen3.8-v2` (hard 150-word budget, copy-exact
indicators, capped lists). Generated reports, never edited by hand:
[BENCHMARKS_extraction.md](BENCHMARKS_extraction.md),
[BENCHMARKS_summary.md](BENCHMARKS_summary.md) (report kind, 100 orkl.eu reports),
[BENCHMARKS_summary-event.md](BENCHMARKS_summary-event.md) (event kind, 100 dev-MISP events).

### Extraction, 100 orkl.eu reports

| | value |
|---|---|
| reports succeeded | 95 / 100 (5 overflow the 10000-token answer budget, IMPROVEMENTS item 25) |
| indicators stored | 1379, none defanged |
| gold view (3 hand-labelled reports): precision / recall / F1 / kappa | 1.00 / 0.92 / 0.96 / 0.93 |
| vs the regex superset: F1 / Jaccard / kappa (micro) | 0.56 / 0.39 / -0.42 |
| recall of classic md5 / sha1 / sha256 / ip-dst / url | 0.95 / 0.89 / 0.98 / 0.68 / 0.42 |
| indicators with a date stated in the text | 36 |
| `to_ids` lowered (not actionable per the model) | 35, listed for review |
| rejections: format / confidence / not-in-source / free-text-type / duplicate | 56 / 39 / 33 / 23 / 9 |
| seconds per report: median / max; whole pass | 9 / 62; 34 min |

How to read it: the classic extractor is a deliberate superset, so an LLM "false positive"
against it is a value the regexes missed and an LLM "false negative" is often a correct
omission (reference links, vendor sites); the hashes agree, URLs and domains are where the two
differ. What only the LLM finds (filenames, threat actors, malware names, registry keys,
CVEs) is checked to be in the text, not yet to be correct: IMPROVEMENTS items 27 and 32.

### Summarization, report kind, 100 orkl.eu reports

| | value |
|---|---|
| summaries passing the gate | 96 / 100 (2 correct rejections of CVE ids not in the text, 1 over length, 1 line-broken GUID since fixed) |
| words: median / p90 / max | 124 / 165 / 187 |
| all four headings present | 96 / 96 |
| coverage of the regex baseline's hashes/IPs/URLs (mean) | 0.31 (at most five indicators are listed, by design) |
| seconds per report: median / max | 4.7 / 9.3 |
| byte-identical in a second pass | 96 / 96 |

### Summarization, event kind, 100 real events with 5-300 attributes

| | value |
|---|---|
| summaries passing the gate | 99 / 100 (1 answer over the 1000-token budget) |
| words: median / p90 / max | 95 / 147 / 179 |
| all four headings present | 99 / 99 |
| coverage of the event's own hashes/IPs/URLs (mean) | 0.54 |
| seconds per event: median / max | 5.3 / 14.2 |
| byte-identical in a second pass | 99 / 99 |

### History of the rounds (tags on `with_full_event`)

| tag | what changed | headline before → after |
|---|---|---|
| `benchmark-2026-09-05` | first extraction benchmark; answer budget 2000 → 10000 | 65 → 95 reports succeed |
| `benchmark-2026-09-05-refang` | refang + hash re-typing in the module, one refang function for module, baseline and metrics | gold recall 0.80 → 0.92, LLM-vs-classic F1 0.43 → 0.56 |
| `benchmark-2026-09-05-summary` | summary prompts with a hard word budget (report kind) | gate 28 → 96 of 100 |
| `benchmark-2026-09-05-event` | event kind benchmarked on real events, capped related-events list | gate 29 → 99 of 100 |
| `benchmark-2026-09-05-dates` | schema v3: dates from the text, `to_ids` lowered, free-text types rejected | gates unchanged, 36 dated, 35 lowered |

Details of each round are in the CHANGELOG and in the commits under each tag; the superseded
generated reports were removed with the v3 clean-up.

## Summarization benchmark

Two kinds. `report` summarises the EventReport of the 100 orkl reports. `event` (the
"story-telling" case) summarises whole events: `python -m benchmarks.misp_sample` draws 100
real events with 5-300 attributes from the dev MISP (seed 42, read-only, `benchmarks/data/misp/`),
`run_llm --kind event` renders each event the way the module does and summarises it; the
coverage reference is then the event's own hashes/IPs/URLs instead of the regex baseline.
`python -m benchmarks.run_llm --use-case summarization [--kind event]` writes one result per
item; a second pass into another directory measures determinism; `compare_summary` writes the
report. There is no reference summary to score against, so the report measures the module's
own structural gate (pass rate and the failing rule), length, headings, coverage
(informational), timing and determinism.

## Method

- Sample: 100 random orkl.eu reports (seeded draw, `benchmarks/data/orkl/sample.json`).
- Classic reference: `iocextract` 1.16.1, a deliberate *superset* extractor (it also catches
  defanged values). Run per report through `genai/classic.py`.
- LLM: the module's extraction use-case (`benchmarks/run_llm.py`), one result file per report
  with model digest, prompt sha256 and timing, so every number is traceable.
- Gold: three hand-labelled lists in `fixtures/gold/*.iocs.json` (two MISP EventReports from
  `fixtures/output/`, one ORKL sample). The coordinator places the classic and LLM results for
  them under `benchmarks/results/gold/`.
- Comparison: `benchmarks/compare.py` matches by normalised **value only** (refanged with
  `genai/refang.py`, the same function the module and the classic baseline use; lower-case,
  whitespace collapsed, trailing `/` and `.` stripped); indicator types are ignored on purpose.

## Commands

python -m benchmarks.orkl --n 100 --seed 42          # draw the sample -> benchmarks/data/orkl/
python -m genai.classic benchmarks/data/orkl/*.json -o benchmarks/results   # classic extractor (skips sample.json's empty text)
GENERIC_AI_REQUEST_TIMEOUT=900 python -m benchmarks.run_llm   # LLM extraction -> benchmarks/results/<id>.llm.json
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

Data and result json files are gitignored (`benchmarks/data/`, `benchmarks/results/*.json`);
the csv and the report are committed. Details of each step: `benchmarks/README.md`.

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
