# Requirements

## Introduction

The **Generic AI MISP module** is a `misp-modules` expansion module that takes a full MISP
Event, validates it, and returns MISP Events. Three use-cases fill its hooks (the third, tag suggestion, calls the misp-tag-suggest service instead of an LLM): **CTI info
extraction** (indicators from the event's EventReport) and **summarization** (of the report or
of the event). Prompts and sampling parameters are shipped as a MISP galaxy.

Supersedes the 2026-07 version of this document, which described a text-attribute input, a
deterministic fallback, a hover mode and four inheriting sub-modules. Those are dropped: the
module has one input (a MISP Event), no fallback (failures are errors), and use-cases are plain
functions selected by `use_case`.

Highest-priority value, unchanged: **human maintainability** — less code, copy-pasteable docs.
Stack per `AGENTS.md`: Python ≥ 3.14, `uv`, `pytest`, stdlib first; the only approved third-party
runtime dependency is **PyMISP**.

Requirement style: EARS (`WHEN/WHERE/IF … THE module SHALL …`). Status tags: *implemented*, *future*.

## Glossary

- **Module**: `expansion/generic_ai.py`.
- **Event**: a MISP Event in the MISP core format, parsed into a PyMISP `MISPEvent`.
- **EventReport**: markdown report attached to an Event; `event_report` is the joined markdown of all non-deleted reports.
- **Use-case**: `extraction` (`extract_iocs`) or `summarization` (`summarize(kind)`).
- **LLM**: the OpenAI-compatible chat endpoint from `.env` (`OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`).
- **Prompt cluster**: a cluster of the `generic-ai-prompts` galaxy carrying use-case, model, sampling parameters and prompt text (docs/PROMPTS.md).
- **AI tags**: `ai-computer-assisted:assistance-level="ai-generated"` and `ai-computer-assisted:review-level="unreviewed"`, taken verbatim from the pinned list.
- **Pinned list**: committed file with the exact machine-tag strings from `misp-taxonomies/ai-computer-assisted/machinetag.json`.
- **Round-trip gate**: `tests/test_e2e_roundtrip.py` (docs/TESTING.md).

## R1 MISP module contract — *implemented*

1. THE module SHALL expose `introspection()`, `version()` and `handler(q)` per misp-modules.
2. WHEN `handler` is called with a falsy query, THE module SHALL return `False`.
3. WHEN the query is not valid JSON, THE module SHALL return `{"error": ...}`.
4. THE module SHALL accept the Event under `event` (`{"Event": {...}}` or bare) or under `data[0]`.
5. IF no Event is present, THEN THE module SHALL return an error naming the expected keys.

## R2 Validation — *implemented*

1. THE module SHALL validate the Event with PyMISP `MISPEvent.load()` (built with `force_timestamps=True`) and SHALL NOT use a JSON schema (none defines EventReport; docs/ARCHITECTURE.md).
2. IF PyMISP rejects the Event, THEN THE module SHALL return `{"error": "Invalid MISP Event: <reason>"}` and no partial result.
3. THE module SHALL deep-copy the input before loading and SHALL drop `distribution`/`sharing_group_id` on default galaxy clusters (PyMISP rejects them, MISP emits them). No other input is altered.

## R3 Output contract — *implemented*

1. THE module SHALL return `{"results": {"Event": {"Event": ...}, "ReportEvent": {"Event": ...}}, "event_report": "<markdown>"}`.
2. WHEN `process_event` is called with `e2etest=True`, THE module SHALL write the processed Event to `tests/e2etests/<uuid>.json`.
3. THE processed Event SHALL be semantically identical to the input (as defined by `tests/misp_compare.py`) except for additions made by a use-case. Verified by the round-trip gate.

## R4 Use-case selection — *implemented*

1. THE module SHALL read `use_case` from the request body, then module config, then `GENERIC_AI_USE_CASE` in `.env`, default `none` (pass-through).
2. WHEN `use_case` is `extraction`, THE module SHALL call `extract_iocs(event)`.
3. WHEN `use_case` is `summarization`, THE module SHALL call `summarize(event, kind)` with `kind` from `summary_kind` (request), then `default_summary_kind` (config), default `report`.
4. WHEN `use_case` is `tag_suggestion`, THE module SHALL call `suggest_tags(event, settings, suggest_limit, suggest_min_score)` against `MISP_TAG_SUGGEST_URL` from `.env` (never from the request), add only tags with `score >= suggest_min_score` that are not on the event, tag the event `ai-computer-assisted` when at least one tag was added, and treat abstention as success with empty output.
5. IF `use_case` or `kind` is unknown, THEN THE module SHALL return an error listing the allowed values.

## R5 CTI info extraction — *implemented*

1. THE module SHALL send the prompt cluster for `cti-info-extraction` plus `event_report` to the LLM and require a JSON array of `{type, category, value, confidence, quote}`.
2. IF the LLM output is not valid JSON, THEN THE module SHALL return an error and SHALL NOT add anything.
3. THE module SHALL refang a defanged value (`hxxp://`, `[.]`, `[at]`, markdown `\.` in network tokens; never in file paths) and SHALL re-type a hash labelled with the wrong hash type by its length, recording both in the attribute comment and the metadata; it SHALL set `first_seen`/`last_seen` only from a date the report states for the indicator (literal spelling checked, unambiguous spellings parsed; a stated publication date is metadata only) and SHALL lower `to_ids` below the type default when the report marks the indicator as not actionable, never raise it; no other normalisation. THE module SHALL add an indicator only if all hold: the (refanged) value is a case-insensitive, whitespace-normalised substring of the refanged `event_report`; `type` exists in PyMISP `describeTypes.json` and is not `other`/`text`/`comment` (an invalid `category` is replaced by the type's default); the model's `quote` contains the value; the per-type format check passes (IPv4/IPv6, domain/hostname, md5/sha1/sha256, url, email, CVE); it is not already on the Event; `confidence >= min_confidence` (default 0.9).
4. THE module SHALL record every rejected candidate with its reason in the response metadata.
5. WHEN hashes and a filename describe one file, THE module SHALL group them in a `file` object; WHEN a CVE is extracted, in a `vulnerability` object.
6. THE count of added indicators SHALL be ≤ the count of candidates (filters only remove).

## R6 Summarization — *implemented*

1. WHEN `kind` is `report`, THE module SHALL summarise `event_report`.
2. WHEN `kind` is `event`, THE module SHALL render attributes, objects, tags, galaxies and related events into a sorted, timestamp-free markdown table and summarise that. Rendering the same Event twice SHALL produce identical bytes.
3. THE module SHALL attach the summary as a **new** EventReport ("AI summary of <report name>" / "AI summary of event <uuid>") and SHALL NOT modify existing reports.
4. THE summary SHALL use the headings and the ≤ 200-word limit fixed in the prompt cluster; the module SHALL verify that no indicator or uuid in the summary is absent from the input and SHALL return an error otherwise.

## R7 AI taxonomy tagging — *implemented*, MUST

1. Every element the LLM suggested SHALL carry both AI tags, verbatim from the pinned list: on each added attribute/object for extraction; on the Event for summaries and any future event-level suggestion (e.g. tags).
2. THE module SHALL NOT return LLM-produced content without these tags.
3. THE pinned list SHALL be checked against upstream `machinetag.json` by a test; IF a required string is missing upstream, THEN the test SHALL fail.
4. Existing tags on the Event SHALL NOT be changed. Review-level transitions (`human-reviewed`, …) are done in MISP, not by the module.

## R8 Prompts and parameters — *implemented*

1. Prompts SHALL be shipped as the `generic-ai-prompts` galaxy; each cluster SHALL carry `use_case`, `model` (name, digest, quantisation, server), `model_parameters` (temperature, seed, top_p, max_tokens, think), `prompt`, `version`, `prompt_sha256`.
2. THE module SHALL resolve `prompt_*` config values as cluster uuid → cluster `value` → inline text → bundled default, and SHALL take sampling parameters from the chosen cluster.
3. THE response metadata SHALL name the cluster (uuid, version, prompt hash) and the model (name, digest) used.

## R9 Configuration and safety — *implemented*

1. Precedence SHALL be request body (allowed keys only) > module config > `.env` > default.
2. `api_base` and `api_key` SHALL NOT be settable from the request body.
3. THE module SHALL bound every LLM call with `request_timeout` (default 120 s); IF it elapses, THEN THE module SHALL return an error. There is no fallback output.
4. *future* — TLP governance: content at or above a configured TLP level SHALL NOT be sent to an endpoint not marked local; `:cloud`-routed Ollama models count as external.

## R10 Testability — *implemented*, see docs/TESTING.md

1. Every use-case SHALL have offline unit tests with a mocked LLM covering each rejection rule and the tagging rule, a local misp-modules e2e test, and live LLM tests that skip when the endpoint is unreachable.
2. Summaries SHALL be reproducible on a pinned model: three identical requests SHALL give identical text; goldens SHALL carry model digest, server version and prompt hash and SHALL only be compared when those match; the structural check (headings, length, no foreign indicators, tags) SHALL be the gate.
3. Extraction SHALL meet precision ≥ 0.95 against hand-labelled gold lists for the fixture reports.
4. The round-trip gate SHALL keep passing for the default path.

## R11 Maintainability — *implemented / ongoing*

1. Source files: `expansion/generic_ai.py` plus at most one file per use-case.
2. Functions ≤ cyclomatic complexity 10; `ruff`, `pylint` clean before commit.
3. WHEN behaviour changes, docs and `CHANGELOG.md` SHALL change in the same commit.
4. No new runtime dependency without explicit approval.

## Open questions

1. Should `summarize(kind="both")` exist (one call, two reports)? Defer until asked.
2. UC1 precision threshold 0.95 and `min_confidence` 0.9 are starting points; revisit after the first gold-list run.
3. Whether to fetch prompt clusters from the MISP instance at runtime or only from the bundled file (bundled first).
