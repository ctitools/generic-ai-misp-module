# Prompts as a MISP galaxy

Prompts are configuration, not code. They are shipped as a MISP galaxy so that MISP instances
can sync, version and override them like any other galaxy, and so that a prompt is always
bundled with the model and the sampling parameters it was validated with. That bundle is what
makes summaries reproducible ([TESTING.md](TESTING.md)).

Status: design. The galaxy files are created in the code round; the v1 prompt texts below are
copied into them verbatim.

## Why a galaxy

- [misp-galaxy](https://github.com/MISP/misp-galaxy) has no prompt galaxy yet (checked
  2026-09-04). The format is two JSON files and needs nothing new.
- A galaxy cluster has a uuid, a version, `meta` key/values and is syncable between instances.
- Prompt selection becomes a MISP concept: module config names a cluster; later an event can
  be tagged `misp-galaxy:generic-ai-prompts="summary-event/qwen3.8-v1"` to select it per event.

## Files

`galaxies/generic-ai-prompts.json`

```json
{"name": "Generic AI prompts", "namespace": "generic-ai", "type": "generic-ai-prompts",
 "description": "Prompts, models and sampling parameters used by the Generic AI MISP module",
 "uuid": "<uuid4, fixed once>", "version": 1, "icon": "robot"}
```

`clusters/generic-ai-prompts.json` — one cluster per **(use-case, model)** pair:

| field | content |
|---|---|
| `value` | human id: `<use-case>/<model>-v<n>`, e.g. `summary-report/qwen3.8-v1` |
| `uuid` | fixed uuid4 per cluster |
| `description` | one line: what the prompt does |
| `meta.use_case` | `cti-info-extraction` \| `summary-report` \| `summary-event` |
| `meta.model` | model this prompt is validated against: `{"name": "qwen3.8:latest", "digest": "22130167c4c2", "quantization": "Q4_K_M", "server": "ollama 0.33.2"}` |
| `meta.model_parameters` | `{"temperature": 0, "seed": 42, "top_p": 1, "max_tokens": 600, "think": false}` |
| `meta.prompt` | the full prompt text (system + user parts joined, `{{input}}` placeholder) |
| `meta.version` | prompt version, bump on every text change |
| `meta.output_schema` | UC1 only: the JSON schema the model must follow |
| `meta.language` | `en` |
| `meta.prompt_sha256` | hash of `meta.prompt`, recorded in golden files |

`meta.model.digest` comes from Ollama `/api/tags`; the server version from `/api/version`.

## Resolution at runtime

For each of `prompt_extraction`, `prompt_summary_report`, `prompt_summary_event`:

1. value looks like a uuid or matches a cluster `value` → load that cluster from the bundled
   clusters file (follow-up: from the MISP instance via `/galaxy_clusters/view/<uuid>`), take
   prompt **and** `model_parameters` from it;
2. otherwise the value is inline prompt text, parameters come from module config / defaults;
3. nothing set → the bundled default cluster for that use-case and the configured model.

The response metadata records which cluster (uuid, version, prompt hash) produced the output.

## Syncing to MISP instances

Copy both files into the instance's custom galaxy directory (`app/files/misp-galaxy/` layout:
`galaxies/` + `clusters/`) and run *Update galaxies*; or publish them in a git repo that the
instances pull. Editing a prompt = bump `meta.version` and the cluster `version`; the module
logs the version it used, so drift between instances is visible.

## v1 prompts

### `cti-info-extraction/qwen3.8-v1`

```
You extract indicators of compromise from a cyber threat intelligence report for MISP.
Only return indicators that appear LITERALLY in the report text. Never infer, complete or
normalise a value. If unsure, leave it out: precision matters more than recall.

Allowed "type" values are MISP attribute types, e.g. ip-src, ip-dst, domain, hostname, url,
md5, sha1, sha256, filename, email-src, email-dst, vulnerability, regkey, mutex, user-agent,
ja3-fingerprint-md5, AS, btc, threat-actor, malware-type. The complete list follows:
{{misp_types}}

Return ONLY a JSON array, no prose, following this schema:
[{"type": "<misp type>", "category": "<misp category>", "value": "<exact text>",
  "confidence": <0..1>, "quote": "<the sentence fragment containing the value>"}]
Set confidence below 0.9 for anything you are not certain about.

Report:
{{input}}
```

`{{misp_types}}` is filled from `describeTypes.json` at call time (so the list is never stale).
Parameters: `temperature 0, seed 42, top_p 1, max_tokens 2000, think false`.

`cti-info-extraction/qwen3.8-v2` (uuid `e1f0a6a2-6b7c-4d3e-9f10-2a3b4c5d6e7f`) is the same prompt
text with `max_tokens 8000`: the first orkl benchmark run truncated the JSON answer on about a
third of the reports at 2000 tokens (one `quote` per indicator is expensive). Select it with
`prompt_extraction: cti-info-extraction/qwen3.8-v2`; v1 stays the default.

### `summary-report/qwen3.8-v1`

```
You are a CTI analyst writing an analyst assessment of the following report for a MISP event.
Write in English, at most 200 words, using exactly these markdown headings:
## Threat
## Targets
## Indicators
## Recommended actions
Use only facts stated in the report. Do not add indicators, names or dates that are not in the
report. If a section has no information, write "Not stated in the report."

Report:
{{input}}
```

Parameters: `temperature 0, seed 42, top_p 1, max_tokens 600, think false`.

### `summary-event/qwen3.8-v1`

```
You are a CTI analyst summarising a MISP event for a manager. Below is a structured rendering
of the event: its attributes, objects, tags, galaxies and related events.
Write in English, at most 200 words, using exactly these markdown headings:
## What happened
## Key indicators
## Context and attribution
## Related events
Mention uuids exactly as given when you refer to objects or related events. Use only the
information below; never invent indicators. If a section has no information, write
"Not present in the event."

Event:
{{input}}
```

Parameters: `temperature 0, seed 42, top_p 1, max_tokens 600, think false`.

## Backlog

- Propose the galaxy upstream to `MISP/misp-galaxy` once two instances have used it.
- Per-event prompt selection through a galaxy tag on the event.
- A `meta.validated_on` date plus the golden-file hash, so a cluster states the last time it
  reproduced its golden summary.
