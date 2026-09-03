# TRAILSIGHT V2 — API AND MCP DESIGN

## 1. Principles

- FastAPI is the only browser-facing application API.
- React never calls DuckDB, MCP, or OpenAI directly.
- MCP is model-facing only.
- All factual work comes from the deterministic Investigation Domain.
- All list endpoints are server-paginated and bounded.
- No API/MCP interface exposes IBM ground truth or `Patterns.txt`.
- No generic SQL, table, graph traversal, account enumeration, or arbitrary database query interface exists.

Base prefix:

```text
/api/v2
```

## 2. Pagination contract

Use cursor/keyset pagination, not million-row browser offsets.

Common request parameters:

```text
limit: integer default 50, min 1, max 100
cursor: opaque string nullable
```

Common response:

```text
CursorPage[T]
  items: T[]
  next_cursor: string | null
  has_more: boolean
```

Cursor format is implementation-owned but must be opaque to frontend and deterministically encode the stable sort keys.

### Stable sorts

Transactions:

```text
transaction_timestamp DESC, transaction_ref DESC
```

Alerts:

```text
entry_cutoff DESC, alert_ref ASC
```

Accounts:

```text
band_order HIGH, MEDIUM, LOW, UNSCORED
network_pattern_score DESC NULLS LAST
account_ref ASC
```

## 3. Health

### GET `/api/v2/health`

Returns:

```text
status
runtime_db_ready
latest_snapshot_id
latest_snapshot_cutoff
ai_configured
product_version
```

Must not inspect or expose hidden truth.

## 4. Alerts API

### GET `/api/v2/alerts`

Query:

```text
cursor?
limit?
q?                        # alert_ref, account_ref, account_id, or bank_id prefix
review_status? = NOT_REVIEWED | IN_REVIEW | REVIEWED
bank_country?
```

`q` is bounded to 256 characters, trimmed, and treated as absent when blank/whitespace. Matching is deterministic prefix matching over `alert_ref`, canonical `account_ref`, `account_id`, and `bank_id`; it composes with review-status membership, Bank Country, and opaque cursor pagination.

Response items:

```text
alert_ref
account_ref
bank_id
account_id
bank_country
network_review_band = HIGH
entry_snapshot_id
entry_cutoff
primary_reason
relevant_recent_transaction_count
review_status
```

No raw score in the queue by default.

`relevant_recent_transaction_count` is frozen as the number of distinct transactions involving the alerted canonical account in:

```text
[alert.entry_cutoff - 24 hours, alert.entry_cutoff)
```

A transaction qualifies when the alerted `account_ref` is either sender or receiver. The left boundary is inclusive, `entry_cutoff` is exclusive, and a self-transfer is counted once.

### GET `/api/v2/alerts/{alert_ref}`

Returns the deterministic alert context, entry detector state, review status, and navigation references. There is no separate alert-detail screen requirement; frontend can use this to enter historical Account Detail.

### PATCH `/api/v2/alerts/{alert_ref}/review-status`

Request:

```text
review_status: NOT_REVIEWED | IN_REVIEW | REVIEWED
```

Response:

```text
alert_ref
review_status
updated_at
```

This writes only the small workflow-state store. It never mutates detector outputs.

Allowed V2 transitions are `NOT_REVIEWED -> IN_REVIEW -> REVIEWED`. `REVIEWED` is deliberately terminal because the V2 runtime state has no workflow event/audit history needed for safe reopening.

## 5. Transactions API

### GET `/api/v2/transactions`

Query:

```text
cursor?
limit?
q?                         # transaction ref, account ID, or bank ID search
priority?                  # HIGH | MEDIUM | LOW | UNSCORED
alert_involvement?         # true | false
date_from?                 # inclusive
date_to?                  # exclusive upper bound
currency?                  # matches payment OR receiving currency
payment_format?
sending_bank_country?
receiving_bank_country?
```

`q` is bounded text input, not raw SQL. Search semantics:

The analyst-facing date-only **To Date** control is inclusive. The frontend converts `YYYY-MM-DD` to the next day's `T00:00:00` exclusive `date_to` value, avoiding loss of transactions later on the selected day. An explicitly supplied timestamp remains the precise exclusive upper bound.

- transaction ref exact/prefix;
- account ID exact/prefix across sender/receiver;
- bank ID exact/prefix across sender/receiver.

Response item:

```text
transaction_ref
timestamp
sender {account_ref, bank_id, account_id, bank_country}
receiver {account_ref, bank_id, account_id, bank_country}
amount_paid
payment_currency
amount_received
receiving_currency
payment_format
aml_review_priority
related_alert
```

Amounts cross HTTP as decimal strings.

### GET `/api/v2/transactions/{transaction_ref}`

Returns the complete bounded Transaction Detail view model:

```text
review_state
transaction_facts
bank_country_route
sender_account_card
receiver_account_card
investigation_indicators
activity_context
local_network_summary
supporting_evidence_summary
```

Every bounded supporting transaction inside `supporting_evidence_summary` is display-ready and includes the authoritative sender/receiver identities and Bank Countries, AML Review Priority, related-alert reference, amounts/currencies, payment format, and cross-currency fact. Clients do not call full Transaction Detail once per supporting row.

`review_state` includes:

```text
aml_review_priority
sender_band
receiver_band
applicable_snapshot_id
detector_cutoff
derivation_text
```

The detail response may contain chart/network data needed immediately, but every array remains explicitly bounded.

## 6. Accounts API

### GET `/api/v2/accounts`

Query:

```text
cursor?
limit?
q?                 # account ID or bank ID
band?               # HIGH | MEDIUM | LOW | UNSCORED
bank_country?
alert_involvement?
```

List state uses the latest COMPLETE detector snapshot.

Response item:

```text
account_ref
bank_id
account_id
bank_country
network_review_band
network_pattern_score nullable
latest_snapshot_id
latest_detector_cutoff
incoming_count
outgoing_count
alert_involvement
```

Raw score may be omitted from default list rendering even if present in API; frontend follows UX contract.

### GET `/api/v2/accounts/{account_ref}`

Optional origin context:

```text
origin_alert_ref?
origin_transaction_ref?
```

At most one origin may be supplied.

The server derives context time/snapshot from the origin; clients may not supply arbitrary `as_of` timestamps.

Returns:

```text
account_identity
context
network_review_state
observed_activity
activity_over_time
currency_activity
bank_country_flows (bounded/optional)
alert_history (latest 100)
alert_history_total
alert_history_truncated
```

`bank_country_flows` contains all aggregated Bank-Country connections for the resolved account/context in deterministic total-activity/ISO order; it has no arbitrary top-12 limit. Each returned `alert_history` item includes current mutable `review_status`. If more than 100 alerts exist, `alert_history_total` reports the complete count and `alert_history_truncated=true`.

### GET `/api/v2/accounts/{account_ref}/transactions`

Query includes the same optional origin context plus:

```text
cursor
limit <= 100
direction? = INCOMING | OUTGOING | BOTH
currency?
counterparty_account_ref?
```

Every row satisfies the resolved context cutoff.

Response items use the display-ready transaction-list shape documented by `GET /api/v2/transactions`: transaction ref/timestamp, authoritative sender and receiver identities with Bank Countries, both amount/currency pairs, payment format, AML Review Priority, and related-alert reference. Account Detail must not hydrate these rows through per-row Transaction Detail requests.

### GET `/api/v2/accounts/{account_ref}/network`

Same origin context. Returns the deterministic bounded one-hop graph contract from `03_DOMAIN_AND_EVIDENCE.md`.

No `hops` parameter exists.

## 7. Evidence API

### GET `/api/v2/evidence/{evidence_id}`

Resolve application-owned evidence and return a display-safe projection:

```text
evidence_id
evidence_type
subject_type
subject_ref
context_time
snapshot_id
detector_cutoff
facts
ui_target
supporting_transaction_count
supporting_transactions[]    # bounded display rows, max 50
support_truncated
```

The endpoint does not accept arbitrary SQL/filter clauses. The `evidence_id` is a self-resolving `ev2.<payload>.<checksum>` token. The endpoint delegates to the deterministic Evidence V2 resolver: decode/verify integrity, resolve authoritative embedded context, recompute evidence, regenerate/verify identity, then return the display-safe projection. Malformed, unknown, cross-context, or future-context IDs fail closed.

## 8. AI Investigation API

### POST `/api/v2/investigations`

Request:

```text
subject_type: ALERT | TRANSACTION | ACCOUNT
subject_ref: string
origin_alert_ref: string | null
origin_transaction_ref: string | null
```

The server resolves authoritative context, validates AI configuration, allocates an `investigation_id`, and runs the initial investigation. It persists the minimal session mapping in `runtime_state.json` only after a valid response exists, so configuration/provider/infrastructure failure leaves no unreachable session. The persisted mapping contains only subject/origin/context identity, `follow_up_used`, and creation time; it contains no transcript, model reasoning, findings, AML disposition, or IBM hidden truth.

Before a generated response can be returned, a deterministic band-alignment guard checks it against the authoritative GARG band in the investigation packet. A response that weakens, contradicts, or recasts that band fails closed with `BAND_ALIGNMENT_FAILED` and is not shown.

Response:

```text
investigation_id
run_status
subject_type
subject_ref
context
summary
observations[]
patterns[]
limits[]
```

### POST `/api/v2/investigations/{investigation_id}/follow-up`

Request:

```text
question: string 1..500 characters
```

Exactly one successful follow-up is allowed per parent investigation. No transcript input.

Server looks up the persisted investigation entry in `runtime_state.json`, reloads the stored authoritative subject/context identity, revalidates that context through the deterministic domain, and atomically reserves the available slot in-process. A valid successful follow-up persists `follow_up_used=true`; configuration/provider/infrastructure failure releases the reservation and leaves the follow-up available. Concurrent requests cannot both succeed, and a request after successful consumption returns HTTP 409 `FOLLOW_UP_ALREADY_USED`. The model may re-call bounded tools; no previous transcript/model reasoning/full output is replayed.

## 9. Common API errors

Safe envelope:

```text
error:
  code
  message
  request_id nullable
```

HTTP mapping:

- 400 INVALID_INPUT / INVALID_CONTEXT;
- 404 NOT_FOUND;
- 409 REVIEW_STATE_CONFLICT or FOLLOW_UP_ALREADY_USED;
- 422 request-schema validation;
- 500 safe DATA_INTEGRITY_ERROR;
- 503 AI/MCP unavailable only for AI endpoints; deterministic endpoints remain available.

AI 503 responses include `BAND_ALIGNMENT_FAILED` when generated prose violates the mandatory GARG band interpretation.

No raw DuckDB/OpenAI/MCP exception bodies reach the browser.

## 10. One MCP server

Run one Python MCP server over **stdio** as a child of the AI investigation path.

The server imports/uses the V2 deterministic Investigation Domain factory/service. It never opens raw IBM files or implements parallel factual logic.

MCP run scope is bounded to the current investigation subject/context. The AI orchestration layer launches/configures the MCP child with the authoritative subject reference/context so a tool cannot silently jump to future state or enumerate unrelated accounts.

## 11. Final MCP tool set

V2 uses exactly **seven** tools.

### Tool 1 — `get_alert_context`

**Purpose:** Explain why a Network Pattern Alert exists.

Input:

```text
alert_ref: string
```

Validated: must equal the current investigation alert or an alert associated with the current root account/context.

Model-facing output, max 4 KiB:

```text
status
evidence_id
alert_ref
account_ref
entry_snapshot_id
entry_cutoff
network_review_band
network_pattern_score nullable
rank nullable
percentile nullable
reason = ENTERED_HIGH
review_status
```

No transaction rows/refs.

Errors: NOT_FOUND, INVALID_CONTEXT, DATA_INTEGRITY_ERROR.

### Tool 2 — `get_transaction_context`

**Purpose:** Explain transaction facts and AML Review Priority derivation.

Input:

```text
transaction_ref: string
```

The transaction must be the current investigation transaction or a transaction already authorized through bounded supporting evidence.

Output, max 4 KiB:

```text
status
evidence_ids[]   # transaction facts + transaction priority + bank-country route
transaction_ref
timestamp
sender/receiver canonical display refs
amount/currencies/payment format
cross_currency
sender_band
receiver_band
aml_review_priority
snapshot_id
detector_cutoff
derivation_text
sending_bank_country
receiving_bank_country
same_bank_country
```

No bulk history.

### Tool 3 — `get_account_context`

**Purpose:** Retrieve detector state and bounded observed activity for a root account at the authoritative context.

Input:

```text
account_ref: string
```

Allowed account must be the alert root, investigated account, or sender/receiver root of the current transaction.

Output, max 5 KiB:

```text
status
evidence_ids[]
account_ref
bank_id/account_id/bank_country
snapshot_id/detector_cutoff
network_review_band
network_pattern_score nullable
rank/percentile nullable
eligible_account_count
unscored_reason nullable
incoming_count
outgoing_count
distinct_counterparties
first_observed
most_recent_observed
```

### Tool 4 — `get_behavioral_indicators`

**Purpose:** Retrieve the deterministic V2 investigation indicators relevant to the current subject.

Input:

```text
account_ref: string | null
```

For a transaction investigation, null means return endpoint-specific indicators for the selected transaction. For account investigation, the root account is required/implicit.

Output, max 8 KiB:

```text
status
evidence_ids[]
amount_behavior nullable
counterparty_novelty nullable
velocity_1h
velocity_24h
fan_in_24h
fan_out_24h
cross_currency nullable
rapid_incoming_outgoing nullable  # only if retained
new_bank_country_route nullable   # only if retained
```

Each metric is already calculated by domain code. The model does not compute counts/percentiles.

### Tool 5 — `get_relationship_context`

**Purpose:** Answer whether/how a root account previously interacted with a specific direct counterparty.

Input:

```text
account_ref: string
counterparty_account_ref: string
```

Validation:

- account must be an authorized root account;
- counterparty must be the selected transaction endpoint or a direct relationship returned by the bounded network context;
- no arbitrary account graph traversal.

Output, max 4 KiB:

```text
status
evidence_id
seen_before
previous_interaction_count
root_to_counterparty_count
counterparty_to_root_count
first_previous_timestamp
most_recent_previous_timestamp
```

No transaction rows by default.

### Tool 6 — `get_network_context`

**Purpose:** Explain the account's bounded local network and persisted GARG structural support.

Input:

```text
account_ref: string
```

Output, max 12 KiB:

```text
status
evidence_ids[]
account_ref
snapshot_id
detector_cutoff
network_review_band
eligible_account_count
first_order_neighbor_count nullable
second_order_neighbor_count nullable
block_measure_support nullable
total_direct_counterparties
shown_counterparties <= 12 for model
truncated
relationships[]   # max 12 aggregate relationship summaries
```

The normal UI may show up to 24 nodes; the model receives at most 12 relationship summaries.

No multi-hop traversal.

### Tool 7 — `get_supporting_evidence`

**Purpose:** Return a few concrete transaction examples only for an evidence item already generated in the current investigation.

Input:

```text
evidence_id: string
```

No `limit` argument.

Output, max 12 KiB:

```text
status
evidence_id
supporting_transaction_count
transactions[]  # max 8
truncated
```

Each transaction summary contains only runtime-safe fields necessary to inspect the evidence.

The tool rejects:

- invented evidence IDs;
- evidence from another investigation subject/context;
- detector evidence with no transaction support;
- attempts to enumerate arbitrary history.

## 12. MCP global bounds

- Generic context tool result: ≤ 4–5 KiB.
- Behavioral indicator result: ≤ 8 KiB.
- Network/support tool result: ≤ 12 KiB.
- Model receives zero hidden labels/patterns.
- Default context tools return zero detailed transaction rows.
- Supporting evidence tool returns max 8 transaction summaries.
- No model-controlled `limit`, `offset`, `hops`, SQL, table name, or raw filter expression.
- On bound violation return `RESULT_TOO_LARGE`; do not silently dump or truncate core deterministic fields.

## 13. Evidence relationship

Every successful tool returns one or more application-issued Evidence V2 IDs.

Flow:

```text
Domain creates complete bounded EvidenceV2
        |
        +--> UI/backend evidence resolver
        |
        +--> MCP model-facing projection
                    |
                    v
                   LLM
```

The model cites only IDs returned in the current run. FastAPI re-resolves and validates them before rendering.

## 14. Prohibited interfaces

Do not create:

- `/query` or `/sql` REST endpoint;
- MCP SQL tool;
- MCP arbitrary account search/enumeration;
- model-controlled graph hop count;
- raw DuckDB table exposure;
- runtime ground-truth endpoint;
- pattern-label endpoint;
- whole-dataset export through API;
- AI endpoint that accepts arbitrary system prompts/tool lists.

## 15. API performance behavior

- List page max: 100.
- Network UI max: 25 nodes (root + 24 counterparties).
- Model network max: 12 relationships.
- Evidence UI supporting rows max: 50.
- MCP concrete transaction examples max: 8.
- Charts use aggregated/bounded series.

Server must return explicit `truncated`, `total_count`, or `has_more` fields where a bounded result could otherwise be mistaken for completeness.

## Integrated API / MCP / AI composition

The release-candidate integration seam is:

```text
create_app()
  -> calls create_investigation_service_v2()
  -> stores app.state.investigation_service
  -> creates/stores app.state.runtime_state_store
  -> dynamically registers trailsight_v2.ai.http when that module exists
```

AI HTTP handlers consume those `app.state` objects and do not construct repositories or services. `trailsight_v2.ai.http` exports the optional router registered by the application factory. This internal composition does not change any `/api/v2` endpoint or MCP contract in this document.
