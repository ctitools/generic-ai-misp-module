# Benchmarks

The first benchmark measures the **CTI info extraction** use-case: the module's LLM extraction
against a classical regex extractor and against hand-labelled gold lists. The measured result is
in [BENCHMARKS_extraction.md](BENCHMARKS_extraction.md) (generated, do not edit by hand).

## Results (2026-09-05 after refanging, qwen3.8:latest digest 22130167c4c2, Ollama 0.33.2, seed 42)

Full tables and charts: [BENCHMARKS_extraction.md](BENCHMARKS_extraction.md) (generated, do not
edit by hand). Prompt cluster `cti-info-extraction/qwen3.8-v1` version 2, `max_tokens` 10000,
`GENERIC_AI_REQUEST_TIMEOUT=900`. Same sample and model as the previous run; the only change
is the refang/re-type step in `genai/extract.py` (and the same refang in the classic baseline).

| | before refang | after refang |
|---|---|---|
| reports succeeded | 95 / 100 | 95 / 100 |
| LLM indicators stored | 1227 | 1498 (0 still defanged) |
| `format` rejections | 220+ | 64 |
| LLM vs classic: F1 / Jaccard / kappa (micro) | 0.43 / 0.28 / -0.55 | 0.56 / 0.38 / -0.41 |
| recall of classic ip-dst / url / domain | 0.12 / 0.15 / 0.01 | 0.68 / 0.42 / 0.07 |
| recall of classic md5 / sha1 / sha256 | 0.95 / 0.84 / 0.90 | 0.95 / 0.89 / 0.98 |
| gold view (3 reports): precision / recall / F1 / kappa | 1.00 / 0.80 / 0.89 / 0.84 | 1.00 / 0.92 / 0.96 / 0.93 |
| classic indicators (baseline) | 1878 | 1614 (264 `http:host` artefacts gone) |

What the numbers say:

1. **Refanging was the largest single loss.** 48 of the 100 reports defang; before this round
   the module rejected 220 correct indicators as malformed and stored 34 still defanged. Now
   every stored value is a real value, the original spelling is in the attribute comment, and
   recall of the regex baseline's IPs went from 0.12 to 0.68 and of URLs from 0.15 to 0.42.
2. **The remaining URL gap is mostly type policy and reference links**: the LLM reports
   scheme-less URLs (`c34718cbb4c6.ngrok-free.app/file.ps1`) which the `url` format check
   rejects, and it leaves out the vendor's reference links that the regexes collect
   (111 of the 469 classic-only values are flagged `reporter-domain`; the flag undercounts).
3. **Domains**: classic derives a domain from every URL (216), the LLM reports the URL instead;
   the LLM's 108 domain-only values are bare domains (`evil[.]com` refanged) that iocextract
   has no extractor for. Matching is by value, so both show up as disagreement, not as errors.
4. **Gold view**: precision stays 1.00 on all three hand-labelled reports; recall on the
   defanged report 59ed4725 went from 0.68 to 0.89 (two misses left: the scheme-less ngrok URL
   and one IP the model did not report), on the Emotet sample 0.94 (`emotet` as a name).
5. **5 reports still overflow 10000 answer tokens**, unchanged (indicator-dense reports with
   pretty-printed JSON and a quote per indicator; IMPROVEMENTS item 25).
6. **What only the LLM finds** is unchanged in kind: filename (321), threat-actor (107),
   malware-type (69), regkey (27), vulnerability, named pipe, pdb: types regexes cannot see.
7. **Speed**: median 9 s per report, max 62 s; the pass took 30 minutes.
8. **Superset artefacts**: iocextract's IPv6 regex matched times (`23:00:15`), and its handling
   of bare defanged domains produced `http:host` strings; both are gone from the baseline.

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
