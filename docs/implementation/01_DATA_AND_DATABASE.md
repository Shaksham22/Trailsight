# TRAILSIGHT — 01 DATA AND DATABASE

# ROLE

You are the **Data Preparation and Runtime Database Implementer** for Trailsight.

You are responsible only for converting the externally downloaded TransXion snapshot into the safe, bounded, read-only DuckDB runtime input required by the approved architecture.

# GOAL

Create a deterministic, reproducible preparation path:

```text
external TransXion repository
        |
        v
validate source + canonicalize transactions
        |
        v
create stable txref-v1 IDs
        |
        v
select approved cases
        |
        v
past-only case slices + minimal entity types
        |
        v
runtime DuckDB
```

Do not build backend/domain logic, MCP, AI, frontend, Docker, or product features.

# SOURCE OF TRUTH

Read before changing anything:

1. `docs/implementation/00_SHARED_CONTRACTS.md`
2. this file

The source data is external and already downloaded by the project owner using Git LFS.

Pinned project provenance for the approved snapshot:

```text
Repository: chaos-max/TransXion
Expected commit: 53932595c37c23b9f55ea5ddf5984e4d57b88369
Expected source files:
  data/tx.csv
  data/person.csv
  data/merchant.csv
```

Do not change to another dataset or another TransXion snapshot without Manager approval.

# DEPENDENCIES

This is the first implementation work package.

It depends only on:

- the shared contracts file;
- the locally downloaded TransXion repository;
- Python 3.12+.

WP02 depends on this package's runtime schema and generated database.

# FILE / DIRECTORY OWNERSHIP

## You own

Create and modify only:

```text
src/trailsight_data/
scripts/prepare_runtime_data.py
data/cases/
tests/data/
pyproject.toml
uv.lock
.gitignore
```

You may also create placeholder directories/files required to keep these generated directories in Git:

```text
data/runtime/
data/traces/
```

but do not commit generated source-derived runtime data or traces.

## You may read

```text
docs/implementation/*
<TRANSXION_SOURCE_DIR>/data/tx.csv
<TRANSXION_SOURCE_DIR>/data/person.csv
<TRANSXION_SOURCE_DIR>/data/merchant.csv
```

You may inspect the external TransXion Git metadata only to verify the expected source commit.

## You must not modify

```text
src/trailsight/
src/trailsight_mcp/
src/trailsight_ai/
prompts/
evals/
frontend/
Dockerfile
README.md
```

Do not edit raw TransXion files.

Before generating any runtime/source-derived artifact, create the initial root `.gitignore`. At minimum include:

```text
data/runtime/*
data/traces/*
eval_results/*
.env
__pycache__/
.pytest_cache/
frontend/node_modules/
frontend/dist/
```

If the repository uses placeholder files such as `.gitkeep` inside generated directories, add only the narrow negation rules needed to keep those placeholders tracked. Do not overbuild the ignore file.

The generated runtime DuckDB must not be committed. Raw TransXion source data must not be copied into or committed to Trailsight.

# INPUTS

Required environment/configuration:

```text
TRANSXION_SOURCE_DIR=<path to external TransXion repository root>
TRAILSIGHT_DB_PATH=<output DuckDB path>
```

Expected physical files under `TRANSXION_SOURCE_DIR`:

```text
data/tx.csv
data/person.csv
data/merchant.csv
```

TransXion profile headers expected by this plan:

```text
person.csv:
  person_id
  bank_account_number
  bank
  ...demographics not permitted at runtime

merchant.csv:
  merchant_id
  bank_account_number
  bank
  ...merchant metadata not permitted at runtime
```

Only `bank_account_number` and `bank` are required from profile files. Entity type comes from which profile file contains the account.

# REQUIRED IMPLEMENTATION

## 1. Create the shared Python project manifest

Create root `pyproject.toml` using Python 3.12+ and `src/` package discovery.

Declare only the approved Python capabilities listed in `00_SHARED_CONTRACTS.md`:

- duckdb;
- fastapi;
- uvicorn;
- pydantic;
- mcp;
- openai-agents;
- PyYAML;
- pytest;
- httpx.

Create `uv.lock` from that manifest.

Do not add pandas unless it is genuinely required by the preparation implementation. Prefer DuckDB/stdlib for this bounded preparation path. If pandas is added, report why.

Do not add any database server client or AI framework beyond the approved dependencies.

---

## 2. Create `src/trailsight_data/`

Create a small data-preparation package with separate responsibilities for:

- source validation;
- canonical transaction normalization;
- `txref-v1` generation;
- case selection/catalog handling;
- runtime DuckDB writing;
- validation/reporting.

Do not put backend/domain investigation calculations here.

The data package may calculate history characteristics only for selecting/validating fixtures and preparing permitted case slices. Those calculations are not the runtime domain API and must not later be imported by MCP/AI as business logic.

---

## 3. Validate the external TransXion source before reading data

Preparation must fail before writing the runtime DB if any required source condition fails.

Validate:

1. `TRANSXION_SOURCE_DIR` exists;
2. all three expected files exist;
3. `data/tx.csv` is real CSV content, not an unresolved Git LFS pointer;
4. repository commit equals the expected pinned commit if Git metadata is present;
5. transaction source contains the required logical fields;
6. `person.csv` contains `bank_account_number` and `bank`;
7. `merchant.csv` contains `bank_account_number` and `bank`.

Before processing any source data, obtain and report the actual external repository HEAD using the equivalent of:

```bash
git -C "$TRANSXION_SOURCE_DIR" rev-parse HEAD
```

Expected commit:

```text
53932595c37c23b9f55ea5ddf5984e4d57b88369
```

If the actual commit matches, continue.

If it does not match, **STOP AND REPORT THE SOURCE SNAPSHOT MISMATCH**. Do not automatically checkout another commit, silently accept the new HEAD, update the expected SHA, or redesign the preparation rules. The project owner/Manager decides whether to checkout the pinned commit or approve a new snapshot.

If Git metadata is unavailable, do not invent verification. Record provenance as unverified and fail unless the preparation CLI has an explicit **developer-only** `--allow-unverified-source` flag. Do not use that flag in acceptance testing.

Do not automatically download TransXion.

---

## 4. Validate the physical transaction CSV headers

For the pinned TransXion snapshot, `data/tx.csv` must contain these explicit source headers:

```text
Timestamp
From Bank
From Account
To Bank
To Account
Amount Received
Receiving Currency
Amount Paid
Payment Currency
Payment Format
Is Laundering
```

Before importing transaction rows, validate that every required header above exists. If any required header is missing, stop preparation and report the schema mismatch.

Use `From Account` and `To Account` by their explicit header names. Do not infer account direction from column position.

The runtime allowlist remains exactly as defined in `00_SHARED_CONTRACTS.md`.

---

## 5. Enforce an explicit transaction allowlist

The runtime transaction table may contain only:

```text
transaction_ref
canonical timestamp
from_bank
from_account
to_bank
to_account
amount_paid
payment_currency
amount_received
receiving_currency
payment_format
```

The preparation query/read path must explicitly select the permitted fields.

Do not use `SELECT *` against the raw source.

`Is Laundering` may be read only as part of source-header validation. Do not copy, hash, filter cases by, select cases by, persist, log, or expose its values.

Case selection must be independent of `Is Laundering`.

---

## 6. Implement `txref-v1` exactly

Create one canonicalization implementation and test it directly.

Follow `00_SHARED_CONTRACTS.md` section `txref-v1` exactly:

- fixed ten-field order;
- exact timestamp format `YYYY-MM-DDTHH:MM:SS.ffffff`;
- no timezone inference;
- Decimal-based amount normalization;
- Unicode NFC text normalization;
- surrounding ASCII whitespace trimmed;
- case preserved;
- compact ordered JSON array with `"txref-v1"` as first element;
- UTF-8 bytes;
- SHA-256;
- final format `tsx_<digest>`.

Do not use Python float when constructing the fingerprint.

Do not use CSV row number.

---

## 7. Detect duplicate/colliding references before completing preparation

Compute transaction references for the source transactions used in case selection/preparation.

Before writing a successful runtime database, verify that no two source transaction rows produce the same `transaction_ref`.

If duplicates exist:

1. stop preparation;
2. identify the duplicate `transaction_ref` values in a safe diagnostic;
3. do not append row numbers;
4. do not silently drop rows.

The runtime DB must never be emitted as "successful" after duplicate-reference detection.

---

## 8. Create the case catalog

Create:

```text
data/cases/cases.yaml
```

Each case entry must contain at least:

```text
case_ref
display_name
selected_transaction_ref
selection_kind
```

`selection_kind` is metadata such as:

```text
fixed_demo
insufficient_amount_history
limited_amount_history
repeat_counterparty
```

It is not a risk label.

### Required fixed primary case

Create:

```text
case_ref: demo-01
display_name: Demo 01
```

Locate the source row using the frozen transaction facts:

```text
Timestamp: 2025-05-08 16:18:46
From Account: A016568
To Account: A013644
Amount Paid: 69.54
Payment Currency: CNY
Amount Received: 9.40
Receiving Currency: USD
Payment Format: Cash
```

Do not assume From Bank or To Bank. Resolve them from the unique matching source row.

The locator must match exactly one source row. If zero or more than one match exists, fail preparation and report the mismatch.

### Required deterministic eval-support cases

Create at least these additional case fixtures so WP04 can build the 15 required eval scenarios without editing the case catalog:

```text
eval-amount-insufficient-01
  selected transaction has 0–4 strictly earlier same-payment-currency outgoing transactions

eval-amount-limited-01
  selected transaction has 5–19 strictly earlier same-payment-currency outgoing transactions

eval-repeat-counterparty-01
  selected sender has at least one strictly earlier outgoing transaction to the same (To Bank, To Account)
```

If a deterministic source scan cannot find a case satisfying one required category, fail and report the missing category; do not fake a transaction.

Use only permitted source fields and approved deterministic derivations when selecting these cases.

When several candidates satisfy a criterion, choose deterministically:

1. ascending selected timestamp;
2. then ascending `transaction_ref`.

This keeps preparation reproducible.

Do not create cases based on `Is Laundering`.

---

## 9. Build a union of past-only case slices

For every case:

1. load the selected transaction;
2. determine the selected sender using `(from_bank, from_account)`;
3. identify all source transactions with that same sender;
4. include only rows where `timestamp < selected_timestamp`;
5. associate the selected transaction with role `selected`;
6. associate strictly earlier rows with role `history`;
7. do not associate equal-timestamp rows as history;
8. do not associate later transactions.

The resulting runtime database may physically store a transaction once even if multiple cases can legitimately see it.

Case-specific access is controlled through the `case_transactions` table.

Example rule:

```text
one physical transaction row
can appear in:
  Case B history
but not:
  Case A history
if it is later than Case A's selected timestamp
```

---

## 10. Import only minimal entity data

Create runtime entity mappings from:

```text
person.csv  -> entity_type = "Person"
merchant.csv -> entity_type = "Merchant"
```

For both files import only:

```text
bank
bank_account_number -> account
entity_type
```

Do not import:

- person age;
- education;
- gender;
- marital status;
- occupation;
- merchant description;
- size/type metadata;
- capital;
- industry;
- operating status;
- establishment date;
- representative IDs;
- person IDs/merchant IDs unless needed temporarily to validate source uniqueness.

The runtime `entities` table must be keyed by canonical `(bank, account)`.

If the same `(bank, account)` appears in both Person and Merchant sources with conflicting entity types, fail preparation and report the conflict.

Only entities referenced by selected/runtime history transactions need to be retained in runtime DuckDB.

---

## 11. Synthetic Region handling

Do not persist geography names.

Synthetic Region is derived from the account's numeric suffix modulo 20.

WP01 must:

- validate the derivation works for every account included in runtime data;
- use the shared rule for fixture validation;
- not create country/city/corridor fields.

Do not make data preparation the sole implementation of the rule. WP02 must own the runtime domain function.

The runtime transaction/entity schema does not need to persist region if it can be cheaply derived; prefer not to persist it unless the Manager explicitly chooses materialization.

---

## 12. Create the runtime DuckDB schema

Create exactly these logical tables.

### `cases`

Required columns:

```text
case_ref TEXT PRIMARY KEY
display_name TEXT NOT NULL
selected_transaction_ref TEXT NOT NULL
```

### `transactions`

Required columns:

```text
transaction_ref TEXT PRIMARY KEY
timestamp TIMESTAMP NOT NULL
from_bank TEXT NOT NULL
from_account TEXT NOT NULL
to_bank TEXT NOT NULL
to_account TEXT NOT NULL
amount_paid DECIMAL NOT NULL
payment_currency TEXT NOT NULL
amount_received DECIMAL NOT NULL
receiving_currency TEXT NOT NULL
payment_format TEXT NOT NULL
```

Use an exact decimal type. Do not store amounts as floating point.

### `case_transactions`

Required columns:

```text
case_ref TEXT NOT NULL
transaction_ref TEXT NOT NULL
role TEXT NOT NULL
```

Allowed roles only:

```text
selected
history
```

Enforce uniqueness for `(case_ref, transaction_ref)`.

### `entities`

Required columns:

```text
bank TEXT NOT NULL
account TEXT NOT NULL
entity_type TEXT NOT NULL
```

Allowed entity types only:

```text
Person
Merchant
```

Enforce uniqueness for `(bank, account)`.

Do not add a laundering column or extra demographic columns.

---

## 13. Keep database organization simple

Do not introduce an external DB server.

DuckDB is the only runtime store.

Create indexes only if a measured preparation/runtime query materially benefits and DuckDB supports the chosen index use. Do not spend time adding indexes by résumé habit.

The expected runtime subset is small enough that good filtering and joins are sufficient.

---

## 14. Implement the preparation CLI

Create:

```text
scripts/prepare_runtime_data.py
```

Required CLI behavior:

```text
--source-root <path>
--case-catalog <path>       # default data/cases/cases.yaml
--output <path>
```

Optional developer-only:

```text
--allow-unverified-source
```

The CLI must:

1. validate source;
2. canonicalize required transactions;
3. resolve/create deterministic case catalog entries;
4. detect duplicate references;
5. build past-only case slices;
6. build minimal entity map;
7. write a new DuckDB atomically or to a temporary file then replace output;
8. run post-write validation;
9. print a concise preparation summary.

Do not leave a partially generated final DB after failure.

---

## 15. Post-write deterministic validation

Before reporting success, validate the generated DB:

### Schema firewall

- `Is Laundering` absent from every table/column;
- only approved entity columns exist.

### Case integrity

For every case:

- selected reference exists exactly once in `transactions`;
- exactly one `case_transactions` row has role `selected`;
- all role `history` rows are strictly earlier than selected timestamp;
- all role `history` rows have the same sender Bank + Account as selected;
- no equal/later transaction appears as history.

### Demo fixture

Validate source-derived deterministic values needed by the next package:

```text
selected From Account = A016568
selected To Account = A013644
amount_paid = 69.54
payment_currency = CNY
amount_received = 9.40
receiving_currency = USD
payment_format = Cash
```

Also verify the demo sender's permitted history count is 74 if the pinned source snapshot matches the approved dataset analysis. If not, fail and report the mismatch rather than changing the product fixture.

Do not calculate suspiciousness or use the hidden label for validation.

---

# REQUIRED TESTS

Create focused tests under:

```text
tests/data/
```

At minimum cover:

## Source validation

- missing source root;
- missing `tx.csv`;
- unresolved Git LFS pointer;
- unexpected source commit;
- missing required headers.

## Fingerprint

- known fixture has stable hash;
- fixed field order;
- timestamp canonicalization;
- `69.54`, `69.540`, `69.5400` canonicalize identically;
- text case preserved;
- leading/trailing ASCII whitespace normalized;
- Unicode NFC normalization;
- `Is Laundering` value cannot affect txref;
- duplicate txrefs fail.

## Past-only slicing

- earlier row included;
- same timestamp excluded;
- later row excluded;
- sender with same account number at different bank does not match;
- overlapping case histories do not leak future rows between cases.

## Entity import

- Person mapping;
- Merchant mapping;
- only `bank`, `account`, `entity_type` persisted;
- conflicting identity/type fails.

## Firewall

- runtime DB has no `Is Laundering` column;
- runtime DB has no prohibited profile columns.

## Runtime schema

- required tables/columns exist;
- roles constrained to selected/history;
- one selected row per case;
- amounts stored with exact decimal semantics.

# DO NOT CHANGE

Do not:

- build FastAPI endpoints;
- build runtime investigation functions;
- create MCP tools;
- call any LLM;
- add eval logic;
- add frontend code;
- Dockerize the application;
- use `Is Laundering` for case selection;
- create a second dataset;
- persist future sender transactions for a case;
- import profile demographics;
- change `txref-v1`;
- change the locked runtime schema without Manager approval.

# ACCEPTANCE CRITERIA

This package is complete only when all are true:

1. `pyproject.toml` and `uv.lock` exist with the approved Python stack.
2. `scripts/prepare_runtime_data.py` can build a runtime DB from the external pinned TransXion source.
3. `demo-01` resolves uniquely from frozen facts.
4. at least the three required eval-support case fixtures exist.
5. all transaction references use `txref-v1` exactly.
6. duplicate/collision handling fails loudly.
7. every case slice contains selected + strictly earlier sender outgoing transactions only.
8. overlapping cases are isolated through `case_transactions`.
9. only minimal entity identity/type data is stored.
10. `Is Laundering` is absent from the runtime DB.
11. all focused tests pass.
12. no files outside this package's ownership were modified.

# COMMANDS TO RUN

Use the project environment and report exact output/counts.

```text
uv sync
uv run pytest tests/data -q
```

Then run the real preparation against the externally downloaded source:

```text
uv run python scripts/prepare_runtime_data.py \
  --source-root "$TRANSXION_SOURCE_DIR" \
  --case-catalog data/cases/cases.yaml \
  --output "$TRAILSIGHT_DB_PATH"
```

Then rerun the data tests against/including the generated runtime DB if the tests support an integration marker/path:

```text
uv run pytest tests/data -q
```

Do not run AI/API/frontend tests in this package.

# RETURN WITH

Return to the Manager:

1. exact files created/modified;
2. resolved source commit and verification status;
3. generated case catalog entries and selected transaction refs;
4. runtime DB path and table row counts;
5. confirmation that all case history slices are strictly past-only;
6. confirmation that `Is Laundering` and profile demographics are absent;
7. `txref-v1` duplicate/collision validation result;
8. commands run and pytest pass/fail counts;
9. any discrepancy in the primary demo fixture;
10. any requested change owned by another package;
11. explicit statement: **No product/architecture redesign was made.**
