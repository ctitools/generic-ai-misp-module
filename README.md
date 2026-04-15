# AI MISP Module

This repository now contains a runnable custom `misp-modules` scaffold for a Generic AI MISP enrichment module.

The first loop is intentionally thin:

- module name: `generic_ai`
- module type: `expansion`
- supported input: raw `text` requests or MISP `attribute` requests with `text` / `comment`
- output format: MISP `EventReport` in `misp_standard` format
- current behavior: live backend summarization when configured, with deterministic fallback when unavailable

The verified live backend path uses Ollama through its OpenAI-compatible endpoint at `http://10.72.0.4:11434/v1`.
The fallback keeps the module executable while preserving the Generic AI request shape described in the architecture notes.

The development-host bootstrap intentionally installs the base upstream `misp-modules` package, not the full `all` extra. That means the server logs warnings for optional upstream modules that are not installed, but the custom `generic_ai` scaffold still loads and runs correctly.

For a general architecture see [ARCHITECTURE.md](ARCHITECTURE.md).
For use-case descriptions see [USE-CASES.md](USE-CASES.md).

**Repository Layout**

```text
.
├── expansion/
│   └── generic_ai.py
├── tests/
│   ├── fixtures/orkl-sample.txt
│   ├── test_generic_ai_e2e.py
│   └── test_generic_ai_unit.py
├── artifacts/
├── logs/
├── CHANGELOG.md
└── pyproject.toml
```

**Development Host Bootstrap**

Run these commands from the local workstation in this repository so the local tree is mirrored into the sandboxed development host directory.

```bash
set -a && source .env
ssh "${DEVELOPER_USER}@${DEVELOPER_HOST}" "mkdir -p \"${DEVELOPER_HOST_DIRECTORY}\""
ssh "${DEVELOPER_USER}@${DEVELOPER_HOST}" 'curl -LsSf https://astral.sh/uv/install.sh | sh'
ssh "${DEVELOPER_USER}@${DEVELOPER_HOST}" 'export PATH="$HOME/.local/bin:$PATH" && cd "'"${DEVELOPER_HOST_DIRECTORY}"'" && uv python install 3.12 && uv venv --python 3.12 .venv'
ssh "${DEVELOPER_USER}@${DEVELOPER_HOST}" 'export PATH="$HOME/.local/bin:$PATH" && cd "'"${DEVELOPER_HOST_DIRECTORY}"'" && [ -d misp-modules ] || git clone https://github.com/MISP/misp-modules.git'
ssh "${DEVELOPER_USER}@${DEVELOPER_HOST}" 'export PATH="$HOME/.local/bin:$PATH" && cd "'"${DEVELOPER_HOST_DIRECTORY}"'" && uv pip install --python .venv/bin/python -e ./misp-modules'
rsync -az --delete \
  --exclude '.git' \
  --exclude '.env' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.ruff_cache' \
  --exclude '.semgrep' \
  ./ "${DEVELOPER_USER}@${DEVELOPER_HOST}:${DEVELOPER_HOST_DIRECTORY}/generic-ai-misp-module/"
```

**Run Command**

On the development host:

```bash
export PATH="$HOME/.local/bin:$PATH"
cd "$DEVELOPER_HOST_DIRECTORY"
.venv/bin/python -m misp_modules -c ./generic-ai-misp-module -l 127.0.0.1 -p 6666
```

For MISP_HOST integration the verified service listener was started on `0.0.0.0:6666` so MISP could reach it from outside the development host.

**Verification Step**

From the development host:

```bash
curl -s http://127.0.0.1:6666/modules | python3 -m json.tool
jq -Rs --arg uuid "0d2f54fb-3910-445c-aeb6-5fd28a7532d9" '{
  module: "generic_ai",
  attribute: {
    type: "text",
    uuid: $uuid,
    value: ("# ORKL CTI Report\n\n- Source fixture: tests/fixtures/orkl-sample.txt\n\n" + .)
  },
  use_case_category: "summarization",
  config: {
    backend: "openai",
    api_base: "http://10.72.0.4:11434/v1",
    default_model_id: "gemma4:latest",
    verify_ssl: false,
    summary_chars: 700
  }
}' generic-ai-misp-module/tests/fixtures/orkl-sample.txt |
  curl -s http://127.0.0.1:6666/query -H 'Content-Type: application/json' --data @- |
  jq .
```

**Artifact Path**

Saved verification artifacts include:

- `artifacts/live_openai_compat_response.json`
- `artifacts/misp_e2e_result.json`
- `artifacts/misp_e2e_event_reports.json`
- `artifacts/misp_e2e_fetched_event.json`
- `logs/live_openai_compat_metrics.json`
- `logs/misp_e2e_metrics.json`

**Data Flow**

1. MISP or a caller posts a `text` attribute or raw text to `/query`.
2. `expansion/generic_ai.py` extracts the input text and sends it to the configured backend.
3. The verified live path uses `backend=openai` with `api_base=http://10.72.0.4:11434/v1`, which targets Ollama's OpenAI-compatible API.
4. If the backend fails or is not configured, the module falls back to a deterministic summary.
5. The module returns `results.EventReport` plus `results.Tag` with `ai-computer-assisted` tags for `ai-generated` and `unreviewed`.
6. On `MISP_HOST`, the verified enrichment route is `enrich_attribute` on a `text` attribute, which stores the generated `EventReport` on the event and tags the event accordingly.

**Verified MISP_HOST Flow**

The successful end-to-end run used:

- report source: `tests/fixtures/orkl-sample.txt`
- event input: one `text` attribute containing a markdown-wrapped ORKL report
- enrichment route: `misp.enrich_attribute(<attribute_uuid>, "generic_ai")`
- result: a generated `EventReport` stored on the same event
- event tags: `ai-computer-assisted:assistance-level="ai-generated"`, `ai-computer-assisted:review-level="unreviewed"`

The successful run metadata is captured in `artifacts/misp_e2e_result.json`.
