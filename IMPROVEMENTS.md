# Repository analysis and improvement backlog

Analysis of `main` at `29ce262` (2026-09-04), before the `with_full_event` rewrite. Items marked
**done** were fixed by that rewrite; the rest are open.

## 1. Security

1. **Secrets in git history — open, needs action.** `.env` was committed in `59b7a76` ("first
   generated code trial") with a real `MISP_API_KEY` and `OPENAI_API_KEY`. Commit `e3c2128`
   "removed" them and `29ce262` untracked the file, but `git show 59b7a76:.env` still returns
   both. The working copy also carries a commented-out 40-character token above
   `OPENAI_API_KEY`. Treat all three as compromised: rotate the MISP and OpenAI keys, and either
   rewrite history (`git filter-repo`) or accept that the repo is burned for those keys.
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
16. **Old fixture `tests/fixtures/orkl-sample.txt` — open.** No test uses it any more. Keep it
    for the benchmark suite (below) or delete it.

## 4. Repository hygiene

17. **No CI although AGENTS.md references `.github/workflows` twice — open.** Add one workflow
    running `ruff check`, `ruff format --check`, `pylint`, `semgrep` and `pytest` on 3.14. The
    live e2e tests already skip without credentials.
18. **No lockfile — done.** A `[build-system]` was added and `uv.lock` (39 packages) is committed,
    as AGENTS.md asks. Hash pinning of the transitive tree is still worth a review.
19. **`benchmarks/` mandated by AGENTS.md and described in BENCHMARKS.md but absent — open.**
    The fixture set (5 events with reports) is a natural seed: reproduce each report's summary
    or extracted attributes from the report text and score coverage/correctness.
20. **README claimed artifacts that don't exist — done.** `artifacts/` and `logs/` were empty; the
    README listed six saved result files. Removed.
21. **AGENTS.md contradictions — partly done.** Python 3.13 vs 3.12 vs README 3.14 (now 3.14
    everywhere); `pandas`, `click`, `rich` listed under "Stdlib first" while third-party deps
    were "none" (still open: decide whether those three are wanted).
22. **`moduleinfo["author"]` was "OpenCode" — done.** Now "CIRCL / ctitools".
23. **misp-modules was an undeclared test dependency — done.** Declared as the `e2e` extra.
