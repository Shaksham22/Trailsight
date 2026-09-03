# TRAILSIGHT V2 — PRODUCT CONTRACT

Status: **FROZEN**. This file is the concise immutable product/domain contract for System Design and implementation. If an implementation instruction conflicts with this file, stop and return the conflict to the Master Product & Engineering Manager.

## 1. Product definition

Trailsight V2 is a **synthetic AML Investigation Workspace**. It uses a published graph-structure detector to prioritize accounts for analyst review, transparently propagates that account review state to transactions, and helps an analyst inspect deterministic transaction, account, network, and bank-country evidence with grounded AI assistance.

The primary product question is:

> **Why does this account or transaction deserve more review, and what evidence should I inspect?**

Trailsight does **not** answer:

> Is this money laundering?

The operating principle is:

> **Detector prioritizes. Code establishes facts. AI investigates and explains. Human judges.**

## 2. Runtime dataset

- Runtime dataset: **IBM AMLworld HI-Small only**.
- Approximate scale: **5.08M transactions and ~515K canonical accounts**.
- Raw IBM files remain external to the public repository.
- Generated analytical/runtime data is reproducible and generally uncommitted.
- Independent IBM simulations must never share identity, history, detector state, or network state.

## 3. Canonical identity

### Account

Canonical account identity is:

```text
(source_dataset, bank_id, account_id)
```

For V2 the source dataset identifier is frozen as:

```text
ibm-amlworld-hi-small
```

`account_id` alone is never a canonical identity.

### Source identifier normalization

The IBM identifier columns `From Bank`, `Account`, `To Bank`, and `Account.1` use one frozen normalization rule everywhere identity participates:

- read the identifier columns from the CSV as strings; do not infer numeric type;
- Unicode-normalize to NFC;
- remove leading/trailing ASCII whitespace only;
- preserve case, punctuation, internal whitespace, and leading zeroes;
- reject missing or empty-after-trim identifiers.

The normalized bank string is the canonical `bank_id`; the normalized account string is the canonical `account_id`. The same representation must be used for account identity, `account_ref`, `transaction_ref`, Bank Country hashing, and GARG node construction. No package may independently coerce these identifiers to integers, change case, or choose a different whitespace rule.

### Transaction

A transaction receives a deterministic Trailsight reference derived from:

- source dataset;
- source-row ordinal from the pinned raw transaction file;
- timestamp;
- From Bank;
- From Account;
- To Bank;
- To Account;
- Amount Received;
- Receiving Currency;
- Amount Paid;
- Payment Currency;
- Payment Format.

`Is Laundering` is never part of transaction identity.

Human-display references may be shorter than canonical database identity, but every display reference must resolve back to the canonical identity.

## 4. GARG role

- Primary detector: **GARG-AML deterministic structural core**.
- V2 uses the **undirected basic GARG score** as the single frozen detector variant.
- GARG is account/network-level, not a transaction classifier.
- GARG is specialized toward smurfing-like local network structure; it is not comprehensive AML detection.
- Trailsight corrects the IBM loader identity from Account-only to canonical Bank+Account identity.
- Do not change GARG score mathematics unless a Manager-approved design revision explicitly says so.
- No Decision Tree, Gradient Boosting, Isolation Forest, GNN fitting, fine-tuning, or any other downstream training.

Analyst-facing terms:

- underlying detector value: **Network Pattern Score**;
- operational account state: **Network Review Band**.

## 5. Detector snapshots and historical correctness

Conceptual cadence: **daily cumulative snapshots**.

A detector snapshot with cutoff `D` may contain only transactions satisfying:

```text
transaction_timestamp < D
```

For a transaction at time `T`, use:

```text
latest completed detector snapshot where snapshot.cutoff <= T
```

No future transaction, graph state, rank, band, alert, or aggregate may leak backward.

If no valid detector state exists or GARG lacks meaningful local context, the account is **UNSCORED**.

Runtime product interaction must read persisted detector state. It must never run GARG interactively.

## 6. Network Review Band policy

For **eligible scored accounts within one snapshot**:

```text
HIGH   = top 1% by Network Pattern Score
MEDIUM = next 4%
LOW    = remaining eligible scored accounts
UNSCORED = no valid eligible score
```

Deterministic rank tie-breaker: canonical `account_ref` ascending after score descending.

For `N` eligible accounts:

```text
high_count   = ceil(0.01 * N)
medium_count = ceil(0.04 * N)
```

Rank `1..high_count` is HIGH; the next `medium_count` ranks are MEDIUM; the remaining eligible accounts are LOW.

These bands are:

- a Trailsight analyst-capacity/ranking policy;
- snapshot-relative;
- label-blind;
- **not** official GARG AML thresholds;
- **not** laundering probability.

LOW does not mean safe. HIGH does not mean laundering.

## 7. Transaction AML Review Priority

Transaction priority is Trailsight application triage metadata derived from the transaction's applicable historical snapshot.

| Sender state | Receiver state | Transaction priority |
|---|---|---|
| HIGH | anything | HIGH |
| anything | HIGH | HIGH |
| MEDIUM | MEDIUM | MEDIUM |
| MEDIUM | LOW | MEDIUM |
| LOW | MEDIUM | MEDIUM |
| MEDIUM | UNSCORED | MEDIUM |
| UNSCORED | MEDIUM | MEDIUM |
| LOW | LOW | LOW |
| LOW | UNSCORED | UNSCORED |
| UNSCORED | LOW | UNSCORED |
| UNSCORED | UNSCORED | UNSCORED |

UI label for `UNSCORED` transaction priority:

> **Insufficient Network Context**

A transaction priority is not a GARG edge prediction and must always expose its derivation and detector cutoff.

## 8. Network Pattern Alerts

Primary alert object: **Account Network Alert**, UI term **Network Pattern Alert**.

Create an alert when an eligible account:

- enters HIGH for the first time; or
- re-enters HIGH after a previous non-HIGH state.

Do not create duplicate alerts while an account remains continuously HIGH.

MEDIUM and LOW accounts do not create detector alerts by default.

Alert review progress has exactly three values:

```text
NOT_REVIEWED
IN_REVIEW
REVIEWED
```

These mean workflow progress only. They are not AML disposition.

The only V2 transitions are `NOT_REVIEWED -> IN_REVIEW -> REVIEWED`. `REVIEWED` is deliberately terminal because V2 does not maintain the workflow event/audit history required for safe reopening. V2 must not add `REVIEWED -> IN_REVIEW`.

V1 `case` / `case_ref` is not a V2 primary domain concept.

## 9. Bank geography

IBM Bank IDs are enriched by Trailsight with deterministic synthetic bank metadata:

- Bank Country;
- ISO country code;
- country centroid/coordinates.

Assignment is:

```text
stable hash(bank_id) -> fixed versioned risk-neutral country list
```

Rules:

- no currency inference;
- no AML risk weighting;
- no customer geography inference;
- no customer nationality inference;
- no synthetic bank brand names required.


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

The map shows:

> **Sending Bank Country → Receiving Bank Country**

It does not show customer location.

## 10. Required navigation and views

Top-level navigation is exactly:

```text
[ ALERTS ] [ ALL TRANSACTIONS ] [ ACCOUNTS ]
```

Default landing page: **ALERTS**.

Primary views:

1. Alerts.
2. All Transactions.
3. Accounts.
4. Account Detail / Investigation.
5. Transaction Detail / Investigation.

No separate dashboard, map page, graph explorer, or chatbot page.

## 11. Transaction browser

All runtime transactions remain queryable through bounded server-side pagination.

Required search:

- transaction reference;
- account ID;
- bank ID.

Required filters:

- AML Review Priority;
- alert involvement;
- date range;
- currency;
- payment format;
- sending Bank Country;
- receiving Bank Country.

React must never load the complete dataset.

## 12. Required deterministic indicators

MUST:

1. amount relative to strictly earlier same-currency history;
2. new / first-observed counterparty;
3. recent transaction velocity;
4. fan-out;
5. fan-in;
6. cross-currency.

SHOULD if implementation scope permits:

7. rapid incoming → outgoing activity;
8. new bank-country route.

These are observed facts/context, not automatic suspiciousness labels.

## 13. Required visualizations

MUST:

- transaction Sending Bank Country → Receiving Bank Country world route map;
- bounded one-hop account relationship graph;
- amount/activity-over-time plot;
- counterparty/supporting-relationship table.

Transaction Detail activity is deliberately fixed to the sender's strictly prior 30 days relative to the resolved historical context. V2 has no 7D/30D/90D selector and no receiver switch.

Do not build:

- global graph;
- unrestricted multi-hop graph;
- Sankey;
- customer-location map.

## 14. Detector transparency

Visible by default:

- Network Review Band;
- AML Review Priority;
- exact derivation reason;
- detector valid-through cutoff;
- concise explanation of the network detector.

Expandable technical detail:

- raw Network Pattern Score;
- rank/percentile;
- GARG algorithm/version;
- identity-rule version;
- bounded structural support facts;
- band-policy explanation.

Hidden at runtime:

- IBM ground truth;
- pattern labels;
- future detector state;
- internal model reasoning.

## 15. Ground-truth firewall

IBM fields/resources:

```text
Is Laundering
Patterns.txt
```

are **OFFLINE EVALUATION ONLY**.

They must be structurally inaccessible from:

- runtime database tables/views consumed by product services;
- domain objects;
- account/transaction priority;
- alert creation;
- APIs;
- evidence;
- MCP;
- LLM prompts/context;
- frontend;
- runtime telemetry/traces.

Offline evaluation may read detector outputs only after those outputs and bands were independently produced without labels.

## 16. AI role

AI answers:

> **Why is this account/transaction prioritized for review, and which available evidence should the analyst examine?**

AI must explicitly distinguish:

- **DETECTOR OUTPUT**;
- **OBSERVED FACT**;
- **INTERPRETATION**.

AI may select and synthesize approved evidence.

AI may not:

- determine laundering truth;
- claim criminal intent;
- call LOW safe;
- call HIGH laundering;
- infer customer geography from Bank Country;
- calculate authoritative deterministic metrics;
- access benchmark labels/patterns;
- invent evidence IDs.

No persistent general chatbot. Exactly one successful bounded follow-up per investigation is sufficient; configuration/provider/infrastructure failure does not consume it.

## 17. Evidence principle

Every material AI factual statement must cite an application-owned Evidence V2 ID.

The application validates every cited ID before rendering. Invalid evidence references fail closed; generated findings are not rendered.

Normal deterministic code owns all authoritative:

- counts;
- medians/percentiles;
- ranks/bands;
- detector cutoffs;
- GARG score;
- network degree;
- novelty;
- velocity;
- review priority.

The same deterministic domain services support product APIs and MCP.

## 18. Explicit non-goals

V2 does not build:

- real Remitly data or claims about Remitly internals;
- all IBM simulations;
- detector/model training;
- transaction laundering probability;
- universal AML detection;
- KYC/customer profiles;
- sanctions/PEP/watchlist checks;
- country risk scores;
- SAR filing/regulatory disposition;
- enterprise case management;
- global or multi-hop graph exploration;
- vector database/RAG corpus;
- multiple AI agents;
- Kafka/Kubernetes/cloud infrastructure;
- customer geography.

## 19. Frozen terminology

Preferred:

- AML Investigation Workspace
- AML Review Priority
- Network Review Band
- Network Pattern Score
- Network Pattern Alert
- Smurfing-like network structure
- Bank Country
- Bank-Country Flow / Route
- Investigation Indicators
- Supporting Evidence
- Investigation Findings
- Insufficient Network Context

Never use as runtime conclusions:

- Money Laundering Detected
- Confirmed Laundering
- Confirmed Smurfing
- Laundering Probability
- Fraud Probability
- Safe
- Cleared
- Criminal Account
- High-Risk Customer

---

This contract intentionally describes **what Trailsight V2 is**. Architecture, storage, API, and implementation mechanics belong to the following V2 design files.
