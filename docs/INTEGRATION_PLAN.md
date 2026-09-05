# Integration plan: how MISP users reach the generic AI MISP module

Status: **not started**, decided 2026-09-05. Research and recommendation; nothing here is
implemented yet. The module itself (docs/USE-CASES.md) continues to evolve independently.

## Context

Today `expansion/generic_ai.py` is one module that takes a full MISP Event and a `use_case`
parameter (`extraction` | `summarization`, plus `summary_kind`). The question: how does a MISP
user pick the function, and should the actions be separate modules or one parameterised one?
Answer derived from the MISP 2.5 sources (app/Controller/EventsController.php,
ModulesController.php, EventReportsController.php, app/Model/Module.php, Event.php,
EventReport.php, WorkflowModules/*) and the installed misp-modules 3.x.

## Research findings (facts, with the code path)

1. **The MISP UI selects a module by name, never by parameter.** Every UI path builds the
   request itself; `config` is filled from instance settings
   `Plugin.Enrichment_<module>_<key>` only (`EventsController::queryEnrichment`,
   `Event::enrichment`, `ModulesController::queryEnrichment`). There is no form where an
   analyst types `use_case=…`. So a single parameterised module cannot be driven from the UI;
   the parameter would be fixed per instance in the module settings.

2. **Our module is invisible in the UI today.** Expansion modules are listed per attribute
   type (`mispattributes.input`); "Enrich" on an attribute/object shows only modules whose
   `input` contains that type; "Enrich event" (`Event::enrichment`) iterates the attributes and
   calls a module once per matching attribute. With `input: []` the module is never offered
   and never called. `queryEnrichment` accepts `$model = 'Event'` in its whitelist but has no
   code path for it (dead branch). No UI path sends a whole event to an expansion module.

3. **MISP's REST endpoint `POST /modules/queryEnrichment` forwards an arbitrary body**, but
   it looks the module up with `getEnabledModule($name, 'hover')`, so only modules declaring
   `"hover"` pass. Hover means "show a tooltip on mouse-over", i.e. immediate feedback; an LLM
   call takes seconds to minutes, so we will **not** declare hover. Consequence: scripted use
   goes to the misp-modules server directly (`POST http://<misp-modules>:6666/query`), which
   is what the tests do; MISP's proxy endpoint is not usable for this module.

4. **MISP already has a first-class "send this report to an LLM" hook, and it is not a
   misp-module.** `EventReport::sendToLLM()` (button on the event-report page, and the workflow
   action `send_report_to_CTIInfoExtractor` on the trigger `event-report-after-save`) POSTs
   `{"text": <report markdown>}` with header `x-api-key` to the URL in MISP's setting
   `Plugin.CTIInfoExtractor_url` (MISP's name for the setting; we only speak its contract)
   and expects `{"AI_ExecutiveSummary", "AI_ThreatActor", "AI_AttributedCountry",
   "AI_Motivation", "AI_Type", "AI_CouldWeBeAffected"}`. MISP then prepends
   `# Executive Summary` to the report content and attaches
   `misp-galaxy:threat-actor="…"`, `threat-actor-country`, `threat-actor-motivation` tags to
   the event. Four yes/no options exist per workflow node. **It adds no ai-computer-assisted
   tag** and rewrites the original report instead of adding a new one, which conflicts with
   two of our rules (never modify the source report; every LLM output tagged).

5. **Workflows are the only UI place with per-invocation parameters.** Action modules
   (`misp-modules/action_mod`) receive `request["data"]` (the trigger's event, MISP core format
   when `expect_misp_core_format: true`) and `request["params"]` set by the admin in the
   workflow editor per node; triggers include `event-publish`, `event-after-save`,
   `event-report-after-save`, `attribute-after-save`. Action modules return `boolean` or `data`
   for the next node; they cannot write attributes back except by calling the MISP API
   themselves (precedent: `mwdb`, `yeti`, `rst_ioc` use `misp_url`/`misp_key` config).
   `attach_enrichment` / `enrich_event` workflow actions call expansion modules per
   attribute, same filtering as above.

6. **Import modules are the UI for "text in, attributes proposed, human reviews".**
   `mispattributes = {"inputSource": ["file", "paste"], "format": "misp_standard"}` plus a
   `userConfig` form (typed fields with validation) that the user fills at import time; the
   result appears in MISP's review screen before anything is saved (Event → Populate from…).
   This is the only path where a user both chooses the function and types parameters.

7. **Attribute-level fit.** Nothing in our two use-cases is keyed on an attribute type;
   both need the EventReport (extraction, summary of report) or the whole event (summary of
   event). Expansion modules are the wrong shape for them unless the module fetches the event
   itself through the MISP API (needs `misp_url`/`misp_key` in module config; precedent exists).

## Recommendation: several thin modules, one engine

Keep exactly one implementation (`genai/`: prompts, llm, extract, summarize, refang) and
expose it through **one thin entry point per action**, because that is what every MISP entry
point (attribute menu, workflow node, import dialog, settings page) keys on. The
`use_case` request parameter becomes an internal detail; nothing in the engine changes.

**Structure: delegation, not inheritance.** misp-modules discovers a module by importing the
file and reading module-level names (`moduleinfo`, `mispattributes`, `moduleconfig`,
`handler(q)`, `introspection()`, `version()`); there is no base class anywhere in
misp-modules, every one of its ~200 modules is a flat file of constants plus functions. A
class hierarchy would still have to be unwrapped into those globals in every file, so it
adds a layer without removing any. The MISP-like shape is:

```
genai/entry.py            one function: run(request: dict, use_case: str, **fixed) -> dict
                          (= today's dict_handler body: extract event, validate, dispatch, tag)
expansion/generic_ai_summary_report.py   moduleinfo/mispattributes/moduleconfig + 5-line handler
expansion/generic_ai_summary_event.py    that calls genai.entry.run(request, "summarization", kind=…)
import_mod/generic_ai_extract.py
action_mod/generic_ai.py
```

Each wrapper is ~30 lines and differs only in its declarations and the fixed arguments it
passes; shared behaviour lives in one function, tested once. `expansion/generic_ai.py` stays
as the parameterised entry for scripts, tests and the benchmark.

| user wants | entry point in MISP | our component | how the user picks it |
|---|---|---|---|
| summary of a report as new EventReport | event-report page "Send to LLM" button, or workflow `event-report-after-save` | `genai/adapter.py`: a small HTTP service speaking the contract MISP's `sendToLLM` expects | one instance setting (`Plugin.CTIInfoExtractor_url` in MISP's naming); the button exists already |
| indicators from a report, reviewed before saving | Event → Populate from… → import module | `import_mod/generic_ai_extract.py` (`inputSource: ["paste", "file"]`, `userConfig`: `min_confidence`, `prompt`) | picks the module and fills the small form |
| summary of the whole event / extraction on an existing report, automated | workflow action on `event-publish` / `event-report-after-save` | `action_mod/generic_ai.py` (`expect_misp_core_format: true`, `params`: `action` select = summary-report \| summary-event \| extraction, `misp_url`, `misp_key`) writes the result back with PyMISP | picks the action in the node's dropdown |
| scripted / API use, tests, benchmark | misp-modules server `POST /query` | `expansion/generic_ai.py` as today (module-type stays `["expansion"]`, no hover) | body parameters as today |

Why not one module with a setting: `Plugin.Enrichment_generic_ai_use_case` would make the
whole instance do one thing, and the UI would still never show it (finding 2).
Why not many full modules: duplicated validation, tagging and tests; the wrappers share
`genai.entry.run`, so every quality gate we have keeps covering all entry points.

## Steps (ordered by value; each is independently shippable)

1. **Extract the shared entry** — `genai/entry.py::run(request, use_case, **fixed)` from
   today's `dict_handler` (behaviour-preserving refactor; `expansion/generic_ai.py` calls it;
   existing tests are the gate). README gains a section **"Does the generic AI MISP module
   work? Test it with curl"**: start the misp-modules server, `curl` `/modules` to see it
   listed, then `curl -X POST http://127.0.0.1:6666/query -d '{"module":"generic_ai","event":
   {...fixture...},"use_case":"summarization"}'` with the expected shape of the answer, and the
   same for extraction; note that MISP's `/modules/queryEnrichment` proxy is not usable (hover).
2. **Adapter for report summaries** — `genai/adapter.py`: stdlib `http.server` exposing
   `POST /` that takes `{"text"}`, checks `x-api-key` against `.env` `GENERIC_AI_ADAPTER_KEY`,
   runs `summarize(kind="report")` on a synthetic event through `genai.entry.run`, and returns
   `{"AI_ExecutiveSummary": <summary>, "AI_ThreatActor": "", "AI_AttributedCountry": "",
   "AI_Motivation": "", "AI_Type": "", "AI_CouldWeBeAffected": null}` — the threat-actor
   fields stay empty for now (a later use-case). CLI `python -m genai.adapter --port 6667`.
   Tests: offline with `fake_llm` (contract keys, 401 on bad key, error passthrough), live e2e.
3. **Upstream PR to MISP, for Aaron's review before anything is sent** — because
   `EventReport::sendToLLM` writes the summary into the report and tags the event without any
   `ai-computer-assisted` tag: prepare the patch against `MISP/MISP` branch 2.5 as
   `docs/upstream/0001-sendToLLM-ai-computer-assisted-tags.patch` plus a PR description in
   `docs/upstream/README.md` (what, why, the two tag strings from the pinned list, optional
   fifth `sendToLLM` option `store_as_new_report` defaulting to false for backwards
   compatibility). Nothing is pushed or opened; Aaron reviews, then decides.
4. **Import module for reviewed extraction** — `import_mod/generic_ai_extract.py` (first
   verify that `misp-modules -c <dir>` loads custom `import_mod/` modules; if it does not,
   document and skip). `userConfig`: `min_confidence` (Integer 0-100), `prompt` (String,
   cluster value). Handler: pasted/uploaded text → synthetic event with one EventReport →
   `genai.entry.run(request, "extraction")` → `{"results": <MISPEvent json>}`. Reuses MISP's
   review screen; the AI tags travel with the attributes.
5. **Workflow action module** — `action_mod/generic_ai.py`: `params` `action` (select),
   `misp_url`, `misp_key`, `verify_ssl`; `expect_misp_core_format: true`; runs the chosen
   use-case on `request["data"]` and pushes the result with PyMISP (`add_attribute`,
   `add_event_report`, `tag`), `returns = "data"` with the metadata. e2e test against the dev
   MISP: create a test event with `tests/fixtures/orkl-sample.txt` as report, run the action,
   verify the new report/attributes and the AI tags (the AGENTS.md E2E loop).
6. **Docs**: USE-CASES.md "How to call it from MISP" with the table above; ARCHITECTURE.md
   gets the findings (short); requirements.md R1 gains the entry points; CHANGELOG. The
   component is called "generic AI MISP module" everywhere; MISP's own setting names are quoted
   only where the user has to type them.

Not planned: patching MISP's UI to offer whole-event expansion (dead `Event` branch in
`queryEnrichment`); a per-instance `use_case` setting; declaring `hover`.

## Verification

- Step 1: `pytest -q` unchanged; README curl how-to executed against a local
  `python -m misp_modules -c . -l 127.0.0.1 -p 6666` and the output pasted into the README.
- Step 2: `python -m genai.adapter` + set the three LLM settings on the dev MISP → press
  "Send to LLM" on a report → `# Executive Summary` appears; offline tests for the contract.
- Step 3: patch applies cleanly to MISP 2.5 (`git apply --check` on a fresh clone in the
  scratchpad); Aaron reviews the text.
- Step 4: misp-modules server lists the import module (`/modules`), MISP "Populate from…"
  shows it, a pasted report yields the review screen with AI-tagged attributes.
- Step 5: workflow with trigger `event-report-after-save` → node `generic_ai`
  action=summary-report → new EventReport "AI summary of …" and both AI tags on the event;
  asserted via PyMISP in `tests/test_generic_ai_e2e.py`.
