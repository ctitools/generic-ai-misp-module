# AI MISP Module

A custom [misp-modules](https://github.com/MISP/misp-modules) expansion module that puts a Large
Language Model to work on a **full MISP Event** ([MISP core
format](https://www.misp-standard.org/rfc/misp-standard-core.html)) — not on a single attribute.

## What this is

You give the module a whole MISP Event, it validates it with
[PyMISP](https://github.com/MISP/PyMISP), takes the markdown of the event's `EventReport`s (the
CTI report an analyst pasted into the event) and hands event plus report to the configured
use-case. What comes back is again a MISP Event, ready to be pushed into MISP.

| use-case | what you get |
|---|---|
| **CTI info extraction** | high-confidence MISP attributes read out of the report — IPs, domains, hashes, CVEs, plus `file` / `vulnerability` objects — each one refanged, deduplicated against the event, and carrying the quote it came from |
| **Summarization** | a new `EventReport` with an executive summary, either of one report or of the whole event |
| **none** (default) | pass-through, no LLM call at all |

Three properties matter more than the feature list:

- **MISP Event in → MISP Event out.** No side format, no bespoke JSON contract to integrate.
- **Everything the LLM produced is tagged**, verbatim, with
  `ai-computer-assisted:assistance-level="ai-generated"` and
  `ai-computer-assisted:review-level="unreviewed"`. Nothing the model made can quietly pass as
  analyst work, and existing event content is never modified or re-tagged.
- **Bring your own model.** Any OpenAI-compatible chat endpoint — a local Ollama on your own GPU,
  vLLM, or a commercial API. Prompts and sampling parameters are not hardcoded: they ship as a
  MISP galaxy you can edit and version ([docs/PROMPTS.md](docs/PROMPTS.md)).

- module name: `generic_ai` · module type: `expansion`
- input: a full MISP Event (see *Input shapes*)
- output: the processed MISP Event, a second MISP Event built from the report, and the report markdown

## Why you need it

CTI arrives as prose. A vendor PDF, an ORKL report, a blog post — a human reads it, then retypes
the indicators into MISP one by one and writes a summary for the people who will not read the
full report. That work is slow, it is boring, and it is exactly where indicators get dropped or
mistyped.

This module does the mechanical part and leaves the judgement to you:

- **Less retyping.** The indicators in the report become MISP attributes with the right type and
  category, defanged spellings (`hxxp://`, `1.2.3[.]4`) resolved back to real values.
- **Faster triage.** An event-level summary tells an analyst whether this event is worth opening.
- **Auditable, not magic.** Every generated element is tagged as AI-generated and unreviewed, so
  you can filter, review or purge it later. Precision is measured, not asserted: there is an
  extraction precision gate against hand-checked indicator lists and a benchmark suite
  ([docs/BENCHMARKS.md](docs/BENCHMARKS.md)).
- **Your data stays where you put it.** Point it at a local model and no report ever leaves your
  network.
- **No lock-in.** It is a plain misp-modules expansion module and a small Python package; the only
  third-party dependency is PyMISP.

## Getting started

New here? Follow **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** — install, configure an
LLM endpoint, run the module and get your first summary and extraction out of a real event, in a
few copy-pasteable commands.

## For developers

Everything below is the working documentation of the repository: data flow, layout,
how to run the module locally, and the test and quality gates.


### Documentation

| document | content |
|---|---|
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | install, configure, first summary and extraction |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | data flow, schema provenance, planned hooks |
| [docs/USE-CASES.md](docs/USE-CASES.md) | the three use-cases (CTI info extraction, summarization, tag suggestion) and their configuration |
| [docs/PROMPTS.md](docs/PROMPTS.md) | prompts shipped as a MISP galaxy, v1 prompt texts |
| [docs/TESTING.md](docs/TESTING.md) | test layers, per-use-case test plan, deterministic summaries |
| [docs/requirements.md](docs/requirements.md) | EARS requirements with status |
| [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md) | repository analysis and backlog |
| [docs/BENCHMARKS.md](docs/BENCHMARKS.md) | extraction benchmark: method, commands, results |
| [docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md) | how MISP users will reach the module (research + recommendation, not started) |
| [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md) | contributor and agent guidance |

### Data flow

```text
POST /query {"module": "generic_ai", "event": {"Event": {...}}}
   │
   ├─ 1. _extract_event()        accept "event" or "data"[0], unwrap {"Event": ...}
   ├─ 2. validate_event()        PyMISP MISPEvent.load()  → error dict on invalid input
   ├─ 3. event                   the validated pymisp.MISPEvent
   ├─ 4. get_event_report()      event_report = markdown of all non-deleted EventReports ("" if none)
   ├─ 5. process_event(event)             → MISPEvent   (dummy: returns event unchanged)
   │     process_eventReport(event_report) → MISPEvent   (dummy: new event holding the markdown)
   └─ 6. response
        {"results": {"Event": {"Event": ...}, "ReportEvent": {"Event": ...}},
         "event_report": "<markdown>"}
```

`process_event()` runs the configured use-case ([docs/USE-CASES.md](docs/USE-CASES.md)):

| `use_case` | what happens | where |
|---|---|---|
| `none` (default) | pass-through, no LLM call | |
| `extraction` | high-confidence MISP attributes from the EventReport, AI-tagged per attribute | `genai/extract.py` |
| `summarization` | `summary_kind: report` or `event` → new AI-tagged EventReport, event tagged | `genai/summarize.py` |

The LLM comes from `.env` (`OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`; any
OpenAI-compatible chat endpoint). Prompts and sampling parameters come from the
`generic-ai-prompts` galaxy in `galaxies/` + `clusters/` ([docs/PROMPTS.md](docs/PROMPTS.md)).

```bash
jq -c '{module: "generic_ai", use_case: "summarization", summary_kind: "report", event: .}' fixtures/summary/dummy-event.json \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{summary: .results.Event.Event.EventReport[-1].content, tags: [.results.Event.Event.Tag[].name], meta: .metadata}'
```

#### Input shapes

Both are accepted and equivalent:

| shape | body |
|---|---|
| direct | `{"module": "generic_ai", "event": {"Event": {...}}}` (bare `{...}` without the wrapper works too) |
| export-module style | `{"module": "generic_ai", "data": [{"Event": {...}}]}` (what misp-modules sends to export modules) |

#### Validation

PyMISP is the validator: bad dates, distributions outside 0–5, an `EventReport` without a
`name`, unknown attribute types, a missing `info` and similar problems come back as
`{"error": "Invalid MISP Event: ..."}`.

One normalisation happens before loading: MISP's `/events/view` output sets `distribution` and
`sharing_group_id` on *default* galaxy clusters, which PyMISP refuses. The module drops those two
keys on default clusters so real API output validates. Nothing else is altered.

Why not a JSON schema? The RFC's embedded schema (MISP `format/2.5/schema.json`) does not define
`EventReport` and has `additionalProperties: false` on Event, so it rejects every event that
carries a report. See docs/ARCHITECTURE.md, "Schema provenance".

### Repository layout

```text
.
├── expansion/generic_ai.py        the module (misp-modules contract, validation, dispatch)
├── genai/                         llm.py (HTTP + LLM client), prompts.py (galaxy + tags), extract.py, summarize.py, suggest.py (misp-tag-suggest client)
├── galaxies/ · clusters/          the generic-ai-prompts MISP galaxy
├── fixtures/summary/dummy-event.json  hand-written event for deterministic summary tests
├── fixtures/gold/*.iocs.json      hand-checked indicator lists for the extraction precision gate
├── tests/golden/summary-*.md      recorded summaries (model digest + prompt hash in the header)
├── fixtures/output/*.json         8 real MISP events (5 with EventReports), used by all tests
├── fixtures/output/hashes.csv     md5 → event uuid map of the fixture set
├── tests/conftest.py              fixture loading + read-only MISP client (MispApi)
├── tests/test_generic_ai_unit.py  in-process tests of the handler
├── tests/test_generic_ai_e2e.py   real misp-modules server + live MISP instance + use-cases
├── tests/test_usecases_unit.py    use-cases with a mocked LLM
├── tests/test_llm_live.py         determinism, extraction precision, summary gate + goldens
├── tests/test_suggest_live.py     tag suggestion against the running misp-tag-suggest service
├── tests/test_e2e_roundtrip.py    round-trip quality gate on 10 random live events
├── tests/misp_compare.py          semantic MISP-event comparison used by the gate
├── tests/e2etests/                events written by process_event(..., e2etest=True)
├── logs/                          e2e server log
├── docs/                          all documentation (see above)
├── CHANGELOG.md · AGENTS.md · CLAUDE.md
└── pyproject.toml
```

### Setup

Python 3.14 and [uv](https://docs.astral.sh/uv/). A `.venv` is expected at the repo root.

```bash
uv pip install --python .venv/bin/python -e ".[dev,e2e]"
```

### Run

```bash
.venv/bin/python -m misp_modules -c . -l 127.0.0.1 -p 6666
```

### Verify

```bash
curl -s http://127.0.0.1:6666/modules | jq '.[] | select(.name=="generic_ai")'
```

```bash
jq -c '{module: "generic_ai", event: .}' fixtures/output/10a94632-a0a1-4062-a3a5-95fe321ae045.json \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{uuid: .results.Event.Event.uuid, report: .event_report[:120]}'
```

Expected: the input uuid echoed back and the first 120 characters of the report markdown.

### Tests

```bash
.venv/bin/pytest -q                                   # offline layers; live layers skip
MISP_VERIFY_SSL=false .venv/bin/pytest -q --require-live   # the pre-tag run: live layers MUST run
```

Layers (details in [docs/TESTING.md](docs/TESTING.md)):

- unit tests: every fixture event validates and round-trips; input shapes; report extraction; error cases; extraction and summarization with a mocked LLM, tag suggestion with a fake service; refang, metrics, benchmark tooling
- e2e, local: starts `misp-modules` on a free port and POSTs every fixture event to `/query`
- live LLM (`-m live_llm`): determinism, extraction precision gate, summary gate and goldens against the endpoint in `.env`
- live tag suggestion (`-m live_suggest`, `tests/test_suggest_live.py`): one fixture event through the misp-tag-suggest service; every suggested tag must exist on the dev MISP and the event carries the AI tags (or the service abstained and nothing changed)
- live MISP (`-m live_misp`): fetches the fixture uuids from `MISP_BASE_URL`, runs them through the module, and the round-trip quality gate on 10 random events
- live write path (`tests/test_e2e_misp_write.py`, needs both): creates an event on the dev MISP with an orkl.eu report (`tests/fixtures/orkl/`) as EventReport, runs extraction, summarization and tag suggestion through the module, pushes the result back with PyMISP, verifies the attributes, the new report, the suggested tags and the `ai-computer-assisted` tags on the instance, then deletes the event. Every such event is distribution "your organisation only" and never published; `E2E_KEEP=1` keeps it for inspection.

Every run ends with a **live gates** summary (`llm: ran …` / `skipped: …` / `not requested`).
Without `--require-live` an unavailable live system skips its layer, so a green run only proves
the offline layers; with `--require-live` the same situation **fails** the run. Use it before
every tag and whenever you claim "all tests pass".

#### Live systems (MISP and LLM server)

Both are configured in `.env` at the repo root (gitignored; the last definition of a key wins):

| key | used by | example |
|---|---|---|
| `MISP_BASE_URL`, `MISP_API_KEY` | live MISP tests, round-trip gate (read-only) | `https://misp-dev.example.org`, an API key of a user who can read events |
| `MISP_VERIFY_SSL` | tests only | `false` for a self-signed dev certificate (never used by the module) |
| `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY` | the module and the live LLM tests | `http://nanu:11434/v1`, `qwen3.8:latest`, empty for Ollama |
| `MISP_TAG_SUGGEST_URL`, `MISP_TAG_SUGGEST_API_KEY` | the `tag_suggestion` use-case and its live tests | `http://127.0.0.1:8000`, the service's `SUGGEST_API_KEY` (empty when unset) |

LLM server: any OpenAI-compatible chat endpoint. The reference setup is Ollama on a GPU host
with the model pulled once (`ollama pull qwen3.8`); the goldens and benchmarks are pinned to
that model's digest and the Ollama version (`curl $OPENAI_BASE_URL/../api/version`). Ollama
serialises requests: do not run the live tests while a benchmark is running, the tests would
hit the module's 120 s timeout. Check reachability with:

```bash
.venv/bin/python -c "from genai import llm; s=llm.LLMSettings.from_env(); print(s, llm.is_reachable(s))"
```

Tag-suggestion service: [misp-tag-suggest](https://github.com/ctitools/misp-tag-suggest),
a read-only FastAPI service with a BGE nearest-event index built from the same MISP. It runs as
its own process (it needs torch and faiss; this repo allows only pymisp) next to the
misp-modules server, one worker, loopback. Its README covers export, index build and start
(`MODEL_DEVICE=cpu uv run uvicorn app:app --port 8000`); the nanu deployment with GPU is
written up in [docs/DEPLOY_TAG_SUGGEST.md](docs/DEPLOY_TAG_SUGGEST.md). Check reachability with:

```bash
.venv/bin/python -c "from genai import suggest; s=suggest.SuggestSettings.from_env(); print(s, suggest.is_reachable(s))"
```

MISP: a reachable instance and an API key. The read-only layers only fetch; the write-path
test creates and deletes its own org-only, unpublished events. Four of the eight fixture
uuids no longer exist on the CIRCL dev instance and skip individually (a data problem, not a
missing system; they stay skips even with `--require-live`).

#### Round-trip quality gate

Before real AI logic lands in `process_event()`, this proves the processing path does not
corrupt events. `process_event(event, e2etest=True)` writes the processed event to
`tests/e2etests/<uuid>.json`; the gate fetches **10 random events** from the MISP instance in
`.env`, runs each through `validate_event()` and `process_event(..., e2etest=True)`, and asserts
that the file is semantically identical to the original.

```bash
MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_e2e_roundtrip.py
```

The seed and the chosen uuids are printed and saved to `tests/e2etests/last_run.json`; reproduce
a run with `E2E_SEED=<seed>`. The test skips when the instance is not configured or unreachable.

"Semantically identical" is defined in [tests/misp_compare.py](tests/misp_compare.py), because a
PyMISP load → to_json round trip is not byte-identical. Tolerated: null/empty values, `"1"` vs
`1`, whitespace, ISO date-time spelling (`+0000` vs `+00:00`), and four allowlisted paths that
PyMISP normalises (default galaxy-cluster `distribution`/`sharing_group_id`, filled-in
`ObjectReference.object_uuid`, the `_canEdit` UI flag, opinions on related events). Everything
else — a changed value, a dropped attribute, a lost timestamp — fails the gate and is printed
with its path.

Lint before pushing:

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check expansion genai tests benchmarks && .venv/bin/pylint expansion genai tests benchmarks
```

### Development host

The sandboxed development host from `.env` can run the same loop. Mirror the tree and run pytest there:

```bash
set -a && source .env
rsync -az --delete --exclude '.git' --exclude '.env' --exclude '.venv' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude '.ruff_cache' \
  ./ "${DEVELOPER_USER}@${DEVELOPER_HOST}:${DEVELOPER_HOST_DIRECTORY}/generic-ai-misp-module/"
ssh "${DEVELOPER_USER}@${DEVELOPER_HOST}" 'export PATH="$HOME/.local/bin:$PATH" && cd "'"${DEVELOPER_HOST_DIRECTORY}"'/generic-ai-misp-module" && uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python -e ".[dev,e2e]" && .venv/bin/pytest -q'
```
