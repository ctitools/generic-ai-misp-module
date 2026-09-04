# AI MISP Module

A custom [misp-modules](https://github.com/MISP/misp-modules) expansion module that takes a
**full MISP Event** ([MISP core format](https://www.misp-standard.org/rfc/misp-standard-core.html)),
validates it, extracts the event's `EventReport` markdown and passes both through two hooks that
will later hold the real AI logic. Today both hooks are dummies.

- module name: `generic_ai`
- module type: `expansion`
- input: a full MISP Event (see *Input shapes*)
- validation: [PyMISP](https://github.com/MISP/PyMISP) (`MISPEvent.load`)
- output: the processed MISP Event, a second MISP Event built from the report, and the report markdown

For the architecture and design history see [ARCHITECTURE.md](ARCHITECTURE.md),
for use cases [USE-CASES.md](USE-CASES.md), for the repo analysis [IMPROVEMENTS.md](IMPROVEMENTS.md).

## Data flow

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

All of this lives in [expansion/generic_ai.py](expansion/generic_ai.py) (about 130 lines).
To add real behaviour, replace the bodies of `process_event()` and `process_eventReport()`.

### Input shapes

Both are accepted and equivalent:

| shape | body |
|---|---|
| direct | `{"module": "generic_ai", "event": {"Event": {...}}}` (bare `{...}` without the wrapper works too) |
| export-module style | `{"module": "generic_ai", "data": [{"Event": {...}}]}` (what misp-modules sends to export modules) |

### Validation

PyMISP is the validator: bad dates, distributions outside 0–5, an `EventReport` without a
`name`, unknown attribute types, a missing `info` and similar problems come back as
`{"error": "Invalid MISP Event: ..."}`.

One normalisation happens before loading: MISP's `/events/view` output sets `distribution` and
`sharing_group_id` on *default* galaxy clusters, which PyMISP refuses. The module drops those two
keys on default clusters so real API output validates. Nothing else is altered.

Why not a JSON schema? The RFC's embedded schema (MISP `format/2.5/schema.json`) does not define
`EventReport` and has `additionalProperties: false` on Event, so it rejects every event that
carries a report. See ARCHITECTURE.md, "Schema provenance".

## Repository layout

```text
.
├── expansion/generic_ai.py        the module
├── fixtures/output/*.json         8 real MISP events (5 with EventReports), used by all tests
├── fixtures/output/hashes.csv     md5 → event uuid map of the fixture set
├── tests/conftest.py              fixture loading
├── tests/test_generic_ai_unit.py  in-process tests of the handler
├── tests/test_generic_ai_e2e.py   real misp-modules server + live MISP instance
├── logs/                          e2e server log
├── CHANGELOG.md · IMPROVEMENTS.md · ARCHITECTURE.md · USE-CASES.md · AGENTS.md
└── pyproject.toml
```

## Setup

Python 3.14 and [uv](https://docs.astral.sh/uv/). A `.venv` is expected at the repo root.

```bash
uv pip install --python .venv/bin/python -e ".[dev,e2e]"
```

## Run

```bash
.venv/bin/python -m misp_modules -c . -l 127.0.0.1 -p 6666
```

## Verify

```bash
curl -s http://127.0.0.1:6666/modules | jq '.[] | select(.name=="generic_ai")'
```

```bash
jq -c '{module: "generic_ai", event: .}' fixtures/output/10a94632-a0a1-4062-a3a5-95fe321ae045.json \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{uuid: .results.Event.Event.uuid, report: .event_report[:120]}'
```

Expected: the input uuid echoed back and the first 120 characters of the report markdown.

## Tests

```bash
.venv/bin/pytest -q
```

- unit tests: every fixture event validates and round-trips; input shapes; report extraction; error cases; the two hooks
- e2e, local: starts `misp-modules` on a free port and POSTs every fixture event to `/query`
- e2e, live: fetches the fixture uuids from `MISP_BASE_URL` with `MISP_API_KEY` (both from `.env`), runs them through the module and compares the report with the fixture. Skipped when `.env` is missing, the key is rejected, or an event is not on the instance. The dev instance has a self-signed certificate; run with `MISP_VERIFY_SSL=false` to accept it (tests only, never the module):

```bash
MISP_VERIFY_SSL=false .venv/bin/pytest -q
```

Lint before pushing:

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check expansion tests && .venv/bin/pylint expansion tests
```

## Development host

The sandboxed development host from `.env` can run the same loop. Mirror the tree and run pytest there:

```bash
set -a && source .env
rsync -az --delete --exclude '.git' --exclude '.env' --exclude '.venv' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude '.ruff_cache' \
  ./ "${DEVELOPER_USER}@${DEVELOPER_HOST}:${DEVELOPER_HOST_DIRECTORY}/generic-ai-misp-module/"
ssh "${DEVELOPER_USER}@${DEVELOPER_HOST}" 'export PATH="$HOME/.local/bin:$PATH" && cd "'"${DEVELOPER_HOST_DIRECTORY}"'/generic-ai-misp-module" && uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python -e ".[dev,e2e]" && .venv/bin/pytest -q'
```
