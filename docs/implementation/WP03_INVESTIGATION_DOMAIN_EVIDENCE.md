# TRAILSIGHT V2 — WP03 INVESTIGATION DOMAIN AND EVIDENCE V2

## PACKAGE
WP03 — Deterministic Investigation Domain and Evidence V2

## IMPLEMENTER
**REGULAR CHATGPT**

## PURPOSE
Implement the deterministic V2 InvestigationService/domain and Evidence V2 identity/resolution over the frozen runtime/detector contracts, including point-in-time indicators, bounded network/supporting evidence, and tests. This package is the factual source of truth for normal APIs and MCP.

## WHY THIS IMPLEMENTER
The package is high-risk but fully specified, deterministic, confined to one V2 domain namespace, and suited to complete-file replacement plus exhaustive fixture tests. It deliberately excludes GARG math, HTTP, SDK integration, and frontend. Final Codex integration will audit it repository-wide.

## PREREQUISITE
Use the latest Manager-approved repository ZIP after WP01 passes (`R1_DATA.zip`). WP03 intentionally runs in parallel with WP02 and must use frozen detector table/interface fixtures rather than importing unfinished WP02 implementation.

## REQUIRED INPUTS
Attach exactly:

1. latest Manager-approved repository ZIP after WP01 (`R1_DATA.zip`)
2. complete FINAL Trailsight V2 system-design ZIP
3. this file: `WP03_INVESTIGATION_DOMAIN_EVIDENCE.md`

Any WP01 completion report supplied by the Manager is supplementary; the actual repository and final design remain sufficient to resolve concrete base-data paths.
## DESIGN DOCUMENTS TO READ
Read:
- `03_DOMAIN_AND_EVIDENCE.md`
- `02_DATA_AND_DETECTOR.md` persisted-state schemas
- `04_API_AND_MCP.md` downstream needs
- `08_TESTING_AND_ACCEPTANCE.md`
- `09_IMPLEMENTATION_ROADMAP.md`
- `docs/v2/00_PRODUCT_CONTRACT.md`
- `docs/v2/01_SYSTEM_ARCHITECTURE.md`
- `docs/v2/04_API_AND_MCP.md`

## OWNED PATHS
Own/create:
```text
src/trailsight_v2/domain/**
tests/v2/domain/**
```
Also own V2 shared domain contracts/config/errors only if placed at package-root paths explicitly listed in the completion report. Preferred public construction path is:
```text
trailsight_v2.domain.service.InvestigationServiceV2
trailsight_v2.domain.service.create_investigation_service_v2
```
Do not modify root manifests.

## FORBIDDEN PATHS
No edits to detector, API, MCP, AI, frontend, Docker/README, WP01 data preparation, or V1 active code except copying/adapting domain-neutral patterns into the V2 namespace.

## SHARED-FILE AUTHORITY
No `pyproject.toml`/`uv.lock`, frontend packages, Docker, README, or root config edits. If a missing dependency is genuinely required, report it in `REQUIRED_INTEGRATION_CHANGES.md`.

## IMPLEMENTATION RESPONSIBILITIES
Own every deterministic investigation fact exposed to normal API or MCP:
- read-only runtime repository over the frozen runtime DB;
- context resolution for alert, transaction, direct-latest account, and historical account origins;
- transaction/account/alert context models;
- account observed activity;
- amount behavior on sender-paid and receiver-received sides with frozen thresholds;
- prior A<->B relationship/newness;
- 1h/24h velocity;
- 24h fan-in/fan-out distinct canonical counterparties;
- cross-currency;
- optional secondary indicators only if still frozen at package start;
- bounded one-hop network root + max 24 counterparties with deterministic ranking/truncation;
- supporting transactions/relationships;
- exact `relevant_recent_transaction_count = involvement in [entry_cutoff-24h, entry_cutoff)`;
- Evidence V2 types/factory/resolver/DisplayEvidence projection;
- application-owned evidence IDs that are self-describing/resolving, URL-safe, integrity-checkable;
- one deterministic service facade/factory.

Evidence resolver must decode/validate/canonicalize, recover subject/context/snapshot/parameters, resolve authoritative context, recompute evidence, regenerate identity, exact-match verify, and reject malformed/unknown/cross/future context. No evidence database.

## NON-RESPONSIBILITIES
Do not compute GARG scores/ranks/bands/priority, write detector tables, implement HTTP/MCP/AI, manage runtime_state.json, or render UI.

## UPSTREAM CONTRACT
Uses WP01 safe transactions/accounts/banks and the frozen WP02 persisted detector table shapes. All history respects the authoritative context cutoff and strict `<` rules. Hidden truth is unavailable.

## DOWNSTREAM HANDOFF
Freeze in completion report:
- exact `InvestigationServiceV2` and `create_investigation_service_v2()` import paths;
- public deterministic methods needed by API/MCP;
- V2 context/evidence/error model paths;
- Evidence V2 ID grammar/resolver path;
- UI target enum/DisplayEvidence shape;
- fixture refs for alert/transaction/account tests.
WP04A/WP04B must use these exact outputs and never reconstruct repositories.

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

Return `WP03_DELIVERY.zip` using the global format and only domain-owned files.

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
Required automated tests:
- read-only DB/firewall/schema failure;
- alert/transaction/latest/historical context and future/equal-time exclusion;
- amount n=0/4/5/19/20, medians/percentile/currency/direction isolation;
- relationship both directions/equal-time exclusion;
- exact 1h/24h velocity boundaries;
- fan-in/fan-out canonical identity;
- cross-currency/no FX inference;
- bounded one-hop ranking/reserved selected relation/truncation;
- exact alert recent-transaction 24h boundary/self-transfer-once/cross-bank-ID cases;
- every Evidence V2 type stable ID, decode, checksum/canonical tamper rejection, context recovery, recompute/regenerate exact match, max support 50, hidden-truth absence;
- persisted detector facts returned unchanged, never recomputed.

## USER-LOCAL VALIDATION
After Merge Gate A with a real generated runtime DB, inspect representative HIGH alert account, transaction historical context, direct-latest account, high-degree network truncation, amount indicators, and evidence resolution. Long GARG compute remains WP02/user responsibility.

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

List exact public import paths/methods/models/errors, fixture database schema used before merge, tests, any detector-table contract assumption, and any required unowned change.

## PASS GATE
Package passes independently when domain/evidence fixture tests pass. It becomes authoritative for downstream only after Merge Gate A confirms compatibility with actual WP02 detector tables and the service factory opens the merged DB read-only.

## WHAT MAY START AFTER THIS WP PASSES
WP03 alone does not unlock WP04. WP02 and WP03 must both pass, then their disjoint overlays are merged and tested at Merge Gate A. The accepted merged core (`R2_CORE.zip`) becomes the prerequisite for WP04A and WP04B.

## PARALLELISM
May run in parallel with WP02 from R1_DATA. No root files or detector paths may overlap. WP04A/WP04B wait for R2_CORE after Merge Gate A.

## CROSS-PACKAGE FAILURE ROUTING
If a genuine contradiction exists between the repository, this WP and the authoritative design bundle, STOP and report it. Do not redesign the contract locally. Unowned changes must be reported rather than implemented.

Base data/identity -> WP01. Detector-state contradiction -> WP02. API/MCP/AI need that would change domain contract -> Manager before implementation. Do not patch outside ownership.

## APPROXIMATE IMPLEMENTATION EFFORT
5–7 engineering hours.
