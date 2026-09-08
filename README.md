# Generic AI MISP module

A custom [misp-modules](https://github.com/MISP/misp-modules) expansion module that puts a Large
Language Model to work on a **full MISP Event** ([MISP core
format](https://www.misp-standard.org/rfc/misp-standard-core.html)) — not on a single attribute.

You give it a whole MISP Event, it validates it with [PyMISP](https://github.com/MISP/PyMISP),
takes the markdown of the event's `EventReport`s (the CTI report an analyst pasted in) and runs
the configured use-case on it. What comes back is again a MISP Event, ready to be pushed into
MISP.

| use-case | what you get |
|---|---|
| **CTI info extraction** | high-confidence MISP attributes read out of the report — IPs, domains, hashes, CVEs, plus `file` / `vulnerability` objects — each one refanged, deduplicated against the event, and carrying the quote it came from |
| **Summarization** | a new `EventReport` with an executive summary, either of one report or of the whole event |
| **Tag suggestion** | taxonomy and galaxy tags voted from the most similar events already in your MISP (no LLM) |
| **none** (default) | pass-through, no model call at all |

Three properties matter more than the feature list:

- **MISP Event in → MISP Event out.** No side format, no bespoke JSON contract to integrate.
- **Everything the model produced is tagged**, verbatim, with
  `ai-computer-assisted:assistance-level="ai-generated"` and
  `ai-computer-assisted:review-level="unreviewed"`. Nothing machine-made can quietly pass as
  analyst work, and existing event content is never modified or re-tagged.
- **Bring your own model.** Any OpenAI-compatible chat endpoint — a local Ollama on your own
  GPU, vLLM, or a commercial API. Prompts and sampling parameters are not hardcoded: they ship
  as a MISP galaxy you can edit and version.

## Documentation

Three guides, one per reader. Start with the one that matches what you want to do.

| guide | for you if you want to | contents |
|---|---|---|
| **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** | understand what it does to an event before deciding to use it | the three jobs with real examples, the rules it always follows, measured quality, where your data goes, what it does *not* do |
| **[docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md)** | install it, run it and keep it alive | install, `.env`, running the server, verification calls, settings, the tag-suggestion service, metrics, logs, failure modes, security, upgrades |
| **[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** | change the code | code map, invariants, how to add a use-case or a prompt, the test layers and gates, how to run and write benchmarks, how to contribute, and where the project stands |

Reference documents behind them — the use-case contracts
([docs/USE-CASES.md](docs/USE-CASES.md)), the architecture
([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)), the prompts
([docs/PROMPTS.md](docs/PROMPTS.md)), the test plan ([docs/TESTING.md](docs/TESTING.md)), the
measurements ([docs/BENCHMARKS.md](docs/BENCHMARKS.md)), the requirements
([docs/requirements.md](docs/requirements.md)) and the backlog
([docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md)) — are indexed in the developer guide.

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
  extraction precision gate against hand-checked indicator lists and a benchmark suite.
- **Your data stays where you put it.** Point it at a local model and no report ever leaves your
  network.
- **No lock-in.** It is a plain misp-modules expansion module and a small Python package; the
  only third-party runtime dependency is PyMISP.

## Try it in a minute

Python 3.14, [uv](https://docs.astral.sh/uv/), and an OpenAI-compatible endpoint in `.env`
(details: [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md)).

```bash
uv pip install --python .venv/bin/python -e ".[dev,e2e]"
.venv/bin/python -m misp_modules -c . -l 127.0.0.1 -p 6666
```

In a second terminal — a summary of the shipped test event, with the AI tags it carries:

```bash
jq -c '{module: "generic_ai", use_case: "summarization", summary_kind: "report", event: .}' fixtures/summary/dummy-event.json \
  | curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- \
  | jq '{summary: .results.Event.Event.EventReport[-1].content, tags: [.results.Event.Event.Tag[].name], meta: .metadata}'
```

## Status

Working and measured: the three use-cases, the round-trip guarantee, the test layers (offline,
local server, live LLM, live MISP, live write path) and the benchmark suite are in place —
current numbers in [docs/BENCHMARKS.md](docs/BENCHMARKS.md), the full picture of what is done,
partial and planned in
[docs/DEVELOPER_GUIDE.md §10](docs/DEVELOPER_GUIDE.md#10-where-the-project-stands).

Not there yet: MISP's web interface has no path that sends a whole event to an expansion module,
so the module is called by script or API today. The researched plan for proper UI integration is
[docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md).

- module name `generic_ai` · module type `expansion` · input: a full MISP Event · output: the
  processed MISP Event, a second MISP Event built from the report, and the report markdown
- licensed under the [GNU AGPL v3](LICENSE); built at [CIRCL](https://www.circl.lu/) with
  [ctitools](https://github.com/ctitools)
