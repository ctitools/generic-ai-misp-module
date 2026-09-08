# User guide

**Who this is for:** anyone who wants to know what the generic AI MISP module does to a MISP
event — analysts, team leads, reviewers, decision makers. Nothing here needs to be installed
first.

**The other two guides:** [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) installs and runs it ·
[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) changes it.

## What it is, in one paragraph

The module hands a **whole MISP event** to a large language model and gives you the **same
event back**, with the model's output added as ordinary MISP content: attributes, a new event
report, tags. Every element the model produced is marked
`ai-computer-assisted:assistance-level="ai-generated"` and
`ai-computer-assisted:review-level="unreviewed"`, so you can always tell machine work from
analyst work, filter it, review it or delete it. Nothing that was already in the event is
changed.

```text
your MISP event  ──▶  generic AI MISP module  ──▶  the same event
(+ its CTI report)     (your LLM, your host)        + AI-tagged additions
```

## What it does today

| job | you give it | you get back |
|---|---|---|
| **CTI info extraction** | an event whose event report holds a CTI report | new attributes — IPs, domains, URLs, hashes, CVEs, filenames — plus `file` and `vulnerability` objects, each tagged and carrying the sentence it came from |
| **Summarization** | the same event | a **new** event report with a four-section analyst summary, either of one report (`report`) or of the whole event (`event`) |
| **Tag suggestion** | any event | taxonomy and galaxy tags proposed from the most similar events already in your MISP (no LLM: a nearest-neighbour service) |
| **none** (the default) | any event | the event, unchanged — no model is called at all |

One event, one job per call. Which job runs is chosen by the caller
(`use_case`), not by the model.

## Example: report in, summary out

This is the module's actual output for the test report shipped with the repository
(`fixtures/summary/dummy-event.json`, recorded in `tests/golden/summary-report.md`).

**In** — an event report an analyst pasted into the event (excerpt):

> On 2 September 2026 ACME Bank customers received phishing e-mails from
> alerts@acme-bank-secure.example asking them to "verify" their account at
> https://login-acme-bank.example/verify. The page, hosted on 203.0.113.42 (domain
> login-acme-bank.example), imitates the ACME Bank login portal and steals credentials and
> one-time codes. […]

**Out** — a new event report named *AI summary of …*, the event tagged as AI-generated and
unreviewed:

```markdown
## Threat
Phishing campaign targeting ACME Bank customers. Attackers use spoofed emails and malicious
Excel attachments to steal credentials and one-time codes. Low-confidence attribution links
this to a March 2026 campaign against Beta Credit Union.

## Targets
ACME Bank customers. Twelve customers reported fraudulent transfers. No employee accounts
were compromised.

## Indicators
alerts@acme-bank-secure.example
https://login-acme-bank.example/verify
203.0.113.42
login-acme-bank.example
Invoice_2026.xlsm
and 2 more in the report

## Recommended actions
Block the domain and IP. Reset credentials of affected customers. Warn customers about the
sender address. Report new URLs to the CSIRT.
```

The four headings, the length limit and "copy indicators character for character" are rules in
the prompt, and the module **rejects** a summary that breaks them rather than storing it.

## Example: report in, indicators out

Extraction adds attributes that read like this in MISP:

| field | value |
|---|---|
| type / category | `ip-dst` / `Network activity` |
| value | `203.0.113.42` |
| comment | `extracted by generic_ai from EventReport <uuid>` (plus `defanged in source as 203.0.113[.]42`, `first_seen from "2 September 2026"` where that applies) |
| tags | `ai-computer-assisted:assistance-level="ai-generated"`, `ai-computer-assisted:review-level="unreviewed"` |

Before an indicator is stored it must survive every one of these checks — anything that fails
is dropped and listed with its reason in the response:

1. the value appears **literally in the report text** (after undoing defanging like
   `1.2.3[.]4` or `hxxp://`) — this is what stops invented indicators;
2. the quote the model gave contains the value — it has to show where it read it;
3. the type is a real MISP attribute type, and not a free-text type (`other`, `text`, `comment`);
4. a per-type format check passes (IP, domain, hash, URL, e-mail, CVE, …);
5. the event does not already have it;
6. the model's own confidence is at least 0.9.

The policy is deliberately **precision over recall**: a few certain indicators beat many
doubtful ones. Dates (`first_seen`, `last_seen`) are set only from a date the report states in
words the module can check; `to_ids` is lowered when the report marks something as not
actionable, never raised.

## Example: tags proposed from your own MISP

Tag suggestion uses no LLM. It sends the event to a companion service
([misp-tag-suggest](https://github.com/ctitools/misp-tag-suggest)) that has indexed the events
your organisation already tagged, and votes on the tags of the most similar ones — so only tags
that exist on your instance can come back:

```text
CERT-XLM:fraud="phishing"                                   0.76
misp-galaxy:mitre-attack-pattern="Phishing - T1566"         0.12
```

When nothing similar enough is indexed the service **abstains**: no tags, no AI tag, the event
comes back untouched.

## The rules it always follows

- **Everything the model produced is tagged**, verbatim, from a pinned list of taxonomy
  strings. There is no path that returns untagged AI content.
- **Existing content is never modified.** Summaries are added as new event reports, never
  written into an existing one; existing tags and attributes are left alone.
- **No silent fallback.** If the model is unreachable, times out, answers with something
  unparsable, or writes a summary that breaks the rules, you get an error — never a
  plausible-looking result that no model produced.
- **The endpoint and the API key come from the server's configuration only**, never from the
  request, so a caller cannot redirect your reports to another host.
- **Reproducible where it can be.** Prompts, the model and its sampling parameters travel
  together as a versioned MISP galaxy cluster, and the response records which cluster and which
  model produced the output.

## How good is it today

Measured on 2026-09-05 with `qwen3.8` on a local GPU, 100 random reports from
[orkl.eu](https://orkl.eu) and 100 real events. Full numbers and method:
[BENCHMARKS.md](BENCHMARKS.md).

| | result |
|---|---|
| extraction, precision against hand-labelled reports | 1.00 (recall 0.92) |
| extraction, reports processed without error | 95 / 100 |
| summaries passing the structural gate (report / event) | 98 / 100 · 99 / 100 |
| summaries reproduced word for word on a second run | 98 / 98 · 97 / 99 |
| tag suggestion, precision / recall against the analysts' own tags | 0.25 / 0.12 (0.59 / 0.30 on events that carry content tags) |
| typical time per report | 9 s extraction · 5 s summary |

How to read that honestly:

- The precision of 1.00 is measured on **three hand-labelled reports**. It is a real number on
  a small set, not a guarantee; growing that set is open work.
- Recall is reported but not gated: the module is allowed to miss indicators, not to invent
  them.
- The five failing reports are unusually indicator-rich ones where the answer exceeded the
  model's answer budget. They fail loudly.
- Tag suggestion looks weak partly because the comparison counts handling markings (`tlp:*`)
  and untagged events against it; the service's own held-out evaluation is precision@3 0.45 /
  recall@3 0.73. Treat it as a first baseline.
- A summary can pass every structural check and still emphasise the wrong thing. Checking
  *meaning* is unmeasured today — that is why everything arrives as `unreviewed`.

## Where your data goes

- The event report text (extraction, report summary), or a rendering of the event (event
  summary), is sent to **the LLM endpoint your operator configured** — nowhere else. Point it
  at a local Ollama or vLLM and no report leaves your network.
- Tag suggestion sends the event to **your own tag-suggestion service**, which is read-only and
  runs next to the module.
- The module stores nothing, phones nobody home, and has no telemetry.
- **Not implemented yet:** an automatic TLP guard that refuses to send restricted content to a
  non-local endpoint. Today the choice of endpoint is the control. Ask your operator which
  endpoint is configured.

## What it does not do

- **It is not a button in the MISP web interface yet.** MISP selects expansion modules per
  attribute type and has no path that sends a whole event to one, so `generic_ai` is not
  offered in the *Enrich* menus. Today it is called by script or API; the plan for proper UI
  integration is researched but not started ([INTEGRATION_PLAN.md](INTEGRATION_PLAN.md)).
- **It does not decide anything.** Everything it adds is `unreviewed` by construction; moving a
  review level is an analyst action in MISP.
- **It does not infer.** No attribution, no kill-chain phase, no TLP unless the report states it
  literally. Threat actors and malware names currently arrive as text attributes rather than
  galaxy clusters (planned work).
- **It is not multilingual today.** Prompts and evaluation are English.
- **It does not publish or push anything to MISP by itself.** Writing the result back is the
  caller's job.

## Words used here

| term | meaning |
|---|---|
| **Event** | the MISP container for one incident/report: attributes, objects, tags, reports |
| **EventReport** | a markdown report attached to an event — usually the CTI report an analyst pasted in |
| **Attribute** | one indicator or piece of data in an event (`ip-dst`, `sha256`, `filename`, …) |
| **Object** | a group of attributes describing one thing (a `file` with its hashes and name) |
| **Tag / taxonomy** | a machine tag like `tlp:amber`; the `ai-computer-assisted` taxonomy marks machine-made content |
| **Galaxy / cluster** | MISP's shared knowledge sets (threat actors, techniques); this project also ships its *prompts* as a galaxy |
| **`to_ids`** | the flag that says "this indicator may be used for detection" |

## Next

- Want to try it? [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) — install and first call in about ten
  minutes.
- Want the exact contract of each job? [USE-CASES.md](USE-CASES.md).
- Want the numbers behind the table above? [BENCHMARKS.md](BENCHMARKS.md).
