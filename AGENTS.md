# AGENTS.md

This repository should be worked in short, closed loops.

The target workflow is not "write a plan and disappear". The target workflow is "build something runnable, verify it, inspect it, then tighten the loop again".

## Operating Style

These are general instructions. 

- Start from the executable surface area.
- Prefer CLIs, HTTP routes, and reproducible file outputs over abstract refactors.
- Keep changes incremental and observable.
- When a task changes data flow, update the docs in the same pass.
- When a pipeline can fail, leave a deterministic fallback instead of a silent no-op.
- If a task takes long, log its progress in logs/ so that the human can be informed when the task might be finished. Always lot number of successes and failures as well as proceesing speed (rows/sec)
- After every change of the agent, document what you changed briefly in CHANGELOG.md 

## Default Loop

1. Read the relevant files first.
2. Identify the thinnest end-to-end path that proves the change.
3. Implement that path.
4. Run the path or explain the blocker concretely.
5. Capture the commands and data flow in docs.
6. Iterate from the observed result, not from an imagined perfect design.

## Repository Priorities

- Prefer official upstream sources over mirrors or convenience datasets.
- Keep intermediate artifacts on disk so they can be reused by humans and agents.
- Separate preparation from ingestion and ingestion from search.
- Prefer a clean sample over pretending the full dataset is cheap.
- Keep outputs deterministic enough to compare runs.
- Preserve enough metadata to trace every stored page back to its source.

# Chosen Stack

Use this stack unless the user asks to change it.

### Runtime And Tooling

1. Python `3.13`
2. `uv` for dependency management and command execution
3. `pytest` for tests

### Stdlib First

Prefer the standard library for:

1. filesystem paths: `pathlib`
2. structured data: `json`, `dataclasses`, `typing`
3. `pandas`
4. logging: `logging`
5. `click` for CLI parsing

### Approved Third-Party Dependencies

none

### Software Supply Chain checks
1. every dependency might pull in other dependencies. This is a DAG.
2. Check those if there are known vulnerabilities
3. If possible, use github for these checks
4. Reduce the number of dependencies to a minimum
5. If a dependency (pip package) is needed, ask first before installing it.
6. Remember and pin versions and their hashes

**When something looks wrong:**
7. If a package was published <48 hours ago, flag it.
8. If a maintainer account changed recently, flag it.
9. If the package name is close to a popular package, flag it (typosquatting).

### Security and coding best practices scans
1. Use the tools in .github/workflows also locally to check (before git pushing) if they complain.
2. If one of the tools complains, try to fix it.
3. Running pytest is not sufficient for good code. 

### Approved External Tools

none

### Dependency Policy

Keep the baseline dependency set permissive-license friendly.

You may add GPL or AGPL dependencies even without explicit user approval.



## Testcases first!!

Add tests as implementation grows. For every new .py file, make sure there is a decent coverage of test cases. 

Before every major release or git tag, re-run the benchmark suite to check for regressions:


- Iterate in inner to outermost loops:

1. unit tests
2. end2 end tests

## Required Output For New Pipelines

If you add or change a pipeline, leave behind:

- one command that runs it
- one artifact path that shows the result
- one verification step
- one doc update

## Repo-Specific Loops

### Setting up the development environment

1. You will find the DEVELOPER_HOST and _USER in your .env 
2. You have ssh access there. Only operate in DEVELOPER_HOST_DIRECTORY. Never somewhere else! You are sandboxed.
3. Generally, follow the README, ARCHITECTURE.md notes to set things up

On the DEVELOPMENT_HOST, do:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python=3.12 .venv
source .venv/bin/activate
git clone https://github.com/MISP/misp-modules.git && cd misp-modules
uv pip install .[all]
misp-modules
```


### Write test-cases first

Write test cases for the MISP AI Module.
Cover all endpoints
Simulate a text summarization use-case task
Input is a CTI report
Output is the summary

#### Unit tests

Loop:

0. make sure the development environment is set up
1. Download misp-modules (https://github.com/MISP/misp-modules)
2. install them on a development host. You will find the DEVELOPER_HOST and _USER in your .env 
3. You have ssh access there. Only operate in DEVELOPER_HOST_DIRECTORY. Never somewhere else! You are sandboxed.
4. write the test cases
5. run the test cases

#### E2E tests

Loop:
0. make sure the development environment is set up
1. Run the MISP module in the development environment
2. Make sure the User configured the MISP_HOST so that it has the MISP_MODULES_HOST (== DEVELOPER_HOST) configured properly in MISP_HOST (this is a manual step only once. )
3. Make sure you have the MISP_API_KEY and the MISP_HOST from .env
4. Now use the MISP API of MISP_HOST to 
 - fetch a random OSINT CTI report from orkl.eu's archive (https://archive.orkl.eu/) (text)
 - make sure it's markdown
 - upload it to a test MISP event
 - send the report to the AI Module from MISP for summarization
 - add the summary to the MISP event
 



## Code quality loop

- use  ruff, semgrep and pylint . See the .github/workflows actions. Use then locally as well. For that you can use the virtual env .venv-pylint/ 
- when writing new code, always run ruff, semgrep and pylint and if there are errors, fix them immediately.
- always run pytest on new code

## Documentation Discipline

- Keep usage examples copy-pasteable.
- Prefer a small number of obvious commands.
- Document the data flow, not just the code.
- Update docs when behavior changes.

## Things To Avoid

- Mixing raw download, transformation, and indexing into one opaque step.
- Writing code that only works if someone remembers hidden setup.
- Adding dependencies when the system tool already exists and is stable.
- Replacing a failed transformation with dropped data.
