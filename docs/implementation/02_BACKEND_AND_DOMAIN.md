# TRAILSIGHT — 02 BACKEND AND DOMAIN

# ROLE

You are the **Deterministic Domain and FastAPI Core Implementer** for Trailsight.

# GOAL

Build the single factual source of truth for Trailsight and expose the deterministic workspace through FastAPI.

This work package owns **all runtime factual calculations**.

MCP and AI must consume this logic; they must not recreate it.

# SOURCE OF TRUTH

Read before changing anything:

1. `docs/implementation/00_SHARED_CONTRACTS.md`
2. `docs/implementation/01_DATA_AND_DATABASE.md`
3. this file

Do not reinterpret data semantics from the source CSV. Use the prepared DuckDB contract from WP01.

# DEPENDENCIES

This package starts after WP01 has:

- created `pyproject.toml` and `uv.lock`;
- generated a valid runtime DuckDB;
- created `data/cases/cases.yaml`;
- passed `tests/data/`.

WP03 MCP depends on the exact deterministic service methods defined here.

WP05 frontend may proceed in parallel from `00_SHARED_CONTRACTS.md`; it must not require backend redesign.

# FILE / DIRECTORY OWNERSHIP

## You own

```text
src/trailsight/
tests/backend/
```

Recommended internal structure:

```text
src/trailsight/
├── __init__.py
├── config.py
├── contracts.py
├── errors.py
├── data/
│   ├── __init__.py
│   └── runtime_repository.py
├── domain/
│   ├── __init__.py
│   ├── service.py
│   ├── evidence.py
│   ├── amount.py
│   ├── currency.py
│   └── synthetic_region.py
└── api/
    ├── __init__.py
    └── app.py
```

Use fewer files if that remains clear. Do not create a service per calculation.

## You may read

```text
src/trailsight_data/
data/cases/
data/runtime/
tests/data/
docs/implementation/
```

## You must not modify

```text
src/trailsight_data/
scripts/prepare_runtime_data.py
data/cases/
pyproject.toml
uv.lock
src/trailsight_mcp/
src/trailsight_ai/
prompts/
evals/
frontend/
Dockerfile
README.md
```

If the runtime schema does not match `00_SHARED_CONTRACTS.md`, stop and report a WP01 contract failure. Do not patch the data package from this session.

# INPUTS

Required runtime environment:

```text
TRAILSIGHT_DB_PATH=<prepared DuckDB path>
```

Optional static-frontend path reserved for integration:

```text
TRAILSIGHT_STATIC_DIR=frontend/dist
```

Input database must contain:

```text
cases
transactions
case_transactions
entities
```

with the exact logical schema from WP01/shared contracts.

# REQUIRED IMPLEMENTATION

## 1. Create shared contracts as concrete Pydantic models

Create `src/trailsight/contracts.py`.

Implement the shared schema shapes from `00_SHARED_CONTRACTS.md` without adding product fields.

At minimum define models/enums for:

```text
EntityRef
SelectedTransaction
SenderHistoryContext
AmountHistoryContext
CounterpartyHistoryContext
RegionHistoryContext
HistoricalTransactionRow
WorkspaceResponse
ApplicationError
RenderedCitation
RenderedFinding
DisplayEvidence
InvestigationResponse
FollowUpRequest
```

Also define internal model-friendly enums/types needed by WP03/WP04, including:

```text
HistoryQuality = insufficient | limited | sufficient
CurrencyDimension = payment | receiving
EvidenceType
UITarget
```

Monetary amounts crossing the package boundary must serialize as canonical decimal strings.

Do not create risk-score or laundering-label fields.

---

## 2. Create the runtime configuration boundary

Create a small configuration loader in `src/trailsight/config.py`.

It must read:

```text
TRAILSIGHT_DB_PATH
```

and optionally:

```text
TRAILSIGHT_STATIC_DIR
```

Do not load `OPENAI_API_KEY` or model configuration in the deterministic domain package. WP04 owns AI configuration.

If `TRAILSIGHT_DB_PATH` is missing for a running application, fail startup with a clear configuration error.

---

## 3. Implement one read-only DuckDB repository

Create `RuntimeRepository` in:

```text
src/trailsight/data/runtime_repository.py
```

Responsibilities:

- open the configured DuckDB in read-only mode;
- validate required runtime tables/columns;
- validate forbidden column `Is Laundering` is absent;
- fetch case metadata;
- fetch selected transaction;
- fetch case-permitted historical transactions;
- fetch minimal entity type mappings.

Do not put median/percentile/counterparty novelty calculations in this repository.

The repository retrieves deterministic rows. The domain service interprets them.

Do not write to DuckDB.

Do not create tables at runtime.

Do not update traces in DuckDB.

### Required repository filtering

Whenever retrieving history for a case, require both:

```text
case_transactions.case_ref = requested case
case_transactions.role = history
```

and ensure the returned rows belong to the selected sender.

The domain must still independently check `timestamp < selected_timestamp` before accepting rows as history.

---

## 4. Implement canonical Synthetic Region derivation

Create exactly one runtime function for Synthetic Region.

Input:

```text
account: string
```

Output:

```text
integer 0..19
```

Rule:

```text
numeric suffix(account) % 20
```

Examples required by tests:

```text
A016568 -> 8
A013644 -> 4
```

Malformed/no numeric suffix must raise a deterministic domain error.

React and MCP must import/consume results; they must not reimplement this rule.

---

## 5. Implement exact decimal handling

Read DuckDB DECIMAL amounts into Python `Decimal` or an exact equivalent.

Do not convert source monetary values to binary float for domain calculations.

Expose amount values to HTTP/MCP as normalized decimal strings.

Percentile may be a numeric decimal/float representation at the API presentation boundary, but its numerator/denominator and comparisons must be deterministic.

---

## 6. Implement the single deterministic service

Create:

```text
src/trailsight/domain/service.py
```

Expose class:

```text
InvestigationService
```

It is initialized with one `RuntimeRepository`.

The following method names and semantics are cross-package contracts and must not be renamed without Manager approval:

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

WP03 must call these methods. WP04 may use `get_selected_transaction_evidence` and `resolve_evidence` but must not calculate facts itself.

---

## 7. Implement selected transaction construction

For the selected transaction:

1. retrieve its row;
2. resolve sender entity type from `(from_bank, from_account)`;
3. resolve counterparty entity type from `(to_bank, to_account)`;
4. derive sender/receiver Synthetic Regions;
5. compute `cross_currency` as `payment_currency != receiving_currency`;
6. format `currency_pair` as `<payment> → <receiving>`;
7. compute `region_relationship` as `same_region` or `cross_region`.

Do not calculate FX rates, fees, expected receive amount, risk, or suspiciousness.

If an entity type cannot be resolved for a runtime transaction, raise a deterministic data-integrity error. Do not guess Person/Merchant.

---

## 8. Enforce history again at runtime

For every historical calculation, begin from the case-permitted history returned by `RuntimeRepository`, then reject any row that does not satisfy:

```text
row.from_bank == selected.from_bank
row.from_account == selected.from_account
row.timestamp < selected.timestamp
```

Equal timestamp is excluded.

If the prepared DB contains an invalid row, fail the deterministic operation rather than silently treating future/equal rows as history.

This is an intentional second defence after WP01's past-only preparation.

---

## 9. Implement `get_sender_history_evidence`

Return internal evidence with:

```text
evidence_id = ev:{case_ref}:sender-history
evidence_type = sender_history
case_ref
facts.prior_outgoing_count
supporting_transaction_refs = every permitted strictly earlier outgoing transaction ref
ui_target = sender_history
```

The count is the length of the validated historical outgoing population.

Zero is valid evidence.

---

## 10. Implement `get_amount_history_evidence`

Start from validated historical outgoing rows.

Filter to:

```text
row.payment_currency == selected.payment_currency
```

Use selected `amount_paid` as the comparison amount.

### n < 5

Return:

```text
history_quality = insufficient
sample_size = n
historical_median = null
empirical_percentile = null
```

### 5 <= n < 20

Return:

```text
history_quality = limited
sample_size = n
historical_median = exact deterministic median
empirical_percentile = null
```

### n >= 20

Return:

```text
history_quality = sufficient
sample_size = n
historical_median = exact deterministic median
empirical_percentile = 100 * count(previous_amount <= selected_amount) / n
```

Do not use P95.

Do not compare Amount Received.

Do not mix Payment Currency values.

Internal evidence:

```text
evidence_id = ev:{case_ref}:amount-history
supporting_transaction_refs = all same-payment-currency historical refs
ui_target = amount_context
```

For `n < 5`, evidence still exists and supporting refs may contain the 0–4 eligible rows.

---

## 11. Implement `get_counterparty_history_evidence`

Counterparty identity is:

```text
(selected.to_bank, selected.to_account)
```

Filter validated historical outgoing rows where both recipient fields match.

Return facts:

```text
seen_before
previous_interaction_count
first_previous_timestamp
most_recent_previous_timestamp
```

For zero matches:

```text
seen_before = false
previous_interaction_count = 0
first_previous_timestamp = null
most_recent_previous_timestamp = null
```

Internal evidence:

```text
evidence_id = ev:{case_ref}:counterparty-history
supporting_transaction_refs = all matching previous refs
ui_target = counterparty_history
```

---

## 12. Implement `get_region_history_evidence`

Derive sender and current receiver regions from the selected transaction.

For every validated prior outgoing transaction, derive the previous recipient's Synthetic Region from `to_account`.

Return:

```text
sender_region
receiver_region
region_relationship
receiver_region_seen_before
previous_receiver_region_count
```

`previous_receiver_region_count` is the number of validated prior outgoing transactions whose derived recipient region equals the selected receiver region.

Internal evidence:

```text
evidence_id = ev:{case_ref}:region-history
supporting_transaction_refs = only previous transactions whose receiver region equals the selected receiver region
ui_target = synthetic_region_history
```

If `receiver_region_seen_before=false`, supporting refs are empty. The negative finding remains deterministic aggregate evidence.

If the Manager has invoked the approved destination-region-novelty cut, do not implement this historical capability. Preserve only selected-transaction sender/receiver region and same/cross-region facts. Report the Manager decision explicitly.

---

## 13. Implement `get_currency_history_evidence`

Signature:

```text
get_currency_history_evidence(case_ref, dimension, currency)
```

Validate:

```text
dimension in {payment, receiving}
currency matches [A-Z]{3}
```

Base population is **always validated previous outgoing transactions from selected sender**.

### payment dimension

Filter:

```text
row.payment_currency == currency
```

### receiving dimension

Filter:

```text
row.receiving_currency == currency
```

Never switch to incoming transactions where selected sender is recipient.

Return:

```text
dimension
currency
seen_before
previous_count
first_previous_timestamp
most_recent_previous_timestamp
```

Internal evidence ID:

```text
ev:{case_ref}:currency:{dimension}:{currency}
```

Internal supporting refs are all matching previous outgoing rows.

`ui_target = historical_evidence`.

---

## 14. Implement selected-transaction evidence

`get_selected_transaction_evidence(case_ref)` must return application-owned evidence:

```text
evidence_id = ev:{case_ref}:selected
evidence_type = selected_transaction
facts = approved selected transaction facts
supporting_transaction_refs = [selected_transaction_ref]
ui_target = selected_transaction
```

This evidence is seeded into every AI run without an MCP call.

---

## 15. Implement `resolve_evidence`

`resolve_evidence(evidence_id)` is used after AI generation to materialize application-owned evidence for validation/UI.

Supported formats are only the evidence ID rules in `00_SHARED_CONTRACTS.md`.

Required behavior:

1. parse the ID deterministically;
2. reject unknown evidence types;
3. recover `case_ref` and allowed parameters;
4. call the corresponding deterministic evidence method;
5. verify returned evidence ID exactly matches requested ID;
6. return complete internal evidence.

For currency evidence, validate the exact dimension/currency encoded in the evidence ID.

Do not look up evidence from AI-generated storage.

Do not accept arbitrary database IDs.

---

## 16. Implement `get_workspace`

`get_workspace(case_ref)` assembles the complete non-AI screen.

It must use the same deterministic evidence functions, not parallel duplicate calculations.

Return `WorkspaceResponse` with:

- case metadata;
- selected transaction;
- sender-history context derived from sender evidence;
- amount-history context derived from amount evidence;
- counterparty-history context derived from counterparty evidence;
- region-history context if retained;
- all permitted historical transaction rows for the visible evidence table.

Historical table ordering must be deterministic:

1. timestamp descending;
2. `transaction_ref` ascending as tiebreaker.

The table contains only case-permitted strictly earlier outgoing rows.

---

## 17. Create the deterministic FastAPI app shell

Create:

```text
src/trailsight/api/app.py
```

Expose:

```text
create_investigation_service()
create_app()
```

`create_investigation_service()` is the single WP02-owned deterministic construction path. It must:

1. read the approved deterministic runtime configuration;
2. create one read-only `RuntimeRepository`;
3. create one `InvestigationService`;
4. return that service.

`create_app()` must call `create_investigation_service()` rather than duplicating repository/service construction, then store the returned service at:

```text
app.state.investigation_service
```

At startup/service construction, fail if:

- DB path missing;
- DB unreadable;
- required schema missing;
- forbidden `Is Laundering` column exists.

---

## 18. Implement deterministic HTTP routes

Implement exactly:

```text
GET /api/health
GET /api/cases
GET /api/cases/{case_ref}
```

Follow exact request/response/error contracts in `00_SHARED_CONTRACTS.md`.

Do not add query parameters that change history rules.

Do not expose raw SQL or internal exception details.

---

## 19. Reserve the AI route integration point without implementing AI

WP04 owns AI behaviour and the investigation/follow-up router.

`create_app()` must support registering the approved AI router from `trailsight_ai` once that package exists, without requiring WP04 to edit deterministic domain files.

Required behavior:

- deterministic routes work when `trailsight_ai` has not yet been implemented;
- after `trailsight_ai` exists, its router can provide exactly:
  - `POST /api/cases/{case_ref}/investigations`
  - `POST /api/cases/{case_ref}/follow-up`;
- do not create placeholder fake AI responses;
- do not duplicate those endpoints in WP02.

Use a narrow optional/lazy registration boundary. Do not swallow arbitrary import/runtime errors after the AI package exists.

---

## 20. Reserve static frontend serving without requiring frontend build

The final approved deployment serves the Vite production build through FastAPI.

WP02 should provide a narrow static-serving capability based on:

```text
TRAILSIGHT_STATIC_DIR
```

Requirements:

- API routes under `/api` always take precedence;
- if the configured static directory does not exist during backend development, deterministic API startup must still work;
- do not build frontend assets here;
- do not modify `frontend/`.

WP06 will verify final integration.

# REQUIRED TESTS

Create tests only under:

```text
tests/backend/
```

Use small deterministic DuckDB fixtures. Do not require the full source dataset for every unit test.

## 1. Runtime repository/read-only

Test:

- valid schema opens;
- missing DB fails;
- missing table fails;
- forbidden `Is Laundering` column fails;
- no runtime write path exists;
- case history retrieval is constrained through `case_transactions`.

## 2. Account identity

Test same account string at different banks is not same sender/counterparty.

## 3. Historical ordering

Test:

- earlier included;
- equal timestamp rejected;
- later rejected;
- invalid prepared history causes domain failure.

## 4. Amount thresholds

Test exactly:

```text
n=0
n=4
n=5
n=19
n=20
```

Verify:

- no median when n<5;
- median at n>=5;
- no percentile until n>=20;
- empirical percentile formula;
- odd/even median;
- Decimal semantics;
- same Payment Currency only.

## 5. Counterparty

Test:

- zero previous;
- one previous;
- multiple;
- first/latest timestamps;
- Bank + Account equality.

## 6. Currency

Test:

- payment dimension;
- receiving dimension;
- both operate only on selected sender outgoing history;
- incoming transfers to selected sender are not included;
- invalid dimension/currency rejected.

## 7. Synthetic Region

Test:

```text
A016568 -> 8
A013644 -> 4
```

and malformed accounts.

## 8. Region history

If retained, test:

- same-region selected transaction;
- cross-region selected transaction;
- destination region seen;
- destination region unseen;
- supporting refs contain only prior transactions to same derived region.

## 9. Evidence

Test:

- deterministic evidence IDs;
- selected evidence;
- complete internal supporting refs;
- `resolve_evidence` for each evidence type;
- wrong/unknown evidence ID rejected;
- currency parameterization cannot resolve to a different currency/dimension.

## 10. Workspace

Test:

- workspace values come from evidence methods;
- historical rows strictly past-only;
- deterministic sort order;
- all monetary HTTP values serialize as strings;
- no hidden label/profile demographics.

## 11. FastAPI

Test:

```text
GET /api/health
GET /api/cases
GET /api/cases/{valid}
GET /api/cases/{missing}
```

Verify exact shared-contract shapes and error envelopes.

## 12. Primary demo integration test

Against the real WP01 runtime DB, verify approved facts:

```text
selected timestamp = 2025-05-08 16:18:46
sender account = A016568
counterparty account = A013644
69.54 CNY -> 9.40 USD
Cash
sender Synthetic Region = 8
receiver Synthetic Region = 4
cross_currency = true
cross_region = true
prior sender outgoing count = 74
prior CNY count = 70
median ~= 15.095
empirical percentile ~= 95.71
prior current-counterparty interactions = 0
```

If destination-region novelty is retained, verify Region 4 previously unseen.

Do not assert suspiciousness.

# DO NOT CHANGE

Do not:

- modify data preparation/schema;
- modify `txref-v1`;
- use the raw TransXion CSV;
- open DuckDB writable;
- implement MCP;
- implement AI/model calls;
- create prompt files;
- implement evals;
- change HTTP contracts;
- add incoming-account investigation;
- calculate risk/suspiciousness;
- use `Is Laundering`;
- add a second persistence layer;
- add caching infrastructure;
- add retries;
- add frontend code.

# ACCEPTANCE CRITERIA

This package is complete only when:

1. `RuntimeRepository` opens the prepared DB read-only and validates the firewall.
2. `InvestigationService` exposes every frozen method name.
3. all factual calculations are implemented only in this deterministic package.
4. runtime history rejects equal/later timestamps even if malformed DB data exists.
5. all amount thresholds and empirical percentile rules match the contract.
6. counterparty identity uses Bank + Account.
7. currency history remains prior outgoing sender activity only.
8. Synthetic Region is implemented exactly once in runtime domain logic.
9. complete internal evidence objects contain supporting transaction refs.
10. `resolve_evidence` deterministically regenerates valid evidence.
11. `get_workspace` provides the complete non-AI UI payload.
12. deterministic FastAPI routes match the shared contract.
13. deterministic API works without AI credentials/package availability.
14. all backend tests pass.
15. no files outside WP02 ownership were modified.

# COMMANDS TO RUN

```text
uv sync
uv run pytest tests/backend -q
```

Then run data + backend regression tests:

```text
uv run pytest tests/data tests/backend -q
```

Run the API locally against the prepared runtime DB:

```text
TRAILSIGHT_DB_PATH="$TRAILSIGHT_DB_PATH" \
uv run uvicorn trailsight.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Smoke:

```text
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/cases
GET http://127.0.0.1:8000/api/cases/demo-01
```

Do not call AI endpoints in this work package.

# RETURN WITH

Return to the Manager:

1. files created/modified;
2. exact `InvestigationService` public method list;
3. read-only DB validation result;
4. primary demo deterministic result summary;
5. pytest commands and counts;
6. explicit confirmation that equal timestamps are excluded;
7. explicit confirmation that MCP/AI calculations were not implemented here;
8. any WP01 contract mismatch;
9. any requested change outside WP02 ownership;
10. explicit statement: **No product/architecture redesign was made.**

## Cross-package deterministic service factory and FastAPI exposure

The frozen WP02 construction function is:

```text
create_investigation_service()
```

FastAPI and the approved standalone eval runner share this one deterministic construction path.

`create_app()` must call the factory and store the returned exact service instance under:

```text
app.state.investigation_service
```

WP04 HTTP routes retrieve this service from request application state. The WP04 standalone eval runner may import `create_investigation_service()` directly. WP04 must not instantiate `RuntimeRepository`, open DuckDB directly, duplicate deterministic runtime configuration, or create an alternative `InvestigationService` construction path.
