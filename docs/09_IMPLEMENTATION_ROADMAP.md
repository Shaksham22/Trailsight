# TRAILSIGHT V2 — FINAL IMPLEMENTATION ROADMAP

**Status:** AUTHORITATIVE IMPLEMENTATION-ORIENTED SYSTEM DESIGN.

This document governs implementation sequencing, implementer allocation, ZIP lineages, merge gates, and cross-package ownership. It does **not** change the frozen product/domain architecture.

## 1. Executive design decision

The V2 architecture remains frozen. The implementation layer is revised because the actual delivery model is manual replacement-file merging across separate AI implementation sessions with limited Codex capacity.

The final plan makes four implementation-only changes:

1. keep all new V2 Python production code under `src/trailsight_v2/` so V1 can coexist until final cleanup;
2. use disjoint WP04A REST/runtime-state and WP04B MCP/AI/evals/telemetry packages so the already-approved API/AI implementation can run in parallel without file overlap;
3. split frontend work into an approved-design fixture implementation followed by a narrow real-API integration pass;
4. reserve Codex for production GARG and final repository-wide integration, while tightly specified deterministic/API/AI/frontend packages use regular ChatGPT replacement-file sessions.

No product semantics, detector semantics, evidence semantics, API resource semantics, or UX hierarchy are changed.

## 2. Actual repository findings used for this plan

The inspected authoritative repository currently contains working V1 packages:

```text
src/trailsight/
src/trailsight_data/
src/trailsight_mcp/
src/trailsight_ai/
frontend/
```

The active frontend is still Case/case_ref based. There is no `src/trailsight_v2/` production implementation yet. The V1 app already demonstrates two reusable infrastructure patterns: a deterministic service factory/app-state boundary and optional AI-router registration. The V1 frontend also already has fixture mode and evidence-focus behavior that can be adapted without carrying V1 domain types forward.

The current Python manifest already contains DuckDB, FastAPI, MCP, OpenAI Agents SDK, Pydantic, pytest, and Uvicorn. The current frontend manifest does **not** contain React Router or Apache ECharts, so WP05A owns adding those approved frontend dependencies.

No WP01 V2 completion report and no GARG spike/benchmark report were present in the supplied repository. Therefore both remain pending. Do not invent benchmark results.

The supplied repository ZIP also contains local/generated artifacts (`.env`, `.venv`, `node_modules`, built frontend output, runtime DuckDB, traces/eval outputs). These are useful local artifacts but must not become replacement-package payloads or public-repository content. Final integration must audit them.

## 3. Source-of-truth order

The final bundle has no separate implementation shared-contract helper. Architecture/interface authority lives in the design document that owns the subject; implementation sequencing/delivery authority lives here; one runnable WP file is one developer assignment.

If documents appear to conflict, use this order:

1. `docs/v2/00_PRODUCT_CONTRACT.md` — frozen product/domain semantics and terminology.
2. The relevant frozen system-design document under `docs/v2/01_SYSTEM_ARCHITECTURE.md` through `docs/v2/08_TESTING_AND_ACCEPTANCE.md` — authoritative technical/interface contract for its subject.
3. The approved UX/UI handoff and approved UI-01..UI-06 mockups — authoritative frontend visual/interaction behavior only; they never override product/domain semantics.
4. `docs/v2/09_IMPLEMENTATION_ROADMAP.md` — implementer allocation, ownership policy, dependency DAG, ZIP lineage, merge rules and universal worker-execution policy.
5. The one specific runnable file under `docs/v2/implementation/WP*.md` assigned to that implementation session — package-specific ownership, responsibilities, tests and delivery requirements.
6. The latest Manager-approved completion handoff/report — concrete implemented paths and commands, only where consistent with items 1–5.
7. The actual current repository implementation — evidence of current code state, not authority to silently redefine a frozen contract.

A worker that finds a genuine contradiction must **STOP AND REPORT** the exact conflicting authorities. It must not choose a new interpretation.

The executable implementation directory is intentionally only a job-ticket list:

```text
docs/v2/implementation/
├── WP01_IBM_DATA_FOUNDATION.md
├── WP02_GARG_PRIORITY_ALERTS.md
├── WP03_INVESTIGATION_DOMAIN_EVIDENCE.md
├── WP04A_REST_API_RUNTIME_STATE.md
├── WP04B_MCP_AI_EVALS_TELEMETRY.md
├── WP05A_FRONTEND_FOUNDATION.md
├── WP05B_FRONTEND_API_INTEGRATION.md
└── WP06_FINAL_INTEGRATION.md
```

No README, index, shared-contract file, merge guide or other non-runnable helper belongs in that directory.
## 4. Implementer allocation

| Package | Implementer | Complexity/risk | Why | Can run parallel with | Codex required? |
|---|---|---:|---|---|---|
| WP01 IBM Data Foundation — `WP01_IBM_DATA_FOUNDATION.md` | REGULAR CHATGPT | MEDIUM | Narrow Python/DuckDB ingestion, identity, firewall, deterministic tests | WP05A | No |
| WP02 GARG + Priority + Alerts — `WP02_GARG_PRIORITY_ALERTS.md` | CODEX | VERY HIGH | Research-code adaptation, parity, graph performance/RAM, point-in-time snapshots, rank/band/alert coupling | WP03 after WP01 | **Yes** |
| WP03 Investigation Domain + Evidence V2 — `WP03_INVESTIGATION_DOMAIN_EVIDENCE.md` | REGULAR CHATGPT | HIGH | Deterministic but fully specified; coherent service/evidence package; narrow V2 paths; later Codex audit | WP02 after WP01 | No |
| WP04A REST API + Runtime State — `WP04A_REST_API_RUNTIME_STATE.md` | REGULAR CHATGPT | MEDIUM | Bounded FastAPI/pagination/state work over frozen service | WP04B | No |
| WP04B MCP + AI + Evals + Telemetry — `WP04B_MCP_AI_EVALS_TELEMETRY.md` | REGULAR CHATGPT | HIGH | Existing V1 patterns plus frozen seven tools/output/eval contracts; explicit SDK observability stop gate | WP04A | No |
| WP05A Approved Frontend Foundation — `WP05A_FRONTEND_FOUNDATION.md` | REGULAR CHATGPT | MEDIUM | Entirely `frontend/**`, approved visual spec, typed mocks, buildable replacement ZIP | WP01/WP02/WP03/WP04A/WP04B | No |
| WP05B Real API Frontend Integration — `WP05B_FRONTEND_API_INTEGRATION.md` | REGULAR CHATGPT | MEDIUM | Narrow frontend-only conversion from typed mocks to actual `/api/v2` | none; starts after backend merge + WP05A | No |
| WP06 Final Integration + Cleanup — `WP06_FINAL_INTEGRATION.md` | CODEX | VERY HIGH | Whole-repository reasoning, imports/dependencies, Docker, dead V1 cleanup, leakage audit, integrated regression | none | **Yes** |

Codex is used for depth, not vague scope. WP02 and WP06 remain explicitly bounded.

## 5. Final dependency DAG

```text
                         FINAL DESIGN / SHARED CONTRACTS
                                      |
                   +------------------+------------------+
                   |                                     |
                   v                                     v
           WP01 DATA FOUNDATION                 WP05A FRONTEND FOUNDATION
           REGULAR CHATGPT                      REGULAR CHATGPT
                   |
                   v
               R1_DATA
          +--------+--------+
          |                 |
          v                 v
   WP02 GARG/PRIORITY   WP03 DOMAIN/EVIDENCE
        CODEX           REGULAR CHATGPT
          |                 |
          +--------+--------+
                   |
          GARG FEASIBILITY GATE
                   |
                   v
              MERGE GATE A
                 R2_CORE
          +--------+--------+
          |                 |
          v                 v
   WP04A API/STATE      WP04B MCP/AI/EVALS
   REGULAR CHATGPT      REGULAR CHATGPT
          |                 |
          +--------+--------+
                   v
              MERGE GATE B
               R3_BACKEND
                   |
        overlay WP05A delivery
                   v
              MERGE GATE C
               R4_PRE_UI
                   |
                   v
        WP05B REAL API INTEGRATION
            REGULAR CHATGPT
                   |
                   v
              R5_CANDIDATE
                   |
                   v
        WP06 FINAL CODEX INTEGRATION
                   |
                   v
               R6_FINAL_RC
                   |
                   v
          USER-LOCAL ACCEPTANCE
```

## 6. Parallel waves and gates

### Wave 0 — design/preflight

Inputs: current authoritative repository ZIP + final design bundle + approved UX/UI handoff.

Outstanding empirical facts:

- no supplied GARG full-final-snapshot benchmark;
- no supplied WP01 V2 completion report;
- no supplied approved mockup image files in this design-revision input.

No production semantics change because of those missing artifacts.

### Wave 1 — two independent lanes

Start in parallel from **R0_BASE**:

- WP01 IBM Data Foundation;
- WP05A Approved Frontend Foundation against typed V2 mocks.

WP01 returns a scoped delivery; after user overlay/test, create **R1_DATA.zip**.

WP05A remains a separate frontend delivery and is not merged into the backend lineage yet.

### Wave 2 — detector/domain fork

Both consume **R1_DATA.zip** and the same frozen DB/table contracts:

- WP02 GARG/priority/alerts — Codex;
- WP03 deterministic domain/Evidence V2 — regular ChatGPT.

They must not share production paths. WP03 tests detector-state reads against contract fixtures; it does not depend on WP02 implementation imports.

**GARG feasibility gate:** before Merge Gate A is accepted, WP02 must pass controlled parity and realistic subset tests, and the user must run the full-final-HI-Small graph/preprocessing/scoring benchmark when it is too expensive for the worker environment. Approved threshold remains full final snapshot <=30 minutes and peak RSS <70% of physical RAM. If baseline fails, try only the approved semantics-preserving contingency; if parity/resources still fail, STOP to Manager.

### Merge Gate A — R2_CORE

Apply WP02 and WP03 deliveries onto the exact same R1_DATA base. Their overlays must have no unexpected file collision.

Run focused cross-package tests proving:

- WP03 reads the actual WP02 detector table/schema contract;
- account/snapshot/transaction priority fields match authoritative design contracts;
- no future-state or hidden-truth leakage;
- `create_investigation_service_v2()` constructs the read-only service against the merged runtime contract.

Then create **R2_CORE.zip**.

### Wave 3 — API/AI fork

From R2_CORE run in parallel:

- WP04A deterministic REST API + runtime state;
- WP04B MCP + AI + evals + telemetry.

WP04A owns `src/trailsight_v2/api/**` and the concrete runtime-state store. WP04B owns `src/trailsight_v2/mcp/**`, `src/trailsight_v2/ai/**`, V2 prompts/evals, and their tests.

The integration seam is frozen: FastAPI stores `investigation_service` and `runtime_state_store` on `app.state`; the V2 app factory dynamically registers `trailsight_v2.ai.http` when present. AI route handlers consume app-state services and never construct repositories.

WP04B has an **SDK observability hard gate**: if the installed MCP/Agents SDK path cannot expose actual tool execution order/status/latency/result metadata sufficient for the frozen telemetry/evidence-validation model, STOP and report. Do not simulate model tool execution.

### Merge Gate B — R3_BACKEND

Overlay WP04A + WP04B onto R2_CORE. Run API, MCP, AI-structure, runtime-state, evidence-validation, and non-live eval tests. Create **R3_BACKEND.zip**.

### Merge Gate C — R4_PRE_UI

Overlay the already-passing WP05A frontend delivery onto R3_BACKEND. This is the first backend/frontend lineage merge.

Run frontend build and backend startup with fixture/real API boundaries as applicable. Create **R4_PRE_UI.zip**.

### Wave 4 — WP05B real API integration

WP05B receives R4_PRE_UI and the actual WP04A/WP04B completion reports/OpenAPI examples. It may modify only `frontend/**`.

It removes production dependence on typed mocks, preserves optional fixture mode where useful, and reports any backend contract mismatch rather than changing Python.

Create **R5_CANDIDATE.zip** after build/route/API smoke.

### Wave 5 — final Codex integration

WP06 receives R5_CANDIDATE plus every completion report and the final design bundle.

Codex performs whole-repository integration, dependency/config reconciliation, Docker/startup, dead V1 runtime cleanup, leakage audit, static/unit/build checks, and final contract drift review.

It may fix contract-preserving glue/import/configuration defects. If it finds a business-semantic defect owned by WP01–WP05B, it must report the failing contract and owner instead of silently redefining semantics.

Output: **R6_FINAL_RC.zip**.

### Final user-local acceptance

The user runs long/credentialed/manual checks that should not be faked inside Codex:

- full IBM HI-Small preparation if not already run;
- full GARG benchmark/daily snapshot sequence when expensive;
- real OpenAI evaluation suite;
- exhaustive Docker/manual workflow;
- screenshot comparison against approved UI-01..UI-06 images;
- final demo walkthrough.

## 7. Authoritative ZIP lineage

Use these names in completion reports to avoid stale-ZIP mistakes:

```text
R0_BASE.zip
  = latest authoritative repo before V2 production implementation

R0_BASE.zip + WP01_DELIVERY.zip
  -> R1_DATA.zip

R1_DATA.zip + WP02_DELIVERY.zip + WP03_DELIVERY.zip
  -> R2_CORE.zip       # only after GARG feasibility + Merge Gate A

R2_CORE.zip + WP04A_DELIVERY.zip + WP04B_DELIVERY.zip
  -> R3_BACKEND.zip    # only after Merge Gate B

R0_BASE.zip
  -> WP05A_DELIVERY.zip   # separate frontend overlay lineage, not whole repo

R3_BACKEND.zip + WP05A_DELIVERY.zip
  -> R4_PRE_UI.zip

R4_PRE_UI.zip + WP05B_DELIVERY.zip
  -> R5_CANDIDATE.zip

R5_CANDIDATE.zip + WP06 final integration work
  -> R6_FINAL_RC.zip
```

A downstream worker must reject an input ZIP whose lineage does not match its package prerequisite.

## 8. Universal worker execution and delivery policy

These rules apply to every runnable WP and are also repeated concretely in each job ticket so the worker does not need another helper document.

### Before editing

Every worker must:

1. inspect the actual repository ZIP supplied for that WP before selecting files;
2. confirm the ZIP lineage/prerequisite matches the WP;
3. read the final system-design ZIP and the assigned WP file;
4. map logical owned areas to concrete current repository paths;
5. stop and report any genuine contradiction instead of redesigning architecture;
6. modify only owned/explicitly authorized shared paths;
7. never commit or push on the user's behalf.

### Shared/root-file authority

- `frontend/package.json` and the frontend lockfile belong to WP05A/WP05B, then WP06 final reconciliation.
- `pyproject.toml`/`uv.lock`: WP01 and WP02 may make only explicitly required additive dependency changes; WP03/WP04A/WP04B report dependency needs unless their WP explicitly authorizes a change; WP06 owns final reconciliation.
- Dockerfile, `.dockerignore`, `.env.example`, README and root runtime/startup integration normally belong to WP06.
- `.gitignore`: WP01 may add narrow raw-data/generated-runtime safety exclusions; WP06 may extend/reconcile them but may not remove those protections.
- Parallel workers never silently overwrite a shared/root file. An unowned required change is reported in `REQUIRED_INTEGRATION_CHANGES.md`.

### Standard scoped delivery

Every production worker except final WP06 returns only owned changed/new/deleted files:

```text
WPXX_DELIVERY.zip
├── replacement/
│   └── <repository-relative owned changed/new files only>
├── MERGE_INSTRUCTIONS.md
├── COMPLETION_REPORT.md
├── DELETE_FILES.txt
└── REQUIRED_INTEGRATION_CHANGES.md
```

Do not include a whole unrelated repository, `.env`, secrets, raw IBM data, generated runtime DuckDB/snapshots, `.venv`, `node_modules`, `dist`, traces, eval outputs or other local artifacts.

`MERGE_INSTRUCTIONS.md` must contain exactly these operational headings:

```text
## DELETE
## REPLACE
## ADD
## DO NOT TOUCH
## REQUIRED CROSS-PACKAGE CHANGES
## VERIFY AFTER MERGE
```

`COMPLETION_REPORT.md` must include:

1. exact input repository ZIP / lineage;
2. files created/replaced/deleted;
3. shared/root files touched and the explicit WP authority used;
4. commands/tests run and exact results;
5. user-local validation still required;
6. concrete downstream contract outputs/import paths/table names/endpoints frozen by this WP;
7. blockers/deviations and any contradiction found;
8. confirmation that no unowned product/architecture change was made.

`REQUIRED_INTEGRATION_CHANGES.md` must contain `NONE` unless an unowned cross-package change is genuinely required. Workers report such changes rather than making them.

### Generic failure routing

A worker must stop and route to the Manager/owning WP when implementation would require changing a frozen product/domain contract, another package's semantic ownership, the ground-truth firewall, point-in-time semantics, detector semantics, Evidence V2 identity, API/MCP resource semantics, AI role, or approved UX behavior.

### Definition of a package pass

A WP passes only when its owned behavior is complete, required practical automated tests pass, previously passed relevant regressions remain green, hidden truth/raw generated artifacts are absent from runtime/public deliverables, the scoped delivery is complete, and the completion report freezes the concrete handoff needed downstream.
## 9. Merge-conflict matrix

| Package | Major owned paths | Shared/root authority | Collision risk | Mitigation |
|---|---|---|---|---|
| WP01 | `src/trailsight_v2/data/**`, data prep scripts/tests | narrow `.gitignore`; additive Python deps only if required | LOW | starts from R0; no detector/domain/frontend edits |
| WP02 | `src/trailsight_v2/detector/**`, detector scripts/tests | may add only GARG-required Python deps to `pyproject.toml`/`uv.lock` | MEDIUM | WP03 forbidden from root manifests; merge from same R1 base |
| WP03 | `src/trailsight_v2/domain/**`, V2 domain contracts/config/errors it is assigned, domain tests | no root manifest edits | LOW | no detector source edits; frozen table contract fixtures |
| WP04A | `src/trailsight_v2/api/**`, runtime-state implementation/tests | no dependency edits unless explicitly approved | LOW | optional AI-router seam avoids WP04B file overlap |
| WP04B | `src/trailsight_v2/mcp/**`, `src/trailsight_v2/ai/**`, `prompts/v2/**`, `evals/v2/**`, tests | report dependency need; do not edit API files | LOW | app-state/dynamic-router contract frozen |
| WP05A | `frontend/**` | owns frontend package/lock files | NONE with backend | separate frontend lineage |
| WP05B | `frontend/**` | same frontend authority, sequential after WP05A | LOW | consumes WP05A result; no Python edits |
| WP06 | root integration, Docker, README, integration tests, proven-dead V1 cleanup | final root/dependency reconciliation | HIGH by design | Codex whole-repo review; semantic owner bugs routed back |

## 10. Cross-package handoff contracts

### WP01 freezes for WP02/WP03

- exact V2 data module paths;
- canonical source ID normalization implementation;
- transaction/account reference implementation;
- runtime-safe DuckDB table/column names from the frozen schema;
- Bank Country metadata mapping artifact/version;
- safe test-fixture builders;
- ground-truth boundary proof;
- preparation command and local source-path contract.

### WP02 freezes for merged core

- exact detector import paths/version constants;
- snapshot tables/state/support columns;
- deterministic snapshot ID/config hash behavior;
- account rank/percentile/band materialization;
- transaction review-state/priority materialization;
- Network Alert materialization;
- performance/parity report and whether baseline or approved optimized scorer is active.

### WP03 freezes for WP04A/WP04B

- `InvestigationServiceV2` import path;
- exact `create_investigation_service_v2()` import path (preferred/frozen target: `trailsight_v2.domain.service`);
- context/evidence model import paths;
- Evidence V2 resolver;
- deterministic error vocabulary;
- list/detail/network/indicator service methods;
- fixture refs for API/MCP tests.

### WP04A freezes for WP04B merge/WP05B

- FastAPI `create_app()` import path;
- REST endpoint schemas/status codes;
- opaque cursor behavior;
- `RuntimeStateStore` concrete path and `TRAILSIGHT_RUNTIME_STATE_PATH` handling;
- `app.state.investigation_service` and `app.state.runtime_state_store` composition seam;
- optional `trailsight_v2.ai.http` router registration behavior.

### WP04B freezes for WP05B/WP06

- exact seven MCP tools;
- AI investigation/follow-up HTTP route schemas;
- prompt/model config names;
- DisplayEvidence/citation shape;
- fail-closed validation behavior;
- telemetry schema;
- eval commands/results and SDK-observability gate result.

### WP05A freezes for WP05B

- route/component structure;
- exact design tokens/layouts;
- ECharts map/graph/timeline implementation boundaries;
- typed V2 API mock shapes matching authoritative design contracts;
- frontend dependency manifest/lockfile;
- mockup comparison notes.

### WP05B freezes for WP06

- actual `/api/v2` API client/types;
- production removal of mock-only data paths;
- final route/filter/pagination/evidence/review/AI interactions;
- frontend build result and any genuine backend mismatch report.

## 11. UX/UI incorporation

`06_FRONTEND_UX.md` is revised to incorporate the approved UX/UI handoff's exact routes, hierarchy, tokens, layout measurements, component inventory, map/graph/timeline behavior, interaction states, accessibility, and responsive rules.

For WP05A/WP05B:

- the approved textual UX/UI handoff is mandatory;
- approved UI-01..UI-06 images, when supplied to the worker, are authoritative visual references at approximately 1440px;
- product/domain/system contracts outrank a visual if they conflict;
- frontend workers must report missing backend data rather than invent it;
- frontend workers must not redesign the approved UI.

No mockup image files were supplied in this final system-design revision input, so screenshot-level acceptance remains a user-local validation item rather than a fabricated pass result.

## 12. Codex responsibilities

### WP02

Codex owns research-code adaptation and production GARG correctness/performance. It must not weaken semantics to make the benchmark pass.

### WP06

Codex owns final repository-wide integration:

- inspect every merged production path and completion report;
- reconcile imports/dependencies/configuration;
- write/fix integration glue;
- run practical Python tests, type/lint checks if configured, frontend production build, startup/import checks;
- audit package contract drift and ground-truth leakage;
- reconcile Docker/runtime state/data mounts;
- remove proven-dead V1 runtime code only after V2 replacement is proven;
- create the candidate-final repository.

If Codex finds an owner-package semantic defect, report:

```text
FAILING CONTRACT
OBSERVED BEHAVIOR
EXPECTED BEHAVIOR
OWNING PACKAGE
MINIMAL CORRECTION REQUIRED
```

## 13. Regular-chat responsibilities

Regular implementation chats must:

- inspect the actual input ZIP;
- stay within narrow owned paths;
- return complete replacement/new files, not fragmentary patch prose;
- return scoped delivery ZIP + mechanical merge instructions;
- run package-level normal tests available in the chat environment;
- state user-local tests separately;
- report any required unowned change rather than making it.

## 14. User-local validation responsibilities

User-local validation is required where the worker lacks real external data, credentials, runtime resources, or approved images:

- IBM full-source preparation and scale timings;
- GARG full-final snapshot wall-clock/peak RSS and long daily run;
- real OpenAI model evals/cost;
- exhaustive Docker/manual workflow;
- screenshot comparison against approved mockups;
- final interview/demo acceptance.

These do not replace unit/integration tests that workers and Codex can run normally.

## 15. Open empirical gates

1. **IBM full-source preparation:** not demonstrated in the supplied ZIP for V2; user-local after WP01.
2. **GARG final-snapshot feasibility:** no benchmark report supplied; hard gate remains <=30 min final snapshot and <70% physical RAM, with parity-preserving contingency only.
3. **Agents SDK/MCP execution telemetry:** WP04B must verify actual tool-call metadata path against the installed SDK; no simulated compliance.
4. **Real-model evals:** credentialed user-local acceptance after WP04B/Merge B.
5. **Visual pixel-level acceptance:** approved textual UX is available; approved mockup images were not attached to this revision input, so final screenshot comparison remains outstanding.

## 16. Implementation effort guidance

These are engineering estimates, not wall-clock promises:

```text
WP01   3–4 h
WP02   6–10 h + offline/user-local compute
WP03   5–7 h
WP04A  3–4 h
WP04B  5–7 h
WP05A  7–9 h
WP05B  2–3 h
WP06   4–6 h
```

Parallel lanes reduce elapsed coordination time, not total engineering work.

## 17. Final executable work-package files

The only runnable implementation assignments in the final bundle are:

```text
docs/v2/implementation/WP01_IBM_DATA_FOUNDATION.md
docs/v2/implementation/WP02_GARG_PRIORITY_ALERTS.md
docs/v2/implementation/WP03_INVESTIGATION_DOMAIN_EVIDENCE.md
docs/v2/implementation/WP04A_REST_API_RUNTIME_STATE.md
docs/v2/implementation/WP04B_MCP_AI_EVALS_TELEMETRY.md
docs/v2/implementation/WP05A_FRONTEND_FOUNDATION.md
docs/v2/implementation/WP05B_FRONTEND_API_INTEGRATION.md
docs/v2/implementation/WP06_FINAL_INTEGRATION.md
```

The directory itself is the definitive list of developer sessions. No additional implementation helper document must be attached. Each worker receives the latest required repository ZIP, the complete final system-design ZIP, and exactly one runnable WP file (plus the approved UX/UI handoff/mockups for WP05A when those are not already embedded in the design bundle).
