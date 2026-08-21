# TRAILSIGHT — 06 INTEGRATION AND DEPLOYMENT

# ROLE

You are the **Trailsight Integration, Docker, and Documentation Implementer**.

You run only after the component work packages are sufficiently complete.

# GOAL

Prove that the approved components work together as one reproducible local application, package them in one Docker deployment unit, and document the exact run/demo path.

This is an integration package, not a redesign package.

# SOURCE OF TRUTH

Read before changing anything:

1. `docs/implementation/00_SHARED_CONTRACTS.md`
2. all completed package instructions `01`–`05`;
3. the completion reports from WP01–WP05;
4. this file.

When integration exposes a contract failure, identify the failing contract and owning package. Do not silently move or duplicate responsibility.

# DEPENDENCIES

Before starting, verify:

## WP01 Data/Database

- runtime DuckDB can be generated;
- source provenance is verified;
- `demo-01` exists;
- eval-support cases exist;
- hidden label is absent;
- data tests pass.

## WP02 Backend/Domain

- deterministic domain tests pass;
- API deterministic routes pass;
- `app.state.investigation_service` exists;
- `demo-01` deterministic results match the fixture.

## WP03 MCP

- five tools registered unless Manager-approved cut applies;
- real stdio smoke passes;
- tool projections expose zero transaction refs/rows.

## WP04 AI/Evals/Observability

- AI router registers;
- evidence validation passes tests;
- trace writer works;
- 15 required eval scenarios exist;
- at least one live AI smoke has been run when credentials are available.

## WP05 Frontend

- `npm run build` passes;
- frozen one-screen workspace exists;
- API types match shared contract.

Do not begin integration with known failing owned-package acceptance criteria unless the Manager explicitly instructs you to isolate the integration blocker.

# FILE / DIRECTORY OWNERSHIP

## You own

```text
tests/integration/
Dockerfile
.dockerignore
.env.example
README.md
```

You may extend/reconcile the root `.gitignore` created by WP01 only to add missing integration/build exclusions. Preserve all WP01 source/runtime exclusions.

You may create a minimal root-level runtime helper script only if strictly required for Docker/startup and only after confirming no existing approved entrypoint covers it. Prefer not to create one.

## You may read

All repository files and completed package reports.

## You must not modify without Manager authorization

```text
src/trailsight_data/
src/trailsight/
src/trailsight_mcp/
src/trailsight_ai/
prompts/
evals/
data/cases/
frontend/src/
```

You may not "fix" a component-owned bug in integration by rewriting its logic.

If correction is required, return:

```text
failing contract
observed behavior
expected behavior
owning work package
minimal required correction
```

and wait for/route the correction through that package.

# INPUTS

Expected local inputs:

```text
external TransXion repository already downloaded with Git LFS
prepared Trailsight runtime DuckDB
OPENAI_API_KEY for live AI demo/evals
TRAILSIGHT_MODEL
TRAILSIGHT_PROMPT_VERSION
```

The raw TransXion CSV files remain outside the public Trailsight repository.

# REQUIRED IMPLEMENTATION

## 1. Verify the final dependency graph before integration

Use this frozen graph:

```text
                   00 SHARED CONTRACTS
                     /           \
                    v             v
              01 DATA/DB       05 FRONTEND
                    |
                    v
              02 BACKEND/DOMAIN
                    |
                    v
                 03 MCP
                    |
                    v
          04 AI/EVALS/OBSERVABILITY
                    \             /
                     \           /
                      v         v
                    06 INTEGRATION
```

Additional dependency:

```text
01 case catalog/runtime DB -> 04 eval scenarios
```

Do not reverse these responsibilities.

---

## 2. Verify Python regression before packaging

Run:

```text
uv sync --frozen
uv run pytest tests/data tests/backend tests/mcp tests/ai -q
```

If a test fails:

- do not delete/skip the test;
- identify its owner;
- stop integration for that boundary unless the failure is strictly in integration-owned configuration.

---

## 3. Verify frontend production build before Docker

Run:

```text
cd frontend
npm install
npm run build
```

Confirm:

```text
frontend/dist
```

exists and contains the production app.

Do not edit React source to fix an API mismatch. Report WP05/WP02/WP04 contract mismatch.

---

## 4. Verify FastAPI static-serving contract

Run FastAPI with:

```text
TRAILSIGHT_STATIC_DIR=<absolute path to frontend/dist>
TRAILSIGHT_DB_PATH=<prepared DB>
```

Verify:

```text
GET /api/health
GET /api/cases
GET /api/cases/demo-01
GET /
```

Expected:

- `/api/*` returns API JSON;
- `/` serves the built React workspace;
- API routing is not shadowed by static files.

If the static-serving extension point in WP02 cannot serve the Vite output as specified, report a WP02 integration contract issue. Do not replace FastAPI with another web server.

---

## 5. Verify AI router registration

With WP04 present, start the same FastAPI application.

Confirm routes exist:

```text
POST /api/cases/demo-01/investigations
POST /api/cases/demo-01/follow-up
```

Do not add duplicate routes in integration.

---

## 6. Verify MCP subprocess behavior through AI

The AI package owns stdio MCP startup.

During one live investigation, verify the application launches/connects to:

```text
python -m trailsight_mcp.server
```

and the trace contains actual MCP tool calls.

Do not add Supervisor, systemd, Docker Compose, or a second MCP container/process service.

The final deployment remains one application container; the stdio MCP process is a child process created by the AI path.

---

## 7. Create `.env.example`

Include only approved environment names with safe placeholders:

```text
TRANSXION_SOURCE_DIR=/absolute/path/to/TransXion
TRAILSIGHT_DB_PATH=/absolute/path/to/data/runtime/trailsight.duckdb
OPENAI_API_KEY=
TRAILSIGHT_MODEL=<configured model identifier>
TRAILSIGHT_PROMPT_VERSION=investigation-v1
TRAILSIGHT_TRACE_PATH=data/traces/investigations.jsonl
TRAILSIGHT_STATIC_DIR=frontend/dist
TRAILSIGHT_MODEL_INPUT_USD_PER_MILLION=
TRAILSIGHT_MODEL_OUTPUT_USD_PER_MILLION=
TRAILSIGHT_EVAL_JUDGE_MODEL=
```

Do not commit a real key or real user-local absolute path.

---

## 8. Extend/reconcile the existing `.gitignore`

WP01 creates the initial root `.gitignore` before any runtime/source-derived data is generated. Do not replace that file. Read it, preserve all WP01 source-data/runtime exclusions, and add only missing integration/build exclusions.

The following exclusions must remain present at minimum:

```text
.env
.venv/
__pycache__/
.pytest_cache/

frontend/node_modules/
frontend/dist/

data/runtime/*.duckdb
data/runtime/*.db
data/traces/*.jsonl
eval_results/

# Common accidental source-data locations
TransXion/
external/
data/source/
data/raw/
```

Preserve WP01's existing source/runtime exclusions, including `data/runtime/*`, `data/traces/*`, and `eval_results/*`. Do not weaken or remove them while reconciling more specific build patterns.

Do not ignore `data/cases/` or prompts/eval scenario definitions.

---

## 9. Create `.dockerignore`

Exclude at minimum:

```text
.git
.env
.venv
__pycache__
.pytest_cache
frontend/node_modules
frontend/dist
data/runtime
data/traces
eval_results
TransXion
external
data/source
data/raw
```

The Docker build context must not accidentally include raw TransXion data or a generated runtime DB.

The runtime DB will be mounted separately.

---

## 10. Create one multi-stage Dockerfile

The final image must be one deployment unit.

### Frontend build stage

Use a Node build stage to:

1. copy `frontend/package*.json` and required config;
2. install dependencies;
3. build Vite;
4. produce `frontend/dist`.

### Python application stage

Use Python 3.12 slim-compatible runtime.

It must contain:

```text
installed Trailsight Python packages
FastAPI
MCP server package
AI package
built React static assets
```

It must **not** contain:

```text
raw TransXion CSVs
runtime DuckDB baked into image
API key
local traces
eval_results
```

Install Python dependencies from the locked project manifest. Do not recalculate/unpin dependency versions during Docker build.

Copy the frontend build output to a stable image path, e.g.:

```text
/app/frontend/dist
```

Set the default static path appropriately through environment/default configuration.

Default application command must run the approved FastAPI app factory on port 8000.

Do not add nginx.

Do not add Docker Compose unless a second deployment service becomes Manager-approved; none is currently required.

---

## 11. Define the Docker runtime path contract

Use a stable in-container DB path:

```text
/app/data/runtime/trailsight.duckdb
```

At run time, mount the host-prepared DB **read-only** to that path.

Set:

```text
TRAILSIGHT_DB_PATH=/app/data/runtime/trailsight.duckdb
TRAILSIGHT_STATIC_DIR=/app/frontend/dist
```

For traces, mount a writable host directory if persistence is desired:

```text
/app/data/traces
```

Set:

```text
TRAILSIGHT_TRACE_PATH=/app/data/traces/investigations.jsonl
```

Do not make DuckDB writable merely because trace output needs a writable location. They are separate paths.

---

## 12. Docker build/run commands documented in README

Document an exact flow equivalent to:

```text
1. obtain/verify external TransXion
2. prepare runtime DB on host
3. run tests
4. build Docker image
5. run Docker with:
   - DB mounted read-only
   - traces mounted writable
   - OPENAI_API_KEY passed as environment
   - TRAILSIGHT_MODEL passed as environment
   - prompt version passed as environment
6. open http://localhost:8000
```

Do not copy `.env` into the image.

Do not place API key in the Dockerfile or command committed to README.

Use placeholder environment examples.

---

## 13. Create integration tests

Create under:

```text
tests/integration/
```

Keep them focused.

### Required non-live integration tests

#### A. Application startup/health

Against a deterministic runtime DB fixture:

```text
GET /api/health -> 200
```

#### B. Primary workspace

```text
GET /api/cases/demo-01
```

Verify primary deterministic fixture fields.

#### C. Hidden-label leakage

Serialize:

- case list;
- workspace response;
- handled error responses;

and assert forbidden hidden-label field/string is absent from structured field names/data.

Do not falsely fail because README/documentation discusses the firewall; this check is runtime response-only.

#### D. Static frontend serving

When a small built/test static directory is configured, verify root/static route works and `/api` still returns JSON.

#### E. AI route registration without live model

Verify investigation/follow-up routes are registered; mock the AI runner so no API credential is required.

### Live integration smoke

Keep live AI integration outside the normal default pytest run or behind an explicit marker/environment check.

Do not make normal CI/tests fail only because `OPENAI_API_KEY` is absent.

---

## 14. Run the complete primary demo manually

Use the real prepared runtime DB and configured model.

Verify this exact user flow:

### Step 1

Open Trailsight.

Expected: `demo-01` loads with deterministic workspace before AI.

### Step 2

Verify primary transaction:

```text
2025-05-08 16:18:46
A016568 -> A013644
69.54 CNY -> 9.40 USD
Cash
Synthetic Region 8 -> 4
cross-currency
cross-region
```

### Step 3

Verify deterministic historical facts:

```text
74 previous sender outgoing transactions
70 previous CNY transactions
median approximately 15.095
empirical percentile approximately 95.71
0 previous current-counterparty interactions
```

If region novelty remains in scope:

```text
Synthetic Region 4 previously seen = No
```

### Step 4

Click **Investigate transaction**.

Verify:

- 2–4 findings on successful run;
- actual adaptive MCP calls appear in trace;
- no evidence-reference validation failure;
- no fraud/laundering/suspiciousness conclusion.

### Step 5

Click one `[E#]`.

Verify:

- correct deterministic section focuses;
- matching historical rows highlight when supporting refs exist;
- no new model/API investigation request is triggered by the click.

### Step 6

Ask one supported bounded follow-up, e.g. counterparty or amount history.

Verify one or minimal necessary MCP tool use.

### Step 7

Reload/change case as needed, then ask an unsupported question through the follow-up flow, such as:

```text
Why did the sender make this transaction?
```

Verify explicit abstention/limit.

### Step 8

Verify a second follow-up cannot be submitted in the same selected-case frontend state.

---

## 15. Run explicit hidden-label leakage checks

Search runtime artifacts, not documentation/source instructions.

Check:

```text
runtime DuckDB schema
FastAPI JSON responses
MCP serialized outputs
AI trace JSONL
AI model-input test fixtures/logging if present
```

Confirm no production data field/value named:

```text
Is Laundering
```

Do not search external TransXion raw source and claim failure because the source naturally contains the field.

---

## 16. Verify no raw TransXion data is committed

Before completion inspect Git status/tracked files.

Raw files must not be tracked in the Trailsight repo:

```text
tx.csv
person.csv
merchant.csv
```

unless the Manager explicitly points to unrelated tiny test fixtures with different names/content created by the project itself.

Generated runtime DB must not be tracked.

Do not commit the external TransXion repository inside Trailsight.

---

## 17. Write README setup/documentation

Create a concise portfolio-grade `README.md`.

It must cover:

### What Trailsight is

Evidence-backed synthetic transaction-review assistant; analyst retains judgment.

### What it is not

No fraud/laundering/suspiciousness decision.

### Architecture

Briefly explain:

```text
React -> FastAPI -> deterministic Python -> DuckDB
                         ^
                         |
LLM -> stdio MCP --------+
```

Explain internal evidence versus model-facing summaries.

### Source data

Document:

```text
TransXion
synthetic dataset
external source repository
expected pinned commit 53932595c37c23b9f55ea5ddf5984e4d57b88369
Git LFS required by source repository for tx.csv
```

State clearly:

- raw TransXion CSV data is not committed to Trailsight;
- CSV redistribution licensing is not asserted by Trailsight;
- source data must be obtained externally;
- this is a project-governance constraint, not legal advice.

### Source-derived region

Document:

```text
Synthetic Region = numeric account suffix modulo 20
```

and clearly say it is not real geography/country/corridor.

### Setup

Exact host preparation commands and environment variables.

### Tests

Exact pytest/build/eval commands.

### AI evals

Explain 15 required scenarios, prompt/model version recording, and eval-results location.

### Run Docker

Exact build/run pattern with read-only DB mount.

### Demo

Short step sequence for `demo-01`.

### Observability

Explain JSONL trace location and contents.

Do not turn README into a huge enterprise architecture document.

---

# REQUIRED TESTS

## Integration checks

Run all of the following.

## Full non-live Python regression

```text
uv run pytest tests/data tests/backend tests/mcp tests/ai tests/integration -q
```

## Frontend production build

```text
cd frontend
npm run build
```

## Docker build

From repo root:

```text
docker build -t trailsight:local .
```

## Docker run smoke

Run with:

```text
runtime DuckDB mounted read-only
traces directory mounted writable
TRAILSIGHT_DB_PATH set to mounted DB
TRAILSIGHT_STATIC_DIR set to image frontend dist
TRAILSIGHT_MODEL set
TRAILSIGHT_PROMPT_VERSION set
OPENAI_API_KEY passed only when live AI smoke is performed
```

Verify:

```text
GET /api/health
GET /api/cases/demo-01
GET /
```

## Live AI smoke

When API credentials exist:

- one `demo-01` investigation;
- one supported follow-up;
- one unsupported/abstention follow-up in a fresh UI case state/run;
- inspect JSONL trace.

## Required eval gate

Confirm WP04 has a completed 15-scenario result for the chosen final prompt/model combination or run it before final handoff.

Scenarios 16–20 are optional.

# DO NOT CHANGE

Do not:

- redesign domain/MCP/AI/frontend;
- move calculations into integration code;
- replace FastAPI with nginx/another server;
- add Docker Compose without a Manager-approved second service;
- add Postgres/Redis;
- add cloud deployment;
- bake raw data/runtime DB into image;
- commit secrets;
- change evidence IDs;
- weaken evidence validation;
- add retries;
- change tool contracts;
- edit product UI features;
- add hidden labels;
- silently patch another work package's files.

# ACCEPTANCE CRITERIA

This package is complete only when:

1. all required component tests pass together.
2. frontend production build passes.
3. FastAPI serves API + built React from one application runtime.
4. AI routes register without duplicate endpoint definitions.
5. AI path connects to the approved local stdio MCP server.
6. one Docker image builds successfully.
7. runtime DB is mounted read-only and is not baked into the image.
8. trace directory is independently writable.
9. no raw TransXion data/runtime DB/API key is tracked or copied into Docker image.
10. primary deterministic demo facts match the approved fixture.
11. live AI smoke works when credentials are available.
12. evidence click works end to end in the browser.
13. unsupported question produces abstention/limits.
14. hidden-label leakage checks pass at runtime boundaries.
15. README documents source provenance, external-data setup, architecture, tests, evals, Docker, and demo.
16. the final selected prompt/model has a 15-scenario eval result.
17. no component architecture was silently redesigned.

# COMMANDS TO RUN

From repo root:

```text
uv sync --frozen
uv run pytest tests/data tests/backend tests/mcp tests/ai tests/integration -q
```

Frontend:

```text
cd frontend
npm install
npm run build
cd ..
```

Docker:

```text
docker build -t trailsight:local .
```

Then run the image using documented safe environment variables and mounts. Do not put a real API key in a committed shell script.

After container startup, smoke:

```text
GET http://localhost:8000/api/health
GET http://localhost:8000/api/cases/demo-01
GET http://localhost:8000/
```

Run live AI/evals only with explicit credentials.

# RETURN WITH

Return to the Manager:

1. files created/modified;
2. component dependency checklist and status;
3. full pytest command and pass/fail counts;
4. `npm run build` result;
5. Docker build result and image name;
6. Docker run/health smoke result;
7. primary demo deterministic values observed;
8. live AI smoke tool sequence/status if credentials available;
9. evidence-click verification result;
10. abstention verification result;
11. hidden-label leakage-check result;
12. Git tracked-file check confirming raw TransXion/runtime DB/secrets are absent;
13. final prompt/model identifier and required 15-scenario eval summary;
14. every contract failure found, mapped to owning work package;
15. explicit statement: **No product/architecture redesign was made during integration.**
