# Repository analysis and improvement backlog

Analysis of `main` at `29ce262` (2026-09-04), before the `with_full_event` rewrite. Items marked
**done** were fixed by that rewrite; the rest are open.

## 1. Security

1. **Secrets in git history — keys rotated (2026-09-04), history still open.** `.env` was
   committed in `59b7a76` ("first generated code trial") with a then-valid `MISP_API_KEY` and
   `OPENAI_API_KEY`. Commit `e3c2128` "removed" them and `29ce262` untracked the file, but
   `git show 59b7a76:.env` still returns both. Both keys have since been rotated, so the
   remaining choice is whether to rewrite history (`git filter-repo`) before the repo is
   shared more widely, or leave the revoked values in place.
2. **TLS verification off by default — done (removed).** `verify_ssl` defaulted to `False`, so
   API keys went to `https://api.openai.com` over an unverified channel. If an HTTP backend
   returns, default to verified TLS; the e2e tests' `MISP_VERIFY_SSL=false` opt-in is for the
   self-signed dev instance only and never touches the module.
3. **Request body could override operator config — done (removed).** `_get_setting` read the
   top-level request first, so a `/query` payload could set `api_base`, `ollama_host`,
   `api_key`, `system_prompt`. That is an SSRF and exfiltration surface (point the module at an
   attacker host, or read the operator's key into the prompt). Only `moduleconfig` keys should
   ever be settable, and never from the request body.
4. **SSRF guard was partial — done (removed).** Only the URL scheme was checked; link-local and
   private hosts were reachable, and a `# nosemgrep` silenced the finding.
5. **Prompt injection — open for the next iteration.** When the hooks call an LLM, the
   EventReport markdown is untrusted CTI text. Delimit it, instruct the model to treat it as
   data, and validate model output before it becomes a MISP object.
6. `.env` defines `OPENAI_MODEL` twice and, since 2026-09-04, `MISP_API_KEY` twice; only the last
   line counts under `source`. Delete the stale lines.

## 2. Correctness

7. **Silent fallback tagged as AI-generated — done (removed).** Any backend failure produced a
   normal-looking `status_code: 200` report tagged `ai-computer-assisted:assistance-level="ai-generated"`
   even though no model ran. If a fallback returns, tag it differently or fail loudly.
8. **`handler()` crashed on malformed JSON — done.** Now returns `{"error": "Invalid JSON request: ..."}`.
9. **Dead `TimeoutError` branch — done (removed).** `urlopen` timeouts surface as `URLError`,
   so the dedicated handler was unreachable.
10. **`version()` mutated the global `moduleinfo` — done.** Returns a copy.
11. **PyMISP quirks discovered while testing** (worth an upstream issue each):
    - `MISPEvent.load()` mutates the caller's dict (pops `name` from objects). The module deep-copies first.
    - `MISPEvent.to_dict(json_format=True)` raises `ValueError` on ISO timestamps in real
      exports while `to_json()` works. The module serialises via `to_json()`.
    - `MISPGalaxyCluster.from_dict` rejects `distribution` on default clusters, which MISP's
      own `/events/view` output sets. The module strips it before loading.
    - `add_event_report()` raises `TypeError`, not a `PyMISPError`, when `name` is missing.
    - `to_json()` drops the event-level `timestamp` when the event is flagged edited, which
      `from_dict` does for published events via `publish()`. The module passes
      `force_timestamps=True`. Measured round-trip losses tolerated by the gate are listed in
      `tests/misp_compare.py`.

## 3. Design and maintainability

12. **No schema for EventReport upstream — documented.** See ARCHITECTURE.md "Schema
    provenance". Worth raising on `MISP/misp-rfc`: the prose defines EventReport, the embedded
    JSON schema does not, and its `additionalProperties: false` contradicts the prose.
13. **Undocumented settings — done (removed).** `api_key` and `use_case_prompt` were read but
    absent from `moduleconfig`, so MISP's UI could never expose them.
14. **Two version numbers — done.** `moduleinfo["version"]` (0.2) and `pyproject` (0.1.0) now both say 0.3.
15. **ARCHITECTURE.md contract unimplemented — open.** `tlp_level`, `model_parameters`
    (seed/temperature), `reference_uploaded_file`, the pydantic schema and the
    `status_code/metadata/answer/extra_tags` envelope exist only in the diagram. Decide per item
    whether it belongs in `process_event()`'s signature or in `moduleconfig`.
16. **Old fixture `tests/fixtures/orkl-sample.txt` — resolved.** Kept for the extraction recall
    report planned in TESTING.md (UC1, informational).

## 4. Repository hygiene

17. **No CI although AGENTS.md references `.github/workflows` twice — open.** Add one workflow
    running `ruff check`, `ruff format --check`, `pylint`, `semgrep` and `pytest` on 3.14. The
    live e2e tests already skip without credentials.
18. **No lockfile — done.** A `[build-system]` was added and `uv.lock` (39 packages) is committed,
    as AGENTS.md asks. Hash pinning of the transitive tree is still worth a review.
19. **`benchmarks/` mandated by AGENTS.md and described in BENCHMARKS.md — in progress.**
    `benchmarks/run_llm.py` runs the module's extraction over an orkl sample (see
    BENCHMARKS.md "Running"). Still open: the summary benchmark on the fixture set (5 events
    with reports): reproduce each report's summary from the report text and score it.
20. **README claimed artifacts that don't exist — done.** `artifacts/` and `logs/` were empty; the
    README listed six saved result files. Removed.
21. **AGENTS.md contradictions — partly done.** Python 3.13 vs 3.12 vs README 3.14 (now 3.14
    everywhere); `pandas`, `click`, `rich` listed under "Stdlib first" while third-party deps
    were "none" (still open: decide whether those three are wanted).
22. **`moduleinfo["author"]` was "OpenCode" — done.** Now "CIRCL / ctitools".
23. **misp-modules was an undeclared test dependency — done.** Declared as the `e2e` extra.

## 5. Dependencies

24. **`iocextract` 1.16.1 (benchmark baseline, 2026-09-04).** Declared in `pyproject.toml`
    and `uv.lock` but used only by `genai/classic.py` (tests and benchmarks); the request path
    never imports it (`tests/test_classic_unit.py` checks). Supply-chain notes: released
    2023-09-22, license GPL, wheel sha256
    `64b0c7faaf127974d780bbdf1e62b29e213495a112ca3befd1f1ae15e0693fc4`
    (from `https://pypi.org/pypi/iocextract/1.16.1/json`); one transitive dependency, `regex`
    2026.9.3 (Apache-2.0 AND CNRI-Python, released 2026-09-01). Nothing is younger than 48 h,
    the names match the well-known packages, no maintainer change observed. Known wart: on
    Python 3.14 the first import emits `SyntaxWarning`s for invalid escapes in iocextract's own
    source (cosmetic, compile-time only), and its email regex swallows the word before the
    address, which `classic.py` works around.
25. **Extraction answer budget (benchmark finding, 2026-09-05).** With `max_tokens 2000` the
    extraction answer was truncated on 35 of 100 orkl reports; the cluster now carries 10000
    and 5 reports still overflow. A probe of one overflowing answer: 79 distinct indicators,
    18 KB, pretty-printed JSON, the `quote` repeating the value, about 127 tokens per
    indicator; the prompt itself was 9.7k tokens. Options, cheapest first: ask for compact
    JSON (no indentation), drop or cap `quote` (the in-source filter already guards against
    hallucination; the quote is only used to group filename+hashes into file objects), or
    chunk long reports. Decide before deploying on indicator-rich reports.
26. **Defanged values passed the LLM path unevenly — done (2026-09-05).** `genai/refang.py` is
    the single refang function for the module, the classic baseline and the benchmark metrics;
    the original spelling is kept in the attribute comment. Hashes labelled with the wrong hash
    type are re-typed by length. `ip-src|port`, `ip-dst|port` and `hostname|port` gained format
    checks.

## 6. Open TODOs from the test-strategy review (2026-09-05, Aaron: keep as backlog)

Details and suggested fixes in docs/TESTING.md section 8; listed here so they are not lost.

27. **Correctness of LLM-only findings is unmeasured.** The extraction benchmark scores
    against a regex superset; hashes agree, but the values only the LLM finds (filenames,
    threat actors, malware names) are checked to be in the text, not to be indicators.
    TODO: a 20-report human-adjudicated review file, then a precision gate per type.
28. **Summary quality beyond structure is unmeasured.** A fluent but wrong Threat section
    passes every check; `summary_kind=event` is benchmarked only on the dummy event.
    TODO: entity agreement check (names in the summary must appear in the report), a
    10-report human review sheet per prompt version, benchmark `event` kind on the fixture
    events with reports.
29. **No context-size guard.** Nothing checks that report plus prompt fit the model's window;
    Ollama truncates silently on small-context models. TODO: use the context length from
    `llm.model_info` and fail (never fall back) when the prompt does not fit; unit test with a
    fake `model_info`.
30. **No adversarial inputs.** Prompt injection, empty or image-only reports, several reports,
    non-UTF-8, RTL text have no fixture. The in-source filter protects extraction by
    construction; the summary path can echo injected text. TODO: `tests/fixtures/adversarial/`
    with offline tests for the filter path and one live test that the summary does not repeat
    the injected sentence.
31. **Benchmark statistics.** One seed, one model, English only, reports capped at 40k chars,
    every run overwrites the previous numbers. TODO: `benchmarks/history.csv` appended by the
    compare scripts (date, commit, tag, cluster, model digest, headline metrics), Wilson
    intervals on pass rates, a second seed per release.
32. **The gold data set is far too small.** Three hand-labelled reports (two MISP fixtures,
    one Emotet sample; 38 indicators in total) carry every precision and recall number the
    module is judged by; one wrong label moves precision by 3 %. TODO: grow
    `fixtures/gold/` to a few dozen reports with a few hundred labelled indicators, drawn
    from the orkl sample (`benchmarks/data/orkl/`) so the same reports feed the benchmark and
    the gate; label every indicator type the module emits, not only hashes/IPs/URLs; record
    who labelled and when in the file; keep the precision gate at ≥ 0.95 and add a recall
    floor once the set is large enough to make one meaningful. Overlaps with item 27 (the
    adjudication of LLM-only values is the same labelling work).
33. **Move from `urllib` to `requests`, everywhere (Aaron, 2026-09-05).** HTTP is done with
    `urllib.request` in `genai/llm.py` (the LLM client), `benchmarks/orkl.py` (orkl.eu),
    `tests/conftest.py` (the read-only MISP client) and `tests/test_generic_ai_e2e.py`
    (misp-modules server); `genai/classic.py` and `benchmarks/compare.py` only use
    `urllib.parse` for URL splitting (stdlib, can stay). `requests` is already installed as a
    transitive dependency of PyMISP (2.34.2), so this adds no new package to the tree; declare
    it explicitly in `pyproject.toml` with a pinned version and note it under section 5.
    TODO, one refactor across the repo: replace `Request`/`urlopen` with `requests.Session`
    calls (timeouts kept, `verify=` for the tests' self-signed dev MISP, `raise_for_status`),
    map `requests.exceptions` where `urllib.error` is handled today (`llm.LLMError`, the
    conftest live gates, the orkl client's base-URL guard, semgrep's dynamic-urllib finding
    disappears), keep behaviour byte-for-byte (same error messages, same timeouts), then run the
    offline suite, the `--require-live` run and one benchmark pass as the gate. Update
    ARCHITECTURE.md ("llm.py is the only network code") and CLAUDE.md.
34. **Content tags only when the report states them (Aaron, 2026-09-05).** Extraction may
    suggest `tlp:*`, kill-chain / ATT&CK and confidence-taxonomy tags **only if the marking,
    phase or confidence statement is literally in the EventReport** (same in-source rule as
    for indicators, same provenance in the comment); otherwise the field stays empty. Never
    derive a kill-chain phase from the narrative, never turn the model's own `confidence`
    score into a `misp:confidence-level` tag. TLP and report-level confidence go on the event
    (event-level content, so the event gets the AI tags); a phase or technique tied to one
    indicator goes on that attribute. Same rule for `first_seen` / `last_seen`: per-indicator
    dates stated in the text, a stated publication date at most as `last_seen`, nothing inferred
    from the EventReport's `timestamp` (that is MISP's save time). TODO together with the
    `to_ids` decision (item 35) as one prompt/schema version bump.
35. **`to_ids` is set blindly.** Every extracted attribute gets PyMISP's per-type default
    (`ip-dst` true, `filename` true …), so a vendor's own domain or `mshta.exe` becomes
    actionable. TODO: an `actionable` boolean from the model, applied only to lower the
    default, recorded in the comment; plus ObjectReference links (exploits, connects-to,
    drops) between candidates the model already groups. From the RFC field review of
    2026-09-05.
36. **Galaxy clusters instead of free-text `threat-actor` / `malware-type` attributes — open
    TODO (Aaron, 2026-09-05).** The module emits `threat-actor: "APT28"` and
    `malware-type: "Emotet"` as text attributes (100 and 65 of them on the orkl sample). MISP
    practice is the cluster tag on the event, `misp-galaxy:threat-actor="APT28"` /
    `misp-galaxy:malware="Emotet"`, which correlates across instances and carries the
    galaxy's synonyms and references. TODO: resolve the model's name against the bundled
    misp-galaxy clusters (PyMISP ships them; exact value or synonym match only, no fuzzy
    matching), attach the cluster tag to the event and keep the literal name in the comment;
    a name with no cluster stays a text attribute as today. Event-level content, so the
    event gets both `ai-computer-assisted` tags. Overlaps with INTEGRATION_PLAN.md: MISP's
    `sendToLLM` contract expects `AI_ThreatActor` and tags the event with exactly this
    galaxy. Needs a labelled check that the resolved cluster is the one the report means
    (item 27's review file can carry it).

