# Changelog

## 2026-09-04 (benchmark)

- `benchmarks/orkl.py`: stdlib-only read-only orkl.eu client (`info`, `entry`, `entries`) and reproducible sampler `sample(n, seed, ...)` / `python -m benchmarks.orkl` that draws random English reports (2000-40000 chars) into `benchmarks/data/orkl/<id>.json` + `sample.json` (resumable, progress in `logs/benchmark-orkl.log`). Offline tests in `tests/test_orkl_unit.py`; data flow and file contracts in `benchmarks/README.md`; `benchmarks/data/`, `benchmarks/results/*.json`, `logs/` gitignored.

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
