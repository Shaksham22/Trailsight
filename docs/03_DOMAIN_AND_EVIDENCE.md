# TRAILSIGHT V2 — DOMAIN AND EVIDENCE DESIGN

## 1. Domain principle

The deterministic Investigation Domain is the sole source of authoritative runtime facts.

It owns:

- subject/context resolution;
- historical cutoffs;
- amount comparisons;
- relationship history;
- velocity;
- fan-in/fan-out;
- cross-currency;
- account activity summaries;
- bounded account neighborhoods;
- bank-country context;
- detector-state/priority explanation retrieval;
- supporting transaction selection;
- Evidence V2 creation and resolution.

FastAPI and MCP both call this layer. React and the LLM never reimplement these calculations.

## 2. Core domain entities

### Account

Canonical identity:

```text
source_dataset
bank_id
account_id
account_ref
bank_country
```

No customer name, person/company type, residence, nationality, KYC, or source-of-funds fields exist in the V2 runtime domain.

### Transaction

```text
transaction_ref
transaction_timestamp
from_account_ref
from_bank_id
to_account_ref
to_bank_id
amount_paid
payment_currency
amount_received
receiving_currency
payment_format
cross_currency
```

### DetectorSnapshot

```text
snapshot_id
source_dataset
cutoff_timestamp
algorithm/config provenance
processing status
```

### AccountDetectorState

```text
snapshot_id
account_ref
scoring_eligible
network_pattern_score nullable
rank nullable
percentile nullable
network_review_band
unscored_reason nullable
```

### TransactionReviewState

```text
transaction_ref
snapshot_id nullable
detector_cutoff nullable
sender_band
receiver_band
aml_review_priority
derivation_code
derivation_text
```

### NetworkPatternAlert

```text
alert_ref
account_ref
entry_snapshot_id
entry_cutoff
reason_code
```

Human review progress is joined from writable operational state:

```text
NOT_REVIEWED | IN_REVIEW | REVIEWED
```

Alert-list `relevant_recent_transaction_count` is a deterministic domain fact:

```text
count DISTINCT transaction_ref
where (from_account_ref = alert.account_ref OR to_account_ref = alert.account_ref)
and transaction_timestamp >= alert.entry_cutoff - 24 hours
and transaction_timestamp <  alert.entry_cutoff
```

The account match uses canonical account identity. The left boundary is inclusive and `entry_cutoff` is exclusive. A self-transfer involving the alerted account is one transaction and is counted once. Transactions at or after `entry_cutoff` are never included.

## 3. Investigation context

Every detail/evidence request resolves an immutable context object. Its canonical identity is:

```text
ContextIdentityV2
  context_kind: ALERT_ENTRY | TRANSACTION | SNAPSHOT
  context_ref            # alert_ref | transaction_ref | snapshot_id, according to kind
  context_time
  snapshot_id nullable
```

`ContextIdentityV2` is application-owned. Clients/models never supply a free-form timestamp as authority. The domain validates that:

- `ALERT_ENTRY` resolves to that alert's immutable entry snapshot/cutoff;
- `TRANSACTION` resolves to that transaction's timestamp and persisted applicable snapshot;
- `SNAPSHOT` resolves to an existing COMPLETE detector snapshot and its cutoff.

The full runtime context is:

```text
InvestigationContext
  subject_type: ALERT | TRANSACTION | ACCOUNT
  subject_ref
  context_identity: ContextIdentityV2
  context_time
  detector_snapshot_id nullable
  detector_cutoff nullable
  root_account_refs[]
  selected_transaction_ref nullable
  alert_ref nullable
```

### Alert context

```text
context_time = alert.entry_snapshot.cutoff
snapshot_id = alert.entry_snapshot_id
root account = alert.account_ref
```

### Transaction context

```text
context_time = selected transaction timestamp
snapshot_id = persisted transaction_review_state.snapshot_id
root accounts = sender + receiver
selected transaction = transaction_ref
```

### Direct account context

Use latest COMPLETE snapshot:

```text
context_time = latest_complete_snapshot.cutoff
snapshot_id = latest_complete_snapshot.snapshot_id
root account = account_ref
```

### Account opened from alert/transaction

The API passes the originating context token/subject reference; the domain derives the historical cutoff. Do not allow a browser/model to supply an arbitrary future timestamp as factual authority.

## 4. Historical semantics

For ordinary historical facts at context time `T`:

```text
historical transaction timestamp < T
```

Equal timestamps are excluded from one another's history.

The selected transaction may be displayed/highlighted alongside historical context, but it is never used in statistics that claim to describe prior behavior.

Detector facts use the persisted detector snapshot cutoff, which may be earlier than `T`.

## 5. Account observed-activity summary

At a context cutoff return deterministic:

- incoming transaction count;
- outgoing transaction count;
- distinct counterparties across either direction;
- first observed timestamp;
- most recent observed timestamp before cutoff;
- incoming distinct counterparties;
- outgoing distinct counterparties.

For direct latest account browsing, a precomputed latest summary may be used if its cutoff exactly matches the requested context. Historical contexts use deterministic queries, not latest/future aggregates.

## 6. Amount behavior

V2 is two-sided rather than V1 sender-only.

For a selected transaction at `T`, calculate two independent contexts when data permits.

### Sender-paid context

Population:

```text
from_account_ref = selected sender
transaction_timestamp < T
payment_currency = selected.payment_currency
```

Compare `selected.amount_paid`.

### Receiver-received context

Population:

```text
to_account_ref = selected receiver
transaction_timestamp < T
receiving_currency = selected.receiving_currency
```

Compare `selected.amount_received`.

Do not mix currencies or incoming/outgoing roles.

History-quality policy reuses the proven deterministic V1 thresholds:

```text
n < 5      -> INSUFFICIENT: sample size only, no median/percentile
5 <= n <20 -> LIMITED: sample size + median, no percentile
n >= 20    -> SUFFICIENT: sample size + median + empirical percentile
```

Empirical percentile:

```text
100 * count(previous_amount <= selected_amount) / n
```

This is context, not a suspiciousness threshold.

## 7. Counterparty relationship / novelty

For selected endpoint accounts A and B at context time `T`, prior relationship history includes any transaction where:

```text
(A -> B OR B -> A)
AND transaction_timestamp < T
```

Return:

- `seen_before`;
- total previous interaction count;
- A→B count;
- B→A count;
- first prior timestamp;
- most recent prior timestamp.

`new_counterparty = not seen_before`.

Do not call a new counterparty suspicious.

## 8. Recent transaction velocity

Fixed V2 windows:

```text
1 hour before context_time
24 hours before context_time
```

For each root account return separately:

- incoming count;
- outgoing count;
- total count.

The selected transaction at exactly `T` is excluded from prior velocity.

No fixed count threshold turns this into a risk flag. The UI can display “X transactions in prior 1h/24h.”

## 9. Fan-in / fan-out

Use the same prior 24-hour window for the selected transaction/account context:

- `fan_in_24h` = distinct sender accounts that sent to the account;
- `fan_out_24h` = distinct receiver accounts the account sent to.

Also provide cumulative distinct counterparties where already available from account activity.

These are deterministic observed network/activity facts, separate from GARG's Network Pattern Score.

## 10. Cross-currency

Selected transaction:

```text
cross_currency = payment_currency != receiving_currency
currency_pair = payment_currency + " -> " + receiving_currency
```

No FX-rate/spread/fee inference.

## 11. Secondary indicators

Implement only if the Manager retains them after core requirements pass.

### Rapid incoming → outgoing

For a selected account/outgoing transaction, find the most recent prior incoming transaction within 60 minutes. Return elapsed time and transaction ref if one exists. Do not attempt amount matching or label “layering.”

### New bank-country route

For an account and selected counterparty bank country, determine whether any strictly earlier transaction involving that account had a counterparty bank assigned to the same country. Explicitly label this **bank-country history**.

## 12. Local account network

One-hop only.

At context time `T`, relationships are built from transactions `< T`, plus the selected transaction relationship may be included only as an explicitly current/highlighted relation when the context is a transaction.

### Deterministic bound

Return at most:

```text
24 counterparty nodes + 1 selected root node
```

For a two-root transaction context, the service may return up to 24 unique counterparties around the selected endpoint being viewed; the transaction detail should not merge two unbounded ego graphs.

### Ranking/truncation

1. Reserve the selected/relevant transaction counterparty if one exists.
2. Rank remaining direct counterparties by:
   - total historical transaction count DESC;
   - most recent historical timestamp DESC;
   - `counterparty_account_ref` ASC.
3. Fill remaining slots to 24.

Return:

```text
total_direct_counterparties
shown_counterparties
truncated
selection_rule_version = ego-one-hop-v1
```

Each relationship summary contains only bounded aggregate facts:

- counterparty ref/bank/country;
- incoming count;
- outgoing count;
- total count;
- first/last historical timestamps;
- selected relationship flag.

No arbitrary multi-hop expansion API exists.

## 13. Activity-over-time data

For transaction detail, return bounded daily/interval buckets around the selected account/context rather than raw millions of points.

Recommended transaction-context chart:

- prior 30 days if data exists, ending at selected timestamp;
- bucket by simulation day;
- separate series by currency rather than summing unlike currencies;
- selected transaction marker.

For account detail:

- full available context range through `context_time`;
- daily buckets;
- display counts plus currency-selectable amount series.

If the simulation period is shorter, return the available range.

## 14. Bank-country context

Transaction route facts:

- sending bank ID/country/coordinates;
- receiving bank ID/country/coordinates;
- `same_bank_country` boolean;
- bank-country mapping version.

No customer-location fields exist.

Account bank-country flow summary, if retained:

- counterparty bank country;
- incoming transaction count;
- outgoing transaction count;
- distinct counterparties;
- latest interaction.

Bound to top 12 countries by total transaction count with deterministic tie-break by ISO code.

## 15. Supporting transactions

Evidence can be supported by very large populations. Do not store/load every ref in an Evidence object.

Internal evidence metadata contains:

```text
supporting_transaction_count
supporting_transaction_refs[]   # deterministic bounded sample/max 50
support_truncated
support_selection_rule
```

Default support selection:

- for relationship evidence: most recent relevant transactions, max 50;
- amount evidence: values nearest in time plus boundary/context rows as needed, max 50;
- velocity/fan evidence: most recent relevant rows, max 50;
- detector evidence: no fabricated transaction list; use structural facts and separately resolved local-network evidence.

Model-facing supporting evidence is stricter and defined in the MCP contract.

## 16. Evidence V2 envelope

Every evidence item is created by deterministic application code.

```text
EvidenceV2
  evidence_id
  evidence_version = evidence-v2
  evidence_type
  subject_type
  subject_ref
  context_identity: ContextIdentityV2
  context_time
  snapshot_id nullable
  detector_cutoff nullable
  facts                  # typed payload by evidence_type
  supporting_transaction_count
  supporting_transaction_refs[]  # bounded application/UI support
  support_truncated
  ui_target
```

Evidence types:

```text
ALERT_CONTEXT
DETECTOR_STATE
TRANSACTION_FACTS
TRANSACTION_PRIORITY
ACCOUNT_ACTIVITY
AMOUNT_BEHAVIOR
COUNTERPARTY_RELATIONSHIP
NETWORK_BEHAVIOR
CURRENCY_BEHAVIOR
BANK_COUNTRY_ROUTE
SUPPORTING_TRANSACTIONS
```

## 17. Evidence IDs

Evidence IDs are deterministic, application-owned, self-describing/self-resolving, URL-safe, and integrity-checkable. No evidence database is required.

### Canonical identity payload

The deterministic evidence function first constructs this bounded canonical object:

```text
{
  "v": "evidence-v2",
  "evidence_type": <frozen EvidenceType>,
  "subject_type": "ALERT" | "TRANSACTION" | "ACCOUNT",
  "subject_ref": <canonical application reference>,
  "context": {
    "kind": "ALERT_ENTRY" | "TRANSACTION" | "SNAPSHOT",
    "ref": <alert_ref | transaction_ref | snapshot_id>,
    "time": <canonical context timestamp>,
    "snapshot_id": <snapshot_id | null>
  },
  "parameters": <evidence-type-specific normalized object>
}
```

`parameters` contains only values that change the deterministic evidence query/meaning, for example amount side, currency, velocity window, relationship counterparty, or requested supporting-evidence subtype. It must not contain prose, UI labels, model text, hidden truth, or unbounded lists.

Normalization rules:

- object keys sorted lexicographically;
- compact canonical JSON, UTF-8, no optional whitespace;
- strings NFC-normalized; source bank/account IDs are already canonical and are not re-normalized;
- timestamps use the canonical domain timestamp representation;
- decimals use plain canonical decimal strings;
- booleans/null/integers use JSON native forms;
- parameter arrays, if an evidence type explicitly requires one, are deterministically ordered by that evidence type contract.

### URL-safe ID format

Let `payload_bytes` be the canonical JSON bytes. Create:

```text
payload = base64url(payload_bytes) without '=' padding
checksum = base64url(SHA256(payload_bytes)) without '=' padding

evidence_id = "ev2." + payload + "." + checksum
```

Use the full SHA-256 digest in the checksum segment. The checksum is an integrity check, not an authorization mechanism; authoritative context/scope validation remains mandatory. Reject canonical identity payloads above 1024 bytes and evidence IDs above 2048 characters.

### Resolver contract

`resolve_evidence(evidence_id)` must:

1. split/parse the `ev2.<payload>.<checksum>` format and enforce size limits;
2. base64url-decode the payload/checksum and verify the full SHA-256 checksum;
3. parse the canonical JSON, validate version/enums/required fields, and verify re-serialization produces the exact same canonical bytes;
4. resolve and validate the embedded `ContextIdentityV2` against authoritative alert/transaction/snapshot state;
5. verify the subject and normalized parameters are allowed in that authoritative context;
6. recompute the deterministic evidence through the normal domain function;
7. regenerate its evidence ID from the recomputed identity and require an exact match;
8. reject malformed, unknown-subject, unknown-context, cross-context, future-context, parameter-invalid, or identity-mismatch IDs.

The LLM never mints evidence IDs. During AI output validation, a syntactically valid self-resolving ID is still rejected unless it was seed evidence or was returned by a successful MCP tool in that same investigation run.

## 18. UI target vocabulary

Frozen targets:

```text
alert-context
review-priority
transaction-facts
bank-country-route
sender-account
receiver-account
account-review
investigation-indicators
activity-context
account-network
counterparty-table
currency-activity
alert-history
supporting-evidence
```

Frontend maps these to actual components; AI never decides DOM selectors.

## 19. Domain service responsibilities

Expose one `InvestigationServiceV2` facade (exact code location decided by implementation chat after ZIP inspection) with logical methods equivalent to:

```text
resolve_context(subject_type, subject_ref, origin_ref?)
get_alert_context(alert_ref)
get_transaction_detail(transaction_ref)
get_account_detail(account_ref, origin_ref?)
list_account_transactions(account_ref, context, cursor, filters)
get_account_network(account_ref, context)
get_behavioral_indicators(subject_type, subject_ref, context)
get_relationship_context(account_ref, counterparty_ref, context)
get_supporting_evidence(evidence_id)
resolve_evidence(evidence_id)
```

List/search pagination belongs to repository/application services but factual derivations remain inside deterministic code.

MCP calls this facade; it does not implement its own SQL/statistics.

## 20. Error and insufficient-context semantics

Use machine-stable status/error concepts:

```text
NOT_FOUND
INVALID_INPUT
INVALID_CONTEXT
INSUFFICIENT_HISTORY
INSUFFICIENT_NETWORK_CONTEXT
DATA_INTEGRITY_ERROR
RESULT_TOO_LARGE
```

Insufficient history is generally a valid evidence state, not infrastructure failure.

Examples:

- amount history n=3 -> evidence exists with quality `INSUFFICIENT`;
- account has no valid GARG state -> `UNSCORED` / Insufficient Network Context;
- malformed/checksum-invalid evidence ID -> INVALID_INPUT;
- well-formed ID whose subject/context no longer resolves -> NOT_FOUND/INVALID_CONTEXT;
- cross-context/future-context evidence ID -> INVALID_CONTEXT;
- historical origin points after allowed subject -> INVALID_CONTEXT.

Do not expose raw SQL, filesystem, stack traces, or hidden truth in public errors.

## 21. Historical integrity assertions

Every domain test must prove:

- no transaction at exactly the selected timestamp becomes prior history;
- no transaction after the context appears;
- account detail opened from historical transaction/alert differs appropriately from latest direct browse;
- detector state always matches the subject's persisted applicable snapshot;
- selected/current transaction inclusion is explicitly marked rather than silently folded into history.
