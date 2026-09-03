# TRAILSIGHT V2 — WP05A APPROVED FRONTEND FOUNDATION

> **Historical implementation ticket — complete.** Do not use this file as a current runbook.

## PACKAGE
WP05A — Approved V2 Frontend Foundation Against Typed Mocks

## IMPLEMENTER
**REGULAR CHATGPT**

## PURPOSE
Replace the active V1 Case-based frontend with the approved V2 React information architecture and exact approved visual/interaction system using typed V2 fixtures/mocks where real `/api/v2` is not yet available. Do not redesign UX or calculate backend facts in TypeScript.

## WHY THIS IMPLEMENTER
The work is entirely frontend-owned, visually and behaviorally specified by the approved UX/UI handoff, and can be delivered as a self-contained `frontend/**` replacement with typed fixtures. It benefits from parallel execution while backend work continues.

## PREREQUISITE
Use the current Manager-approved base repository ZIP (`R0_BASE.zip`) and run this package as an independent frontend lineage. It may start in parallel with WP01.

## REQUIRED INPUTS
Attach exactly:

1. current Manager-approved base repository ZIP (`R0_BASE.zip`)
2. complete FINAL Trailsight V2 system-design ZIP
3. this file: `WP05A_FRONTEND_FOUNDATION.md`
4. approved UX/UI handoff, if it is not already embedded in the final design ZIP
5. approved UI-01 through UI-06 mockup images, if they are not already embedded/available with the final design bundle
## DESIGN DOCUMENTS TO READ
At minimum:
- `00_PRODUCT_CONTRACT.md`
- revised `06_FRONTEND_UX.md`
- `04_API_AND_MCP.md` for frozen response concepts
- `09_IMPLEMENTATION_ROADMAP.md`
- `docs/v2/00_PRODUCT_CONTRACT.md`
- `docs/v2/04_API_AND_MCP.md`
- approved UX/UI handoff and mockups
- actual V1 frontend/build config.

## OWNED PATHS
Own all:
```text
frontend/**
```
including `frontend/package.json` and lockfile. Add the approved React Router and Apache ECharts dependencies. If no frontend test framework exists, a minimal Vitest/React Testing Library setup is permitted only if needed for focused route/component semantic tests; do not add Playwright or a large UI framework.

## FORBIDDEN PATHS
No Python, DuckDB, prompts/evals, Docker, root README/config, or backend contract edits.

## SHARED-FILE AUTHORITY
Frontend package/lock files only. No root Python manifests. Report missing backend fields rather than changing design or Python.

## IMPLEMENTATION RESPONSIBILITIES
Replace active V1 Case UI with the approved V2 visual/interaction implementation using typed V2 fixtures/mocks:
- `/` -> `/alerts`;
- Alerts / All Transactions / Accounts top nav;
- list-page tables/filters/cursor controls;
- Transaction Detail frozen 1–9 hierarchy;
- Account Detail frozen hierarchy;
- Bank-Country route map with local world geometry and same-country semantics;
- bounded one-hop graph display contract;
- currency-separated activity timeline;
- AI panel states/categories/evidence focus/one-follow-up visuals;
- review workflow UI exactly NOT_REVIEWED/IN_REVIEW/REVIEWED;
- exact approved design tokens, measurements, components, loading/error/empty/accessibility/responsive behavior;
- typed V2 API model layer and fixture mode matching frozen contracts.

Remove active CaseSelector/case_ref/Person/Merchant/Synthetic Region UI semantics. Reuse only domain-neutral V1 patterns.

## NON-RESPONSIBILITIES
No real `/api/v2` integration beyond a clean typed client boundary/fixture adapter. Do not calculate GARG, priority, band, indicators, graph truncation, Bank Country, percentile, velocity, fan-in/out, or evidence labels in TypeScript.

## UPSTREAM CONTRACT
Typed mock shapes must mirror the frozen V2 API/domain contracts, including priority/band/status enums, ContextIdentity/Evidence display, cursor list shapes, map/network/timeline payloads, and AI response states. Do not invent optional fields just to fill a mockup.

## DOWNSTREAM HANDOFF
WP05B may rely on:
- route/component hierarchy;
- exact design tokens/layout implementation;
- ECharts adapters;
- typed V2 API model definitions;
- API client interface with fixture/real mode seam;
- evidence focus/state behavior;
- package/lock dependencies;
- build/test scripts.

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

Return `WP05A_DELIVERY.zip` containing only `frontend/**` replacements/new files plus global merge/completion files. It remains a frontend overlay, not a whole repository lineage.

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
At minimum `npm run build`, plus focused tests where configured for:
- `/` redirect/nav routes;
- priority/band/status wording (LOW never safe; UNSCORED label);
- server-query construction interface rather than loaded-page filtering;
- historical origin query preservation;
- same-country map no fake arc + Bank Country disclaimer;
- graph truncation text/no hop expansion;
- timeline currency separation;
- AI categories/citations/evidence focus without model call;
- one follow-up used state;
- AI error retains deterministic content;
- exactly three review statuses;
- route ref change clears stale subject state.

## USER-LOCAL VALIDATION
Compare implementation screenshots at ~1440px against approved UI-01..UI-06 images when supplied. Check keyboard focus, contrast, narrower laptop layouts, map/graph/chart text summaries. Mockup image files were not supplied to this system-design revision, so the worker/user must use the actual approved images later.

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

List routes/components, frontend dependencies, V1 files replaced/deleted, fixture types, build/tests, mockup comparison, accessibility/responsive limits, and any backend field contradiction. No backend fixes.

## PASS GATE
WP05A passes when approved visual hierarchy is implemented in fixture mode, production build succeeds, and Manager/user visual review accepts it. It stays as a separate overlay until Merge Gate C.

## WHAT MAY START AFTER THIS WP PASSES
WP05A does not create a new backend repository lineage. Keep its scoped frontend delivery separate. After WP04A/WP04B merge produces `R3_BACKEND.zip`, overlay the accepted WP05A delivery to create `R4_PRE_UI.zip`; then WP05B may start.

## PARALLELISM
May run from R0 in parallel with WP01 and all backend waves. It does not consume their ZIPs until merged later.

## CROSS-PACKAGE FAILURE ROUTING
If a genuine contradiction exists between the repository, this WP and the authoritative design bundle, STOP and report it. Do not redesign the contract locally. Unowned changes must be reported rather than implemented.

Missing/contradictory API field -> report to Manager/backend owner. UX visual contradiction with product semantics -> Manager. Do not redesign or patch Python.

## APPROXIMATE IMPLEMENTATION EFFORT
7–9 engineering hours.
