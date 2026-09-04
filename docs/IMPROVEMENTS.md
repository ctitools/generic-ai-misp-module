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
    extraction answer was truncated on 35 of 100 orkl reports (one `quote` per indicator is
    expensive). Options: raise the budget in the cluster (v2 does, at the cost of multi-minute
    generations that need `request_timeout` > 120 s), shorten `quote` to a few words, or ask
    for values only and locate them in the text ourselves. Decide before the module is deployed
    on indicator-rich reports.
26. **Defanged values pass the LLM path unevenly.** `url` and `ip-dst|port` have no strict
    format check, so `http://169.197.142[.]162/vt.zip` is stored defanged while `ip-dst`
    `131.226.2[.]6` is rejected. Either refang as an explicit step or reject consistently.

