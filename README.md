# AI MISP Module

This repository now contains a runnable custom `misp-modules` scaffold for a Generic AI MISP enrichment module.

The first loop is intentionally thin:

- module name: `generic_ai`
- module type: `expansion`
- supported input: raw `text` requests or MISP `attribute` requests with `text` / `comment`
- current behavior: deterministic summarization fallback with no external AI dependency

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
│   ├── fixtures/sample_cti_report.md
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

**Verification Step**

From the development host:

```bash
curl -s http://127.0.0.1:6666/modules | python3 -m json.tool
curl -s http://127.0.0.1:6666/query \
  -H 'Content-Type: application/json' \
  --data @generic-ai-misp-module/tests/fixtures/sample_query.json | python3 -m json.tool
```

**Artifact Path**

The saved example response lives at `artifacts/sample_query_response.json` after the bootstrap and smoke test run.

**Data Flow**

1. MISP or a caller posts `text` or a MISP `attribute` to `/query`.
2. `expansion/generic_ai.py` extracts the input text and applies a deterministic summarization fallback.
3. The module returns a standard MISP expansion `results` payload plus metadata about the request.
4. The smoke-test response is saved to `artifacts/sample_query_response.json` for inspection.
