# Benchmarks

## Running: LLM extraction over the orkl sample

Data flow: `benchmarks/data/orkl/sample.json` (`{"seed", "n", "ids": [...]}`) and one
`benchmarks/data/orkl/<id>.json` per report (`id`, `title`, `plain_text`, ...) are produced by
the sampler; `benchmarks/run_llm.py` wraps each report as a MISP event with one EventReport,
sends it through `expansion.generic_ai.dict_handler` with `use_case=extraction` (the module as
deployed, LLM from `.env`) and writes one result per report.

```bash
.venv/bin/python -m benchmarks.run_llm                 # all ids in sample.json, resumable
.venv/bin/python -m benchmarks.run_llm --ids a,b --force
```

- artifact: `benchmarks/results/<id>.llm.json` = `{"model", "prompt", "indicators": [[type, value], ...], "rejected", "seconds"}`, or `{"error", "seconds"}` (a report is never dropped)
- progress: `logs/benchmark-llm.log` (ok/fail counts, reports/s, ETA); exit code 2 when the LLM is unreachable
- verification: `.venv/bin/pytest -q tests/test_run_llm_unit.py` (offline, mocked LLM)

Benchmarks exist per use-case and per community profile.

**Note well**: there are different MISPs out there which focus on different aspects. Such as law enforcement, classical CERTs, drones, etc.
We will call this "community profile".

Within a community profile, we have at least three dimensions for evaluation:
- model
- prompt
- use-case


## Models
Make sure that we support a few different models (on-prem, SaaS) are supported and documented.
Initially we could focus on:

* qwen3.6
* gemma4
* DeepSeek-V4
* gpt-oss:120b (?)
* nemotron (nvidia)
* kimi k2.x
* mistral models (mixtral 8x22b, -large)


## Prompts

Depend on the use-case. 

Combined with prompts's parameters (temp., seed, etc.)

## Use-case 

See [USE-CASES.md](USE-CASES.md). 
We initially focus on these use-cases fore the benchmark:

1. UC1: story-telling based on the contents of the events (i.e on the graph). The task here is to generate a CTI report (in natural language) based on the attributes, event, objects
2. UC2: summarization of the CTI report
3. UC3: info extraction
4. UC4: NER / tagging
5. UC5: Quality review (which tags are missing, etc.) --> recommendation engine on what other *similar* events have w.r.t tags, attributes, etc.


## Problems to consider
Older MISP data is very simplistic. It's not very valuable potentially for eval/benchmarking.

- clean out simplistic events to create a dataset which is more interesting.
- ask Sami for this ("LS eval"). Anything below a specific score gets dropped.
  - we are looking for edges and nodes, the use of objects, galaxies and taxonomies . That's a good indicator for the "matureness" of an event. Existing python script.
 
# Benchmarks

## Use-case 1: 

start with a set of 5 hand-crafted events and use that for the entire benchm. 
@igklocska to propose a simple JSON-* format for the stripped down KGs.
@aaronkaplan to review, make sure the benchmark runs and is reapeatable for individual models.
@igklocska ping Sami on the script.


