# TRAILSIGHT V2 — RUNTIME, CONFIGURATION, AND LOCAL OPERATION

This document describes the integrated V2 repository. The root [README](../README.md) is the shortest runbook.

## 1. Preparation/runtime split

Trailsight has two explicit phases.

Offline preparation reads the external IBM HI-Small transaction CSV, writes a runtime-safe canonical DuckDB, enriches synthetic Bank Country metadata, and materializes GARG snapshots, review bands, transaction priorities, and Network Pattern Alerts. It may be long-running and is never triggered by an HTTP request.

Interactive runtime is:

```text
React -> /api/v2 -> FastAPI -> deterministic domain -> read-only DuckDB
                              -> local JSON runtime state
                              -> optional bounded MCP/AI -> JSONL telemetry
```

The runtime requires neither the raw IBM CSV nor detector recomputation.

## 2. Repository-local artifact layout

```text
data/v2/runtime/trailsight_v2.duckdb   # generated analytical DB, uncommitted
data/v2/metadata/bank_country_v1.json  # checked-in deterministic metadata
data/state/runtime_state.json          # mutable operational state, uncommitted
data/traces/investigations-v2.jsonl    # mutable AI telemetry, uncommitted
eval_results/                          # generated evaluation output, uncommitted
```

The raw IBM source remains outside the repository. The generated analytical DB is opened read-only by the V2 domain repository. Mutable review/session state is deliberately separate.

`runtime_state.json` is created deterministically when missing. It is not checked in, so a fresh clone never inherits another analyst's review progress or AI-session consumption.

## 3. Runtime-state contract

The JSON store contains only:

```json
{
  "version": "runtime-state-v1",
  "alerts": {},
  "investigations": {}
}
```

Alert entries store current `review_status` and `updated_at`. Investigation entries store subject/origin identity, authoritative context identity, creation time, and `follow_up_used`.

Rules:

- absent alert state is `NOT_REVIEWED`;
- workflow is `NOT_REVIEWED -> IN_REVIEW -> REVIEWED`;
- `REVIEWED` is terminal in V2;
- an investigation entry is written only after a valid initial AI response exists;
- a successful follow-up persists `follow_up_used=true`;
- configuration, provider, infrastructure, and other failed attempts release the in-process reservation and do not consume the follow-up;
- concurrent follow-ups cannot both succeed within the one process;
- writes use an in-process lock, validated read/modify/write, same-directory temporary file, fsync, and atomic replace;
- the file contains no transcript, previous response, model reasoning, evidence cache, AML disposition, or hidden IBM truth.

This is a **single-process MVP**. Do not start multiple FastAPI workers against the same JSON state file.

## 4. Configuration

The checked-in `.env.example` is the canonical variable list:

```text
IBM_HI_SMALL_TRANSACTIONS_PATH       # offline preparation only
TRAILSIGHT_V2_DB_PATH                # default data/v2/runtime/trailsight_v2.duckdb
TRAILSIGHT_RUNTIME_STATE_PATH        # default data/state/runtime_state.json
TRAILSIGHT_TRACE_PATH                # default data/traces/investigations-v2.jsonl
OPENAI_API_KEY                       # optional; server-side only
TRAILSIGHT_MODEL                     # optional exact API model identifier
TRAILSIGHT_PROMPT_VERSION            # investigation-v2
TRAILSIGHT_MODEL_INPUT_USD_PER_MILLION   # optional telemetry estimate
TRAILSIGHT_MODEL_OUTPUT_USD_PER_MILLION  # optional telemetry estimate
```

Copy `.env.example` to the ignored `.env` and start Uvicorn with `--env-file .env`. Never commit a real key or machine-specific absolute path. Never put `OPENAI_API_KEY` in `frontend/.env*`.

`GET /api/v2/health` reports:

- deterministic runtime readiness and current latest snapshot metadata;
- `ai_configured=true` only when both `OPENAI_API_KEY` and `TRAILSIGHT_MODEL` are non-empty;
- `product_version=v2`.

The health flag does not make a provider call. Prompt/model/provider validation occurs on an investigation request. Missing AI configuration never blocks deterministic startup.

## 5. Local setup and startup

One-time dependency setup:

```bash
cp .env.example .env
uv sync --frozen
npm --prefix frontend ci
```

When the prepared database is absent:

```bash
uv run python scripts/v2_data_prepare.py \
  --source /absolute/path/to/HI-Small_Trans.csv \
  --output data/v2/runtime/trailsight_v2.duckdb

uv run python scripts/v2_detector_prepare.py \
  --database data/v2/runtime/trailsight_v2.duckdb
```

Backend:

```bash
uv run uvicorn trailsight_v2.api.app:create_app \
  --factory --env-file .env --host 127.0.0.1 --port 8000
```

Normal real-API frontend:

```bash
cd frontend
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. `VITE_TRAILSIGHT_API_BASE_URL` is only needed when the API is hosted elsewhere. Fixture mode is explicit through `npm run dev:fixture`; normal development and production builds have no runtime fixture fallback.

The production artifact check is `npm run build`. This repository does not require Docker and does not claim a production deployment topology.

## 6. AI and MCP lifecycle

The AI runner creates the bounded local stdio MCP child for an investigation/follow-up and closes it when complete. It passes only the V2 DB path, runtime-state path, and closed investigation scope. The MCP surface contains exactly seven typed tools; it exposes no raw SQL, filesystem, arbitrary graph traversal, or hidden-truth lookup.

One sanitized JSONL trace is appended per handled run where possible. It includes model/prompt provenance, timing, bounded tool order/status/latency/result sizes, evidence IDs, validation status, token usage, optional cost estimate, and failure code. It excludes secrets, transcript, private reasoning, full evidence payloads, raw history, AML disposition, and hidden truth.

## 7. Ground-truth isolation

Runtime startup does not require or mount hidden IBM labels or pattern annotations. Runtime schema validation rejects forbidden hidden-truth columns/views. The only permitted hidden-label reader is the explicit offline detector-evaluation path after detector outputs already exist.

## 8. Reproducibility and failure behavior

The generated DB records source checksum/count/range, data-contract and identity versions, Bank Country mapping version, detector provenance/config, snapshot state, and build metadata. Startup validates required tables and at least one applicable COMPLETE snapshot.

Failure behavior:

- missing/corrupt DB: fail startup safely; never prepare data from HTTP;
- incomplete snapshot: never use it as an applicable detector context;
- corrupt runtime state: reject state reads/mutations; never overwrite it silently;
- unwritable trace path: log telemetry degradation without exposing OS details to the browser;
- AI/MCP/provider failure: deterministic UI and APIs remain usable.

## 9. Release-candidate performance expectations

These are local-demo baselines, not service-level agreements. Recent warm prepared-DuckDB observations were approximately:

- Alerts list: 22 ms;
- Accounts list: 150 ms;
- Account Detail: 291 ms median;
- Account Network: 69 ms median;
- Transactions list: 105–140 ms;
- Transaction Detail: variable around 0.9–1.9 seconds at HTTP level after reducing the request from roughly 297 to roughly 32 SQL statements.

Treat restored N+1 loops, display-before-limit queries, hundreds of Transaction Detail statements, or fixture inclusion in the initial production bundle as regressions. Do not add connection pooling, caching, indexing, or materialization without a newly measured reason.

## 10. Repository hygiene and operational limits

Ignored local/generated material includes `.env`, `.venv`, caches, `frontend/node_modules`, `frontend/dist`, generated V2 runtime artifacts, mutable state, traces, eval outputs, notebooks/checkpoints, and generated delivery ZIPs.

Trailsight V2 is a local synthetic-data portfolio application. It does not include authentication/IAM, a multi-user state service, distributed workers, Kubernetes, cloud deployment, a message bus, or a secrets manager. Those omissions are explicit V2 limitations, not startup prerequisites.
