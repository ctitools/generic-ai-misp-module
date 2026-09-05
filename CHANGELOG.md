# Changelog

## 2026-09-05 (summary benchmark)

- `docs/IMPROVEMENTS.md` section 6: the open TODOs from the test-strategy review (items 27-33: labelled precision set, urllib → requests refactor, larger gold data set, summary quality, context-size guard, adversarial inputs, benchmark statistics/history).
- Live write-path e2e (`tests/test_e2e_misp_write.py`): creates an event on the dev MISP (distribution 0, unpublished) with an orkl.eu report from `tests/fixtures/orkl/` as EventReport, runs extraction and summarization through the module, pushes the result back with PyMISP, verifies attributes/report/AI tags/distribution on the instance and deletes the event (`E2E_KEEP=1` keeps it). Two orkl reports committed as fixtures with provenance.
- Tests: live gates are explicit. `tests/conftest.py` marks tests `live_llm`/`live_misp` from the fixtures they use, prints a "live gates" summary after every run, and `--require-live` fails (instead of skipping) when the LLM or MISP is unavailable, the API key is rejected or a golden header does not match; the message points to README "Live systems (MISP and LLM server)", a new section describing `.env`, Ollama and the reachability check.
- CI: `.github/workflows/checks.yml` runs ruff (pinned 0.16.6), pylint (`--disable=fixme`), the offline pytest layers (`uv sync --extra dev --extra e2e`, live files deselected) and semgrep (`p/python`, `p/security-audit`) on every push and pull request; `benchmarks/orkl.py` refuses URLs outside its https base (semgrep audit finding); `.githooks/pre-commit` runs the same locally (`git config core.hooksPath .githooks`). CLAUDE.md and TESTING.md gap 1 updated.
- `docs/TESTING.md` section 8: review of the test and benchmark strategy with 12 ranked gaps (no CI, silent live skips, the AGENTS.md write-path e2e loop not implemented, unmeasured correctness of LLM-only findings and summary content, no context-size guard, no adversarial inputs, no run history).
- `tests/misp_compare.py`: whitespace-only strings count as empty (PyMISP serialises a whitespace-only EventReport content as ""; the round-trip gate flagged live event 244b2366 as "content missing after processing"). Rule 1 of the comparator documented accordingly.
- `summary-report/qwen3.8-v2` is now the default summary-report cluster (galaxy version bumped; v1 kept, selectable by value/uuid); `tests/golden/summary-report.md` re-recorded with the v2 prompt and reviewed.
- First summarization benchmark on the 100 orkl reports: v1 prompt passes the gate on 28 (35 truncated at 600 tokens, 36 over 200 words), the new `summary-report/qwen3.8-v2` on 96; both byte-deterministic across two passes. Reports `docs/BENCHMARKS_summary.md`, `docs/BENCHMARKS_summary-v2.md`; table and interpretation in `docs/BENCHMARKS.md`. v2 is not yet the default.
- `benchmarks/run_llm.py --use-case summarization` writes `<id>.summary.json` per report; new `benchmarks/compare_summary.py` → `docs/BENCHMARKS_summary.md` (gate pass rate and failing rules, length, headings, indicator coverage, timing, determinism against a second pass). Tests: `tests/test_compare_summary_unit.py`, runner test for the summary use-case.
- `genai/summarize.py`: the structural check also matches indicators against the whitespace-free report (PDF text breaks GUIDs and hashes across lines); it refangs the report and the summary before the foreign-indicator test (a summary of a defanged report was rejected for mentioning the refanged IP).
## 2026-09-05 (refang)

- New `docs/INTEGRATION_PLAN.md`: how MISP actually invokes modules (UI selects by module name, no per-call parameters; whole-event expansion is not offered; `sendToLLM` hook and its contract; workflows and import modules) and the recommendation: several thin entry points around one engine, delegation instead of inheritance. Research only, nothing implemented.
- Benchmark re-run after refanging (same sample, model and budget): LLM vs classic F1 0.43 → 0.56, recall of classic IPs 0.12 → 0.68, gold recall 0.80 → 0.92 at precision 1.00; `format` rejections 220 → 64. Before/after table in `docs/BENCHMARKS.md`.
- New `genai/refang.py`: one refang function (`hxxp://`, `[.]`, `(.)`, `{.}`, `[dot]`, `[:]`, `[at]`, markdown-escaped dots in network tokens; paths and named pipes untouched) used by the extraction use-case, `genai/classic.py` and `benchmarks/metrics.py`. `extract.py` stores refanged values, keeps the original in the attribute comment (`defanged in source as …`), re-types hashes labelled with the wrong hash type by length (`typed … by the model`), reports `refanged`/`retyped` counts, and format-checks `ip-src|port`, `ip-dst|port`, `hostname|port`; rejections report the value as the model gave it. Gold list 59ed4725 refanged; live precision test compares refanged values. Docs: USE-CASES (step 0), requirements R5.3, PROMPTS, IMPROVEMENTS 26 resolved, BENCHMARKS method.

## 2026-09-04 (benchmark)

- Benchmark re-run with the 10000-token budget: 95/100 reports succeed (5 overflow at any budget), median 9 s per report; `docs/BENCHMARKS.md` Results rewritten, interim `BENCHMARKS_extraction-v2.md` removed.
- Extraction cluster `cti-info-extraction/qwen3.8-v1`: `max_tokens` 2000 → 10000 (cluster version 2), the interim v2 cluster removed. Reason: the benchmark truncated 35 of 100 answers at 2000 and 5 at 8000. Long answers exceed the 120 s default `request_timeout`; set `GENERIC_AI_REQUEST_TIMEOUT` for such reports.
- `genai/summarize.py`: the structural check's URL pattern no longer swallows a closing backtick or sentence punctuation (a summary quoting `` `https://…/verify`. `` failed as "indicator not in input"). Unit test added.
- First extraction benchmark run on 100 orkl.eu reports: results and interpretation in `docs/BENCHMARKS.md` (Results), generated reports `docs/BENCHMARKS_extraction.md` (as deployed) and `docs/BENCHMARKS_extraction-v2.md` (8000-token cluster). `genai/classic.py` validates IPv6 candidates (iocextract matched times as IPs); `benchmarks/metrics.py` refangs values before matching. New IMPROVEMENTS items 25-26 (answer budget, defanged values).
- Added `genai/classic.py`: deterministic regex IoC extractor over `iocextract` 1.16.1 (new
  dependency in `pyproject.toml`/`uv.lock`, GPL, transitive `regex`), refanging defanged values
  and returning sorted `(misp_type, value)` pairs plus a `python -m genai.classic` CLI. Benchmark
  and test tooling only — never on the request path (`tests/test_classic_unit.py` enforces it, plus
  the gold-subset gate on `orkl-sample`). Supply-chain notes in IMPROVEMENTS.md item 24.
- `benchmarks/orkl.py`: stdlib-only read-only orkl.eu client (`info`, `entry`, `entries`) and reproducible sampler `sample(n, seed, ...)` / `python -m benchmarks.orkl` that draws random English reports (2000-40000 chars) into `benchmarks/data/orkl/<id>.json` + `sample.json` (resumable, progress in `logs/benchmark-orkl.log`). Offline tests in `tests/test_orkl_unit.py`; data flow and file contracts in `benchmarks/README.md`; `benchmarks/data/`, `benchmarks/results/*.json`, `logs/` gitignored.
- `benchmarks/run_llm.py`: runs the module's LLM extraction through `expansion.generic_ai.dict_handler` over the orkl sample (`benchmarks/data/orkl/sample.json`) and writes `benchmarks/results/<id>.llm.json` (`model`, `prompt`, sorted `indicators`, `rejected`, `seconds`; `{"error", "seconds"}` on failure, no report is dropped). Resumable (`--force` re-runs), exits 2 when the LLM in `.env` is unreachable, logs ok/fail, reports/s and ETA to `logs/benchmark-llm.log`. Offline tests in `tests/test_run_llm_unit.py`; `benchmarks/data/` and `benchmarks/results/*.json` are gitignored. Docs: BENCHMARKS.md "Running", IMPROVEMENTS item 19.
- `expansion/generic_ai.py`: `dict_handler` also turns `PyMISPError` from the use-case into an `{"error": ...}` response (a candidate that passes all filters but PyMISP still refuses, e.g. an unparsable `datetime`, no longer crashes the handler).
- `benchmarks/compare.py` (+ `tests/test_compare_unit.py`): compares the LLM extraction with the classic `iocextract` results and the gold lists by normalised value, writes `docs/BENCHMARKS_extraction.md` (confusion matrices, micro/macro precision, recall, specificity, accuracy, F1, Jaccard, Cohen's kappa, per-type recall, Mermaid charts, deviations with a `reporter-domain` flag, gold view) and `benchmarks/results/extraction.csv`. `docs/BENCHMARKS.md` rewritten as the benchmark index (method, commands, artifacts, metric definitions, superset caveat).

## 2026-09-04 (use-cases)

- Implemented the two use-cases in a new `genai/` package: `extract.py` (CTI info extraction: LLM proposes JSON candidates, five deterministic filters — in-source, known type, format, duplicate, confidence — decide; file/vulnerability objects; every added attribute AI-tagged) and `summarize.py` (`kind=report|event`, deterministic event rendering, structural gate: headings, ≤ 200 words, no indicator that is not in the input; summary attached as a new EventReport, event AI-tagged).
- `genai/llm.py`: the single OpenAI-compatible chat client (endpoint/key/model from `.env` only, timeout → error, no fallback, thinking disabled via `reasoning_effort: none`, JSON mode, model digest/server lookup for Ollama, API key masked in reprs).
- `genai/prompts.py` + `galaxies/generic-ai-prompts.json` + `clusters/generic-ai-prompts.json`: prompts shipped as a MISP galaxy; a cluster carries use-case, model (name/digest/quantisation/server), sampling parameters and the prompt text; resolution by uuid, value, inline text or default. `genai/ai_taxonomy_pinned.json` pins the `ai-computer-assisted` tag strings.
- `expansion/generic_ai.py`: `process_event(event, e2etest, settings, metadata)` dispatches on `use_case` (`none` default, `extraction`, `summarization`); `resolve_settings()` implements request > config > `.env` > default for the `moduleconfig` keys; `api_base`/`api_key` are never request-settable; response gained `metadata`. Module version 0.4.
- Tests: `tests/test_usecases_unit.py` (26 offline tests with a mocked LLM: every filter, objects, tagging, rendering determinism, structural gate, precedence), `tests/test_llm_live.py` (determinism, model pinning, extraction precision gate on two reports + Emotet recall report, summary gate and goldens with `--update-goldens`), use-case cases through the real misp-modules server. Fixtures: `fixtures/summary/dummy-event.json`, `fixtures/gold/*.iocs.json`, `tests/golden/summary-*.md`.
- Docs: USE-CASES, TESTING, requirements, ARCHITECTURE, README, CLAUDE updated to the implementation and the first measured results.

## 2026-09-04

- Rewrote `expansion/generic_ai.py` (609 → ~130 lines): the module now takes a **full MISP Event** instead of a text attribute. Removed the OpenAI/Ollama backends, prompts, deterministic summariser and the 13 runtime settings.
- Input accepted under `event` (`{"Event": {...}}` or bare) or export-module style under `data[0]`.
- Validation with PyMISP `MISPEvent.load()`; invalid input returns `{"error": "Invalid MISP Event: ..."}`. Added a normalisation for `distribution`/`sharing_group_id` on default galaxy clusters, which MISP emits but PyMISP rejects.
- New functions `validate_event()`, `get_event_report()` (markdown of all non-deleted EventReports), and the dummy hooks `process_event(event) -> MISPEvent` and `process_eventReport(event_report) -> MISPEvent`.
- Response shape: `{"results": {"Event": ..., "ReportEvent": ...}, "event_report": "..."}`.
- `handler()` now returns an error dict on malformed JSON; `version()` no longer mutates `moduleinfo`.
- Added `fixtures/output/` (8 real MISP events, 5 with EventReports, plus `hashes.csv` / `manifest.json`) as the shared test set.
- Rewrote the tests: 21 unit tests (all fixtures validate and round-trip, input shapes, report extraction, 8 rejection cases, hooks), local e2e against a real `misp-modules` server for every fixture, and live e2e fetching the fixture uuids from the MISP instance in `.env` (skips on missing key / 404 / unreachable; `MISP_VERIFY_SSL=false` for the self-signed dev cert).
- `pyproject.toml`: Python `>=3.14`, dependency `pymisp>=2.5.34.2`, extras `dev` (pytest, ruff, pylint) and `e2e` (misp-modules), build system, version `0.3.0` (module and package versions now agree).
- Docs: README rewritten for the new data flow; ARCHITECTURE.md gained the current flow, the schema-provenance check (no official JSON schema defines `EventReport`) and the test-data note; AGENTS.md updated (Python 3.14, PyMISP approved); new IMPROVEMENTS.md with the repository analysis.
- Added a round-trip quality gate: `process_event(event, e2etest=False)` gained the `e2etest` flag that writes the processed event to `tests/e2etests/<uuid>.json`; `tests/test_e2e_roundtrip.py` fetches 10 random events from the live instance (seedable with `E2E_SEED`, last run recorded in `tests/e2etests/last_run.json`) and proves the files are semantically identical to the originals via the new `tests/misp_compare.py` (own tests in `tests/test_misp_compare.py`).
- `validate_event()` now builds the `MISPEvent` with `force_timestamps=True`; PyMISP otherwise dropped the event `timestamp` on published events.
- Moved the `.env` loader and a small read-only MISP client (`MispApi`: `fetch`, `index`) into `tests/conftest.py`, shared by the live e2e test and the gate.
- Consolidated all documentation under `docs/` (`git mv` of ARCHITECTURE, BENCHMARKS, USE-CASES, IMPROVEMENTS, architecture.png); README got a documentation index; links fixed.
- Rewrote `docs/USE-CASES.md` around the two use-cases in focus: CTI info extraction (`extract_iocs`, high-confidence only, five deterministic post-filters) and summarization (`summarize(event, kind="report"|"event")`); other hackathon ideas parked as one-liners. Tagging rule: LLM-suggested attributes are tagged, LLM-suggested event-level content tags the event.
- New `docs/PROMPTS.md`: prompts shipped as a MISP galaxy (cluster = use-case + model/digest + sampling parameters + prompt text), resolution order, v1 prompt texts.
- New `docs/TESTING.md`: existing layers, per-use-case test plan with gates, and the deterministic-summary strategy (pinned model digest/server/prompt hash, seed 42 / temperature 0 / think off, three strictness levels, structural gate). Measured on `nanu`: three identical requests → identical output.
- Rewrote `docs/requirements.md` to the current module (full-event input, no fallback, two use-cases, prompt galaxy, tagging MUST); obsolete requirements dropped.
- `docs/ARCHITECTURE.md`: planned-hooks section (dispatch, LLM boundary, prompt resolution, tagging).
- Module metadata: author "Aaron Kaplan / ctitools", name "Generic AI MISP module".
- Verified locally: `pytest` 49 passed / 4 skipped (events absent on the instance), `ruff`, `pylint` clean; the gate passed 10/10 on three seeds.
- Added `benchmarks/metrics.py`, a stdlib-only metrics library for the LLM-vs-regex IoC
  extraction benchmark: value-only normalisation, `Confusion` counts against an optional
  universe, precision/recall(sensitivity)/specificity/accuracy/F1/Jaccard overlap, Cohen's
  kappa, micro/macro aggregation and per-reference-type buckets. Hand-computed tests in
  `tests/test_metrics_unit.py`.

## 2026-06-15

- updated use-cases.

## 2026-04-15

- Bootstrapped a custom `misp-modules` expansion scaffold for a Generic AI module.
- Added live backend support in `expansion/generic_ai.py` for `ollama` and OpenAI-compatible `/v1` APIs, with a deterministic fallback when the backend is unavailable.
- Switched the module output to MISP `EventReport` in `misp_standard` format.
- Added unit and live service E2E tests for `/modules`, `/healthcheck`, and `/query`, including OpenAI-compatible local model coverage.
- Switched report-based testing to the fixed fixture `tests/fixtures/orkl-sample.txt` instead of fetching random ORKL archive content.
- Added `ai-computer-assisted` event tags to the MISP results so AI-generated content tags the containing event as `ai-generated` and `unreviewed`.
- Documented the development-host bootstrap, run command, artifact path, and verification step in `README.md`.
- Verified the scaffold on the development host with Python `3.12`, a shared `.venv`, and an editable upstream `misp-modules` install.
- Passed the remote quality loop: `pytest` (`13 passed`), `ruff`, `pylint`, and `semgrep`.
- Saved live backend smoke artifacts for both direct `ollama` and OpenAI-compatible Ollama queries.
- Configured `MISP_HOST` to use the Generic AI enrichment module and verified the end-to-end MISP flow with the fixed ORKL sample, a test event, a generated `EventReport`, and the expected event-level AI assistance tags.
- Captured the successful MISP end-to-end artifacts in `artifacts/misp_e2e_*.json` and the verification metrics in `logs/misp_e2e_metrics.json`.
