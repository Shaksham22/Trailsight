# TRAILSIGHT V2 — WP02 GARG, PRIORITY, AND ALERTS

> **Historical implementation ticket — complete.** Do not use this file as a current runbook.

## PACKAGE
WP02 — GARG, Priority, and Network Pattern Alerts

## IMPLEMENTER
**CODEX**

## PURPOSE
Implement the production GARG structural detector pipeline, daily cumulative point-in-time snapshots, eligibility/rank/bands, transaction priority, Network Pattern Alerts, parity/performance gates, and label-blind offline evaluation boundary.

## WHY THIS IMPLEMENTER
This is the highest-risk production package: research-code parity, canonical graph identity, Louvain/preprocessing, point-in-time cumulative snapshots, score/rank/band persistence, transaction-priority materialization, alert lifecycle, memory/performance, and possible semantics-preserving optimization. Repository-wide algorithmic reasoning materially reduces risk.

## PREREQUISITE
Use the latest Manager-approved repository ZIP after WP01 passes and its delivery has been merged/tested (`R1_DATA.zip`). Do not start from the pre-WP01 base.

## REQUIRED INPUTS
Attach exactly:

1. latest Manager-approved repository ZIP after WP01 (`R1_DATA.zip`)
2. complete FINAL Trailsight V2 system-design ZIP
3. this file: `WP02_GARG_PRIORITY_ALERTS.md`

If the Manager separately supplies a GARG spike/benchmark or WP01 completion report, use it as supplementary evidence. Its absence does not authorize inventing results or changing the frozen empirical gates; inspect the actual repository for concrete WP01 paths/schema.
## DESIGN DOCUMENTS TO READ
Read:
- `02_DATA_AND_DETECTOR.md`
- `03_DOMAIN_AND_EVIDENCE.md` for downstream table expectations only
- `08_TESTING_AND_ACCEPTANCE.md`
- `09_IMPLEMENTATION_ROADMAP.md`
- `docs/v2/00_PRODUCT_CONTRACT.md`
- `docs/v2/01_SYSTEM_ARCHITECTURE.md`
Inspect pinned/reference GARG research code/provenance actually available to the project before adapting it.

## OWNED PATHS
Own/create:
```text
src/trailsight_v2/detector/**
scripts/v2_detector_* or equivalent benchmark/preparation entrypoints
tests/v2/detector/**
```
May add version/provenance metadata under an approved V2 metadata area if WP01 did not already own the exact file.

## FORBIDDEN PATHS
Do not modify WP03 domain/Evidence code, WP04A API/runtime-state or WP04B MCP/AI/evals, frontend, Docker/README, or hidden-truth runtime schemas. Do not alter WP01 canonical identity implementation; report a defect if it is wrong.

## SHARED-FILE AUTHORITY
May add only detector-required dependencies to `pyproject.toml`/`uv.lock` after inspecting existing dependencies. Do not remove/re-pin unrelated packages. No frontend/root runtime files.

## IMPLEMENTATION RESPONSIBILITIES
Implement the frozen detector pipeline:
- GARG-AML undirected basic structural core;
- simple unweighted undirected canonical account graph;
- Bank+Account `account_ref` nodes;
- frozen Louvain config/semantics;
- `garg-eligibility-v1` wrapper without changing GARG math;
- daily cumulative COMPLETE/FAILED snapshots and baseline;
- score/support persistence for eligible accounts and explicit UNSCORED states for all accounts;
- deterministic rank/percentile and top-1%/next-4%/remaining band policy;
- point-in-time transaction snapshot association and priority matrix;
- account-native HIGH entry/re-entry Network Pattern Alerts;
- immutable detector artifacts;
- offline evaluation command/path isolated from runtime and label-blind until outputs already exist.

## NON-RESPONSIBILITIES
Do not implement domain indicators/Evidence V2, REST/MCP/AI, review workflow state, frontend, or Docker. Do not train any classifier or use hidden labels to set policy.

## UPSTREAM CONTRACT
Rely on WP01 canonical transaction/account/bank tables and detector-safe edge/day inputs. Use only frozen normalized bank/account representation. Snapshot/band/priority/alert schemas and semantics are frozen by design.

## DOWNSTREAM HANDOFF
Downstream may rely on exact persisted tables/columns for:
```text
detector_snapshots
account_detector_states
account_detector_support
transaction_review_states
network_alerts
```
plus exact detector version/config constants, snapshot ID/config hash functions, preparation/benchmark commands, and whether baseline or approved optimized scorer is active.

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

Return `WP02_DELIVERY.zip` with only detector-owned source/scripts/tests plus explicitly authorized dependency manifest changes. Never include generated multi-GB snapshot DB/artifacts or hidden truth.

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
Before any full daily run:
1. controlled parity fixtures covering chain/star/clique/block/disconnected/repeated-edge/self-loop/Bank+Account collision;
2. realistic canonical subset parity against pinned/reference semantics;
3. point-in-time snapshot fixtures;
4. eligibility/rank/band boundary/tie tests;
5. every transaction priority matrix combination;
6. alert entry/re-entry/no-duplicate tests;
7. future-alert and future-snapshot leakage tests;
8. hidden-label firewall/offline separation;
9. deterministic repeatability.

### EARLY HARD FEASIBILITY GATE
After parity fixtures/subset and **before** implementing/running the complete daily sequence, build and benchmark the **full final HI-Small graph + required GARG preprocessing/scoring**. Record wall-clock and peak RSS.

Approved limits remain:
```text
full final snapshot <= 30 minutes
peak RSS < 70% physical RAM
```
If baseline exceeds limits, try only the already-approved semantics-preserving compact adjacency/CSR scoring contingency, re-prove parity, and benchmark again. If it still fails parity/resources: **STOP TO MANAGER**. Never skip snapshots, reduce graph scope, alter Louvain/GARG math, or weaken point-in-time semantics.

## USER-LOCAL VALIDATION
When real HI-Small data or long runtime is unavailable in Codex, the user runs the exact benchmark command and reports wall-clock/peak RSS. After feasibility passes, user may run the complete daily sequence and report snapshot count/status/timings and generated DB checks. Long compute is not faked by the worker.

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

Include:
- pinned GARG provenance;
- exact active scorer path (reference or approved optimized);
- parity fixture/subset results;
- benchmark command and measured result or explicit USER-LOCAL PENDING;
- dependency additions;
- table/schema import/write paths;
- snapshot/band/priority/alert test results;
- any safe failure/restart/checkpoint behavior.

## PASS GATE
WP02 code is not sufficient by itself. Manager pass requires parity plus accepted full-final feasibility result. The daily sequence may remain user-local but must not be declared feasible without measured benchmark data.

## WHAT MAY START AFTER THIS WP PASSES
WP02 alone does not unlock WP04. WP02 and WP03 must both pass and their overlays must merge cleanly at Merge Gate A. After that merged core (`R2_CORE.zip`) is Manager-approved, WP04A and WP04B may start in parallel.

## PARALLELISM
May run in parallel with WP03 **after WP01**, because WP02 owns detector paths and WP03 owns domain paths. Both must use the frozen detector-table contracts; WP03 may use contract fixtures until merge. Merge Gate A waits for WP02 feasibility acceptance.

## CROSS-PACKAGE FAILURE ROUTING
If a genuine contradiction exists between the repository, this WP and the authoritative design bundle, STOP and report it. Do not redesign the contract locally. Unowned changes must be reported rather than implemented.

Data/identity defects -> WP01. Domain/evidence query interpretation -> WP03. Performance/parity failure -> Manager/system-design gate; do not modify semantics. API/frontend concerns are out of scope.

## APPROXIMATE IMPLEMENTATION EFFORT
6–10 engineering hours plus potentially several hours user-local detector computation.
