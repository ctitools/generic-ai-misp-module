# Testing

Everything known about how this module is tested: what exists, what each use-case will need,
and how a summary produced by an LLM can be tested deterministically. E2E tests and quality
gates are the priority of this repository; unit tests with mocks did not catch the real
problems here, live runs did (PyMISP rejecting real API output, a dropped timestamp, a stale
API key).

## 1. Layers that exist today

| layer | file | needs | what it proves |
|---|---|---|---|
| unit | `tests/test_generic_ai_unit.py`, `tests/test_misp_compare.py` | nothing | handler contract, input shapes, report extraction, 8 rejection cases, comparator rules |
| local e2e | `tests/test_generic_ai_e2e.py` (first half) | `misp-modules` installed | the real server lists the module and round-trips every fixture through `/query` |
| live e2e | `tests/test_generic_ai_e2e.py` (second half) | `.env` + MISP instance | the fixture uuids fetched live still validate and yield the same report |
| **round-trip gate** | `tests/test_e2e_roundtrip.py` | `.env` + MISP instance | 10 random live events survive `validate_event` → `process_event(e2etest=True)` semantically unchanged |

```bash
.venv/bin/pytest -q                                            # everything; live layers skip without .env
MISP_VERIFY_SSL=false .venv/bin/pytest -q                      # dev instance has a self-signed cert
MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_e2e_roundtrip.py   # the gate, prints seed + uuids
E2E_SEED=42 MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_e2e_roundtrip.py  # reproduce a draw
```

Conventions: live tests **skip** (never fail) when `.env` is missing, the key is rejected, the
host is unreachable or an event returns 404; `tests/conftest.py` holds the `.env` loader (last
line wins) and the read-only `MispApi` (`fetch`, `index`). The gate writes
`tests/e2etests/<uuid>.json` and `last_run.json` (gitignored).

"Identical" in the gate is semantic, defined in `tests/misp_compare.py`: null/empty values,
numeric strings, whitespace and ISO date-time spelling are ignored, plus four allowlisted PyMISP
normalisations. Widen the allowlist only with a stated reason, never to make a run pass.

Fixtures: `fixtures/output/*.json` are 8 real events exported from the instance in `.env`
(`hashes.csv` maps md5 → uuid), 5 with EventReports. Four uuids no longer exist on the instance
and always skip in the live layer. `tests/fixtures/orkl-sample.txt` (Emotet report, 15 KB) is
kept for extraction recall tests.

## 2. LLM access in tests

`.env` → `OPENAI_BASE_URL=http://nanu:11434/v1`, `OPENAI_MODEL=qwen3.8:latest` (Ollama). A
session fixture `llm` probes `GET /models` once; unreachable → every LLM test skips. Tests
never read the API key or endpoint from anywhere else. Measured 2026-09-04: three identical
requests with `seed=42, temperature=0` returned byte-identical text; cold call 17 s, warm 1.2 s.
Budget LLM tests accordingly (≈ 15 calls per full run).

`qwen3.8` is a reasoning model: with `max_tokens=120` only 54 characters of answer came back,
the rest was thinking. All use-case calls set `think: false` (Ollama) and size `max_tokens` for
the answer alone; a test asserts the answer is not truncated (`finish_reason == "stop"`).

## 3. Test plan per use-case

Gate = must be green before merge. Offline tests mock the LLM with a canned reply
(`monkeypatch` on `genai.llm.llm_chat`, the single LLM-call function), so they run everywhere.
Files: `tests/test_usecases_unit.py` (offline), `tests/test_llm_live.py` (live LLM),
`tests/test_generic_ai_e2e.py` (through misp-modules, live LLM for the use-case cases).

```bash
.venv/bin/pytest -q tests/test_usecases_unit.py                 # offline, ~2 s
MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_llm_live.py   # live, ~1-2 min, prints precision/recall
MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_llm_live.py --update-goldens  # re-record summaries
```

### UC1 — CTI info extraction

| test | layer | input | assertion | gate |
|---|---|---|---|---|
| adds attributes from canned JSON | unit | fixture `10a94632`, mock returns 3 valid IoCs | 3 new attributes, correct type/category/value, source report untouched | yes |
| every added attribute is tagged | unit | same | both `ai-computer-assisted` tags on each new attribute, `comment` names the report uuid; **no** new event tags | yes |
| hallucination guard | unit | mock returns a value not in the report | rejected, listed in `metadata.rejected` with reason `not-in-source` | yes |
| unknown type / wrong category | unit | mock returns `type: "ipv4"` | rejected, reason `unknown-type` | yes |
| PyMISP validation | unit | `type: sha256, value: "zz"` | rejected, reason `pymisp` | yes |
| format check | unit | `type: ip-dst, value: "999.1.1.1"` | rejected, reason `format` | yes |
| duplicate | unit | value already on the event (attribute and inside an object) | not added twice | yes |
| low confidence | unit | `confidence: 0.5` | rejected, reason `confidence` | yes |
| model returns non-JSON | unit | mock returns prose | `{"error": ...}`, event unchanged | yes |
| objects | unit | md5+sha256+filename of one file, one CVE | one `file` object, one `vulnerability` object, attributes inside them tagged | yes |
| round-trip still holds | unit | run extraction, then `misp_event_diff(original, result)` | only additions reported, nothing changed or dropped | yes |
| through misp-modules | local e2e | `/query` with `use_case: extraction` and mocked LLM via env flag | same as unit, over HTTP | yes |
| **precision gate** | live LLM | report of `10a94632` (and `59ed4725`, `ec93ed24`) vs hand-labelled `fixtures/gold/<uuid>.iocs.json` | precision ≥ 0.95; recall printed, not gated (high-confidence policy) | yes |
| determinism | live LLM | same report twice | identical attribute set | yes |
| recall report | live LLM | `tests/fixtures/orkl-sample.txt` wrapped as an EventReport | recall vs a labelled list, printed as a table | no (informational) |

The gold IoC lists (`fixtures/gold/*.iocs.json`) were seeded by regex over the report text and
completed by hand after the first live run; every entry is literally in the report. Results on
2026-09-04 with `qwen3.8`: `10a94632` (no real indicators) → 0 extracted, precision 1.0;
`59ed4725` (ToolShell) → filenames, hashes, CVEs and threat-actor names found, defanged IPs
correctly rejected; Emotet sample → all 11 hashes found (recall 1.0).

### UC2 — Summarization

| test | layer | input | assertion | gate |
|---|---|---|---|---|
| `kind` dispatch | unit | `kind="report"`, `"event"`, `"nope"` | right prompt chosen; unknown kind → error | yes |
| event rendering is deterministic | unit | fixture `10a94632` rendered twice; attributes shuffled in the input | identical bytes; sorted; all attribute values and object/related uuids present; no timestamps | yes |
| summary attached correctly | unit | mock returns a 4-section summary | new EventReport with the expected name, source reports untouched, **event** carries both AI tags, no attribute tags | yes |
| request selection | unit | body `summary_kind` vs config `default_summary_kind` vs default | precedence order | yes |
| through misp-modules | local e2e | `/query` with `use_case: summarization`, mocked LLM | same over HTTP | yes |
| **structural gate (L3)** | live LLM | dummy event + fixture `10a94632`, both kinds | required headings present; ≤ 200 words; every IoC/uuid in the summary exists in the input (no hallucinated indicators); tags present; `finish_reason == stop` | yes |
| repeat-run determinism | live LLM | same request 3× | identical text | yes |
| golden match (L1/L2) | live LLM | dummy event | see section 4 | warning only |

### Cross-cutting

| test | layer | assertion | gate |
|---|---|---|---|
| config precedence | unit | request > module config > `.env` > default for allowed keys | yes |
| request body cannot set `api_base` / `api_key` | unit | value ignored, endpoint from `.env` used | yes |
| timeout | unit (mock raises) | `{"error": "LLM timeout after N s"}`, no fallback output, nothing tagged | yes |
| pinned taxonomy strings | unit + network | the committed pinned list equals the predicate/value pairs in upstream `ai-computer-assisted/machinetag.json`; module uses only pinned strings | yes (network part skips offline) |
| prompt cluster resolution | unit | uuid → cluster; `value` → cluster; inline text; missing → default; parameters come from the cluster | yes |
| response metadata | unit | model name + digest, prompt cluster uuid/version/hash, rejected list, timing | yes |
| round-trip gate | live | unchanged: 10 random events through `process_event` default path | yes |

## 4. Deterministic summaries

The question: how can a test assert "the same summary" when an LLM writes it?

### 4.1 What is fixed

| dimension | how |
|---|---|
| input | `fixtures/summary/dummy-event.json`: hand-written, ~6 attributes, 1 object, 1 EventReport (≈ 300 words), 2 tags, 1 related event. Small enough that the whole prompt fits far below the context window and a human can judge the summary. |
| prompt bytes | rendering is sorted and whitespace-normalised; prompt text comes from the galaxy cluster; `prompt_sha256` recorded |
| sampling | `temperature 0, seed 42, top_p 1, stream false, think false, max_tokens fixed`, Ollama `num_ctx` fixed; no time or random ids in the prompt |
| model | name **and digest** (`/api/tags` → `22130167c4c2`), quantisation `Q4_K_M`, server `ollama 0.33.2` (`/api/version`) |

All sampling values come from the prompt cluster, not from code constants, so "which prompt"
and "which parameters" cannot drift apart.

### 4.2 Three strictness levels

| level | comparison | when it applies | on mismatch |
|---|---|---|---|
| L1 | byte-identical to the golden | `GOLDEN_STRICT=1` and golden header matches | fail |
| L2 | identical after whitespace collapse and trailing-punctuation strip | golden header matches (default) | warning with diff |
| L3 | structural: required headings, ≤ 200 words, every IoC/uuid mentioned exists in the input, no IoC that is not in the input, tags present, not truncated | always | **fail — this is the quality gate** |

Golden file `tests/golden/summary-<kind>-<cluster value>.md` starts with a header:

```
model: qwen3.8:latest  digest: 22130167c4c2  quant: Q4_K_M  server: ollama 0.33.2
prompt: summary-report/qwen3.8-v1  prompt_sha256: <hash>  recorded: 2026-09-04
---
```

If the header does not match the live endpoint (other digest, server version or prompt hash),
L1/L2 are **skipped with a message**, not failed — a different model cannot be expected to
reproduce another model's words. L3 still runs. Re-recording is explicit:
`pytest tests/test_summary_golden.py --update-goldens`, never automatic, and the diff is shown
in the commit.

### 4.3 Why seed + temperature 0 is necessary but not sufficient

Greedy decoding with a fixed seed is reproducible on the same model file, quantisation, server
version and hardware — measured today. It is not portable: different GPU kernels, batching,
KV-cache state, a re-quantised model or an Ollama upgrade change logits slightly, and at
temperature 0 one flipped token changes the rest of the text. That is why the golden header
pins the digest and server, and why L3 (meaning) is the gate while L1/L2 (wording) are
warnings. Do not "fix" an L2 drift by widening the normaliser; re-record and review the diff.

### 4.4 Repeat-run test first

Before any golden is trusted, `test_llm_is_deterministic` sends the same request three times
and requires identical output. If that fails, the endpoint does not honour `seed`/`temperature`
(or `think` leaked randomness) and every other LLM test is meaningless — so it runs first and
the others depend on it.

### 4.5 Reviewing a golden

A golden is only as good as the human who read it once. The recording command prints the
summary and the input side by side; the reviewer checks the four headings, that every indicator
mentioned is in the dummy event, and that nothing is invented. Only then is the file committed.

## 5. Coverage matrix

| | unit (mock) | local e2e (misp-modules) | live MISP | live LLM |
|---|---|---|---|---|
| module contract / validation | ✔ | ✔ | ✔ | – |
| round-trip gate | – | – | ✔ | – |
| UC1 extraction | ✔ | ✔ | – | precision gate, determinism |
| UC2 summary `report` | ✔ | ✔ | – | L3 gate, determinism, golden |
| UC2 summary `event` | ✔ | ✔ | – | L3 gate, determinism, golden |
| tagging rule | ✔ | ✔ | – | ✔ (asserted on live output) |

Gates that must be green before merging: unit, local e2e, round-trip gate, UC1 precision gate,
UC2 L3 gate, repeat-run determinism. Live layers skip (not fail) when their backend is down;
a merge with skipped gates is allowed only if the CI log shows the skip reason.

## 6. Golden files recorded

`tests/golden/summary-report.md` and `summary-event.md` were recorded on 2026-09-04
(`qwen3.8:latest`, digest `22130167c4c2`, Ollama 0.33.2) and reviewed: every indicator they
mention is in the dummy event, all four headings are present, both under 200 words.

## 7. Where tests run

Locally, against `nanu` and the dev MISP instance from `.env`. The developer-host loop in
README.md is an alternative when the laptop cannot reach them, not a requirement.
