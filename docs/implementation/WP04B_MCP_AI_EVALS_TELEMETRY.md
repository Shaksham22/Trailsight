# TRAILSIGHT V2 — WP04B MCP, AI, EVALS, AND TELEMETRY

> **Historical implementation ticket — complete.** Do not use this file as a current runbook.

## PACKAGE
WP04B — Model-facing MCP, AI Investigation, Evals, and Telemetry

## IMPLEMENTER
**REGULAR CHATGPT**

## PURPOSE
Implement the seven frozen stdio MCP tools as adapters over the deterministic InvestigationService, OpenAI Agents SDK orchestration, structured analyst-summary output, one bounded follow-up route, JSONL telemetry, prompts, and the AI eval harness. The deterministic packet is the trust boundary; generated prose is structurally parsed but not post-validated against Evidence V2 citations.

## WHY THIS IMPLEMENTER
The package uses existing V1 MCP/Agents/eval/JSONL patterns but has frozen V2 tools, packet-boundary semantics, prompt semantics, and bounded paths. It is large enough to require discipline but does not require detector math or repository-wide refactoring. An explicit SDK observability preflight prevents fake compliance.

## PREREQUISITE
Use the latest Manager-approved repository ZIP after WP02 and WP03 have both passed and Merge Gate A has produced the merged core (`R2_CORE.zip`). WP04B runs in parallel with WP04A and must not edit WP04A-owned API construction/runtime-state files.

## REQUIRED INPUTS
Attach exactly:

1. latest Manager-approved merged-core repository ZIP after WP02 + WP03 (`R2_CORE.zip`)
2. complete FINAL Trailsight V2 system-design ZIP
3. this file: `WP04B_MCP_AI_EVALS_TELEMETRY.md`

Any upstream completion reports supplied by the Manager are supplementary; inspect the actual merged repository for the concrete InvestigationService/Evidence V2 import paths.
## DESIGN DOCUMENTS TO READ
Read `docs/v2/00_PRODUCT_CONTRACT.md`, `docs/v2/01_SYSTEM_ARCHITECTURE.md`, `docs/v2/03_DOMAIN_AND_EVIDENCE.md`, `docs/v2/04_API_AND_MCP.md`, `docs/v2/05_AI_AND_EVALUATION.md`, `docs/v2/07_RUNTIME_AND_DEPLOYMENT.md`, `docs/v2/08_TESTING_AND_ACCEPTANCE.md`, `docs/v2/09_IMPLEMENTATION_ROADMAP.md`, and current V1 MCP/AI code for reusable infrastructure patterns only.

## OWNED PATHS
Own/create:
```text
src/trailsight_v2/mcp/**
src/trailsight_v2/ai/**
prompts/v2/**
evals/v2/**
tests/v2/mcp/**
tests/v2/ai/**
```
Generated local traces/eval results remain ignored/uncommitted and outside replacement payload.

## FORBIDDEN PATHS
Do not edit WP04A API/runtime-state files, WP03 domain, detector/data, frontend, Docker/README, or V1 packages except copying/adapting generic patterns into V2 paths.

## SHARED-FILE AUTHORITY
Do not edit `pyproject.toml`/`uv.lock` merely to re-add dependencies already present. If the installed SDK version is concretely incompatible, STOP/report exact dependency need rather than silently upgrading. No frontend/root runtime changes.

## IMPLEMENTATION RESPONSIBILITIES
Implement:
- one local stdio MCP server;
- exactly seven frozen V2 tools and bounded projections;
- no SQL/arbitrary DB/graph traversal/ground truth;
- MCP server startup through WP03 `create_investigation_service_v2()` only;
- OpenAI Agents SDK model config/prompt versioning;
- initial account/transaction/alert investigation;
- `trailsight_v2.ai.http` router or `create_router()` exporting the frozen investigation/follow-up endpoints;
- HTTP route handlers obtain deterministic service/runtime-state store from `request.app.state`; they do not construct repositories;
- structured AI output with DETECTOR_OUTPUT / OBSERVED_FACT / INTERPRETATION distinction;
- application-issued Evidence V2 references only;
- fail-closed validation against seed/successful-tool evidence IDs;
- one bounded follow-up using persisted subject/context supplied by runtime-state when merged with WP04A; no transcript memory;
- explicit abstention/limits;
- JSONL telemetry with investigation/subject/context/prompt/model/timing/ordered MCP calls/safe inputs/status/latency/result size/evidence/tokens/cost/validation;
- 15 required AI eval scenarios minimum, plus prompt iteration support;
- offline GARG policy evaluation remains separate from AI evals.

### SDK observability hard gate
Before building telemetry around assumptions, prove the installed MCP/Agents SDK integration exposes actual model-requested tool execution sufficiently to record ordered tool name, safe input, status, latency, result size/evidence IDs. If not available through supported hooks/results, STOP and report. Do not simulate tool execution or parse hidden reasoning.

## NON-RESPONSIBILITIES
Do not implement deterministic calculations, runtime-state storage mechanics, core REST list/detail resources, GARG, frontend, Docker, or hidden-truth evaluation inside runtime AI.

## UPSTREAM CONTRACT
Uses only WP03 deterministic service and frozen MCP/evidence contracts. At HTTP merge time relies on WP04A app-state keys:
```text
app.state.investigation_service
app.state.runtime_state_store
```
The router must be importable even when tested in a small FastAPI app with test doubles in app.state.

## DOWNSTREAM HANDOFF
Freeze:
- exact MCP server command/import;
- seven tool schemas/results/bounds;
- AI router import/export;
- investigation/follow-up route schemas;
- model/prompt config names;
- telemetry JSONL schema;
- eval scenario/result format and commands;
- SDK-observability gate result.

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

Return `WP04B_DELIVERY.zip` with only MCP/AI/prompt/eval/test files plus metadata reports. No secrets/traces/generated eval outputs.

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
No live model required for normal suite:
- exactly seven tools registered, no prohibited tools;
- domain factual projection equality and bounds;
- no hidden truth in tools/errors/prompts/telemetry fixtures;
- structured output schema/category rules;
- valid/invalid/unissued/cross-context Evidence V2 citation validation;
- complete output rejected on evidence-validation failure;
- unsupported/criminal-overclaim fixtures abstain;
- HIGH/LOW/Bank Country wording constraints;
- HTTP router with fake app-state services;
- follow-up request contract and 409 passthrough behavior when state store says used;
- telemetry schema/tool ordering using supported SDK/test instrumentation;
- required 15 eval scenarios runnable deterministically where model is mocked.

## USER-LOCAL VALIDATION
Run credentialed real-model smoke/eval after Merge Gate B:
- tool selection/efficiency;
- factual/evidence support;
- priority explanation;
- detector-vs-fact distinction;
- abstention/AML overclaim;
- Bank Country wording;
- label leakage;
- tokens/cost.
Do not require the user to expose API keys to delivery files.

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

Include SDK versions, observability proof path, MCP command/tool table, AI router path, prompt/model configs, automated results, real-model command, and any runtime-state integration assumption.

## PASS GATE
WP04B passes independently when non-live tests and SDK observability gate pass. It becomes application-complete only at Merge Gate B with WP04A, where AI router/state behavior is tested together.

## WHAT MAY START AFTER THIS WP PASSES
WP04A and WP04B must both pass and merge at Merge Gate B to create `R3_BACKEND.zip`. The accepted WP05A frontend overlay is then applied at Merge Gate C before WP05B starts.

## PARALLELISM
May run in parallel with WP04A from R2_CORE. Must not touch `src/trailsight_v2/api/**`. Merge Gate B combines both overlays.

## CROSS-PACKAGE FAILURE ROUTING
If a genuine contradiction exists between the repository, this WP and the authoritative design bundle, STOP and report it. Do not redesign the contract locally. Unowned changes must be reported rather than implemented.

Wrong deterministic facts/evidence -> WP03. Missing runtime-state mechanics -> WP04A. SDK observability incompatibility -> Manager; do not fake. Frontend rendering -> WP05B.

## APPROXIMATE IMPLEMENTATION EFFORT
5–7 engineering hours plus user-local real-model eval time.
