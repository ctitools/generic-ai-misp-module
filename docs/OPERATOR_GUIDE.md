# Operator guide

**Who this is for:** whoever installs, runs and keeps the generic AI MISP module alive next to a
MISP instance. It goes from an empty directory to a running module, then to running it in
production: what to configure, what you can measure, what the failures look like and what to do
about them.

**The other two guides:** [USER_GUIDE.md](USER_GUIDE.md) explains what it does ·
[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) explains how to change it.

Every command is copy-pasteable from the repository root.

---

## Part 1 — Get it running

### 1.1 What you need

| | |
|---|---|
| Python `3.14` and [uv](https://docs.astral.sh/uv/) | the runtime |
| an OpenAI-compatible chat endpoint | [Ollama](https://ollama.com/) on a GPU host (`ollama pull qwen3.8`), vLLM, or a commercial API |
| a MISP instance | optional for the module itself; needed to read real events and push results back |
| a host that can reach both | the module is a small stateless HTTP responder; the model does the work |

Reference deployment (all numbers in this repository come from it): the module on a laptop or
on the CIRCL developer host, `qwen3.8:latest` on Ollama 0.33.2 on a 2× RTX 4090 host, a MISP
2.5 dev instance. Sizing: see [4.4](#44-capacity-timing-and-timeouts).

The module has one third-party runtime dependency, `pymisp`.

### 1.2 Install

```bash
git clone https://github.com/ctitools/generic-ai-misp-module.git && cd generic-ai-misp-module
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -e ".[dev,e2e]"
```

`.[dev,e2e]` also pulls in `misp-modules`, pytest and the linters, so the same checkout can run
the module in a real misp-modules server and run the test suite.

### 1.3 Configure

Endpoints, keys and the model are read from a `.env` file **next to the code** (the repository
root), never from a request. The module finds it relative to its own location, so the working
directory of the server process does not matter. Real environment variables override `.env`.

```bash
cat > .env <<'ENV'
# --- LLM: any OpenAI-compatible /v1 endpoint ---
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen3.8:latest
OPENAI_API_KEY=

# --- MISP (optional: live tests, reading and writing real events) ---
MISP_BASE_URL=https://misp.example.org
MISP_API_KEY=
MISP_VERIFY_SSL=true

# --- tag suggestion (optional: the misp-tag-suggest service, part 3) ---
MISP_TAG_SUGGEST_URL=
MISP_TAG_SUGGEST_API_KEY=
ENV
chmod 600 .env
```

| key | used by | note |
|---|---|---|
| `OPENAI_BASE_URL` | the module | must end in the OpenAI-compatible root, e.g. `.../v1` |
| `OPENAI_MODEL` | the module | must exist on that endpoint |
| `OPENAI_API_KEY` | the module | empty for a local Ollama |
| `GENERIC_AI_REQUEST_TIMEOUT` | the module | seconds per model call, default 120; see [4.4](#44-capacity-timing-and-timeouts) |
| `GENERIC_AI_<SETTING>` | the module | default for any setting in [2.1](#21-settings) (e.g. `GENERIC_AI_USE_CASE`) |
| `MISP_TAG_SUGGEST_URL`, `MISP_TAG_SUGGEST_API_KEY` | the module (tag suggestion) | see part 3 |
| `MISP_BASE_URL`, `MISP_API_KEY`, `MISP_VERIFY_SSL` | the **tests and benchmarks** only | the module itself never talks to MISP |

Rules that matter:

- `.env` is gitignored. Keep it out of git and readable only by the service user.
- It follows shell semantics: **the last definition of a key wins**. Duplicate lines are a
  common cause of "it used the wrong model".
- `MISP_VERIFY_SSL=false` is a *test* switch for a self-signed dev certificate. The module never
  reads it.

Check that the model answers:

```bash
.venv/bin/python -c "from genai import llm; s=llm.LLMSettings.from_env(); print(s, llm.is_reachable(s))"
```

Expected: the settings with the API key masked, and `True`.

### 1.4 Run

```bash
.venv/bin/python -m misp_modules -c . -l 127.0.0.1 -p 6666
```

`-c .` points misp-modules at this repository as its custom-module root; `-l` and `-p` are the
listen address and port. Add `-d` for debug logging ([4.2](#42-logs-what-exists-and-where)).

Under a supervisor — a minimal systemd unit for a checkout in `/opt/generic-ai-misp-module`
(not shipped in this repository, adapt to your conventions):

```ini
[Unit]
Description=misp-modules with the generic AI MISP module
After=network-online.target

[Service]
User=misp-modules
WorkingDirectory=/opt/generic-ai-misp-module
ExecStart=/opt/generic-ai-misp-module/.venv/bin/python -m misp_modules \
          -c /opt/generic-ai-misp-module -l 127.0.0.1 -p 6666
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Bind to loopback unless something else needs the port: `/query` executes model calls for anyone
who can reach it.

### 1.5 Verify

The server exposes `/modules`, `/query`, `/healthcheck`, `/version`, `/openapi.json` and a
Swagger UI on `/openapi`.

```bash
curl -s http://127.0.0.1:6666/healthcheck                                   # {"status":true}
curl -s http://127.0.0.1:6666/modules | jq '.[] | select(.name=="generic_ai") | {name, meta: .meta.version}'
```

**a) Pass-through** — no model involved; proves validation and the round trip:

```bash
jq -c '{module: "generic_ai", event: .}' fixtures/output/10a94632-a0a1-4062-a3a5-95fe321ae045.json \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{uuid: .results.Event.Event.uuid, report: .event_report[:120]}'
```

**b) Summarization** — a new, AI-tagged `EventReport` is appended to the event:

```bash
jq -c '{module: "generic_ai", use_case: "summarization", summary_kind: "report", event: .}' fixtures/summary/dummy-event.json \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{summary: .results.Event.Event.EventReport[-1].content, tags: [.results.Event.Event.Tag[].name], meta: .metadata}'
```

**c) CTI info extraction** — the shipped dummy event already contains every indicator its report
mentions (all of them would be rejected as duplicates), so build an event from one of the
orkl.eu reports in `tests/fixtures/orkl/`:

```bash
jq -n --rawfile r tests/fixtures/orkl/40301ca4-fed9-4b59-95ba-b668eb8eb7aa.txt \
  '{module: "generic_ai", use_case: "extraction", event: {Event: {info: "extraction walkthrough", EventReport: [{name: "report", content: $r}]}}}' \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{attributes: [.results.Event.Event.Attribute[] | {type, value, comment}], added: .metadata.added, rejected: [.metadata.rejected[] | .reason]}'
```

**d) Tag suggestion** — needs part 3 first:

```bash
jq -c '{module: "generic_ai", use_case: "tag_suggestion", suggest_limit: 5, event: .}' fixtures/output/10a94632-a0a1-4062-a3a5-95fe321ae045.json \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{tags: [.results.Event.Event.Tag[].name], added: .metadata.added, abstained: .metadata.abstained}'
```

### 1.6 Check the installation with the test suite

```bash
.venv/bin/pytest -q                                        # offline layers; live layers skip
MISP_VERIFY_SSL=false .venv/bin/pytest -q --require-live    # live layers MUST run (pre-deployment run)
```

Every run ends with a **live gates** line saying whether the LLM, MISP and tag-suggestion gates
ran or were skipped. A green run without `--require-live` only proves the offline layers.
Details: [TESTING.md](TESTING.md).

---

## Part 2 — Configure the behaviour

### 2.1 Settings

Every key below is a misp-modules `moduleconfig` entry — settable per MISP instance as
`Plugin.Enrichment_generic_ai_<key>` — and, except `request_timeout`, also per request.

| key | default | meaning |
|---|---|---|
| `use_case` | `none` | `none` (pass-through), `extraction`, `summarization`, `tag_suggestion` |
| `summary_kind` | `report` | `report` (summarise the event report) or `event` (summarise the whole event) |
| `min_confidence` | `0.9` | extraction: drop indicators the model is less sure about |
| `suggest_limit` | `5` | tag suggestion: how many tags to ask for (1..10) |
| `suggest_min_score` | `0.0` | tag suggestion: minimum vote score to accept |
| `model_id` | `OPENAI_MODEL` | override the model for one call; must exist on the endpoint |
| `prompt_extraction`, `prompt_summary_report`, `prompt_summary_event` | the bundled galaxy cluster | a cluster uuid, a cluster value, or inline prompt text |
| `request_timeout` | `120` s | seconds per model call — **settings only, never from a request** |

Precedence: **request body > module config > `.env` (`GENERIC_AI_<KEY>`) > built-in default.**

`api_base` and `api_key` are deliberately **not** settable, from either place. They come from
`.env` only, so no caller can point the module at another endpoint or read your key into a
prompt.

Sampling parameters (temperature, seed, top_p, max_tokens, think) are not settings: they travel
with the prompt in its galaxy cluster, so a prompt is always paired with the parameters it was
validated with ([PROMPTS.md](PROMPTS.md)).

### 2.2 How callers reach the module today

`POST http://<host>:6666/query` on the misp-modules server, with the event in the body:

```json
{"module": "generic_ai", "use_case": "summarization", "summary_kind": "report",
 "event": {"Event": {"info": "...", "EventReport": [{"name": "...", "content": "..."}]}}}
```

The event may also be sent as `{"data": [{"Event": {...}}]}` (the export-module shape), and the
`{"Event": ...}` wrapper may be omitted.

**MISP's own UI does not offer this module.** MISP selects expansion modules per attribute type
and has no path that sends a whole event to one; its `/modules/queryEnrichment` proxy only
forwards to modules that declare `hover`, which an LLM call must not. So today the callers are
scripts, workflows you write, and the test suite. The researched plan for real UI integration is
[INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) (not started). A complete scripted round trip —
create an event, run the use-cases, push the result back with PyMISP, verify the tags on the
instance — exists as a test and is the worked example: `tests/test_e2e_misp_write.py`.

---

## Part 3 — Connect the tag-suggestion service

`use_case: tag_suggestion` does not use the LLM. It asks
[misp-tag-suggest](https://github.com/ctitools/misp-tag-suggest), a separate read-only service
that indexes your already-tagged events and votes on the tags of the most similar ones. It is a
separate process because it needs torch and faiss; this module stays pymisp-only.

**a) Get the service running** — follow its README on a host that can reach your MISP: export
events, snapshot the taxonomies, build the dataset, build the index, start the API. The short
version:

```bash
git clone https://github.com/ctitools/misp-tag-suggest.git && cd misp-tag-suggest
uv sync
cp .env.example .env    # MISP_BASE_URL, MISP_API_KEY, MISP_VERIFY_SSL: the same keys as this repo's .env
uv run python -m scripts.export_events --workers 1
uv run python -m scripts.snapshot_taxonomy
uv run python -m scripts.build_dataset --skip-near-dedup && uv run python -m scripts.validate_dataset
uv run python -m retrieval.build_index --device cpu      # or --device cuda, see its README for GPU torch
SUGGEST_API_KEY=change-me MODEL_DEVICE=cpu uv run uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

```bash
curl -s http://127.0.0.1:8000/health      # expect "artifacts_ready": true
```

**b) Point the module at it** — two lines in this repository's `.env`:

```dotenv
MISP_TAG_SUGGEST_URL=http://127.0.0.1:8000
MISP_TAG_SUGGEST_API_KEY=change-me
```

**c) Check the connection:**

```bash
.venv/bin/python -c "from genai import suggest; s=suggest.SuggestSettings.from_env(); print(s, suggest.is_reachable(s))"
```

Operational notes: the index is **stateful** — it is the one thing here worth backing up, and it
must be rebuilt when your taxonomy or event corpus moves on. Only tags that exist on your MISP
can come back, because the index is built from your own taxonomy snapshot. Abstention is normal,
not an error. A full deployment with GPU, the index-build numbers and the run log is
[DEPLOY_TAG_SUGGEST.md](DEPLOY_TAG_SUGGEST.md).

---

## Part 4 — Operate it

### 4.1 The per-request `metadata` block: your metrics

The module writes no metrics of its own. Every `/query` answer carries a `metadata` object
describing exactly what happened — this is the surface to log, count and alert on.

Always present when a use-case ran:

| field | meaning |
|---|---|
| `use_case` | which job ran |
| `prompt` | `{cluster, uuid, version, sha256}` — which prompt version produced this |
| `model` | `{name, server, digest, quantization}` (digest/quantisation for Ollama) or, for tag suggestion, the service version and URL |

Extraction adds:

| field | meaning |
|---|---|
| `added` | indicators stored |
| `objects` | `file` / `vulnerability` objects created |
| `rejected` | every dropped candidate with `type`, `value` and a `reason` (`not-in-source`, `quote-mismatch`, `unknown-type`, `free-text-type`, `format`, `duplicate`, `confidence`) |
| `refanged`, `retyped` | values whose defanged spelling was resolved · hashes re-typed by length |
| `dated`, `dates_unparsed` | indicators that got a date from the text · dates the parser refused as ambiguous |
| `not_actionable` | indicators whose `to_ids` was lowered because the report marks them as context |
| `published` | a publication date stated by the report (informational; never applied to indicators) |

Summarization adds: `kind`, `report_name`, `words`, `input_chars`.

Tag suggestion adds: `added` (tag + score), `skipped_existing`, `below_min_score`, `abstained`,
`model_version`, `dataset_manifest_sha256`.

Counting rejections by reason across a batch of stored answers:

```bash
jq -r '.metadata.rejected[]?.reason' answers/*.json | sort | uniq -c | sort -rn
```

A healthy extraction run has most rejections under `format`, `confidence` and `duplicate`.
A rising share of `not-in-source` means the model is inventing values — check the prompt version
and the model in the same `metadata`.

### 4.2 Logs: what exists and where

**The module itself writes no log lines.** It answers, and its answer carries the metadata
above. Everything you see in a log comes from the processes around it:

| source | where | what you get |
|---|---|---|
| misp-modules server | **stderr** of the process (`journalctl -u <unit>`, or your redirect) | `2026-09-05 12:00:00,000 - misp-modules - INFO - …`, one tornado access line per request with status and duration, warnings and full tracebacks |
| misp-modules with `-d` | same | additionally `QueryModule generic_ai request <full payload>` — **the whole event, including the report text**. Useful for debugging, unsuitable for permanent production logging |
| the LLM server | its own log (`journalctl -u ollama`) | model load, per-request duration, out-of-memory and context problems |
| misp-tag-suggest | its `logs/service.log` | uvicorn access log, index state |
| MISP | its own logs | anything MISP does with the result — the module never writes to MISP |

`logs/` **in this repository** is for benchmark and test runs (progress, rows/s, failures), not
for production. Nothing writes there at request time.

Practical setup: run the server under a supervisor that captures stderr, keep it at INFO,
and store the JSON answers (or just their `metadata`) of the calls you make — that pair covers
both "was there an error" and "what did it do".

### 4.3 Health checks and monitoring

```bash
curl -sf http://127.0.0.1:6666/healthcheck                                    # server alive
curl -s http://127.0.0.1:6666/modules | jq -e '.[] | select(.name=="generic_ai")' >/dev/null   # module loaded
.venv/bin/python -c "from genai import llm; s=llm.LLMSettings.from_env(); exit(0 if llm.is_reachable(s) else 1)"   # model reachable
curl -sf http://127.0.0.1:8000/health | jq -e '.artifacts_ready'              # tag suggestion ready
```

Worth alerting on, in this order: the module missing from `/modules` (a syntax error in a file
under `expansion/` removes it silently), the LLM endpoint unreachable, a rising rate of
`{"error": ...}` answers, and answer latency above your timeout budget.

An end-to-end probe that exercises the whole chain is call **b)** from [1.5](#15-verify)
against the shipped dummy event: it is deterministic, needs no MISP, and either returns a
summary or tells you what broke.

### 4.4 Capacity, timing and timeouts

Measured on the reference deployment (`qwen3.8`, 2× RTX 4090):

| | median | worst observed |
|---|---|---|
| extraction, one orkl.eu report | 9 s | 67 s |
| summarization, report kind | 4.7 s | 9.2 s |
| summarization, event kind | 5.1 s | 13.4 s |
| tag suggestion (GPU service) | 0.44 s | |

Three timeouts stack, and they must be ordered correctly:

1. **the model call** — module setting `request_timeout`, default **120 s**
   (`GENERIC_AI_REQUEST_TIMEOUT` in `.env`);
2. **the misp-modules server** — `timeout` in the request body, default **300 s**; on expiry the
   server answers `{"error": "Timeout."}` and logs `Timeout on generic_ai`;
3. **your client**.

Indicator-rich reports can need far more than 120 s (the benchmarks run with
`GENERIC_AI_REQUEST_TIMEOUT=900`). If you raise the module timeout above 300 s, **also send
`"timeout": <seconds>` in the request body**, or the server will cut the call off first.

Concurrency: the misp-modules server handles requests in a thread pool, but a single Ollama
instance **serialises** them — parallel calls queue and each one's wall-clock time grows toward
the timeout. Size for one call in flight per model server, and never run benchmarks and live
tests against the same Ollama at once.

### 4.5 Failure modes

Every failure is an explicit `{"error": "..."}`; there is no fallback output and nothing is
tagged as AI-generated when no model ran.

| error | what happened | what to do |
|---|---|---|
| `Invalid MISP Event: …` | PyMISP rejected the input (bad date, `distribution` outside 0–5, an `EventReport` without a `name`, unknown attribute type, missing `info`) | fix the caller's payload; the message names the field |
| `Invalid JSON request: …` | the body is not JSON | caller bug |
| `This module requires a MISP Event under "event" or "data".` | no event in the body | caller bug |
| `unknown use_case …` / `unknown summary_kind …` | typo in a setting or request key | the message lists the allowed values |
| `the event has no EventReport to extract from` / `nothing to summarise for kind='report'` | the event carries no (non-deleted) report | use `summary_kind: event`, or attach a report |
| `LLM endpoint unreachable or timed out (Ns): …` | the model host is down, or the answer took longer than `request_timeout` | check the LLM server; raise `GENERIC_AI_REQUEST_TIMEOUT` (and the body `timeout`) for long reports |
| `LLM endpoint returned HTTP 404: …` | the model name does not exist on the endpoint | fix `OPENAI_MODEL` / `model_id` |
| `LLM endpoint returned HTTP 401/403: …` | wrong or missing `OPENAI_API_KEY` | fix `.env` |
| `LLM answer was truncated (max_tokens too small)` | the answer exceeded the prompt cluster's budget — expect this on the most indicator-rich reports (5 of 100 in the benchmark) | nothing to configure per request: the budget lives in the prompt cluster ([PROMPTS.md](PROMPTS.md)) |
| `LLM answer was empty` / `LLM answer had no message content` | the model returned nothing usable, often a reasoning model spending its budget on thinking | check the model and its cluster parameters (`think`) |
| `extraction answer is not JSON` / `extraction answer must be {"indicators": [...]}` | the model ignored the output schema | usually a model/prompt mismatch: check that the cluster's model matches `OPENAI_MODEL` |
| `summary failed the structural check: …` | the summary broke a rule (missing heading, over the word limit, an indicator that is not in the input) — **the gate working as intended** | if it happens often, the model or prompt version does not fit; see the benchmark reports |
| `misp-tag-suggest: endpoint unreachable or timed out …` | the service is down or still loading its index | `curl /health`; `artifacts_ready` must be true |
| `misp-tag-suggest: endpoint returned HTTP 401` | `MISP_TAG_SUGGEST_API_KEY` does not match the service's `SUGGEST_API_KEY` | fix `.env` |
| `MISP_TAG_SUGGEST_URL is not set in .env …` | tag suggestion requested but not configured | part 3 |
| `Timeout.` | the **server-side** timeout hit before the module answered | [4.4](#44-capacity-timing-and-timeouts): send `"timeout"` in the body |
| `Something went wrong, look in the server logs for details` | an unhandled exception inside misp-modules | the traceback is on the server's stderr; please report it with the payload |
| the module is missing from `/modules` | a file under `expansion/` failed to import | start the server in the foreground and read the import error |

### 4.6 Security posture

- **Configuration is not caller-controlled.** `api_base` and `api_key` can never be set from a
  request; only the keys in [2.1](#21-settings) can, and `request_timeout` not even from there.
- **Outbound requests are restricted** to `http(s)` URLs from your own configuration; there is
  one HTTP function in the code and it refuses anything else.
- **TLS verification is on** for the module's own calls. `MISP_VERIFY_SSL=false` affects tests
  only.
- **Report text is untrusted input.** Extraction is protected by construction — a value that is
  not literally in the report is dropped — but a *summary* can echo text from a hostile report,
  and prompt injection has no dedicated test fixture yet (open work,
  [IMPROVEMENTS.md](IMPROVEMENTS.md) item 30). Treat summaries of untrusted reports as
  untrusted text.
- **No TLP guard yet.** Nothing stops a restricted report from being sent to whichever endpoint
  is configured (requirement R9.4, *future*). Choose the endpoint accordingly.
- **Debug logging prints whole events**, report text included ([4.2](#42-logs-what-exists-and-where)).
- **Secrets:** `.env` only, mode 0600. The repository's git history still contains two
  long-rotated keys from an early commit ([IMPROVEMENTS.md](IMPROVEMENTS.md) item 1) — worth
  knowing before mirroring the repository.

### 4.7 Changing the model, the prompt or the index

The output depends on three versioned things: the **model** (name + digest + server version),
the **prompt cluster** (version + sha256) and — for tag suggestion — the **index**. Each answer
records which ones it used, so drift is visible after the fact.

| change | do this |
|---|---|
| new model or new Ollama version | run `MISP_VERIFY_SSL=false .venv/bin/pytest -q --require-live`. Golden summaries are pinned to the model digest and skip when it changes; the structural gate still runs. Re-record goldens deliberately, never automatically ([TESTING.md](TESTING.md) §4) |
| edited prompt | bump the cluster version in `clusters/generic-ai-prompts.json` (never edit a released cluster in place), re-run the live tests and, before a release, the benchmark round ([BENCHMARKS.md](BENCHMARKS.md)) |
| new tag-suggestion index | re-run `benchmarks/run_suggest.py` and compare against the previous numbers; the service's model version travels in the metadata |
| upgraded module | `uv pip install --python .venv/bin/python -e ".[dev,e2e]"`, restart the server, re-run [1.5](#15-verify) |

Rollback is a git checkout plus a restart: the module keeps no state.

## Next

- What the module actually promises per use-case: [USE-CASES.md](USE-CASES.md)
- The prompts, and how to version one: [PROMPTS.md](PROMPTS.md)
- The measured quality of each use-case: [BENCHMARKS.md](BENCHMARKS.md)
- Test layers and gates: [TESTING.md](TESTING.md)
- Changing the code: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
