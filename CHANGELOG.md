# Changelog

## 2026-04-15

- Bootstrapped a custom `misp-modules` expansion scaffold for a Generic AI module.
- Added live backend support in `expansion/generic_ai.py` for `ollama` and OpenAI-compatible `/v1` APIs, with a deterministic fallback when the backend is unavailable.
- Switched the module output to MISP `EventReport` in `misp_standard` format.
- Added unit and live service E2E tests for `/modules`, `/healthcheck`, and `/query`, including OpenAI-compatible local model coverage.
- Switched report-based testing to the fixed fixture `tests/fixtures/orkl-sample.txt` instead of fetching random ORKL archive content.
- Added `ai-computer-assisted` event tags to the MISP results so AI-generated content tags the containing event as `ai-generated` and `unreviewed`.
- Documented the development-host bootstrap, run command, artifact path, and verification step in `README.md`.
- Verified the scaffold on the development host with Python `3.12`, a shared `.venv`, and an editable upstream `misp-modules` install.
- Passed the remote quality loop: `pytest` (`13 passed`), `ruff`, `pylint`, and `semgrep`.
- Saved live backend smoke artifacts for both direct `ollama` and OpenAI-compatible Ollama queries.
- Configured `MISP_HOST` to use the Generic AI enrichment module and verified the end-to-end MISP flow with the fixed ORKL sample, a test event, a generated `EventReport`, and the expected event-level AI assistance tags.
- Captured the successful MISP end-to-end artifacts in `artifacts/misp_e2e_*.json` and the verification metrics in `logs/misp_e2e_metrics.json`.
