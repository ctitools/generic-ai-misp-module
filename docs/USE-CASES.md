# Use-cases

Two use-cases are in focus. Both keep the module contract **MISP Event in → MISP Event out**
([ARCHITECTURE.md](ARCHITECTURE.md)) and both send *a prompt plus the event's content* to the
LLM configured in `.env` (`OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`; any
OpenAI-compatible chat endpoint, today Ollama on `nanu`). Prompts and sampling parameters are
configurable and shipped as a MISP galaxy ([PROMPTS.md](PROMPTS.md)). Tests for both are
specified in [TESTING.md](TESTING.md); formal requirements in [requirements.md](requirements.md).

Status: **implemented** in `genai/extract.py` and `genai/summarize.py`, dispatched by
`process_event()` in `expansion/generic_ai.py`. The default `use_case` is `none` (pass-through,
no LLM call), so the round-trip gate and plain validation never touch the LLM.

## Rule that applies to every output

Anything the LLM produced is marked with the `ai-computer-assisted` taxonomy, verbatim strings
from a pinned list:

| what the LLM suggested | tags go on | tags |
|---|---|---|
| attributes / objects (UC1) | each new attribute (and object) | `ai-computer-assisted:assistance-level="ai-generated"`, `ai-computer-assisted:review-level="unreviewed"` |
| event-level content: a summary EventReport (UC2), tags (future) | the event | same two tags |

Nothing the module adds may leave without these tags. Existing content of the event is never
modified or re-tagged.

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

An indicator is added only if it passes all of the following; every rejection is recorded in
the response metadata:

1. `value` (refanged) is a substring of the refanged source report (case-insensitive,
   whitespace-normalised) — the hallucination guard; `quote` must contain `value` too.
2. `type` exists in `describeTypes.json`; an invalid or missing `category` is replaced by the type's default category.
3. PyMISP `MISPAttribute(type, value)` accepts it (PyMISP's own per-type validation).
4. A per-type format check for the common types (IPv4/IPv6, domain/hostname, md5/sha1/sha256,
   url, email, CVE id, `ip-src|port`/`ip-dst|port`/`hostname|port`). Types without a check rely on 1–3.
5. Not already on the event (same type + value, including inside objects).

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

## Configuration

All keys are `moduleconfig` entries (settable in MISP's module settings), overridable per
request only for the keys marked *request*. Endpoint and API key are **never** settable from
the request body ([IMPROVEMENTS.md](IMPROVEMENTS.md) item 3).

| key | default | request | meaning |
|---|---|---|---|
| `use_case` | `none` | yes | `none` (pass-through), `extraction` or `summarization` |
| `summary_kind` | `report` | yes | `report` or `event` |
| `prompt_extraction`, `prompt_summary_report`, `prompt_summary_event` | bundled galaxy cluster | yes | galaxy cluster uuid or `value`, or inline prompt text |
| `model_id` | `OPENAI_MODEL` from `.env` | yes | must exist on the endpoint |
| sampling (`temperature`, `seed`, `top_p`, `max_tokens`, `think`) | from the prompt cluster (`0` / `42` / `1` / per use-case / `false`) | via the cluster | select another cluster to change them |
| `min_confidence` | `0.9` | yes | UC1 gate |
| `request_timeout` | `120` s | no | LLM call bound; timeout → error, no fallback |
| `api_base`, `api_key` | `.env` | **no** | endpoint |

Precedence: request body (allowed keys only) > module config > `.env` > built-in default.

## Not in focus (parked)

Collected during hackathon 2026; kept as one-liners so they are not lost.

- **Tag proposal**: propose the best matching taxonomy/galaxy tags for an event (would reuse UC2's event rendering; tags go on the event, AI-tagged).
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
