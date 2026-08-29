# TRAILSIGHT V2 — RUNTIME AND DEPLOYMENT DESIGN

## 1. Preparation/runtime split

Trailsight V2 has two explicit phases.

### Offline preparation

Runs on the developer/analyst machine before runtime:

```text
IBM HI-Small external source
-> runtime-safe canonical ingestion
-> bank-country enrichment
-> day-edge preparation
-> GARG daily snapshots
-> account states/bands
-> transaction review states
-> Network Pattern Alerts
-> generated analytical DuckDB
```

This phase may take significant wall-clock time and is restartable/checkpointed.

### Interactive runtime

Runs the product:

```text
React static build
+ FastAPI
+ deterministic domain
+ read-only generated DuckDB
+ local MCP child for AI runs
+ small writable runtime state
+ writable JSONL traces
```

Runtime never requires the raw IBM CSV or GARG recomputation.

## 2. Logical generated-artifact layout

The implementation chat must inspect the actual V1 ZIP before choosing exact existing paths, but the V2 repository should converge on the following logical areas:

```text
data/generated/v2/
  trailsight_v2.duckdb           # generated, uncommitted
  detector/                      # snapshot checkpoints/intermediate outputs, uncommitted
  manifests/                     # generation manifest/checksums, generated

data/state/
  runtime_state.json             # writable local operational state, uncommitted

data/traces/
  investigations-v2.jsonl        # writable runtime trace, uncommitted

eval_results/v2/
  ai/
  detector/
```

Raw IBM files remain outside the repository and are referenced by environment/config path.

Checked-in configuration/provenance definitions may live under a V2 config/data-contract area, for example:

- country metadata list;
- detector config defaults;
- prompt files;
- eval scenario definitions;
- documentation.

## 3. Analytical runtime DB mode

Mount/open the generated DuckDB **read-only** in product runtime.

Benefits:

- detector/account/transaction review state cannot mutate accidentally;
- reproducibility is clear;
- hidden-truth firewall is easier to assert;
- MCP/API cannot become write paths.

All mutable operational state is separate from the analytical DuckDB.

## 4. Runtime-state persistence

V2 has two small categories of mutable operational state that must survive a normal app restart when the mounted state path is retained:

1. Network Pattern Alert review progress;
2. minimal investigation-session metadata needed to reload authoritative context and enforce exactly one follow-up.

Use one small JSON file rather than adding another database service. File name and logical shape are frozen:

```text
runtime_state.json

{
  "version": "runtime-state-v1",
  "alerts": {
    "<alert_ref>": {
      "review_status": "NOT_REVIEWED | IN_REVIEW | REVIEWED",
      "updated_at": "<UTC RFC3339 timestamp>"
    }
  },
  "investigations": {
    "<investigation_id>": {
      "subject_type": "ALERT | TRANSACTION | ACCOUNT",
      "subject_ref": "<canonical ref>",
      "origin_alert_ref": "<alert_ref | null>",
      "origin_transaction_ref": "<transaction_ref | null>",
      "context_identity": {
        "kind": "ALERT_ENTRY | TRANSACTION | SNAPSHOT",
        "ref": "<authoritative origin/snapshot ref>",
        "time": "<canonical context timestamp>",
        "snapshot_id": "<snapshot_id | null>"
      },
      "follow_up_used": false,
      "created_at": "<UTC RFC3339 timestamp>"
    }
  }
}
```

Rules:

- absent alert review entry = NOT_REVIEWED;
- create an investigation entry once authoritative context is resolved and `investigation_id` is allocated;
- investigation state stores no chat transcript, previous model response, private reasoning, evidence payload cache, AML disposition, or IBM hidden truth;
- follow-up reloads subject/context only from this persisted entry plus deterministic runtime data;
- accepting a follow-up atomically changes `follow_up_used=false -> true` before AI execution; a second attempt returns 409 `FOLLOW_UP_ALREADY_USED`;
- mutations use one in-process lock, read/validate/modify, same-directory temp write, flush/fsync, then atomic replace;
- single FastAPI process/worker remains the MVP concurrency assumption;
- validate referenced alert/transaction/account/context against immutable runtime data before writing/reusing state;
- state survives normal app restart when its mount/path is retained;
- no AML disposition fields.

If the existing V1 repository already has a simpler safe local state mechanism, implementation may reuse it only if it obeys this same contract.

## 5. Configuration/environment

Recommended runtime variables:

```text
TRAILSIGHT_V2_DB_PATH
TRAILSIGHT_RUNTIME_STATE_PATH
TRAILSIGHT_TRACE_PATH
TRAILSIGHT_STATIC_DIR
TRAILSIGHT_MODEL
TRAILSIGHT_PROMPT_VERSION
OPENAI_API_KEY
```

Offline preparation/detector variables:

```text
IBM_HI_SMALL_TRANSACTIONS_PATH
IBM_HI_SMALL_PATTERNS_PATH          # offline evaluation only; never runtime app
TRAILSIGHT_V2_GENERATED_DIR
GARG_WORKERS                        # default 1
```

Optional telemetry pricing:

```text
TRAILSIGHT_MODEL_INPUT_USD_PER_MILLION
TRAILSIGHT_MODEL_OUTPUT_USD_PER_MILLION
TRAILSIGHT_EVAL_JUDGE_MODEL
```

Do not put real secrets/absolute user paths in committed `.env` files.

## 6. Ground-truth path isolation

The runtime command/container must not require or mount:

```text
IBM_HI_SMALL_PATTERNS_PATH
raw Is Laundering data source
```

Offline evaluation is a separate developer command that explicitly opts into those files.

Generated runtime DB startup validation rejects hidden-truth columns/views.

## 7. Docker decision

One application image, multi-stage build.

### Frontend build stage

- install existing/pinned Node dependencies;
- build Vite V2 frontend;
- produce static assets.

### Python runtime stage

Contains:

- FastAPI application;
- deterministic V2 domain;
- MCP/AI packages;
- built frontend assets;
- Python dependencies.

Does not contain:

- raw IBM dataset;
- `Patterns.txt`;
- generated analytical DuckDB;
- detector checkpoints;
- runtime state;
- traces;
- API keys;
- offline evaluation reports containing hidden truth.

## 8. Docker runtime mounts

Conceptual:

```text
/generated/trailsight_v2.duckdb -> /app/data/trailsight_v2.duckdb : read-only
/state/                          -> /app/state/ : read-write
/traces/                         -> /app/traces/ : read-write
```

Environment supplies the model key/config.

Do not add Docker Compose merely for MCP; MCP remains a stdio child process inside the application container.

## 9. Application startup

Startup order:

1. load runtime configuration;
2. verify V2 DB path exists and is readable;
3. open DuckDB read-only;
4. validate source/product schema version;
5. validate required tables;
6. assert forbidden ground-truth columns/tables are absent;
7. validate at least one COMPLETE detector snapshot exists (unless explicitly running a data-only developer mode);
8. initialize deterministic service factory;
9. validate/create `runtime_state.json` path and validate/create the `runtime-state-v1` structure;
10. initialize trace writer path;
11. register deterministic API routes;
12. register AI routes; AI may report unconfigured if API key/model is absent;
13. serve built React assets if static path exists.

A missing OpenAI key must not stop deterministic application startup.

## 10. Static serving

Serve Vite production files through FastAPI in the final local runtime.

Rules:

- `/api/v2/*` always wins over SPA fallback;
- known static assets served directly;
- non-API frontend paths fall back to `index.html` for React Router;
- development backend can run without built static assets.

No nginx required.

## 11. MCP lifecycle

For the bounded local demo, launch the one stdio MCP child per AI investigation/follow-up run and close it when complete, reusing the V1 pattern if already working.

Pass only runtime-safe configuration:

- V2 DB path;
- investigation scope/context information;
- no hidden-truth paths.

Do not add HTTP MCP hosting or a process manager.

## 12. Trace file behavior

JSONL trace path is writable and separate from analytical DB.

Requirements:

- append one complete record/run where possible;
- include exact prompt/model/tool order/latency/evidence validation;
- rotate manually/developer-side if file becomes large; no log platform required;
- traces are gitignored;
- no hidden benchmark truth.

## 13. Detector workflow execution

The offline detector runner should expose explicit stages so a failure does not require restarting everything:

```text
1. ingest/validate-runtime-safe-data
2. build-bank-metadata
3. prepare-daily-edge-deltas
4. generate-snapshot <cutoff or all>
5. assign-bands
6. materialize-transaction-priorities
7. generate-alerts
8. validate-runtime-db
```

Exact CLI names may be chosen by the implementation package after ZIP inspection, but stage boundaries and restart semantics are frozen.

### Resume behavior

- recognize COMPLETE snapshot checkpoints with matching config hash;
- skip/reuse them;
- re-run FAILED/incomplete snapshot;
- never mix outputs from different detector/identity/config versions into one runtime DB.

## 14. Reproducibility manifest

Generated runtime output must record:

```text
Trailsight V2 schema/data-contract version
IBM raw transaction SHA-256
raw row count
source min/max timestamp
bank-country mapping version
account identity version
transaction-ref version
GARG upstream/reference provenance
GARG variant/config
GARG eligibility version
review-band policy version
snapshot cutoffs generated
snapshot statuses
build timestamp
application git commit if available
```

A runtime DB with mismatched/incomplete manifest fails startup rather than silently serving mixed state.

## 15. Git ignore requirements

Ignore at minimum:

```text
.env
__pycache__/
.pytest_cache/
frontend/node_modules/
frontend/dist/
data/generated/v2/
data/state/runtime_state.json
data/traces/*.jsonl
eval_results/v2/
```

Also ignore any repository-local accidental raw IBM source directories used by the project.

Preserve small checked-in test fixtures/configs/documentation.

## 16. Performance targets

Targets are local-demo engineering goals, not enterprise SLAs.

With warm filesystem/cache on the target Mac:

- transaction list page (50 rows, common filters): **<500 ms target**;
- alert/account list page: **<500 ms target**;
- transaction detail deterministic payload: **<1.0 s target**;
- account detail base payload: **<1.0 s target**;
- bounded one-hop network: **<1.5 s target**;
- evidence resolution/support page: **<1.0 s target**;
- application startup after DB exists: **<10 s target**;
- AI latency measured separately and does not block deterministic page render.

If a specific selective lookup exceeds target, benchmark before adding DuckDB indexes/materialization.

## 17. Detector performance targets

Offline, not runtime:

- final/full snapshot baseline target ≤30 min on target Mac;
- peak RSS <70% physical RAM;
- all daily snapshots run sequentially;
- total snapshot build may take hours and is acceptable because it is a reproducible preparation step;
- every snapshot checkpoint allows restart.

If baseline fails, use the parity-gated compact scorer contingency in `02_DATA_AND_DETECTOR.md`.

## 18. Failure recovery

### Runtime DB missing/corrupt

Fail startup with safe actionable message. Do not regenerate GARG from an HTTP request.

### Incomplete detector snapshot

Ignore it for applicable-snapshot lookup; only COMPLETE snapshots are valid. If latest expected snapshot missing, health may report degraded preparation completeness.

### Runtime-state corruption

Fail alert-review and investigation-session mutations and report a local state-file error while deterministic analytics remain read-only/usable. Do not overwrite corrupt state blindly.

### Trace path unwritable

Report telemetry degradation; do not expose raw OS error to browser.

### AI unavailable

Deterministic application remains usable.

### MCP failure

Only AI investigation fails/partials; deterministic application remains usable.

## 19. Deployment flow

```text
Developer obtains IBM HI-Small externally
        |
        v
Run V2 data + detector preparation
        |
        v
Validate generated runtime DB + tests
        |
        v
Build frontend
        |
        v
Build one Docker image
        |
        v
Run container with read-only DB mount + writable state/traces + API key env
        |
        v
Open /alerts
```

No cloud deployment is required for V2 acceptance.

## 20. Security/operational limits

This is a local synthetic-data portfolio application, not production banking infrastructure.

Do not add:

- authentication/IAM system merely for appearance;
- Kubernetes;
- managed database;
- message bus;
- distributed tracing backend;
- secrets manager dependency;
- background job infrastructure in runtime.

The heavy detector pipeline is an explicit developer/offline command.

## FINAL IMPLEMENTATION OWNERSHIP AND ARTIFACT HYGIENE

Implementation delivery follows `09_IMPLEMENTATION_ROADMAP.md`.

Root/runtime integration is intentionally deferred to WP06 Codex except for narrowly authorized package changes:

- WP01 may add source/runtime safety ignores to `.gitignore` and only strictly required data dependencies;
- WP02 may add only detector/GARG dependencies required by its approved implementation;
- WP05A/WP05B own `frontend/package.json` and its lockfile;
- WP06 performs final Python/frontend dependency reconciliation, Docker, `.env.example`, README, startup, and generated-artifact audit.

The inspected repository ZIP contains local `.env`, `.venv`, `frontend/node_modules`, `frontend/dist`, runtime DuckDB, traces, and eval outputs. Those are not package-delivery inputs/outputs to redistribute. Scoped `WPXX_DELIVERY.zip` files must contain only owned changed/new repository files plus merge/completion metadata. Secrets, raw IBM files, generated analytical DBs, traces, model eval outputs, local virtual environments, and node_modules must never be included in a replacement delivery.

Final Codex integration may remove proven-dead V1 runtime code only after active V2 imports/tests/builds demonstrate replacement. It must not delete V1 code preemptively during earlier waves.



## Implementation ownership note

Root runtime/deployment integration (`Dockerfile`, `.dockerignore`, `.env.example`, README/startup glue and final dependency reconciliation) is final-WP06 ownership unless a runnable earlier WP explicitly authorizes a narrow shared-file change. WP01 may add raw-data/generated-runtime `.gitignore` protections; those protections must survive WP06 reconciliation. This is an implementation ownership rule only and does not alter runtime architecture.
