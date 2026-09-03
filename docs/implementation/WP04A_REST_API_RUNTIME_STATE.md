# TRAILSIGHT V2 — WP04A REST API AND RUNTIME STATE

> **Historical implementation ticket — complete.** Do not use this file as a current runbook.

## PACKAGE
WP04A — Deterministic REST API and Minimal Runtime State

## IMPLEMENTER
**REGULAR CHATGPT**

## PURPOSE
Implement the deterministic FastAPI `/api/v2` resources, cursor pagination/search/filtering, alert review-status mutations, minimal atomic `runtime_state.json` investigation-session persistence, and the app-state composition seam—without MCP/LLM behavior.

## WHY THIS IMPLEMENTER
FastAPI pagination/resource/state work is bounded by frozen schemas and the WP03 service. Separating it from MCP/AI avoids SDK coupling and creates disjoint paths suitable for parallel replacement delivery.

## PREREQUISITE
Use the latest Manager-approved repository ZIP after WP02 and WP03 have both passed and Merge Gate A has produced the merged core (`R2_CORE.zip`).

## REQUIRED INPUTS
Attach exactly:

1. latest Manager-approved merged-core repository ZIP after WP02 + WP03 (`R2_CORE.zip`)
2. complete FINAL Trailsight V2 system-design ZIP
3. this file: `WP04A_REST_API_RUNTIME_STATE.md`

Any upstream completion reports supplied by the Manager are supplementary; inspect the actual merged repository for the concrete detector/domain import paths.
## DESIGN DOCUMENTS TO READ
Read `docs/v2/00_PRODUCT_CONTRACT.md`, `docs/v2/01_SYSTEM_ARCHITECTURE.md`, `docs/v2/03_DOMAIN_AND_EVIDENCE.md`, `docs/v2/04_API_AND_MCP.md`, `docs/v2/07_RUNTIME_AND_DEPLOYMENT.md`, `docs/v2/08_TESTING_AND_ACCEPTANCE.md`, `docs/v2/09_IMPLEMENTATION_ROADMAP.md`.

## OWNED PATHS
Own/create:
```text
src/trailsight_v2/api/**
tests/v2/api/**
```
Concrete runtime-state implementation belongs inside this API/runtime area, preferred:
```text
src/trailsight_v2/api/runtime_state.py
```

## FORBIDDEN PATHS
Do not modify `domain/**`, `detector/**`, `mcp/**`, `ai/**`, frontend, Docker/README, prompts/evals, or V1 runtime packages.

## SHARED-FILE AUTHORITY
No root dependency changes unless Manager explicitly authorizes a missing FastAPI/runtime dependency. Current baseline already includes FastAPI/Pydantic. No frontend/Docker changes.

## IMPLEMENTATION RESPONSIBILITIES
Implement the frozen deterministic `/api/v2` resources except AI investigation/follow-up routes owned by WP04B:
- health/runtime-safe startup checks;
- Alerts list/detail + PATCH review status;
- Transactions list/detail with frozen search/filter/cursor pagination;
- Accounts list/detail with latest/historical origin semantics;
- Evidence GET resolution endpoint;
- safe error envelope/status codes;
- runtime-state store `runtime_state.json` with alert review status and minimal investigation session records;
- `TRAILSIGHT_RUNTIME_STATE_PATH`;
- atomic same-directory temp write + replace under single-process MVP assumption;
- FastAPI app factory that calls only `create_investigation_service_v2()` and stores `app.state.investigation_service`;
- create/store one `RuntimeStateStore` instance at `app.state.runtime_state_store`;
- optional/dynamic registration of `trailsight_v2.ai.http` if present, so WP04B can merge without editing this package.

Runtime state must never contain transcript, chain-of-thought, model reasoning, findings cache, AML disposition, hidden truth, or evidence database.

## NON-RESPONSIBILITIES
Do not implement MCP, Agents SDK, AI prompts/output/evals/telemetry, detector/domain calculations, frontend, Docker.

## UPSTREAM CONTRACT
All facts come from WP03 InvestigationServiceV2. Runtime-state session schema/context identity and API resource shapes are frozen by `docs/v2/04_API_AND_MCP.md` and `docs/v2/07_RUNTIME_AND_DEPLOYMENT.md`.

## DOWNSTREAM HANDOFF
Freeze:
- `create_app()` import path;
- runtime-state store import path/methods;
- exact API route/response/error schemas;
- cursor encoding behavior;
- `app.state.investigation_service` + `app.state.runtime_state_store` seam;
- optional AI router registration contract.
WP04B/05B/WP06 may rely on these.

## REQUIRED OUTPUT
Return a scoped delivery package; do not return an unrelated whole-repository copy:

```text
WPXX_DELIVERY.zip
├── replacement/
│   └── <repository-relative owned changed/new files only>
├── MERGE_INSTRUCTIONS.md
├── COMPLETION_REPORT.md
├── DELETE_FILES.txt
└── REQUIRED_INTEGRATION_CHANGES.md
```

Return `WP04A_DELIVERY.zip` with API/state files/tests only.

## MERGE INSTRUCTIONS
`MERGE_INSTRUCTIONS.md` is mandatory and must use these exact headings:

```text
## DELETE
## REPLACE
## ADD
## DO NOT TOUCH
## REQUIRED CROSS-PACKAGE CHANGES
## VERIFY AFTER MERGE
```

List exact repository-relative paths. Report any required unowned change under `REQUIRED CROSS-PACKAGE CHANGES`; do not silently make it. `DELETE_FILES.txt` must contain exact paths or `NONE`.

## TESTS WORKER MUST RUN
- list/detail/search/filter/cursor tests for Alerts/Transactions/Accounts;
- max page bounds and invalid cursor;
- historical origin propagation/cross-context rejection;
- Evidence V2 route valid/malformed/tampered/cross-context;
- alert review status PATCH exact three enums, atomic persistence, failure safety;
- runtime-state initialization/corruption/restart behavior;
- minimal investigation session persistence helpers and second-follow-up conflict semantics at state layer;
- app construction with WP03 factory and AI package absent;
- safe error tests/no SQL/path/provider leakage;
- hidden truth absent from serialized API/state.

## USER-LOCAL VALIDATION
Restart app with retained runtime state and verify review status/session flags survive. Exercise realistic cursor pages against local full DB if available.

## COMPLETION REPORT
Include at minimum:
1. exact input repository ZIP / prerequisite used;
2. concrete owned paths inspected and changed;
3. files created/replaced/deleted;
4. shared/root files touched and explicit authority used;
5. commands/tests run with exact results;
6. user-local validation still required;
7. concrete downstream contract outputs/import paths/table names/endpoints frozen by this WP;
8. blockers/deviations and any unowned changes requested;
9. explicit confirmation that no unowned product/architecture change was made.

Include actual app/state import paths, endpoint table, cursor behavior, commands/results, user-local restart check, and optional AI-router seam.

## PASS GATE
WP04A passes when deterministic API/state tests pass independently with no AI package installed. Merge Gate B later proves WP04B router registration.

## WHAT MAY START AFTER THIS WP PASSES
WP04A and WP04B must both pass and merge at Merge Gate B. Only after the combined backend (`R3_BACKEND.zip`) is accepted should the previously completed WP05A frontend overlay be merged to create the pre-integration frontend/backend ZIP.

## PARALLELISM
May run in parallel with WP04B from identical R2_CORE. Path overlap is forbidden. Both may read WP03 service contracts.

## CROSS-PACKAGE FAILURE ROUTING
If a genuine contradiction exists between the repository, this WP and the authoritative design bundle, STOP and report it. Do not redesign the contract locally. Unowned changes must be reported rather than implemented.

Wrong facts/context/evidence -> WP03; detector materialization -> WP02; AI route/tool need -> WP04B; frontend request for invented fields -> Manager/owning backend package.

## APPROXIMATE IMPLEMENTATION EFFORT
3–4 engineering hours.
