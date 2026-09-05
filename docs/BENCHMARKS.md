# Benchmarks

The first benchmark measures the **CTI info extraction** use-case: the module's LLM extraction
against a classical regex extractor and against hand-labelled gold lists. The measured result is
in [BENCHMARKS_extraction.md](BENCHMARKS_extraction.md) (generated, do not edit by hand).

## Results (2026-09-05, qwen3.8:latest digest 22130167c4c2, Ollama 0.33.2, seed 42)

Full tables and charts: [BENCHMARKS_extraction.md](BENCHMARKS_extraction.md) (generated, do not
edit by hand). Prompt cluster `cti-info-extraction/qwen3.8-v1` version 2, `max_tokens` 10000,
`GENERIC_AI_REQUEST_TIMEOUT=900`.

What the numbers say:

1. **95 of 100 reports succeed; 5 overflow even 10000 answer tokens.** The first run with the
   original 2000-token budget (a guess, never measured) failed on 35 reports; 8000 recovered
   30 of them; 10000 recovers the same 30. The remaining 5 are genuinely indicator-dense: a
   probe of one shows 79 distinct indicators in 18 KB of pretty-printed JSON, about 127 tokens
   per indicator, because the answer is indented and the `quote` repeats the value. The module
   returns an error for them, never partial results. Compact JSON and a shorter or absent
   `quote` would roughly halve the cost (IMPROVEMENTS item 25).
2. **Speed with the 10000 budget**: median 9 s per report, p90 34 s, max 62 s, none above the
   module's default 120 s timeout; the full pass took 30 minutes. The earlier 8000-token re-run
   of the hard reports had taken up to 194 s per report.
3. **Against the three hand-labelled gold lists the LLM is precise**: precision 1.00,
   recall 0.80, F1 0.89, kappa 0.84 (micro). Its misses are defanged values
   (`131.226.2[.]6`) and a name (`emotet`), both rejected by the module's own filters. The
   classic extractor on the same reports: precision 0.21, recall 0.49, kappa negative, because
   it also returns the reporting vendor's links.
4. **Against the classic superset (95 reports) agreement is low by construction**: F1 0.43,
   Jaccard 0.28, kappa -0.55. The classic-only values are URLs and domains (802 of 888), a large
   part of them reference links and vendor sites (109 flagged `reporter-domain`; the flag only
   catches hosts named in the entry metadata, so it undercounts). On hashes the two agree:
   recall of classic md5/sha1/sha256 is 0.84-0.95; on ip-dst 0.12, url 0.15, domain 0.01
   (classic derives a domain from every URL; the LLM reports the URL, and matching is by value).
5. **What only the LLM finds**: 644 values in types the regexes cannot see: filename (331),
   threat-actor (100), malware-type (65), regkey (27), vulnerability, named pipe, pdb, mutex.
   These are the module's added value and need a human-labelled set to be scored; on the 3 gold
   lists every such value was literally in the text (precision 1.0).
6. **Superset artefacts found on the way**: iocextract's IPv6 regex matched times such as
   `23:00:15` (116 false IPs before `genai/classic.py` validated candidates with `ipaddress`),
   and its e-mail regex swallows the preceding word. The comparison refangs values before
   matching so a defanged LLM value equals its refanged classic twin.

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
python -m benchmarks.compare --results-dir benchmarks/results-v2 --out docs/BENCHMARKS_extraction-v2.md --csv benchmarks/results/extraction-v2.csv
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
