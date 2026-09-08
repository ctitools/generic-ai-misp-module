# Use-cases

Two LLM use-cases are in focus, plus tag suggestion (UC3) which uses no LLM. All keep the module contract **MISP Event in → MISP Event out**
([ARCHITECTURE.md](ARCHITECTURE.md)) and both send *a prompt plus the event's content* to the
LLM configured in `.env` (`OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`; any
OpenAI-compatible chat endpoint, today Ollama on `nanu`). Prompts and sampling parameters are
configurable and shipped as a MISP galaxy ([PROMPTS.md](PROMPTS.md)). Tests for both are
specified in [TESTING.md](TESTING.md); formal requirements in [requirements.md](requirements.md).

Status: **implemented** in `genai/extract.py`, `genai/summarize.py` and `genai/suggest.py`, dispatched by
`process_event()` in `expansion/generic_ai.py`. The default `use_case` is `none` (pass-through,
no LLM call), so the round-trip gate and plain validation never touch the LLM.

## Rule that applies to every output

Anything the LLM produced is marked with the `ai-computer-assisted` taxonomy, verbatim strings
from a pinned list:

| what the LLM suggested | tags go on | tags |
|---|---|---|
| attributes / objects (UC1) | each new attribute (and object) | `ai-computer-assisted:assistance-level="ai-generated"`, `ai-computer-assisted:review-level="unreviewed"` |
| event-level content: a summary EventReport (UC2), suggested tags (UC3) | the event | same two tags |

Nothing the module adds may leave without these tags. Existing content of the event is never
modified or re-tagged. Content tags (`tlp:*`, kill chain, confidence taxonomy) may only ever be suggested when the
report states them literally; nothing is inferred (IMPROVEMENTS.md item 34, not implemented
yet). Dates follow the same rule and are implemented (step 0 below).

## UC1 — CTI info extraction

`extract_iocs(event: MISPEvent) -> MISPEvent`

| | |
|---|---|
| input | `event_report` = markdown of all non-deleted EventReports of the event (as `get_event_report()` returns it today) |
| output | the same event with new `Attribute`s; `file` / `vulnerability` objects where hashes+filename or CVEs co-occur |
| types | any attribute type of the [MISP core format](https://www.misp-standard.org/rfc/misp-standard-core.html#name-attribute); the machine-readable list is PyMISP's `describeTypes.json` (194 types, 16 categories) |
| policy | **high confidence only**: fewer, certain attributes beat many doubtful ones |

The LLM is asked for structured JSON, one entry per indicator:

```json
[{"type": "ip-dst", "category": "Network activity", "value": "91.200.14.10",
  "confidence": 0.98, "quote": "C2 at 91.200.14.10 and update.example-cdn.net"}]
```

Then deterministic post-filters run, no LLM involved. Two **normalisations** come first and are
the only ones the module performs; both are recorded in the attribute comment and counted in
the response metadata (`refanged`, `retyped`):

0. **Refang**: `hxxp://evil[.]com`, `1.2.3[.]4`, `bad[at]evil[.]com`, markdown-escaped
   `pastebin\.com` become the real value (`genai/refang.py`). MISP stores real values and
   defangs on display; the original spelling is kept as `defanged in source as <raw>`.
   Windows paths and named pipes (`\\.\pipe\x`) are left alone.
   **Hash re-typing**: a hash labelled with the wrong hash type is re-typed by its hex length
   (32 md5, 40 sha1, 64 sha256, 128 sha512), noted as `typed <old> by the model`.
   **Dates**: `first_seen` / `last_seen` are set only from a date the report states for that
   indicator, copied by the model character for character, checked to be in the text, and
   parsed by `genai/dates.py` (unambiguous spellings only: `2026-03-12`, `12 March 2026`,
   `March 12, 2026`; `03/04/2026` is dropped, never guessed). A publication date the report
   states is reported in the metadata only, never applied to indicators (on a live report the
   model took a referenced blog's date for it). Noted as `first_seen from "…"`.
   **`to_ids`**: PyMISP's per-type default, lowered to false when the model marks the
   indicator as not actionable (the reporting organisation's own infrastructure, legitimate
   tools, benign filenames named as context); never raised. Noted as `not actionable per report`.

An indicator is added only if it passes all of the following; every rejection is recorded in
the response metadata:

1. `value` (refanged) is a substring of the refanged source report (case-insensitive,
   whitespace-normalised) — the hallucination guard; `quote` must contain `value` too.
2. `type` exists in `describeTypes.json` and is not a free-text type (`other`, `text`,
   `comment` carry no indicator semantics and are rejected as `free-text-type`); an invalid or
   missing `category` is replaced by the type's default category.
3. A per-type format check for the common types (IPv4/IPv6, domain/hostname, md5/sha1/sha256,
   url, email, CVE id, `ip-src|port`/`ip-dst|port`/`hostname|port`). Types without a check rely on 1–2.
4. Not already on the event (same type + value, including inside objects).

PyMISP is not one of the filters but the last word: it validates each accepted candidate when
the attribute is created, and a value it refuses (e.g. an unparsable date) fails the whole
request instead of being reported as a rejection.

`confidence` is only a gate (`>= min_confidence`, default 0.9); it is not stored.
If the model output is not valid JSON, the request fails with an error — never partial results.

Each added attribute carries the two AI tags and
`comment = "extracted by generic_ai from EventReport <uuid>"`.

## UC2 — Summarization

`summarize(event: MISPEvent, kind: str = "report") -> MISPEvent`

`kind` selects what is summarised:

| `kind` | summarises | attached as |
|---|---|---|
| `report` (default) | the EventReport markdown (`event_report`) | a **new** EventReport "AI summary of *report name*", worded as an analyst assessment |
| `event` | the event's attributes, objects, tags, galaxies and related-event links, rendered by the module into a compact, sorted markdown table (uuids kept) | a **new** EventReport "AI summary of event *uuid*" |

Both never modify existing reports; the event gets the two AI tags. Unknown `kind` → error.

Why a string enum and not a boolean: it reads in config and logs (`summary_kind: event`),
and `both` or `attributes-only` can be added without changing the signature.

How the caller selects it:

```json
{"module": "generic_ai", "event": {"Event": {...}},
 "use_case": "summarization", "summary_kind": "event"}
```

`summary_kind` falls back to the module config `summary_kind`, then to `report`.

Deterministic rendering for `kind=event` matters for testing: attributes sorted by
`(type, value)`, objects by `(name, uuid)`, tags by name, no timestamps, so identical events
produce identical prompts. See TESTING.md "Deterministic summaries".

## UC3 — Tag suggestion

`suggest_tags(event: MISPEvent, settings, limit=5, min_score=0.0) -> metadata`

Not an LLM: the [misp-tag-suggest](https://github.com/ctitools/misp-tag-suggest) service
(BGE nearest-event retrieval over an index of previously tagged events of the same MISP)
proposes taxonomy/galaxy tags by similarity-weighted voting, and abstains when the nearest
indexed event is not similar enough.

| | |
|---|---|
| input | the whole event, serialised with PyMISP and POSTed to `MISP_TAG_SUGGEST_URL/suggest` with `limit` (1..10). The service strips existing tags from its model input itself. |
| output | the same event with the suggested tags added (`event.add_tag`), plus the two AI tags on the event when at least one tag was added |
| filters | `score >= suggest_min_score`; tags already on the event are skipped (recorded as `skipped_existing`) |
| abstention | not an error: no tag, no AI tag, metadata `abstained: true` |
| errors | service unreachable, HTTP error, malformed answer → `{"error": "misp-tag-suggest: …"}`, nothing added |
| metadata | `added` (tag + score), `skipped_existing`, `below_min_score`, `abstained`, `model_version`, `dataset_manifest_sha256`, `model.server` |

Only tags that exist on the target MISP come back: the service's index is built from a
taxonomy snapshot of that instance. Why HTTP and not `import`: the service needs torch,
faiss and sentence-transformers; this repo allows only pymisp and runs inside the
misp-modules server (ARCHITECTURE.md). The call goes through the same stdlib HTTP function as
the LLM (`genai.llm.http_json`); tests fake it.

```json
{"module": "generic_ai", "event": {"Event": {...}},
 "use_case": "tag_suggestion", "suggest_limit": 5, "suggest_min_score": 0.3}
```

## Configuration

All keys are `moduleconfig` entries (settable in MISP's module settings), overridable per
request only for the keys marked *request*. Endpoint and API key are **never** settable from
the request body ([IMPROVEMENTS.md](IMPROVEMENTS.md) item 3).

| key | default | request | meaning |
|---|---|---|---|
| `use_case` | `none` | yes | `none` (pass-through), `extraction`, `summarization` or `tag_suggestion` |
| `summary_kind` | `report` | yes | `report` or `event` |
| `prompt_extraction`, `prompt_summary_report`, `prompt_summary_event` | bundled galaxy cluster | yes | galaxy cluster uuid or `value`, or inline prompt text |
| `model_id` | `OPENAI_MODEL` from `.env` | yes | must exist on the endpoint |
| sampling (`temperature`, `seed`, `top_p`, `max_tokens`, `think`) | from the prompt cluster (`0` / `42` / `1` / per use-case / `false`) | via the cluster | select another cluster to change them |
| `min_confidence` | `0.9` | yes | UC1 gate |
| `suggest_limit`, `suggest_min_score` | `5`, `0.0` | yes | UC3: tags requested (1..10), minimum vote score |
| `request_timeout` | `120` s | no | LLM / service call bound; timeout → error, no fallback |
| `api_base`, `api_key`, `MISP_TAG_SUGGEST_URL`, `MISP_TAG_SUGGEST_API_KEY` | `.env` | **no** | endpoints |

Precedence: request body (allowed keys only) > module config > `.env` > built-in default.

## Not in focus (parked)

Collected during hackathon 2026; kept as one-liners so they are not lost.

- **Tag proposal by LLM**: UC3 does this by retrieval; an LLM variant (UC2's event rendering + the taxonomy list as prompt) could be compared against it with `benchmarks/run_suggest.py`.
- **ML checker**: pre-publish best-current-practice check with a community-overridable prompt.
- **Chatbot "Marty McFly"**: Mattermost bot with MISP search tools (FastMCP).
- **Threat-actor clustering**: propose canonical TA names from T-codes and attributes; MISP galaxy synonyms as seed.
- **Knowledge graphs**: LLM-suitable representation of MISP relationships; output a markdown story with uuids.
- **Periodic / quarterly reports**: summarise pre-tagged input with links back to events for analyst review.
- **MISP MCP server** ([MISP-mcp](https://github.com/MISP/MISP-mcp)) and **AI-assisted search** on [misp-workbench](https://github.com/MISP/misp-workbench).
- **Prompt template library**: superseded by the prompt galaxy in PROMPTS.md.
- **Long jobs** (e.g. video analysis) and async request topologies: out of scope while the module is a synchronous `/query` responder.

## Known limits (from the first live runs, 2026-09-04)

- Defanged values were rejected by the format check until 2026-09-05 (220 of the candidates on
  the 100-report orkl benchmark); the module now refangs (step 0 above), and the benchmark
  refangs with the same function on all sides.
- Precision on the fixture reports was 1.0 once the gold lists were complete; every extra
  indicator the model found (filenames, threat-actor names) was literally in the text.
- A classical, deterministic baseline exists for benchmarks: `genai/classic.py` wraps
  `iocextract` (regex, refang enabled) and returns a *superset* of `ip-dst`, `url`, `domain`,
  `email` and hash indicators, including defanged ones. It is test/benchmark tooling only and
  is never used by the module (`python -m genai.classic <textfile> [-o out.json]`).
