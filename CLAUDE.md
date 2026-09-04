@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Read `AGENTS.md` first: it is the binding contributor guide (short closed loops, "less code is
more", tests first, CHANGELOG entry after every change, docs updated in the same pass, only
`pymisp` as third-party dependency). This file only adds what AGENTS.md does not say. All other documentation lives in `docs/`;
the use-case contracts are in `docs/USE-CASES.md`, the test plan in `docs/TESTING.md`.

## Commands

The `.venv` (Python 3.14) already exists at the repo root; never recreate it. Use `uv` for installs.

```bash
uv pip install --python .venv/bin/python -e ".[dev,e2e]"   # deps + pytest/ruff/pylint + misp-modules
.venv/bin/pytest -q                                          # whole suite (live tests skip without .env)
MISP_VERIFY_SSL=false .venv/bin/pytest -q                    # include live tests (dev MISP has a self-signed cert)
.venv/bin/pytest -q tests/test_generic_ai_unit.py -k report  # one file / one test by keyword
MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_e2e_roundtrip.py   # quality gate: 10 random live events
E2E_SEED=42 MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_e2e_roundtrip.py  # reproducible draw
.venv/bin/ruff check . && .venv/bin/ruff format --check expansion tests && .venv/bin/pylint expansion genai tests
.venv/bin/python -m misp_modules -c . -l 127.0.0.1 -p 6666  # run the module in a real misp-modules server
```

Lint must be clean (pylint 10/10, ruff) before a commit; `ruff format expansion tests` fixes formatting.

## Architecture

One module, `expansion/generic_ai.py`, loaded by upstream `misp-modules` as a custom expansion
module (`handler` / `introspection` / `version` contract; `dict_handler` is the in-process entry
used by tests), plus the `genai/` package (`llm.py` is the only network code; `prompts.py`
loads the prompt galaxy and pinned tags; `extract.py`, `summarize.py` are the use-cases).
misp-modules imports every `.py` in `expansion/`, which is why helpers live in `genai/`. Data flow:

`request` → `_extract_event` (accepts `event` wrapped/bare or export-style `data[0]`) →
`validate_event` (PyMISP `MISPEvent.load`, built with `force_timestamps=True`) → `event` →
`get_event_report` (markdown of non-deleted EventReports) → `process_event(event)` and
`process_eventReport(event_report)` → `{"results": {"Event", "ReportEvent"}, "event_report"}`.

`process_event()` dispatches on `use_case` (`none` default = no LLM call, `extraction`,
`summarization` with `summary_kind`); `process_eventReport()` is still a dummy. Every LLM-made
element carries the two `ai-computer-assisted` tags from `genai/ai_taxonomy_pinned.json`.
`process_event(..., e2etest=True)` writes the result to `tests/e2etests/<uuid>.json` for the gate.
LLM tests skip when `OPENAI_BASE_URL` from `.env` is unreachable; `--update-goldens` re-records
`tests/golden/` and the diff must be reviewed by a human.

Things that are not obvious from the code alone:

- **No JSON schema on purpose.** No official MISP schema defines `EventReport` (checked
  misp-rfc, MISP/MISP, PyMISP); PyMISP is the validator. Details in docs/ARCHITECTURE.md
  "Schema provenance". Do not vendor or invent a schema.
- **PyMISP quirks the module works around** (keep them; each has a test): it mutates the input
  dict on load (deep-copy first), `to_dict(json_format=True)` fails on real exports (serialise via
  `to_json()`), it rejects `distribution` on default galaxy clusters that MISP itself emits
  (`_normalise_for_pymisp` strips them), and it drops the event `timestamp` on published events
  unless `force_timestamps=True`. The full list is in docs/IMPROVEMENTS.md item 11.
- **Test data is real.** `fixtures/output/*.json` are eight events exported from the MISP
  instance in `.env` (five with EventReports; `hashes.csv` maps md5 → uuid). All tests use them.
  Four of those uuids no longer exist on the instance, so four live tests always skip.
- **Live MISP access lives in `tests/conftest.py`** (`load_env`, `MispApi.fetch/index`, the
  session fixture `misp_api`). It is read-only and turns auth/network problems into skips.
  `.env` follows shell semantics: the last definition of a key wins.
- **"Identical" for the round-trip gate means semantic**, as defined in `tests/misp_compare.py`.
  Its allowlist covers only PyMISP's own normalisations; widen it only with a stated reason, never
  to make a failing gate pass.
- `.env` is gitignored but old keys are still in git history (rotated); never commit it.
