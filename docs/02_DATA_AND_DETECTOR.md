# TRAILSIGHT V2 — DATA AND DETECTOR DESIGN

## 1. Scope

This design covers:

- IBM AMLworld HI-Small ingestion;
- canonical runtime-safe schema;
- stable identity/reference generation;
- deterministic Bank Country enrichment;
- GARG-AML integration and point-in-time snapshot computation;
- persisted account detector state;
- Network Review Bands;
- transaction priority;
- Network Pattern Alerts;
- GARG parity/performance validation;
- isolated offline benchmark evaluation;
- the hard ground-truth firewall.

No runtime request performs heavy detector computation.

## 2. Source and runtime separation

Use three logically separate data zones.

### External source zone

Contains the user's externally obtained IBM AMLworld HI-Small files. It is never committed to Trailsight.

Expected transaction semantics are the IBM fields:

```text
Timestamp
From Bank
Account          # sender account in source file
To Bank
Account.1        # receiver account when parser disambiguates the second Account header
Amount Received
Receiving Currency
Amount Paid
Payment Currency
Payment Format
Is Laundering    # OFFLINE ONLY
```

The ingestion package must inspect and validate the actual source header before mapping; do not invent additional IBM fields.

### Frozen source-ID normalization

Read `From Bank`, `Account`, `To Bank`, and `Account.1` as **strings directly from the source CSV**. Do not allow CSV type inference to turn bank/account identifiers into integers. For all four identifier columns apply exactly:

1. Unicode NFC normalization;
2. remove leading/trailing ASCII whitespace only;
3. preserve case;
4. preserve punctuation and internal whitespace;
5. preserve leading zeroes;
6. reject missing or empty-after-trim values.

Map the normalized values as:

```text
From Bank -> from_bank_id
Account   -> from_account_id
To Bank   -> to_bank_id
Account.1 -> to_account_id
```

This representation is authoritative everywhere: canonical account tuples, `account_ref`, `transaction_ref`, Bank Country hashing, detector edge/node construction, API search fields, and deterministic evidence. No downstream package may re-normalize an IBM bank/account identifier differently.

### Runtime-safe preparation zone

Contains only allowed transaction/account/bank metadata and detector artifacts. No hidden truth.

### Offline evaluation zone

May read `Is Laundering` and `Patterns.txt`, but only after detector/band/priority outputs have been produced independently. It must not write labels or pattern names back to the runtime database.

## 3. Canonical transaction schema

Recommended runtime `transactions` logical columns:

```text
transaction_ref            string primary identity
source_dataset             string = ibm-amlworld-hi-small
source_row_ordinal          integer provenance
transaction_timestamp      timestamp (simulation-local / timezone-unspecified)
from_bank_id                string
from_account_id             string
from_account_ref            string
to_bank_id                  string
to_account_id               string
to_account_ref              string
amount_received             DECIMAL
receiving_currency          string
amount_paid                 DECIMAL
payment_currency            string
payment_format              string
cross_currency              boolean
```

Do not persist `Is Laundering` or a pattern label in any runtime-safe table.

## 4. Stable identifiers

### 4.1 Source dataset

Frozen V2 identifier:

```text
ibm-amlworld-hi-small
```

Persist a source manifest alongside generated data with:

- external file path as local provenance only;
- SHA-256 of raw transaction file;
- row count;
- minimum/maximum timestamp;
- preparation timestamp;
- data-contract version.

### 4.2 Account reference

Canonical tuple:

```text
(source_dataset, bank_id, account_id)
```

Deterministic display/API reference:

```text
account-ref-v1
canonical compact UTF-8 JSON array:
["account-ref-v1", source_dataset, bank_id, account_id]
SHA-256
account_ref = "acct_" + first 24 lowercase hex characters
```

Store the full canonical tuple; the short hash is a resolvable stable reference, not a replacement for the tuple.

If a short-hash collision occurs during preparation, fail and increase reference length only through a contract-version change. Never append a random value.

### 4.3 Transaction reference

Version:

```text
ibm-txref-v1
```

Canonical array, fixed order:

```text
[
  "ibm-txref-v1",
  source_dataset,
  source_row_ordinal,
  timestamp,
  from_bank_id,
  from_account_id,
  to_bank_id,
  to_account_id,
  amount_received,
  receiving_currency,
  amount_paid,
  payment_currency,
  payment_format
]
```

Rules:

- `source_row_ordinal` is the 1-based data-row ordinal in the exact raw transaction file after the header; it is label-independent and ensures identical operational rows remain distinguishable.
- Timestamp canonical form: `YYYY-MM-DDTHH:MM:SS` with no timezone inference. If the source has minute precision, seconds are `00`.
- Amounts use Decimal parsing, plain decimal notation, no exponent, insignificant trailing zeroes removed, `0.00 -> "0"`.
- Bank/account identity fields use the frozen source-ID normalization above and the canonical normalized `*_bank_id` / `*_account_id` values are serialized into the transaction identity. Other text fields use Unicode NFC, surrounding ASCII whitespace stripped, source case/internal characters preserved.
- Serialize compact JSON UTF-8, no optional whitespace.
- SHA-256 digest.
- Final reference: `txn_` + full lowercase hexadecimal digest.
- `Is Laundering` is never read to construct identity.

The raw source checksum + source-row ordinal make the transaction reference reproducible for the pinned input file without pretending IBM supplied a transaction ID.

## 5. Canonical account table

Recommended `accounts` logical columns:

```text
account_ref
source_dataset
bank_id
account_id
bank_country_code
```

Accounts are created as the distinct union of sender and receiver canonical tuples.

No customer/person/company type is inferred.

## 6. Bank metadata enrichment

### 6.1 Versioned country set

Check in one risk-neutral metadata file, version:

```text
bank-country-v1
```

Each entry contains:

```text
country_name
iso_alpha2
centroid_latitude
centroid_longitude
```

Use the frozen diverse set from the approved Product Contract. The list carries no AML weighting.

### 6.2 Stable mapping

For each distinct IBM `bank_id`:

```text
SHA256("bank-country-v1|" + normalized_bank_id)
-> unsigned integer from first 8 digest bytes
-> modulo number_of_countries
-> country entry
```

`normalized_bank_id` is exactly the frozen canonical `bank_id` produced by source-ID normalization above; do not parse it numerically or normalize it again.

Persist:

```text
bank_id
mapping_version
country_name
iso_alpha2
centroid_latitude
centroid_longitude
```

No currency, transaction amount, detector output, IBM label, or pattern is allowed in this mapping.

### Frozen `bank-country-v1` list and order

The list order is part of the deterministic mapping contract:

| Index | Country | ISO | Latitude | Longitude |
|---:|---|---|---:|---:|
| 0 | Canada | CA | 56.1304 | -106.3468 |
| 1 | United States | US | 37.0902 | -95.7129 |
| 2 | Mexico | MX | 23.6345 | -102.5528 |
| 3 | Brazil | BR | -14.2350 | -51.9253 |
| 4 | United Kingdom | GB | 55.3781 | -3.4360 |
| 5 | France | FR | 46.2276 | 2.2137 |
| 6 | Germany | DE | 51.1657 | 10.4515 |
| 7 | Netherlands | NL | 52.1326 | 5.2913 |
| 8 | Switzerland | CH | 46.8182 | 8.2275 |
| 9 | Spain | ES | 40.4637 | -3.7492 |
| 10 | United Arab Emirates | AE | 23.4241 | 53.8478 |
| 11 | Saudi Arabia | SA | 23.8859 | 45.0792 |
| 12 | India | IN | 20.5937 | 78.9629 |
| 13 | Pakistan | PK | 30.3753 | 69.3451 |
| 14 | Bangladesh | BD | 23.6850 | 90.3563 |
| 15 | Singapore | SG | 1.3521 | 103.8198 |
| 16 | China | CN | 35.8617 | 104.1954 |
| 17 | Japan | JP | 36.2048 | 138.2529 |
| 18 | South Korea | KR | 35.9078 | 127.7669 |
| 19 | Australia | AU | -25.2744 | 133.7751 |
| 20 | South Africa | ZA | -30.5595 | 22.9375 |
| 21 | Nigeria | NG | 9.0820 | 8.6753 |
| 22 | Kenya | KE | -0.0236 | 37.9062 |
| 23 | Philippines | PH | 12.8797 | 121.7740 |

These coordinates are versioned visualization centroids, not customer locations. Changing the list, order, or coordinates requires a new mapping version.

## 7. Runtime analytical database

DuckDB remains the single analytical runtime engine.

Recommended physical/materialized tables:

```text
source_manifest
banks
accounts
transactions

detector_snapshots
account_detector_states
account_detector_support
transaction_review_states
network_alerts

account_latest_state
account_static_summary       # optional materialized summary for latest final cutoff
```

Views may be used for convenience only where they are fast and do not make historical logic ambiguous.

### Required physical materialization

Persist physically:

- all runtime-safe transactions (~5.08M);
- canonical accounts (~515K);
- bank metadata;
- detector snapshot metadata;
- one account detector-state row for **every canonical account in every COMPLETE snapshot**, including baseline/unscored state;
- compact GARG support values for scored accounts;
- one transaction review-state row per transaction;
- Network Pattern Alert rows.

This increases generated DB size but makes browsing/filtering deterministic and fast.

### Strongly recommended materialization

Persist latest/final-cutoff account aggregates used on lists:

- incoming transaction count;
- outgoing transaction count;
- distinct counterparties;
- first observed timestamp;
- most recent observed timestamp.

Do not materialize every possible historical behavioral metric for every timestamp.

## 8. GARG detector variant

V2 chooses:

> **GARG-AML undirected basic structural score**

Rationale:

- directly matches the published deterministic core;
- uses the second-order neighborhood block-density idea;
- avoids model fitting entirely;
- is simpler to explain than a second directed variant;
- published HI-Small experiments make the undirected base core a reasonable single V2 choice.

This is a detector-selection decision; runtime bands remain label-blind.

## 9. GARG semantic compatibility

Preserve these research semantics unless parity work proves an equivalent implementation:

1. Build a **simple unweighted undirected account graph** from canonical account relationships before the snapshot cutoff.
2. Remove self-loops.
3. Multiple transactions between the same two accounts collapse to one graph edge for GARG structural scoring; transaction multiplicity remains available to ordinary investigation analytics.
4. Apply the GARG research pipeline's Louvain community preprocessing before node scoring.
5. Freeze preprocessing config with detector version. Initial V2 parity target:
   - NetworkX Louvain implementation;
   - resolution `10`;
   - seed `1997`;
   - retain intra-community edges as the research implementation does.
6. Compute the undirected second-order-neighborhood block measures and basic score.
7. Do not use label/pattern parsing modules from the GARG repository in the production detector path.

Identity correction:

> The graph node is `account_ref` derived from `(source_dataset, bank_id, account_id)`, never raw Account alone.

Because this can change topology, Trailsight must describe results as a corrected-identity application of GARG semantics rather than claiming exact reproduction of the repository's Account-only IBM results.

## 10. Scoring eligibility

The upstream score functions contain edge cases that can yield mathematically defined but operationally weak outputs for tiny neighborhoods. Trailsight therefore adds an explicit **eligibility wrapper**, separate from the GARG score mathematics.

An account is eligible only when, after the frozen GARG community preprocessing:

- it exists in the snapshot graph;
- it has at least one first-order neighbor;
- it has at least one second-order neighbor;
- the computed score and required support measures are finite.

Otherwise:

```text
scoring_eligible = false
network_pattern_score = null
rank = null
percentile = null
network_review_band = UNSCORED
unscored_reason = NOT_YET_OBSERVED | NO_FIRST_ORDER_CONTEXT | NO_SECOND_ORDER_CONTEXT | NON_FINITE_SCORE
```

This policy is versioned as `garg-eligibility-v1` and must be kept separate from the GARG algorithm version.

## 11. Snapshot cadence

Generate cutoffs from actual raw timestamps rather than hard-coding dates.

Let:

```text
first_day = floor_to_day(min(transaction_timestamp))
last_day  = floor_to_day(max(transaction_timestamp))
```

Snapshot cutoffs are every day boundary from `first_day` through `last_day + 1 day` inclusive.

The first cutoff is persisted as a COMPLETE **baseline snapshot** with an empty graph and zero eligible accounts. No GARG scoring run is required for that baseline. Canonical accounts have UNSCORED state with reason `NOT_YET_OBSERVED` until meaningful prior graph context exists.

For the known approximately ten-day HI-Small interval this is expected to produce approximately:

- one empty/baseline cutoff at the beginning;
- ten non-empty cumulative scoring cutoffs.

The preparation job must print the actual derived cutoff count from the user's source. It must not filter or extend the period based on hidden labels/patterns.

## 12. Snapshot metadata

`detector_snapshots` minimum contract:

```text
snapshot_id
source_dataset
cutoff_timestamp
algorithm_name = GARG-AML
algorithm_variant = undirected-basic
algorithm_version
upstream_code_provenance
identity_rule_version = account-ref-v1
eligibility_rule_version = garg-eligibility-v1
community_algorithm
community_resolution
community_seed
config_hash
status = PENDING | RUNNING | COMPLETE | FAILED
started_at
completed_at
account_count
eligible_account_count
scored_account_count
failure_message_safe
```

`snapshot_id` is deterministic from source dataset + cutoff + detector config hash.

Incomplete/FAILED snapshots are never valid for transaction review.

## 13. Account detector state

`account_detector_states`:

```text
snapshot_id
account_ref
scoring_eligible
network_pattern_score nullable
rank nullable
percentile nullable
network_review_band HIGH | MEDIUM | LOW | UNSCORED
unscored_reason nullable
```

Ranking:

```text
ORDER BY network_pattern_score DESC, account_ref ASC
```

Percentile is presentation/context only. Recommended deterministic value:

```text
100 * (N - rank + 1) / N
```

where rank 1 approaches 100. Do not assign percentile to unscored accounts.

## 14. Detector explanation support

Persist only compact structural support needed to explain a score, not full ego graphs for every account.

`account_detector_support` recommended facts:

```text
snapshot_id
account_ref
first_order_neighbor_count
second_order_neighbor_count
community_id_or_stable_snapshot_local_index
block_measure_1
block_measure_2
block_measure_3
network_pattern_score
```

If the exact upstream variant uses additional support measures required for parity, persist those too under a versioned schema.

Runtime local network display is retrieved from canonical transactions on demand; it is not persisted as 515K graph blobs.

## 15. Network Review Band generation

After every snapshot completes scoring:

1. select eligible finite-scored accounts only;
2. sort score descending, `account_ref` ascending;
3. assign rank;
4. compute percentile;
5. `HIGH = first ceil(N * 0.01)`;
6. `MEDIUM = next ceil(N * 0.04)`;
7. remainder LOW;
8. unscored accounts remain UNSCORED.

Do not inspect `Is Laundering` or `Patterns.txt` before/during this operation.

Persist the policy version:

```text
review-band-policy-v1
```

## 16. Transaction snapshot association and priority

Materialize one `transaction_review_states` row per transaction.

For transaction `T`:

```text
applicable_snapshot = max(COMPLETE snapshot.cutoff_timestamp where cutoff_timestamp <= T.timestamp)
```

Then resolve sender/receiver account state in that snapshot; absent/invalid state maps to UNSCORED.

Persist:

```text
transaction_ref
snapshot_id nullable
detector_cutoff nullable
sender_band
receiver_band
aml_review_priority
derivation_code
derivation_text
alert_involvement
sender_related_alert_ref nullable
receiver_related_alert_ref nullable
```

Under normal prepared V2 data, first-day transactions map to the COMPLETE baseline snapshot and both endpoints are UNSCORED until prior network context exists. `snapshot_id = null` is reserved for a data-integrity/preparation failure, not normal first-day behavior.

Priority matrix is exactly the Product Contract matrix.

Related alert involvement is point-in-time: `alert_involvement=true` when either endpoint has at least one Network Pattern Alert whose `entry_cutoff <= transaction_timestamp`. Store the most recent applicable sender/receiver alert ref when present. Future alert entry must never mark an earlier transaction as alert-involved.

`derivation_text` is deterministic, for example:

> Sender is HIGH in the latest valid network snapshot; transaction review priority is HIGH.

Never write “transaction is high-risk” or “GARG flagged the transaction.”

## 17. Network Pattern Alert generation

Process each account's ordered snapshot bands.

Create alert when:

```text
current_band == HIGH
AND previous_observed_band != HIGH
```

Previous state may be MEDIUM, LOW, UNSCORED, or no previous state.

Alert ID:

```text
alert-ref-v1
SHA256(source_dataset, account_ref, entry_snapshot_id)
"alert_" + first 24 hex chars
```

Persist:

```text
alert_ref
account_ref
entry_snapshot_id
entry_cutoff
entry_score
entry_rank
entry_percentile
reason_code = ENTERED_HIGH
created_state = NOT_REVIEWED
```

Human review status itself is stored in the separate writable workflow-state file; runtime DB alert rows remain immutable.

## 18. GARG compute strategy on target Mac

### Baseline implementation path

Do **not** rewrite GARG first.

Use a Trailsight snapshot runner that adapts the research NetworkX implementation while preserving:

- simple undirected graph semantics;
- Louvain preprocessing/config;
- second-order neighborhood definition;
- block measures;
- basic score.

Canonical `account_ref` values may be mapped to compact integer node IDs for compute efficiency as long as the mapping is bijective and persisted for debug/parity.

### Daily graph construction

Pre-split canonical transactions into day-level unique undirected edge deltas.

For snapshots run sequentially:

1. add the next day's unique canonical relationships to a cumulative edge set/graph;
2. recompute Louvain on the complete current graph;
3. apply the same intra-community edge filtering;
4. score all eligible nodes;
5. persist snapshot output atomically/checkpoint;
6. continue to next cutoff.

Do **not** reuse yesterday's Louvain community assignment as today's answer. Community detection is graph-global and reuse could change GARG semantics.

Do **not** score only changed nodes in the baseline. A new edge can alter communities and local neighborhoods beyond its endpoints.

### Multiprocessing/RAM policy

The published repository runner parallelizes node scoring, but copying a large NetworkX graph into spawned workers can be expensive on macOS.

V2 therefore defaults to:

```text
GARG_WORKERS=1
```

Benchmark 1 and 2 workers on the target machine. Increase only when:

- score parity is unchanged;
- peak RSS remains below 70% of physical RAM;
- wall-clock improves materially.

Snapshots run one at a time; do not compute several full snapshots concurrently.

### Feasibility gate

Before running every daily snapshot, benchmark:

1. a controlled graph fixture;
2. a realistic subset;
3. the final/full graph snapshot.

Acceptance target for the baseline path:

- full final snapshot completes within **30 minutes** on the target Mac;
- peak RSS remains below **70% of physical RAM**;
- parity tests pass.

If the final snapshot exceeds either limit, use the pre-approved optimization contingency below rather than silently relaxing semantics.

### Optimization contingency

Implement a compact adjacency-set/CSR scorer that computes the same second-order block-density measures without materializing a dense adjacency matrix for each ego neighborhood.

This optimization is allowed only after:

- exact graph-preprocessing equivalence is retained;
- controlled fixtures match upstream measures/scores;
- sampled real nodes match within a frozen floating tolerance;
- rankings/bands match on the parity subset;
- the implementation is documented as a semantics-preserving performance port, not a new detector.

Louvain still recomputes per snapshot unless a future design proves exact equivalence.

## 19. Restart/failure behavior

Every snapshot writes to a temporary/checkpoint artifact first.

On success:

- mark `COMPLETE`;
- atomically commit detector/account state to generated outputs.

On failure:

- mark `FAILED` with safe diagnostic;
- do not expose partial account states as valid;
- restart from the latest previously COMPLETE snapshot and rebuild the failed snapshot.

Persist day-level canonical unique-edge deltas so a failed later snapshot does not require reparsing all raw CSV rows.

## 20. GARG parity strategy

### Fixture parity

Create small hand-designed graphs covering:

- pure smurfing-like structure;
- chain;
- star;
- triangle/clique;
- disconnected components;
- self-loop input removed;
- repeated transaction edges collapsed;
- same account string at two different banks remains two nodes.

Compare:

- first/second-order neighborhoods;
- community-filtered edges;
- block measures;
- final score.

### Upstream code parity

On a controlled IBM-derived runtime-safe subset:

- run the vendored/pinned reference GARG code with the same canonical graph;
- run Trailsight's detector adapter;
- compare node scores within strict tolerance.

### Identity-correction test

Create a fixture where raw `Account X` exists in two banks. Prove Account-only graph merges it and canonical identity does not. This validates the deliberate compatibility correction; do not require equality to the original buggy loader for this fixture.

## 21. Offline detector/policy evaluation

This is a separate command/module/path from runtime preparation.

Inputs:

1. frozen persisted detector/band/priority/alert outputs;
2. raw IBM hidden `Is Laundering` field;
3. `Patterns.txt` where available.

Recommended metrics:

### Account metrics

Define offline positive account as an account incident to at least one IBM-labelled laundering transaction, using canonical Bank+Account identity.

Report per snapshot and aggregate:

- Precision@HIGH-count;
- Recall@HIGH-count;
- proportion of known laundering-associated accounts in HIGH;
- proportion in HIGH or MEDIUM;
- unscored fraction among known laundering-associated accounts.

### Transaction metrics

- fraction of labelled laundering transactions with HIGH transaction review priority;
- fraction with HIGH or MEDIUM priority;
- coverage by at least one HIGH endpoint;
- unscored laundering-transaction fraction.

### Alert/policy metrics

- alert count;
- unique alerted accounts;
- alert re-entry count;
- review-band population sizes;
- alert volume by snapshot.

### Pattern-family metrics

Using `Patterns.txt` only offline:

- pattern-family count;
- fraction of family transactions/accounts covered by HIGH and HIGH+MEDIUM;
- unscored coverage.

Do not use these metrics to silently change 1%/4%, eligibility, country assignment, or detector algorithm.

## 22. Ground-truth firewall implementation contract

### Runtime-safe ingestion

Use an explicit allowlist. Never write `SELECT *` from raw IBM source into runtime artifacts.

### Separate code/config paths

Runtime/preparation uses:

```text
IBM_HI_SMALL_TRANSACTIONS_PATH
```

Offline evaluation additionally uses separately named hidden-truth inputs.

The runtime application container does not need or receive the hidden-truth paths.

### Automated assertions

Fail preparation/runtime tests if any product-facing DuckDB table/view contains a column whose canonical name is:

```text
is_laundering
pattern
pattern_label
aml_pattern
```

Allow documentation/test fixture strings discussing the firewall; leakage checks target runtime schemas/payloads/traces, not prose.

### Offline outputs

Store offline evaluation reports outside the runtime DB, e.g. generated JSON/CSV under an offline-evaluation output directory. They are not served by FastAPI.

## 23. Data performance organization

Initial DuckDB strategy:

- cluster/write `transactions` in timestamp order;
- store `transaction_review_states` keyed by transaction ref and joined/materialized into list-friendly runtime views if benchmark supports it;
- add selective ART indexes only for measured point lookups such as transaction ref/account ref if they materially reduce latency;
- do not add indexes by habit to low-cardinality columns such as review priority.

Runtime performance should be measured against the API targets in `07_RUNTIME_AND_DEPLOYMENT.md`.

## 24. Design limitations

- Daily snapshots intentionally trade freshness for point-in-time reproducibility and compute feasibility.
- GARG's structural score ignores many non-network AML factors.
- The bank-country model is synthetic visualization metadata.
- Corrected Bank+Account graph topology means Trailsight should not claim exact parity with published Account-only IBM benchmark results.
