# TRAILSIGHT V2 — WP06 FINAL CODEX INTEGRATION

> **Historical implementation ticket — superseded by the completed authoritative working-tree integration.** Do not create the ZIP/report artifacts described below; the current release-candidate commands and documentation live in the root README and docs `07`–`08`.

## PACKAGE
WP06 — Final Repository Integration, Docker, Regression, Cleanup, and Documentation

## IMPLEMENTER
**CODEX**

## PURPOSE
Perform the final whole-repository Codex integration: reconcile package outputs/imports/dependencies/runtime/Docker/frontend serving, run practical regression/build/leakage checks, remove proven-dead V1 runtime code, document setup, and produce the candidate-final repository without changing owner-package business semantics.

## WHY THIS IMPLEMENTER
This is intentionally repository-wide: reconcile independently delivered packages, imports/dependencies/config, Docker/startup, dead V1 cleanup, contract drift, leakage, frontend build, and integration tests. Broad reasoning materially reduces risk and is where scarce Codex capacity is most valuable.

## PREREQUISITE
Use only the latest Manager-approved candidate repository after WP01–WP05B have passed (`R5_CANDIDATE.zip`). This is the sole whole-repository merge/integration session.

## REQUIRED INPUTS
Attach:

1. latest Manager-approved candidate repository ZIP (`R5_CANDIDATE.zip`)
2. complete FINAL Trailsight V2 system-design ZIP
3. this file: `WP06_FINAL_INTEGRATION.md`
4. WP01–WP05B completion reports and any `REQUIRED_INTEGRATION_CHANGES.md` reports available to the Manager
5. approved UX/UI handoff/mockups if not embedded in the final design bundle
6. available user-local GARG/full-preparation/real-model validation results; missing long-running results must be reported rather than fabricated
## DESIGN DOCUMENTS TO READ
Read all `docs/v2/*.md`, all final `docs/v2/implementation/*.md`, every completion report, and actual merged repository. Do not rely on memory.

## OWNED PATHS
Repository-wide **integration authority**, especially:
```text
Dockerfile
.dockerignore
.env.example
README.md
root startup/config/glue
root dependency manifests/locks
integration tests
static frontend serving/startup wiring
proven-dead V1 runtime files after replacement proof
```
Codex may make minimal contract-preserving import/config/wiring fixes in merged package code when the defect is genuinely integration-only.

## FORBIDDEN PATHS
Do not silently change business/domain semantics owned by WP01–WP05B, GARG math, priority/band policy, Evidence V2 identity, API resource semantics, MCP tools, approved UX, or hidden-truth firewall. Do not use hidden IBM truth to make runtime tests pass.

## SHARED-FILE AUTHORITY
WP06 owns final `pyproject.toml`/`uv.lock`, frontend dependency reconciliation when merge-only, Docker, root env/config/docs, `.gitignore` reconciliation, and removal of local/generated/secrets from candidate deliverables.

## IMPLEMENTATION RESPONSIBILITIES
- inspect full merged repo and completion reports;
- reconcile Python package discovery/imports and V2 app entrypoint;
- reconcile WP04A optional AI-router registration with WP04B export;
- reconcile runtime DB/state paths and mounts;
- reconcile frontend build/static serving;
- final dependency/lock consistency;
- Docker build/startup configuration;
- safe environment/secrets handling;
- generated artifact hygiene;
- whole-repo ground-truth leakage audit;
- practical unit/integration/static/type/lint/build checks where configured;
- dead V1 runtime import graph audit and removal/bypass of proven-dead Case/TransXion/Person-Merchant/Synthetic Region/V1 MCP/evidence/prompts/evals/frontend code;
- final README/setup/data-prep/detector/run/eval/demo instructions;
- create candidate-final repository.

## NON-RESPONSIBILITIES
Do not retune GARG, review bands, transaction priority, evidence semantics, AI role, or UX. Do not perform every expensive external-data/model/manual acceptance step merely to claim completion.

## UPSTREAM CONTRACT
All Manager-passed package outputs are presumed correct until integrated tests show a concrete failing contract. Source-of-truth order is frozen in `09_IMPLEMENTATION_ROADMAP.md`.

## DOWNSTREAM HANDOFF
Deliver one **R6_FINAL_RC.zip** candidate repository plus integration report containing:
- final app/startup commands;
- final dependency versions/entrypoints;
- files deleted as dead V1;
- automated test/build results;
- unresolved owner-package defects;
- user-local acceptance commands;
- leakage audit result.

## REQUIRED OUTPUT
WP06 is the authorized final whole-repository merge owner. Return the complete candidate-final repository ZIP plus `FINAL_INTEGRATION_REPORT.md` and any owner-package defect reports. Do not package raw IBM data, generated detector databases, secrets, local caches, traces, or other non-source artifacts.

Unlike regular packages, WP06 returns the whole candidate-final repository ZIP because it is the authorized merge owner. Also return a concise `FINAL_INTEGRATION_REPORT.md` and any owner-defect reports.

## MERGE INSTRUCTIONS
WP06 performs the merge rather than returning an overlay for another worker. Its final report must nevertheless classify repository-wide changes under these headings so the Manager can audit the integration:

```text
## DELETE
## REPLACE
## ADD
## DO NOT TOUCH
## REQUIRED CROSS-PACKAGE CHANGES
## VERIFY AFTER MERGE
```

`REQUIRED CROSS-PACKAGE CHANGES` must identify owner-package semantic defects rather than silently absorbing them into integration.

## TESTS WORKER MUST RUN
Where practical:
- full non-live Python unit/integration suite;
- configured lint/type/static checks;
- frontend production build and frontend tests;
- V2 import/startup/health checks;
- API/MCP child smoke with fixture/safe DB;
- runtime-state tests;
- Evidence V2 and point-in-time contract tests;
- Docker build and lightweight runtime smoke if environment permits;
- active import/search audit proving V1 domain paths are not used by V2;
- ground-truth leakage audit of runtime schema/API/MCP/prompts/frontend/traces;
- no secret/generated artifact included in final candidate.

## USER-LOCAL VALIDATION
User may run:
- full IBM preparation;
- full/long GARG daily run and performance measurements;
- credentialed real-model AI evals;
- exhaustive Docker flow with local mounts;
- visual screenshot acceptance against approved mockups;
- final demo walkthrough.
Codex must provide exact commands but not fake these results.

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

For every discovered failure classify:
```text
FAILING CONTRACT
OBSERVED BEHAVIOR
EXPECTED BEHAVIOR
OWNING PACKAGE
MINIMAL CORRECTION REQUIRED
```
State which integration-only defects Codex fixed directly and why they did not alter semantics. List all root/dependency/deletion changes and test results.

## PASS GATE
WP06 passes when practical automated integration gates are green, V2 is the active runtime, secrets/hidden truth/generated artifacts are absent from candidate distribution, Docker/startup/docs are coherent, and any remaining long/manual checks are explicitly user-local rather than silently skipped.

## WHAT MAY START AFTER THIS WP PASSES
No further production implementation WP starts automatically. WP06 produces the final release-candidate repository for user-local long-running/manual acceptance and any Manager-routed owner-package correction that acceptance may expose.

## PARALLELISM
None. This is the final merge owner and consumes the single R5_CANDIDATE lineage.

## CROSS-PACKAGE FAILURE ROUTING
If a genuine contradiction exists between the repository, this WP and the authoritative design bundle, STOP and report it. Do not redesign the contract locally. Unowned changes must be reported rather than implemented.

Pure import/config/Docker/root wiring -> WP06 may fix. Data/identity -> WP01. GARG/band/priority/alert -> WP02. Domain/Evidence -> WP03. REST/state -> WP04A. MCP/AI/evals -> WP04B. Frontend semantics/API integration -> WP05A/WP05B. Owner-package semantic defects are returned rather than silently changed.

## APPROXIMATE IMPLEMENTATION EFFORT
4–6 engineering hours plus user-local final acceptance time.
