# TRAILSIGHT V2 — WP05B REAL API FRONTEND INTEGRATION

## PACKAGE
WP05B — Real `/api/v2` Frontend Integration

## IMPLEMENTER
**REGULAR CHATGPT**

## PURPOSE
Connect the already-approved WP05A frontend to the real `/api/v2` contracts, runtime review-state behavior, Evidence V2 focus, AI investigation/follow-up routes, and server-driven pagination without changing backend semantics or visual design.

## WHY THIS IMPLEMENTER
This is a narrow frontend-only integration pass after both the visual foundation and backend contracts are real. It is mechanical typed-client/state wiring rather than visual redesign or backend development.

## PREREQUISITE
Use the latest Manager-approved repository ZIP created after the combined backend and accepted WP05A frontend are merged (`R4_PRE_UI.zip`). Do not run another frontend owner concurrently.

## REQUIRED INPUTS
Attach exactly:

1. latest Manager-approved backend + accepted frontend-foundation repository ZIP (`R4_PRE_UI.zip`)
2. complete FINAL Trailsight V2 system-design ZIP
3. this file: `WP05B_FRONTEND_API_INTEGRATION.md`

Any WP04A/WP04B/WP05A completion reports or OpenAPI examples supplied by the Manager are supplementary; the actual merged repository and final design are authoritative for concrete integration paths.
## DESIGN DOCUMENTS TO READ
Read `docs/v2/00_PRODUCT_CONTRACT.md`, `docs/v2/04_API_AND_MCP.md`, `docs/v2/05_AI_AND_EVALUATION.md`, revised `docs/v2/06_FRONTEND_UX.md`, `docs/v2/09_IMPLEMENTATION_ROADMAP.md`, the approved UX handoff/mockups, and WP04A/WP04B/WP05A completion reports.

## OWNED PATHS
Own only:
```text
frontend/**
```
This is sequential ownership after WP05A.

## FORBIDDEN PATHS
No Python/API/MCP/AI/domain/detector changes, no Docker/README/root Python manifests.

## SHARED-FILE AUTHORITY
May update `frontend/package.json`/lock only if a frontend-owned integration dependency is genuinely required; do not change approved visualization/router stack unnecessarily.

## IMPLEMENTATION RESPONSIBILITIES
Connect the approved frontend to actual `/api/v2`:
- replace production fixture data paths with real typed fetches;
- preserve optional fixture/dev mode only if cleanly isolated;
- real server-side search/filter/cursor pagination;
- Alerts review status PATCH save/rollback error behavior;
- transaction/account detail including historical origin refs;
- Evidence V2 GET/focus only when needed; use backend citation labels;
- investigation start and one follow-up; terminal 409 FOLLOW_UP_ALREADY_USED;
- API/AI failures remain scoped and deterministic content stays visible;
- map/graph/timeline render actual backend payloads without browser-side factual calculation;
- eliminate stale Case/V1 types from active production imports.

## NON-RESPONSIBILITIES
Do not redesign UI, invent fields, calculate deterministic facts, change backend contracts, or delete backend V1 code.

## UPSTREAM CONTRACT
Actual WP04A/WP04B API shapes/status codes are authoritative if they conform to system-design contracts. Any mismatch with design must be reported, not normalized client-side into a new semantic contract.

## DOWNSTREAM HANDOFF
Freeze final frontend API types/client paths, consumed endpoint list, production-vs-fixture boundary, routes, error/409 handling, evidence-focus behavior, and successful production build.

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

Return `WP05B_DELIVERY.zip` with only `frontend/**` changed/new/deleted paths and standard reports.

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
- `npm run build`;
- focused client URL/query/cursor tests;
- route navigation/history origin;
- review PATCH success/failure rollback;
- Evidence citation focus/no model call;
- AI start/follow-up/409/error states;
- server responses drive all band/priority/indicator/map/graph/chart facts;
- production build has no active V1 Case/Synthetic Region/Person/Merchant imports;
- deterministic content survives AI unavailable.

## USER-LOCAL VALIDATION
Run the real backend locally and manually walk Alerts -> Account -> Transaction -> evidence -> AI -> follow-up; compare screenshots with approved mockups; exercise narrow laptop widths and keyboard navigation.

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

List real endpoints consumed, types/client files, production mocks removed/retained, build/tests, manual workflow, backend mismatches, and V1 frontend active-import audit.

## PASS GATE
WP05B passes when real API integration works without Python changes, production build succeeds, required interaction tests pass, and no V1 active UI semantics remain.

## WHAT MAY START AFTER THIS WP PASSES
After WP05B passes and its delivery is merged/tested, the Manager creates `R5_CANDIDATE.zip`. WP06 final Codex integration may then start; no other production frontend package follows.

## PARALLELISM
No production parallelism needed. Starts only after R4_PRE_UI. Do not run concurrently with another frontend owner.

## CROSS-PACKAGE FAILURE ROUTING
If a genuine contradiction exists between the repository, this WP and the authoritative design bundle, STOP and report it. Do not redesign the contract locally. Unowned changes must be reported rather than implemented.

REST/runtime state -> WP04A. MCP/AI route/evidence behavior -> WP04B. Wrong deterministic facts -> WP03/WP02. Do not patch backend.

## APPROXIMATE IMPLEMENTATION EFFORT
2–3 engineering hours.
