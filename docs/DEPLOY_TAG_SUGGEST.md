# Deploying misp-tag-suggest on the developer host and connecting the module

How the `tag_suggestion` use-case was brought up on `DEVELOPER_HOST` (nanu) on 2026-09-05,
step by step, so it can be redone by hand. Everything for misp-tag-suggest lives in
`DEVELOPER_HOST_DIRECTORY_TAG_SUGGEST` (from `.env`), the module in `DEVELOPER_HOST_DIRECTORY`.
Both `.env` files stay on the host, mode 0600, never in git.

```text
laptop ──rsync──▶ nanu:$DEVELOPER_HOST_DIRECTORY_TAG_SUGGEST   (misp-tag-suggest checkout)
                       │ scripts.export_events / snapshot_taxonomy   ← read-only MISP API (.env)
                       │ scripts.build_dataset / validate_dataset
                       │ retrieval.build_index --device cuda          ← GPU
                       ▼
                  uvicorn app:app 0.0.0.0:8000  (SUGGEST_API_KEY)
                       ▲
nanu:$DEVELOPER_HOST_DIRECTORY/generic-ai-misp-module ──POST /suggest──┘
   .env: MISP_TAG_SUGGEST_URL=http://127.0.0.1:8000, MISP_TAG_SUGGEST_API_KEY=<same key>
laptop .env: MISP_TAG_SUGGEST_URL=http://nanu:8000, same key   (live tests from the laptop)
```

## 0. Prerequisites on the host

- `uv` ≥ 0.12 (`uv self update`; 0.7 only knew a 3.14 beta) and `uv python install 3.14`.
- NVIDIA driver with CUDA 12.8 (`nvidia-smi`), ~2 GB free GPU memory for the BGE encoder.
- The host must reach the MISP instance in `.env`. nanu resolved `misp-dev.lo-res.org` to
  an IPv6 address without an IPv6 route ("No route to host") until Aaron fixed the routing;
  check with `curl -sk -o /dev/null -w '%{http_code}' https://$MISP_HOST/` (expect 302).

## 1. Install the code

```bash
# laptop, misp-tag-suggest is a sibling checkout of this repo
rsync -az --delete --exclude .venv --exclude data --exclude artifacts --exclude .env \
  --exclude acl.json --exclude __pycache__ ../misp-tag-suggest/ \
  $DEVELOPER_USER@$DEVELOPER_HOST:$DEVELOPER_HOST_DIRECTORY_TAG_SUGGEST/
# host
cd $DEVELOPER_HOST_DIRECTORY_TAG_SUGGEST
uv sync --group dev                       # Python 3.14 venv, CPU torch from the lock
```

GPU: the lock pins CPU-only torch on purpose (README of misp-tag-suggest). Swap it after
the sync; `uv run` would re-sync and undo it, so start the service with `.venv/bin/...`:

```bash
uv pip install --python .venv/bin/python "torch==2.11.0+cu128" \
  --index-url https://download.pytorch.org/whl/cu128     # newest cu128 wheel for cp314
.venv/bin/python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## 2. `.env` on the host

```dotenv
MISP_BASE_URL=https://misp-dev.lo-res.org
MISP_API_KEY=<read-only key>
MISP_VERIFY_SSL=false           # self-signed dev certificate
SUGGEST_API_KEY=<python3 -c "import secrets; print(secrets.token_hex(24))">
```

The first three are the same keys as in this repo's `.env` (copy them). `SUGGEST_API_KEY`
is read from the process environment by `app.py`, not from `.env`: export it when starting.

## 3. Data, dataset, index (misp-tag-suggest README steps 3-7)

```bash
cd $DEVELOPER_HOST_DIRECTORY_TAG_SUGGEST
nohup .venv/bin/python -m scripts.export_events --workers 1 > logs/export.log 2>&1 &   # resumable
.venv/bin/python -m scripts.snapshot_taxonomy         # data/taxonomy/snapshot.json
.venv/bin/python -m scripts.build_dataset --skip-near-dedup
.venv/bin/python -m scripts.validate_dataset          # data/processed/validation_report.md: Status: PASS
.venv/bin/python -m retrieval.build_index --device cuda   # artifacts/retrieval/*
```

Numbers from the 2026-09-05 run are at the end of this file. The export of 82k events took
about two hours, the dataset build about 25 minutes; both run detached (`nohup`) with logs in
`logs/`. `tests/test_suggest_live.py` checks every suggested tag against `GET /tags/index`
(27k tags, ~1 min once per session).

## 4. Run the service

```bash
cd $DEVELOPER_HOST_DIRECTORY_TAG_SUGGEST
set -a; . ./.env; set +a
nohup env MODEL_DEVICE=cuda .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 \
  > logs/service.log 2>&1 &
curl -s http://127.0.0.1:8000/health      # {"status":"ok","artifacts_ready":true,...}
```

`0.0.0.0` so the laptop can run the live tests against `http://nanu:8000`; the shared secret
is required on `/suggest` and `/similar`. Stop with `pkill -f "uvicorn app:app"`.

## 5. Connect the module

On the host, `$DEVELOPER_HOST_DIRECTORY/generic-ai-misp-module/.env` = this repo's `.env` plus:

```dotenv
MISP_TAG_SUGGEST_URL=http://127.0.0.1:8000
MISP_TAG_SUGGEST_API_KEY=<the SUGGEST_API_KEY above>
```

On the laptop the same two lines with `http://nanu:8000`. Then:

```bash
.venv/bin/python -c "from genai import suggest; s=suggest.SuggestSettings.from_env(); print(s, suggest.is_reachable(s))"
MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_suggest_live.py
MISP_VERIFY_SSL=false .venv/bin/pytest -q -s tests/test_e2e_misp_write.py -k tag_suggestion
MISP_VERIFY_SSL=false .venv/bin/python -m benchmarks.run_suggest --n 20 --k 5
```

## Run log 2026-09-05 (nanu, 2× RTX 4090, Ollama sharing the GPUs)

| step | result |
|---|---|
| export | 82,327 events, 9.4 GB `events.jsonl.gz`, ~2 h with `--workers 1` (resumable page shards) |
| taxonomy snapshot | 180 taxonomies (11 enabled), 148 galaxies (55,973 clusters), 298 custom tags; 89 MB |
| dataset | 75,377 representatives after exact dedup (6,950 unions); train 60,301 / val 7,538 / test 7,538, chronological split at 2025-08-11 and 2026-02-23; 33,905 labeled, 3,335 distinct labels, 499 with ≥20 train examples; `validate_dataset`: PASS |
| dropped labels (top) | `tlp:*` 94,521, free-text 68,035, "stone" predicates 26,819, namespace not allowlisted 19,508 (policy in `tagrec/allowlist.py`) |
| index build | `--device cuda`, BGE-base `a5beb1e3e68b`, 943 batches, ~10 min incl. validation sweep; selected k=25, similarity threshold 0.0 (never abstains on similarity; "abstained" then means no labelled neighbour). Validation (4,583 labelled events): precision@3 0.446, recall@3 0.726, candidate recall@25 0.884. Artifacts 172 MB `train_embeddings.npz` + 21 MB `index_meta.jsonl` |
| service | `uvicorn` on `0.0.0.0:8000`, `MODEL_DEVICE=cuda`, ~1 GB GPU memory after the first request; `/health` → `artifacts_ready: true` |
| module tests | nanu and laptop: `tests/test_suggest_live.py` (2) and `tests/test_e2e_misp_write.py -k tag_suggestion` (1) pass; example answer for fixture `10a94632`: `CERT-XLM:fraud="phishing"` 0.76, `misp-galaxy:mitre-attack-pattern="Phishing - T1566"` 0.12, … |
| benchmark | `run_suggest --n 20 --k 5` on nanu: precision 0.27, recall 0.13, hit@1 0.35, no suggestion for 10/20, 34 events/s; `benchmarks/results-suggest/20260905T195653Z.json` on nanu. First number, one seed, 20 events: a baseline for later index rebuilds, not a verdict |
