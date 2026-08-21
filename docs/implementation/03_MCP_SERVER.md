# TRAILSIGHT — 03 MCP SERVER

# ROLE

You are the **Trailsight MCP Adapter Implementer**.

# GOAL

Implement one local Python stdio MCP server that exposes exactly five bounded model-facing capabilities over the already-complete deterministic `InvestigationService`.

MCP is an adapter.

It does **not** own factual calculations.

# SOURCE OF TRUTH

Read before changing anything:

1. `docs/implementation/00_SHARED_CONTRACTS.md`
2. `docs/implementation/02_BACKEND_AND_DOMAIN.md`
3. this file

If a required `InvestigationService` method is missing or behaves differently from the shared contract, stop and report a WP02 contract failure. Do not reimplement the calculation in MCP.

# DEPENDENCIES

Requires WP02 complete and passing.

Required imports from WP02:

```text
trailsight.config
trailsight.data.runtime_repository.RuntimeRepository
trailsight.domain.service.InvestigationService
trailsight.contracts shared enums/types as needed
```

Exact domain methods consumed:

```text
get_sender_history_evidence(case_ref)
get_amount_history_evidence(case_ref)
get_counterparty_history_evidence(case_ref)
get_region_history_evidence(case_ref)
get_currency_history_evidence(case_ref, dimension, currency)
```

WP04 AI depends on this MCP server and its exact five tool contracts.

# FILE / DIRECTORY OWNERSHIP

## You own

```text
src/trailsight_mcp/
tests/mcp/
```

Recommended structure:

```text
src/trailsight_mcp/
├── __init__.py
├── contracts.py
└── server.py
```

Do not create another process/service directory.

## You may read

```text
src/trailsight/
data/runtime/
docs/implementation/
tests/backend/
```

## You must not modify

```text
src/trailsight/
src/trailsight_data/
src/trailsight_ai/
frontend/
prompts/
evals/
pyproject.toml
uv.lock
Dockerfile
README.md
```

# INPUTS

Runtime environment:

```text
TRAILSIGHT_DB_PATH=<prepared runtime DuckDB>
```

No API key is needed by the MCP server.

The server must never read:

```text
OPENAI_API_KEY
```

MCP does not call the model.

# REQUIRED IMPLEMENTATION

## 1. Create one stdio MCP server entrypoint

Create:

```text
src/trailsight_mcp/server.py
```

It must be runnable as:

```text
python -m trailsight_mcp.server
```

Use the official Python MCP SDK and stdio transport.

Do not open a TCP port.

Do not add HTTP MCP transport.

Do not add authentication, service discovery, or remote hosting.

---

## 2. Initialize the existing deterministic runtime only

On server startup:

1. read `TRAILSIGHT_DB_PATH` through the existing deterministic configuration boundary;
2. create the existing read-only `RuntimeRepository`;
3. create one `InvestigationService`;
4. register the approved tools.

Do not execute SQL directly from MCP tool functions.

Do not copy queries from `RuntimeRepository`.

Do not create a second database connection abstraction with business logic.

---

## 3. Create model-facing MCP contracts

Create:

```text
src/trailsight_mcp/contracts.py
```

Use typed/Pydantic-compatible structures for tool inputs and outputs.

The models must match `00_SHARED_CONTRACTS.md` exactly.

Every response must contain only approved summary fields.

Global rules for all tools:

```text
maximum transaction refs returned to model = 0
detailed transaction rows returned = never
serialized JSON response <= 4096 bytes
model-controlled limits = none
```

Do not add:

```text
limit
offset
page_size
include_details
include_transactions
raw_rows
sql
account_id override
```

---

# 4. TOOL 1 — `get_sender_history`

## Product question

> How much previous outgoing activity does this sender have?

## Exact domain method

```text
InvestigationService.get_sender_history_evidence(case_ref)
```

## Exact input schema

```text
case_ref: string
```

No other field.

## Exact model-facing output

```text
status: "ok" | "not_found" | "error"
evidence_id: string | null
prior_outgoing_count: integer | null
error_code: string | null
```

## Projection rule

From the internal `SenderHistoryEvidence`, expose only:

```text
evidence_id
prior_outgoing_count
```

Never expose:

```text
supporting_transaction_refs
raw historical rows
```

## Evidence ID

Use the evidence ID returned by the domain object.

Expected format:

```text
ev:{case_ref}:sender-history
```

MCP must not construct a different ID.

## Maximum result size

- transaction refs: 0;
- detailed rows: never;
- hard JSON ceiling: 4 KiB.

## Failure states

Case not found:

```text
status = not_found
evidence_id = null
```

Domain/runtime failure:

```text
status = error
error_code = domain_error
```

Zero prior history is valid:

```text
status = ok
prior_outgoing_count = 0
```

## Example useful analyst question

> How much history does this sender have?

## Example where this tool should NOT be called

> Has this sender used this counterparty before?

---

# 5. TOOL 2 — `compare_amount_history`

## Product question

> How does this payment amount compare with earlier outgoing transactions in the same Payment Currency?

## Exact domain method

```text
InvestigationService.get_amount_history_evidence(case_ref)
```

## Exact input

```text
case_ref: string
```

The model must not supply an amount or currency override.

## Exact model-facing output

```text
status:
  "ok" |
  "insufficient_history" |
  "not_found" |
  "error"
evidence_id: string | null
payment_currency: string | null
selected_amount: decimal string | null
sample_size: integer | null
history_quality: "insufficient" | "limited" | "sufficient" | null
historical_median: decimal string | null
empirical_percentile: decimal number | null
error_code: string | null
```

## Projection rule

Expose deterministic aggregate facts only.

Do not expose the same-currency supporting-reference set.

## Evidence ID

Use domain-returned:

```text
ev:{case_ref}:amount-history
```

For fewer than 5 previous same-currency rows, the evidence ID still exists.

## Maximum result size

- transaction refs: 0;
- rows: never;
- hard JSON ceiling: 4 KiB.

## Insufficient-history behavior

If domain evidence has:

```text
history_quality = insufficient
```

return:

```text
status = insufficient_history
sample_size = n
historical_median = null
empirical_percentile = null
```

Do not convert this into a tool error.

## Example useful analyst question

> How does this amount compare with earlier CNY payments?

## Example where this tool should NOT be called

> Is the current counterparty new?

---

# 6. TOOL 3 — `get_counterparty_history`

## Product question

> Has the selected sender previously sent to the selected counterparty?

## Exact domain method

```text
InvestigationService.get_counterparty_history_evidence(case_ref)
```

## Exact input

```text
case_ref: string
```

The model cannot pass another account/counterparty.

## Exact model-facing output

```text
status: "ok" | "not_found" | "error"
evidence_id: string | null
seen_before: boolean | null
previous_interaction_count: integer | null
first_previous_timestamp: canonical timestamp | null
most_recent_previous_timestamp: canonical timestamp | null
error_code: string | null
```

## Projection rule

Expose counts/first/latest only.

Do not expose matching transaction references or rows.

## Evidence ID

Domain-returned:

```text
ev:{case_ref}:counterparty-history
```

## Maximum result size

- transaction refs: 0;
- rows: never;
- hard JSON ceiling: 4 KiB.

## Failure behavior

Zero previous interactions:

```text
status = ok
seen_before = false
previous_interaction_count = 0
```

This is evidence, not an error.

## Example useful analyst question

> Has this sender used this counterparty before?

## Example where this tool should NOT be called

> How high is 69.54 CNY relative to previous CNY payments?

---

# 7. TOOL 4 — `get_region_history`

## Product question

> What is the current source-derived Synthetic Region relationship, and has this destination Synthetic Region appeared in this sender's prior outgoing history?

## Exact domain method

```text
InvestigationService.get_region_history_evidence(case_ref)
```

## Exact input

```text
case_ref: string
```

## Exact model-facing output

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

## Projection rule

Do not expose prior transactions to the same region.

## Evidence ID

Domain-returned:

```text
ev:{case_ref}:region-history
```

## Maximum result size

- transaction refs: 0;
- rows: never;
- hard JSON ceiling: 4 KiB.

## Failure behavior

If domain cannot derive an account suffix:

```text
status = error
error_code = domain_error
```

Do not invent a region.

## Example useful analyst question

> Has this sender previously sent to Synthetic Region 4?

## Example where this tool should NOT be called

> Has this sender paid in EUR before?

## Controlled cut

If the Manager has explicitly invoked the approved first scope cut, remove this tool entirely and report that Manager decision. Do not repurpose it as a generic region tool.

---

# 8. TOOL 5 — `get_currency_history`

## Product question

> In the selected sender's prior outgoing transactions, has a specified currency appeared on the payment or receiving side?

## Exact domain method

```text
InvestigationService.get_currency_history_evidence(case_ref, dimension, currency)
```

## Exact input

```text
case_ref: string
dimension: "payment" | "receiving"
currency: string matching [A-Z]{3}
```

No `flow` field.

No incoming-history field.

## Exact semantics

Base population is always previous outgoing transactions from the selected sender.

For:

```text
dimension = payment
```

use prior outgoing `Payment Currency`.

For:

```text
dimension = receiving
```

use prior outgoing `Receiving Currency`.

Do not query transactions where the selected sender is the recipient.

## Exact model-facing output

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

## Evidence ID

Use domain-returned:

```text
ev:{case_ref}:currency:{dimension}:{currency}
```

## Maximum result size

- transaction refs: 0;
- detailed rows: never;
- hard JSON ceiling: 4 KiB.

No detail-expansion request exists.

## Example useful analyst question

> Has this sender previously made an outgoing transaction where the receiving currency was USD?

or:

> Has this sender paid in EUR before?

## Example where this tool should NOT be called

> Has this account received USD from other senders before?

That question is outside the approved outgoing-history scope.

---

# 9. Result-size enforcement

For every tool:

1. construct the typed projection;
2. serialize the model-facing result to JSON bytes;
3. measure byte length;
4. if `> 4096`, do not send a partial/truncated result;
5. return a bounded error result:

```text
status = error
error_code = result_too_large
```

The limit is fixed in server code/configuration and is not a tool input.

Do not include internal evidence in error diagnostics.

---

# 10. Error mapping

Map known deterministic errors consistently.

### Missing case

```text
status = not_found
evidence_id = null
```

### Invalid tool input

The MCP schema should reject it before the domain call where possible.

If represented as a result:

```text
status = error
error_code = invalid_input
```

### Domain/data integrity error

```text
status = error
error_code = domain_error
```

Do not return raw stack traces, SQL, or DuckDB error text to the model.

Server-side stderr logging may retain a concise developer error message, but not hidden/source-only data.

---

# 11. No hidden-label path

The MCP package must have no import, model, string field, or tool output related to:

```text
Is Laundering
```

MCP operates on the prepared runtime DB only through the deterministic domain.

Do not open the raw source repository.

---

# REQUIRED TESTS

Create tests only under:

```text
tests/mcp/
```

Do not use a live LLM.

## 1. Tool registration

Verify the server exposes exactly the approved five tools unless the Manager has explicitly applied the region cut.

Verify no generic SQL/history/account tool exists.

## 2. Input schema tests

Verify:

- valid case_ref accepted;
- currency dimension only payment/receiving;
- currency must match `[A-Z]{3}`;
- no arbitrary limit/detail fields accepted.

## 3. Domain == MCP factual projection

For each tool:

1. call the corresponding `InvestigationService` method directly;
2. call the MCP tool adapter for the same inputs;
3. compare all model-facing factual fields with the domain evidence facts;
4. verify the evidence ID is identical.

Required invariant:

```text
domain factual result == MCP projection factual result
```

MCP may omit internal fields; it may not change factual values.

## 4. No supporting references

For each successful tool response assert:

```text
supporting_transaction_refs is absent
transaction_refs is absent
rows is absent
```

and no source transaction list is nested anywhere in the output.

## 5. Result-size bound

Assert every normal fixture response is `< 4096` bytes.

Test the result-size guard path deterministically with a deliberately oversized test projection/fixture without modifying the domain contract.

Expected result:

```text
status = error
error_code = result_too_large
```

## 6. Error mapping

Test:

- missing case -> not_found;
- invalid input -> validation/invalid_input;
- domain error -> bounded `domain_error`;
- no raw exception text leaks.

## 7. Amount thresholds

Verify MCP reflects:

- insufficient history;
- limited history;
- sufficient history;
- no percentile for limited;
- no median/percentile for insufficient.

## 8. Outgoing-only currency semantics

Use a fixture containing incoming transactions to the selected sender and prove they do not affect `get_currency_history`.

## 9. Hidden-label absence

Search serialized successful/error MCP outputs for forbidden field names and assert absent.

## 10. Real stdio protocol smoke

Add one focused integration-style pytest that launches:

```text
python -m trailsight_mcp.server
```

through the MCP client/stdio mechanism, lists tools, and successfully calls one tool against a deterministic test DB.

Do not rely only on calling Python functions in-process.

# DO NOT CHANGE

Do not:

- implement calculations in MCP;
- modify `InvestigationService`;
- modify DuckDB schema;
- query DuckDB directly from tools;
- expose transaction refs/rows;
- add a sixth evidence-detail tool;
- add raw account search;
- add SQL;
- add HTTP MCP transport;
- add incoming account history;
- add model calls;
- implement AI prompts/evals;
- modify dependencies;
- change evidence IDs;
- add retries.

# ACCEPTANCE CRITERIA

This package is complete only when:

1. `python -m trailsight_mcp.server` starts one stdio MCP server.
2. exactly five approved tools are exposed unless a Manager-approved cut applies.
3. every tool delegates to the exact approved `InvestigationService` method.
4. no historical calculation is duplicated in MCP.
5. all model-facing outputs match the exact schemas.
6. successful tool outputs expose zero transaction references and zero detailed rows.
7. every serialized result is bounded to <=4 KiB or fails with `result_too_large`.
8. currency history is prior outgoing activity only.
9. evidence IDs come directly from domain evidence.
10. hidden labels/raw source are inaccessible.
11. domain-versus-MCP equality tests pass for all tools.
12. real stdio smoke test passes.
13. no files outside WP03 ownership were modified.

# COMMANDS TO RUN

```text
uv sync
uv run pytest tests/mcp -q
```

Then regression:

```text
uv run pytest tests/backend tests/mcp -q
```

Run the real stdio smoke through the test suite; do not leave a manually started MCP process waiting for stdin as the only verification.

# RETURN WITH

Return to the Manager:

1. files created/modified;
2. exact registered tool names;
3. table mapping each MCP tool to its imported `InvestigationService` method;
4. maximum serialized response size observed for each test fixture;
5. confirmation that transaction refs/rows are absent from every model-facing result;
6. confirmation of outgoing-only currency behavior;
7. pytest commands and pass/fail counts;
8. real stdio smoke result;
9. any WP02 contract mismatch;
10. any requested change outside WP03 ownership;
11. explicit statement: **No product/architecture redesign was made.**
