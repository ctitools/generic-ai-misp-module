# Getting started

From nothing to a summarized and enriched MISP Event in about ten minutes. Everything here is
copy-pasteable from the repository root.

## 1. What you need

| | |
|---|---|
| Python `3.14` and [uv](https://docs.astral.sh/uv/) | the runtime |
| an OpenAI-compatible chat endpoint | e.g. [Ollama](https://ollama.com/) on a GPU host (`ollama pull qwen3.8`), vLLM, or a commercial API |
| a MISP instance (optional) | only needed to read real events and to push results back |

The module itself has one third-party dependency, `pymisp`.

## 2. Install

```bash
git clone https://github.com/ctitools/generic-ai-misp-module.git && cd generic-ai-misp-module
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -e ".[dev,e2e]"
```

`.[dev,e2e]` also pulls in `misp-modules`, pytest and the linters, so you can run the module in a
real misp-modules server and run the test suite.

## 3. Configure the LLM (and, optionally, MISP)

Endpoint, key and model are read from a `.env` file at the repository root — never from a
request. Create it:

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

# --- tag suggestion (optional: the misp-tag-suggest service, section 9) ---
MISP_TAG_SUGGEST_URL=
MISP_TAG_SUGGEST_API_KEY=
ENV
```

`.env` is gitignored — keep your keys out of git. It follows shell semantics: the *last*
definition of a key wins.

Check that the model answers:

```bash
.venv/bin/python -c "from genai import llm; s=llm.LLMSettings.from_env(); print(s, llm.is_reachable(s))"
```

Expected: the settings (the API key is masked) and `True`.

## 4. Run the module

```bash
.venv/bin/python -m misp_modules -c . -l 127.0.0.1 -p 6666
```

`-c .` tells misp-modules to load the custom modules from this repository. In a second terminal:

```bash
curl -s http://127.0.0.1:6666/modules | jq '.[] | select(.name=="generic_ai") | {name, meta: .meta.version}'
```

## 5. Your first four calls

The module takes a **full MISP Event** and gives you a MISP Event back. The `use_case` in the
request body decides what happens.

**a) Pass-through** — no LLM involved, proves the validation and the round trip:

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

**c) CTI info extraction** — high-confidence attributes read out of the report. The dummy
event already carries every indicator its report mentions (the module would reject all of them
as duplicates), so build an event from one of the orkl.eu reports in `tests/fixtures/orkl/`:

```bash
jq -n --rawfile r tests/fixtures/orkl/40301ca4-fed9-4b59-95ba-b668eb8eb7aa.txt \
  '{module: "generic_ai", use_case: "extraction", event: {Event: {info: "extraction walkthrough", EventReport: [{name: "report", content: $r}]}}}' \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{attributes: [.results.Event.Event.Attribute[] | {type, value, comment}], added: .metadata.added, rejected: [.metadata.rejected[] | .reason]}'
```

Expected: a handful of attributes (threat actors, malware names, hashes, domains from the
text), each with `comment: "extracted by generic_ai from EventReport …"` and the two AI tags;
`rejected` lists what the filters dropped and why.

**d) Tag suggestion** — taxonomy/galaxy tags proposed by the
[misp-tag-suggest](https://github.com/ctitools/misp-tag-suggest) service (no LLM; needs
section 9 first):

```bash
jq -c '{module: "generic_ai", use_case: "tag_suggestion", suggest_limit: 5, event: .}' fixtures/output/10a94632-a0a1-4062-a3a5-95fe321ae045.json \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{tags: [.results.Event.Event.Tag[].name], added: .metadata.added, abstained: .metadata.abstained}'
```

Every element the model produced carries
`ai-computer-assisted:assistance-level="ai-generated"` and
`ai-computer-assisted:review-level="unreviewed"`, and `.metadata` tells you what was refanged,
re-typed or rejected. Nothing that was already in the event is modified.

## 6. Knobs

Set them in the request body, or per instance in MISP's module settings
(`Plugin.Enrichment_generic_ai_<key>`):

| key | default | meaning |
|---|---|---|
| `use_case` | `none` | `none`, `extraction`, `summarization`, `tag_suggestion` |
| `summary_kind` | `report` | `report` (summarize the EventReport) or `event` (summarize the whole event) |
| `min_confidence` | `0.9` | extraction: drop indicators the model is less sure about |
| `suggest_limit`, `suggest_min_score` | `5`, `0.0` | tag suggestion: how many tags to ask for (1..10), minimum vote score to accept |
| `model_id` | from `.env` | override the model for one call |
| `prompt_extraction`, `prompt_summary_report`, `prompt_summary_event` | from the galaxy | override a prompt text |
| `request_timeout` | `120` | seconds; settings only, not accepted from a request |

Prompts and sampling parameters normally come from the `generic-ai-prompts` MISP galaxy in
`galaxies/` + `clusters/`, so they are versioned and reviewable — see
[PROMPTS.md](PROMPTS.md).

## 7. Using it from MISP

Today the module is called by POSTing to the misp-modules server directly, as above. The MISP
UI selects expansion modules per attribute type and has no path that sends a whole event to
one, so `generic_ai` is not yet offered in the "Enrich" menus. The research and the
recommendation for a proper UI integration are in [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md).

A complete scripted round trip — create an event on MISP with a CTI report, run extraction and
summarization through the module, push the result back with PyMISP, verify the tags on the
instance — exists as a test: `tests/test_e2e_misp_write.py`. Read it as the worked example.

## 8. Check your installation

```bash
.venv/bin/pytest -q                     # offline layers; anything needing a live system skips
```

With `.env` pointing at a reachable LLM and MISP, the live layers run too:

```bash
MISP_VERIFY_SSL=false .venv/bin/pytest -q --require-live
```

## 9. Connect the tag-suggestion service

`use_case: tag_suggestion` does not use the LLM. It asks
[misp-tag-suggest](https://github.com/ctitools/misp-tag-suggest), a separate read-only
service that finds the most similar previously tagged events of your MISP and votes on their
tags. It is a separate process because it needs torch and faiss; this module stays pymisp-only.

**a) Get the service running.** Follow its README, steps 1 to 8, on a host that can reach your
MISP: export the events, snapshot the taxonomies, build the dataset, build the index, start
the API. The short version, once its prerequisites are met:

```bash
git clone https://github.com/ctitools/misp-tag-suggest.git && cd misp-tag-suggest
uv sync
cp .env.example .env    # MISP_BASE_URL, MISP_API_KEY, MISP_VERIFY_SSL: the same keys as this repo's .env
uv run python -m scripts.export_events --workers 1
uv run python -m scripts.snapshot_taxonomy
uv run python -m scripts.build_dataset --skip-near-dedup && uv run python -m scripts.validate_dataset
uv run python -m retrieval.build_index --device cpu      # or: --device cuda, see its README step 8 for GPU torch
SUGGEST_API_KEY=change-me MODEL_DEVICE=cpu uv run uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

```bash
curl -s http://127.0.0.1:8000/health      # expect "artifacts_ready": true
```

**b) Point this module at it.** Two lines in this repo's `.env`:

```dotenv
MISP_TAG_SUGGEST_URL=http://127.0.0.1:8000
MISP_TAG_SUGGEST_API_KEY=change-me
```

**c) Check the connection**, then run call **5 d)**:

```bash
.venv/bin/python -c "from genai import suggest; s=suggest.SuggestSettings.from_env(); print(s, suggest.is_reachable(s))"
```

```bash
MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_suggest_live.py
```

The service abstains when nothing similar is indexed; then the event comes back unchanged and
`.metadata.abstained` is `true`. Every tag it adds exists on your MISP (the index is built from
your taxonomy snapshot) and the event gets the two `ai-computer-assisted` tags. The full
deployment on the CIRCL developer host, with GPU and the numbers of the first index build, is
in [DEPLOY_TAG_SUGGEST.md](DEPLOY_TAG_SUGGEST.md).

## Where to go next

| | |
|---|---|
| [USE-CASES.md](USE-CASES.md) | what extraction and summarization guarantee, and the tagging rule |
| [ARCHITECTURE.md](ARCHITECTURE.md) | the data flow and why there is no JSON schema |
| [PROMPTS.md](PROMPTS.md) | the prompt galaxy and how to change a prompt |
| [BENCHMARKS.md](BENCHMARKS.md) | how good the extraction and the summaries actually are |
| [TESTING.md](TESTING.md) | the test layers and the quality gates |
| [DEPLOY_TAG_SUGGEST.md](DEPLOY_TAG_SUGGEST.md) | misp-tag-suggest on the developer host and the connection, step by step |
| [../README.md](../README.md) | the developer view of the repository |
