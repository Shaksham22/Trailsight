# TRAILSIGHT V2 — WP01 IBM DATA FOUNDATION

> **Historical implementation ticket — complete.** Do not use this file as a current runbook.

## PACKAGE
WP01 — IBM Data Foundation

## IMPLEMENTER
**REGULAR CHATGPT**

## PURPOSE
Build the runtime-safe IBM AMLworld HI-Small data foundation: canonical identities, deterministic Bank Country metadata, runtime-safe DuckDB base data, source/runtime/offline separation, and data/firewall tests. No detector or investigation logic.

## WHY THIS IMPLEMENTER
The work is deterministic Python/DuckDB ingestion with frozen identity/firewall contracts, narrow ownership, and strong fixture tests. It does not require broad repository reasoning or GARG mathematics.

## PREREQUISITE
Use the latest Manager-approved repository ZIP before any V2 production package has been applied (roadmap snapshot `R0_BASE.zip`). Inspect the actual repository before choosing concrete files.

## REQUIRED INPUTS
Attach exactly:

1. latest Manager-approved repository ZIP before V2 production implementation (`R0_BASE.zip` when using roadmap names)
2. complete FINAL Trailsight V2 system-design ZIP
3. this file: `WP01_IBM_DATA_FOUNDATION.md`

The external IBM HI-Small source remains user-local for validation and is not an implementation-chat attachment or delivery artifact.
## DESIGN DOCUMENTS TO READ
Read at minimum:
- `docs/v2/00_PRODUCT_CONTRACT.md`
- `docs/v2/02_DATA_AND_DETECTOR.md`
- `docs/v2/08_TESTING_AND_ACCEPTANCE.md`
- `docs/v2/09_IMPLEMENTATION_ROADMAP.md`
- this file.

## OWNED PATHS
Create/own:
```text
src/trailsight_v2/__init__.py          # create minimal package root only if absent
src/trailsight_v2/data/**
scripts/v2_data_* or equivalent narrowly named V2 preparation entrypoints
tests/v2/data/**
data/v2/metadata/**                     # checked-in safe metadata only, if needed
.gitignore                              # data-safety additions only
```
Exact script names may follow repository convention after inspection. Do not put generated runtime DB in replacement ZIP.

## FORBIDDEN PATHS
Do not modify:
```text
src/trailsight_v2/detector/**
src/trailsight_v2/domain/**
src/trailsight_v2/api/**
src/trailsight_v2/mcp/**
src/trailsight_v2/ai/**
frontend/**
Dockerfile
README.md
prompts/**
evals/**
```
Do not rewrite V1 packages except a root import/package discovery change explicitly required for the new V2 namespace.

## SHARED-FILE AUTHORITY
May make additive `pyproject.toml` / `uv.lock` changes only if a strictly required data dependency is missing. Prefer existing DuckDB/Python facilities. May add `.gitignore` exclusions for raw IBM/generated runtime artifacts. No Docker/README/frontend package changes.

## IMPLEMENTATION RESPONSIBILITIES
Build the runtime-safe IBM HI-Small foundation:
- validate expected source fields without inventing IBM columns;
- frozen bank/account string normalization;
- canonical account tuple/ref;
- `ibm-txref-v1` transaction reference;
- runtime-safe transactions/accounts/banks/source manifest;
- deterministic `bank-country-v1` enrichment;
- cross-currency direct fact;
- source/runtime/offline-evaluation separation;
- detector-safe canonical edge/day inputs or query surfaces required by WP02;
- safe DuckDB schema creation/preparation command;
- small deterministic test fixtures.

The raw external source and hidden truth remain outside runtime-safe tables. `Is Laundering` may be acknowledged only by source validation/firewall code and must not be copied into runtime tables/models.

## NON-RESPONSIBILITIES
Do not implement GARG, snapshots, bands, transaction priority, alerts, investigation indicators, Evidence V2, API, MCP, AI, frontend, Docker, or offline policy metrics.

## UPSTREAM CONTRACT
Frozen contracts include:
- source dataset `ibm-amlworld-hi-small`;
- canonical identity `(source_dataset, bank_id, account_id)`;
- source-ID normalization exactly as defined in `docs/v2/02_DATA_AND_DETECTOR.md`;
- Bank Country hash mapping/version/list;
- transaction ref canonicalization;
- runtime-safe logical tables in `02_DATA_AND_DETECTOR.md`.

## DOWNSTREAM HANDOFF
Downstream may rely on:
- exact implemented import paths for canonicalization/source/preparation helpers;
- exact DuckDB base table/column names matching system design;
- safe account/transaction refs;
- bank metadata mapping;
- detector input query/edge extraction contract;
- test fixture builder/schema;
- full-source preparation command and source path env/config;
- proof that hidden truth is absent from runtime-safe DB.

Freeze these exact paths in `COMPLETION_REPORT.md`.

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

Return `WP01_DELIVERY.zip` using the scoped structure defined immediately above. Replacement payload must not contain raw IBM files or generated real-data DuckDB.

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
At minimum fixture/unit tests for:
- source header/required columns;
- bank/account normalization including whitespace/case/leading zeroes/missing values;
- account_ref uniqueness across banks/sources;
- transaction_ref determinism/source ordinal/hidden-label independence;
- Bank Country determinism and forbidden inputs;
- runtime schema and firewall;
- canonical detector edge identity;
- small DuckDB preparation/query smoke.
Run relevant existing Python tests impacted by root dependency/config changes.

## USER-LOCAL VALIDATION
The user runs the preparation command against the actual external HI-Small source and reports:
- row count;
- account count;
- min/max timestamp;
- raw source checksum;
- runtime DB generated path/size;
- preparation wall-clock;
- runtime schema firewall check.
If actual IBM headers contradict the frozen source contract, STOP to Manager; do not reinterpret silently.

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

Include input `R0_BASE`, exact owned paths, commands/results, user-local command, actual dependency changes, actual data contract import paths, generated table names, and any source mismatch.

## PASS GATE
WP01 passes when automated data/identity/firewall tests pass and the user-local full-source preparation completes without hidden-truth leakage. Manager then creates `R1_DATA.zip` from R0 + WP01 delivery; generated real data stays local/uncommitted.

## WHAT MAY START AFTER THIS WP PASSES
After WP01 passes and the user overlays/tests its delivery, the Manager creates the latest repository ZIP after WP01 (`R1_DATA.zip`). WP02 and WP03 may then start in parallel. WP05A may already be running independently from the original base.

## PARALLELISM
May run in parallel with WP05A because paths are disjoint. WP02/WP03 wait for the WP01 contract/code delivery; their full-real-data tests may use the user's locally generated DB without requiring it inside the repository ZIP.

## CROSS-PACKAGE FAILURE ROUTING
If a genuine contradiction exists between the repository, this WP and the authoritative design bundle, STOP and report it. Do not redesign the contract locally. Unowned changes must be reported rather than implemented.

Identity/source/schema/firewall defects return to WP01. GARG-specific needs belong to WP02. Investigation query needs belong to WP03. Report unowned changes; do not implement them.

## APPROXIMATE IMPLEMENTATION EFFORT
3–4 engineering hours plus user-local full-source preparation time.
