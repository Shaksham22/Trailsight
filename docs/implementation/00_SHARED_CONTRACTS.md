# TRAILSIGHT — 00 SHARED CONTRACTS

## ROLE

You are implementing one bounded portion of Trailsight. This document is the authoritative interoperability contract for every Codex work package.

## GOAL

Prevent independent Codex sessions from redesigning interfaces, duplicating business logic, or moving responsibilities across package boundaries.

## SOURCE OF TRUTH

1. Approved Trailsight System Design v2.
2. This `00_SHARED_CONTRACTS.md` file.
3. The package-specific instruction file assigned to the current Codex session.

If a package-specific instruction conflicts with this file, stop and report the conflict. Do not choose a new architecture.

# DEPENDENCIES

This file has no implementation dependency. It must be supplied to every Codex session together with exactly one assigned package file.

# FILE / DIRECTORY OWNERSHIP

No implementation Codex session owns this file. Treat `docs/implementation/00_SHARED_CONTRACTS.md` as read-only during implementation. Directory ownership for all executable work is frozen in section 4 below.

# INPUTS

The input to this contract is the Manager-approved Trailsight System Design v2. No Codex session may substitute a different architecture, dataset, product workflow, evidence model, or history definition.

# REQUIRED IMPLEMENTATION

This file does not ask Codex to implement product code. It defines the exact contracts that the assigned package must implement. Read every section that intersects the assigned package before editing files.

# REQUIRED TESTS

The assigned package must run the tests listed in its package-specific instruction and must preserve the shared testing invariants in section 25. Do not weaken a cross-package contract to make a test pass.

# DO NOT CHANGE

Do not modify this shared-contract file from an implementation session. Do not reinterpret its API, MCP, identity, evidence, history, security, or ownership rules. If a change is required, return it to the Manager as a proposed contract change and stop at that boundary.

# ACCEPTANCE CRITERIA

A Codex session complies with this shared contract only when it changes files within its assigned ownership, implements the frozen interfaces exactly, runs its required tests, and reports any cross-package mismatch instead of silently repairing another package.

# COMMANDS TO RUN

There is no standalone implementation command for this shared-contract file. Run only the commands specified by the assigned `01`–`06` work package.

# RETURN WITH

Every package return must include the global return items in section 28 and explicitly state whether any shared-contract conflict was found.

---

# 1. PRODUCT INVARIANTS

Trailsight is a one-screen transaction-review application for synthetic TransXion data.

The transaction-review analyst must be able to:

1. select one approved synthetic review case;
2. see the selected transaction immediately;
3. see deterministic historical context without AI;
4. click **Investigate transaction**;
5. receive 2–4 concise AI findings linked to application-owned evidence;
6. click `[E1]`, `[E2]`, etc. to focus/highlight deterministic evidence;
7. ask at most one bounded follow-up about the selected transaction/history;
8. receive a grounded answer or explicit abstention.

Trailsight does **not** decide or label:

- fraud;
- money laundering;
- suspicious/not suspicious;
- whether to block a transaction;
- regulatory action.

Do not add another product surface, dashboard, chatbot, graph explorer, timeline, alerting system, or multi-page workflow.

---

# 2. ARCHITECTURE INVARIANTS

The locked stack is:

- frontend: React + TypeScript + Vite;
- backend/domain: Python;
- HTTP API: FastAPI;
- runtime database: DuckDB;
- MCP: one local Python stdio MCP server;
- AI integration: OpenAI Agents SDK;
- tests: pytest;
- telemetry: JSONL;
- deployment: one local Docker deployment unit.

The architecture is:

```text
React UI
   |
   v
FastAPI
   |
   +---------------------------+
   |                           |
   v                           v
Shared deterministic       AI orchestration
Python domain                  |
   |                           v
   v                     configured LLM
read-only DuckDB               |
                               v
                        local stdio MCP
                               |
                               v
                     same deterministic domain
```

Hard rules:

1. **The deterministic domain owns all factual calculations.**
2. FastAPI uses that domain directly.
3. MCP imports and uses that same domain; MCP does not reimplement calculations.
4. AI never queries DuckDB directly.
5. Frontend never queries DuckDB, MCP, or the model directly.
6. Evidence is application-owned.
7. MCP gives the model only bounded evidence summaries, never full historical evidence.
8. Runtime data is case-scoped, past-only, and read-only.
9. `Is Laundering` is structurally unavailable to the production runtime path.
10. Model identity is configuration, not architecture.
11. Follow-up is one bounded new run, not persistent chat memory.
12. Invalid AI evidence references fail closed: reject the entire generated investigation.

---

# 3. APPROVED REPOSITORY STRUCTURE

Use this structure unless the Manager explicitly changes it:

```text
trailsight/
├── docs/
│   └── implementation/
│       ├── 00_SHARED_CONTRACTS.md
│       ├── 01_DATA_AND_DATABASE.md
│       ├── 02_BACKEND_AND_DOMAIN.md
│       ├── 03_MCP_SERVER.md
│       ├── 04_AI_EVALS_OBSERVABILITY.md
│       ├── 05_FRONTEND.md
│       └── 06_INTEGRATION_DEPLOYMENT.md
├── src/
│   ├── trailsight_data/          # WP01 only
│   ├── trailsight/               # WP02 only
│   ├── trailsight_mcp/           # WP03 only
│   └── trailsight_ai/            # WP04 only
├── scripts/
│   └── prepare_runtime_data.py   # WP01
├── data/
│   ├── cases/                    # WP01, checked in
│   ├── runtime/                  # generated, gitignored except placeholder
│   └── traces/                   # generated, gitignored except placeholder
├── prompts/                      # WP04
├── evals/                        # WP04
├── eval_results/                 # generated, gitignored
├── frontend/                     # WP05 only
├── tests/
│   ├── data/                     # WP01
│   ├── backend/                  # WP02
│   ├── mcp/                      # WP03
│   ├── ai/                       # WP04
│   └── integration/              # WP06
├── pyproject.toml                # WP01 creates frozen Python manifest; WP06 may only reconcile, not redesign
├── uv.lock                       # WP01 creates/locks; WP06 may only refresh if required by approved manifest
├── Dockerfile                    # WP06
├── .dockerignore                 # WP06
├── .env.example                  # WP06
├── .gitignore                    # WP01 creates initial file; WP06 may extend/reconcile without removing source/runtime exclusions
└── README.md                     # WP06
```

Do not create additional top-level services or repositories.

---

# 4. DIRECTORY OWNERSHIP

| Work package | Owns | May read | Must not modify |
|---|---|---|---|
| 01 Data/DB | `src/trailsight_data/`, `scripts/prepare_runtime_data.py`, `data/cases/`, `tests/data/`, initial `pyproject.toml`, initial `uv.lock`, initial root `.gitignore` | shared contracts, external TransXion source | `src/trailsight/`, `src/trailsight_mcp/`, `src/trailsight_ai/`, `frontend/`, prompts/evals, Docker/README |
| 02 Backend/Domain | `src/trailsight/`, `tests/backend/` | WP01 outputs, shared contracts | WP01 files, MCP, AI, frontend, Docker/README, dependency manifest |
| 03 MCP | `src/trailsight_mcp/`, `tests/mcp/` | `src/trailsight/`, runtime DB, shared contracts | domain calculations, FastAPI, AI, frontend, WP01 data prep, dependency manifest |
| 04 AI/Evals/Obs | `src/trailsight_ai/`, `prompts/`, `evals/`, `tests/ai/` | backend/domain, MCP, shared contracts | domain calculations, MCP contracts, frontend, WP01, dependency manifest |
| 05 Frontend | `frontend/` | shared contracts and API examples | all Python/domain/MCP/AI/data prep files |
| 06 Integration | `tests/integration/`, `Dockerfile`, `.dockerignore`, `.env.example`, `README.md`; may extend/reconcile the root `.gitignore` created by WP01 | all completed packages | may not remove WP01 source/runtime exclusions, move business logic, or redesign component contracts; may only make narrowly required packaging/startup corrections after reporting the owner |

If a package needs a change in another owner's files, do not make that change silently. Return the exact failing contract and owning package to the Manager.

---

# 5. PYTHON DEPENDENCY CONTRACT

WP01 creates the shared Python project manifest once so later sessions do not conflict on dependency files.

The manifest must support these locked capabilities only:

- `duckdb`;
- `fastapi`;
- `uvicorn`;
- `pydantic`;
- official Python `mcp` SDK;
- `openai-agents`;
- `PyYAML`;
- `pytest`;
- `httpx` for FastAPI test client/integration support.

Use Python 3.12+.

Do not add Postgres clients, Redis, vector DB packages, orchestration frameworks, browser automation frameworks, or observability platforms.

WP01 locks compatible versions in `uv.lock`. WP02–WP05 must not change dependency manifests. If a required locked-stack package is missing or incompatible, report it to the Manager; do not substitute a new framework.

---

# 6. SHARED DOMAIN TERMINOLOGY

Use these terms exactly:

- **case**: a Trailsight-owned review fixture pointing to one selected transaction;
- **case_ref**: Trailsight-owned stable case identifier;
- **transaction_ref**: Trailsight-owned stable `txref-v1` fingerprint;
- **selected transaction**: transaction under review;
- **selected sender**: `(From Bank, From Account)` of selected transaction;
- **counterparty**: `(To Bank, To Account)` of selected transaction;
- **historical transaction**: strictly earlier outgoing transaction from selected sender permitted for this case;
- **Synthetic Region**: source-derived numeric account suffix modulo 20;
- **internal evidence**: complete deterministic application-owned evidence object;
- **model-facing evidence summary**: bounded MCP projection of internal evidence;
- **finding**: model-generated concise statement referencing one or more application-issued evidence IDs;
- **limit**: explicit statement explaining unavailable or unsupported information.

Never use Synthetic Region as a synonym for country, city, province, international corridor, or remittance corridor.

---

# 7. ACCOUNT IDENTITY

Canonical account identity is the ordered pair:

```text
(bank, account)
```

Account number alone is never sufficient for identity comparisons.

Counterparty equality requires both `to_bank` and `to_account` to match.

---

# 8. `txref-v1` — CANONICAL TRANSACTION FINGERPRINT

The source contains no trusted transaction ID. Trailsight owns the transaction reference.

## 8.1 Version

Fingerprint algorithm identifier:

```text
txref-v1
```

Final reference format:

```text
tsx_<64 lowercase SHA-256 hex characters>
```

## 8.2 Fixed field order

Exactly:

1. Timestamp
2. From Bank
3. From Account
4. To Bank
5. To Account
6. Amount Paid
7. Payment Currency
8. Amount Received
9. Receiving Currency
10. Payment Format

`Is Laundering` must never participate.

## 8.3 Timestamp normalization

Parse the source timestamp and serialize exactly as:

```text
YYYY-MM-DDTHH:MM:SS.ffffff
```

Always six fractional-second digits.

Example:

```text
2025-05-08 16:18:46
→ 2025-05-08T16:18:46.000000
```

Do not infer, append, or convert a timezone. Do not append `Z`.

## 8.4 Decimal normalization

Parse `Amount Paid` and `Amount Received` as exact base-10 decimals, never binary float for fingerprinting.

Canonical formatting rules:

```text
69.5400 → "69.54"
69.54   → "69.54"
15.000  → "15"
0.00    → "0"
```

Rules:

- no exponent notation;
- remove insignificant trailing fractional zeros;
- remove trailing decimal point;
- no leading `+`;
- preserve `-` if source value is negative;
- canonical zero is `"0"`.

## 8.5 Text normalization

For bank, account, currency, and payment-format fields:

1. parse as string;
2. apply Unicode NFC normalization;
3. remove leading/trailing ASCII whitespace;
4. preserve case;
5. preserve internal whitespace;
6. preserve punctuation.

Do not uppercase or lowercase identifiers during fingerprint generation.

## 8.6 Canonical serialization

Construct this ordered array of strings:

```text
[
  "txref-v1",
  canonical_timestamp,
  canonical_from_bank,
  canonical_from_account,
  canonical_to_bank,
  canonical_to_account,
  canonical_amount_paid,
  canonical_payment_currency,
  canonical_amount_received,
  canonical_receiving_currency,
  canonical_payment_format
]
```

Serialize as compact JSON:

- UTF-8 bytes;
- no optional whitespace;
- array order fixed as above;
- non-ASCII represented directly in UTF-8, not escaped solely for hashing.

Compute SHA-256 over those exact bytes.

## 8.7 Collision/duplicate rule

Preparation must fail if two source rows generate the same `transaction_ref`.

Do not:

- silently deduplicate;
- append CSV row number;
- append random data;
- choose one row.

If canonical payloads differ but SHA-256 collides, also fail.

---

# 9. CASE IDENTITY

`case_ref` is Trailsight-owned and must match:

```text
[a-z0-9][a-z0-9-]{0,63}
```

Examples:

```text
demo-01
eval-amount-insufficient-01
```

Each case points to exactly one selected `transaction_ref`.

Case IDs do not come from TransXion.

Primary demo case:

```text
case_ref: demo-01
Timestamp: 2025-05-08 16:18:46
From Account: A016568
To Account: A013644
Amount Paid: 69.54 CNY
Amount Received: 9.40 USD
Payment Format: Cash
```

The exact banks must be resolved from the source transaction during preparation; do not invent them in instructions or UI fixtures.

---

# 10. HISTORY RULES

A historical transaction must satisfy all of:

1. it is in the selected case's permitted `case_transactions` slice;
2. its sender identity equals the selected sender `(from_bank, from_account)`;
3. `timestamp < selected_timestamp`.

Equal timestamps are never history for one another.

CSV row order is irrelevant.

Preparation-time past-only slicing and runtime timestamp enforcement are both mandatory.

---

# 11. AMOUNT-HISTORY CONTRACT

Population:

- selected sender;
- previous outgoing transactions only;
- same `Payment Currency` as selected transaction;
- strictly earlier timestamp.

Do not mix raw amounts across currencies.

## Fewer than 5

```text
history_quality = insufficient
sample_size = n
median = null
empirical_percentile = null
```

User-facing meaning: **Insufficient same-currency history.**

## 5–19

```text
history_quality = limited
sample_size = n
median = deterministic median
empirical_percentile = null
```

## 20+

```text
history_quality = sufficient
sample_size = n
median = deterministic median
empirical_percentile = 100 * count(previous_amount <= selected_amount) / n
```

No P95 suspiciousness threshold.

Use exact deterministic values internally. Round only for presentation.

---

# 12. SOURCE-DERIVED SYNTHETIC REGION

Derivation:

```text
numeric account suffix modulo 20
```

Examples:

```text
A016568 → 16568 % 20 → 8
A013644 → 13644 % 20 → 4
```

If an account has no parseable numeric suffix, fail that derivation; do not guess.

This function belongs in deterministic Python domain logic. Data preparation may validate it, but React and MCP must never reimplement it.

---

# 13. HIDDEN-LABEL FIREWALL

The source transaction file contains `Is Laundering`.

Production runtime rules:

1. WP01 must import transaction columns through an explicit allowlist.
2. Never use `SELECT *` from raw source data.
3. `Is Laundering` must not exist in runtime DuckDB schema.
4. It must not appear in `transaction_ref` canonicalization.
5. It must not exist in domain models.
6. It must not exist in FastAPI responses.
7. It must not exist in MCP results.
8. It must not enter prompt/model input.
9. Startup/runtime tests must assert it is absent.

Other unnecessary person demographics must also be excluded. Runtime entity information is only what is necessary to map `(bank, account)` to `Person` or `Merchant`.

---

# 14. SHARED DATA / PYDANTIC SCHEMAS

WP02 owns the concrete Pydantic implementation under `src/trailsight/`. Other packages import these contracts; they do not redefine semantically different versions.

Use JSON-safe types. Monetary values crossing HTTP/MCP boundaries are decimal strings, not JSON floats.

## 14.1 EntityRef

```text
bank: string
account: string
entity_type: "Person" | "Merchant"
synthetic_region: integer 0..19
```

## 14.2 SelectedTransaction

```text
transaction_ref: string
timestamp: canonical timestamp string
sender: EntityRef
counterparty: EntityRef
amount_paid: decimal string
payment_currency: string
amount_received: decimal string
receiving_currency: string
payment_format: string
cross_currency: boolean
currency_pair: string             # "CNY → USD"
region_relationship: "same_region" | "cross_region"
```

## 14.3 SenderHistoryContext

```text
evidence_id: string
prior_outgoing_count: integer >= 0
```

## 14.4 AmountHistoryContext

```text
evidence_id: string
history_quality: "insufficient" | "limited" | "sufficient"
sample_size: integer >= 0
selected_amount: decimal string
payment_currency: string
historical_median: decimal string | null
empirical_percentile: decimal number | null
```

## 14.5 CounterpartyHistoryContext

```text
evidence_id: string
seen_before: boolean
previous_interaction_count: integer >= 0
first_previous_timestamp: canonical timestamp | null
most_recent_previous_timestamp: canonical timestamp | null
```

## 14.6 RegionHistoryContext

If destination-region novelty is retained:

```text
evidence_id: string
sender_region: integer 0..19
receiver_region: integer 0..19
region_relationship: "same_region" | "cross_region"
receiver_region_seen_before: boolean
previous_receiver_region_count: integer >= 0
```

If the Manager invokes the approved first scope cut, keep selected-transaction region derivation and `region_relationship`, but remove destination-region historical novelty consistently from API/MCP/evals/UI.

## 14.7 HistoricalTransactionRow

```text
transaction_ref: string
timestamp: canonical timestamp string
counterparty_bank: string
counterparty_account: string
counterparty_type: "Person" | "Merchant"
amount_paid: decimal string
payment_currency: string
receiving_currency: string
receiver_region: integer 0..19
payment_format: string
```

## 14.8 WorkspaceResponse

```text
case_ref: string
display_name: string
selected_transaction: SelectedTransaction
sender_history: SenderHistoryContext
amount_history: AmountHistoryContext
counterparty_history: CounterpartyHistoryContext
region_history: RegionHistoryContext | null
historical_transactions: list[HistoricalTransactionRow]
```

Currency pair/cross-currency live in `selected_transaction`; do not create a second calculation path.

---

# 15. INTERNAL EVIDENCE CONTRACT

Evidence is created by deterministic domain functions and owned by Trailsight.

Base envelope:

```text
evidence_id: string
evidence_type:
  "selected_transaction" |
  "sender_history" |
  "amount_history" |
  "counterparty_history" |
  "region_history" |
  "currency_history"
case_ref: string
facts: typed evidence-specific facts
supporting_transaction_refs: list[string]
ui_target:
  "selected_transaction" |
  "sender_history" |
  "amount_context" |
  "counterparty_history" |
  "synthetic_region_history" |
  "historical_evidence"
```

Internal evidence may contain the complete relevant transaction-reference set.

The model does not receive this object directly.

---

# 16. EVIDENCE ID RULES

Application-issued deterministic formats:

```text
ev:{case_ref}:selected
ev:{case_ref}:sender-history
ev:{case_ref}:amount-history
ev:{case_ref}:counterparty-history
ev:{case_ref}:region-history
ev:{case_ref}:currency:payment:{CURRENCY}
ev:{case_ref}:currency:receiving:{CURRENCY}
```

Currency must be exactly three uppercase ASCII letters in MCP/API parameter validation.

The model may reference only evidence IDs issued by successful tool calls in the current AI run, plus selected-transaction evidence seeded for that run.

The model does not invent `[E1]` labels. FastAPI assigns display labels after validation.

---

# 17. MODEL-FACING EVIDENCE PROJECTION

MCP projections contain:

- `status`;
- `evidence_id` when deterministic evidence exists;
- only the minimum typed facts needed by the model.

For all five tools:

- maximum transaction references returned to model: **0**;
- detailed transaction rows returned to model: **never**;
- model-controlled `limit`, `offset`, `page_size`, or `include_details`: **forbidden**;
- maximum serialized JSON result size: **4 KiB**.

If a result would exceed 4 KiB, return tool error `result_too_large`; do not truncate factual fields.

No detail-expansion MCP tool exists in MVP.

---

# 18. FASTAPI CONTRACTS

Base path: `/api`.

All timestamp strings use the canonical source timestamp representation. All monetary values are decimal strings.

## 18.1 Health

### Method/path

```text
GET /api/health
```

### Response 200

```text
status: "ok"
database: "ok"
```

This endpoint does not call AI.

### Error

If runtime DB cannot be opened/read at startup, application startup should fail rather than report false health.

---

## 18.2 List cases

### Method/path

```text
GET /api/cases
```

### Response 200

```text
cases: [
  {
    case_ref: string,
    display_name: string
  }
]
```

No AI call.

---

## 18.3 Load case workspace

### Method/path

```text
GET /api/cases/{case_ref}
```

### Response 200

`WorkspaceResponse` from section 14.8.

### Errors

```text
404 case_not_found
500 deterministic_error
```

Error envelope:

```text
error: {
  code: string,
  message: string
}
```

Do not expose stack traces or raw SQL.

---

## 18.4 Initial AI investigation

### Method/path

```text
POST /api/cases/{case_ref}/investigations
```

### Request

Empty JSON object or no body. Do not accept tool/result-limit controls from frontend.

### Response 200

```text
investigation_id: string
case_ref: string
parent_investigation_id: null
run_status:
  "success" |
  "partial" |
  "unavailable" |
  "model_error" |
  "tool_error" |
  "structured_output_invalid" |
  "evidence_validation_failed"
findings: list[RenderedFinding]
limits: list[string]
evidence: list[DisplayEvidence]
```

`RenderedFinding`:

```text
text: string
citations: [
  {
    label: "E1" | "E2" | ...,
    evidence_id: string
  }
]
```

`DisplayEvidence`:

```text
label: "E1" | "E2" | ...
evidence_id: string
evidence_type: string
ui_target: string
supporting_transaction_refs: list[string]
```

Only evidence referenced by rendered findings needs to be included in `evidence`.

On `model_error`, `tool_error`, `structured_output_invalid`, or `evidence_validation_failed`, return an empty `findings` list. Do not render partial generated prose after validation failure.

### Errors

```text
404 case_not_found
500 unhandled_server_error
```

Expected/handled AI failures should use the 200 response envelope with a non-success `run_status`, so the deterministic workspace stays intact.

---

## 18.5 One bounded follow-up

### Method/path

```text
POST /api/cases/{case_ref}/follow-up
```

### Request

```text
question: string, 1..500 characters after trimming
parent_investigation_id: string | null
```

### Response

Same investigation response shape as 18.4, except `parent_investigation_id` echoes the request value.

The backend does not load or replay a previous transcript.

### Errors

```text
400 invalid_question
404 case_not_found
500 unhandled_server_error
```

Frontend enforces one follow-up in the frozen workflow; backend does not need a persistent conversation/session store.

---

# 19. MCP TOOL CONTRACTS

The concrete MCP server is WP03. These contracts are frozen.

## 19.1 `get_sender_history`

Input:

```text
case_ref: string
```

Output:

```text
status: "ok" | "not_found" | "error"
evidence_id: string | null
prior_outgoing_count: integer | null
error_code: string | null
```

Zero history is `status="ok"`, count `0`.

---

## 19.2 `compare_amount_history`

Input:

```text
case_ref: string
```

Output:

```text
status: "ok" | "insufficient_history" | "not_found" | "error"
evidence_id: string | null
payment_currency: string | null
selected_amount: decimal string | null
sample_size: integer | null
history_quality: "insufficient" | "limited" | "sufficient" | null
historical_median: decimal string | null
empirical_percentile: decimal number | null
error_code: string | null
```

For `n < 5`, an evidence ID still exists and status is `insufficient_history`.

---

## 19.3 `get_counterparty_history`

Input:

```text
case_ref: string
```

Output:

```text
status: "ok" | "not_found" | "error"
evidence_id: string | null
seen_before: boolean | null
previous_interaction_count: integer | null
first_previous_timestamp: canonical timestamp | null
most_recent_previous_timestamp: canonical timestamp | null
error_code: string | null
```

Zero interactions is a valid `ok` result.

---

## 19.4 `get_region_history`

Input:

```text
case_ref: string
```

Output:

```text
status: "ok" | "not_found" | "error"
evidence_id: string | null
sender_region: integer | null
receiver_region: integer | null
region_relationship: "same_region" | "cross_region" | null
receiver_region_seen_before: boolean | null
previous_receiver_region_count: integer | null
error_code: string | null
```

If destination-region novelty is cut by Manager decision, this tool must be removed consistently from MCP, AI prompt, evals, and frontend references. Do not repurpose the tool.

---

## 19.5 `get_currency_history`

Input:

```text
case_ref: string
dimension: "payment" | "receiving"
currency: string matching [A-Z]{3}
```

Base population always remains prior outgoing transactions from the selected sender.

Output:

```text
status: "ok" | "not_found" | "error"
evidence_id: string | null
dimension: "payment" | "receiving" | null
currency: string | null
seen_before: boolean | null
previous_count: integer | null
first_previous_timestamp: canonical timestamp | null
most_recent_previous_timestamp: canonical timestamp | null
error_code: string | null
```

No incoming-account-history semantics are permitted.

---

# 20. AI STRUCTURED-OUTPUT CONTRACT

The model output is not the same as the HTTP response.

Model output:

```text
status: "success" | "partial" | "unavailable"
findings: list[Finding], max 4
limits: list[string], max 3
```

`Finding`:

```text
text: string
evidence_ids: list[string]
```

Rules:

- successful initial investigation: 2–4 findings;
- focused follow-up: 1–3 findings is acceptable;
- every material factual finding has at least one evidence ID;
- unavailable answer may contain zero findings;
- the model references application-issued evidence IDs, never `[E1]` strings;
- model must not state fraud/laundering/suspiciousness conclusions.

---

# 21. EVIDENCE VALIDATION

For one AI run:

```text
AVAILABLE_EVIDENCE =
  selected-transaction evidence
  + evidence IDs from successful MCP calls in that same run
```

Every `finding.evidence_ids` value must be a member of this set.

FastAPI/AI application logic must also re-resolve every referenced evidence ID through the deterministic domain and verify:

- same `case_ref`;
- correct evidence type;
- correct parameterization for currency evidence;
- evidence resolves successfully.

If any reference fails:

```text
run_status = evidence_validation_failed
findings = []
evidence = []
```

Reject the whole generated investigation. Do not repair or partially salvage it in MVP.

---

# 22. STATUS / ERROR VOCABULARY

Use these codes consistently where applicable.

## HTTP/application error codes

```text
case_not_found
invalid_question
deterministic_error
unhandled_server_error
```

## AI run statuses

```text
success
partial
unavailable
model_error
tool_error
structured_output_invalid
evidence_validation_failed
```

## MCP statuses

```text
ok
not_found
error
insufficient_history   # amount tool only
```

## MCP error codes

Use only when `status="error"`:

```text
invalid_case
invalid_input
domain_error
result_too_large
```

Do not leak raw exception messages or SQL in model-facing output.

---

# 23. ENVIRONMENT VARIABLES

## Required at data-preparation time

```text
TRANSXION_SOURCE_DIR
TRAILSIGHT_DB_PATH
```

`TRANSXION_SOURCE_DIR` points to the external TransXion repository root containing `data/tx.csv`, `data/person.csv`, and `data/merchant.csv`.

## Required at application runtime

```text
TRAILSIGHT_DB_PATH
```

## Required only for AI investigations/evals

```text
OPENAI_API_KEY
TRAILSIGHT_MODEL
TRAILSIGHT_PROMPT_VERSION
```

## Optional

```text
TRAILSIGHT_TRACE_PATH
TRAILSIGHT_STATIC_DIR
TRAILSIGHT_MODEL_INPUT_USD_PER_MILLION
TRAILSIGHT_MODEL_OUTPUT_USD_PER_MILLION
```

Defaults:

```text
TRAILSIGHT_TRACE_PATH=data/traces/investigations.jsonl
TRAILSIGHT_STATIC_DIR=frontend/dist
```

If model pricing variables are absent, record token usage and set approximate cost to null.

Do not add a model router or dynamic provider registry.

---

# 24. RUNTIME DUCKDB OWNERSHIP

WP01 creates the runtime DB.

WP02 domain repository opens it read-only.

WP03 accesses it only indirectly by importing WP02 domain/repository services.

WP04 never opens DuckDB.

WP05 never opens DuckDB.

WP06 mounts/points to it but does not change its schema.

Runtime application code must never mutate tables.

---

# 25. SHARED TEST EXPECTATIONS

Every work package must:

1. run its own focused tests;
2. not disable or delete previously passing tests;
3. use deterministic fixtures for normal software tests;
4. never require a live model for the full pytest suite;
5. keep live-AI smoke/evals opt-in when API credentials are required;
6. assert hidden-label exclusion at its boundary where applicable;
7. assert same-timestamp transactions are not history;
8. preserve Bank + Account identity;
9. preserve decimal strings across HTTP/MCP boundaries;
10. report exact commands and pass/fail counts to the Manager.

The production AI evidence validator must also be reused by AI evals; do not create a weaker eval-only validator.

---

# 26. EXPLICITLY FORBIDDEN CROSS-SECTION CHANGES

## Frontend

Must not:

- add/change FastAPI fields;
- compute median/percentile/history itself;
- derive Synthetic Region;
- call OpenAI or MCP directly;
- invent unsupported API data.

## MCP

Must not:

- query DuckDB directly with duplicated business calculations;
- calculate counts/median/percentile independently;
- return transaction-reference arrays;
- return detailed history rows;
- add arbitrary query/filter tools;
- add model-controlled limits.

## AI/Evals

Must not:

- query DuckDB;
- calculate factual statistics;
- receive `Is Laundering`;
- send full history into prompts;
- change MCP schemas;
- create persistent chat memory;
- automatically repair invalid evidence citations.

## Data

Must not:

- add product features;
- add risk/fraud labels to runtime;
- add future transactions to a case slice;
- expose unnecessary demographics;
- redefine history semantics.

## Backend/domain

Must not:

- call AI to calculate deterministic context;
- implement hidden-label-dependent behaviour;
- create second calculation paths for MCP.

## Integration

Must not:

- move business logic into Docker/startup scripts;
- change API/MCP contracts silently;
- change evidence semantics;
- replace the locked stack;
- add cloud infrastructure.

---

# 27. CONTROLLED CUT ORDER

Only the Manager may invoke these cuts, in this order:

1. destination-region novelty;
2. receiving-currency/pair novelty;
3. suggested-question chips;
4. evidence animation/polish;
5. extra table interactions;
6. eval scenarios 16–20.

Do not independently cut:

- deterministic source of truth;
- stable transaction IDs;
- hidden-label firewall;
- past-only history;
- core deterministic tests;
- MCP;
- bounded model-facing evidence;
- evidence validation;
- basic AI eval suite;
- abstention;
- basic telemetry;
- reproducible Docker run.

---

# 28. GLOBAL RETURN RULE

At the end of every Codex work package, return to the Manager:

1. files created;
2. files modified;
3. tests/commands run and results;
4. acceptance criteria status;
5. any contract mismatch/blocker;
6. any requested change outside this package's ownership;
7. explicit statement that no unapproved architecture/product change was made.

Do not proceed into another work package unless explicitly assigned.

---

# 29. DETERMINISTIC SERVICE METHOD CONTRACT

WP02 must expose class `InvestigationService` with these exact public methods:

```text
get_workspace(case_ref)
get_selected_transaction_evidence(case_ref)
get_sender_history_evidence(case_ref)
get_amount_history_evidence(case_ref)
get_counterparty_history_evidence(case_ref)
get_region_history_evidence(case_ref)
get_currency_history_evidence(case_ref, dimension, currency)
resolve_evidence(evidence_id)
```

WP03 calls the evidence methods; it does not duplicate calculations.

WP04 may call `get_selected_transaction_evidence` and `resolve_evidence` for AI seeding/validation; it does not query DuckDB directly.

These method names/semantics are frozen cross-package interfaces.

# 30. DETERMINISTIC SERVICE CONSTRUCTION + FASTAPI APPLICATION-STATE CONTRACT

WP02 owns one frozen deterministic construction function:

```text
create_investigation_service()
```

It must:

1. read the approved deterministic runtime configuration;
2. create the read-only `RuntimeRepository`;
3. create the `InvestigationService`;
4. return that service.

No other work package may duplicate this construction path.

WP02 `create_app()` must call `create_investigation_service()` rather than constructing the repository/service separately, then expose the returned exact service instance as:

```text
app.state.investigation_service
```

WP04 AI HTTP routes consume this exact instance through request application state. The standalone WP04 eval runner may import and call `create_investigation_service()` directly. WP04 must not open DuckDB directly, instantiate `RuntimeRepository` directly, duplicate deterministic runtime configuration, or construct an alternative deterministic service path.

# 31. OPTIONAL EVAL-ONLY JUDGE CONFIGURATION

WP04 may use this optional environment variable for semantic factual-support judging in evals only:

```text
TRAILSIGHT_EVAL_JUDGE_MODEL
```

If absent, it defaults to `TRAILSIGHT_MODEL`.

This does not create production model routing. The exact judge model must be stored in eval results whenever a judge is used.
