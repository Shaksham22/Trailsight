# TRAILSIGHT V2 — TESTING AND ACCEPTANCE DESIGN

## 1. Testing principle

V2 must separately prove:

1. data/firewall correctness;
2. GARG semantic parity;
3. point-in-time detector correctness;
4. deterministic domain correctness;
5. API/MCP contract correctness;
6. frontend behavior;
7. AI grounding/overclaim behavior;
8. end-to-end runtime/deployment behavior.

Do not rely on the AI eval suite as a substitute for normal software tests.

Normal pytest/build tests must not require a live model API key.

## 2. Data tests

### Raw schema validation

- required IBM transaction columns exist;
- malformed/missing source rejected;
- source row count/checksum manifest generated;
- no invented customer/entity columns.

### Canonical account identity

- `From Bank`, `Account`, `To Bank`, and `Account.1` are read as strings, not numeric identifiers;
- source IDs use Unicode NFC + leading/trailing ASCII-whitespace trim only;
- case, internal whitespace, punctuation, and leading zeroes are preserved;
- missing/empty-after-trim bank/account identifiers are rejected;
- the same normalized bank/account strings feed account identity, `account_ref`, `transaction_ref`, Bank Country hashing, and GARG node identity;
- same Account ID at different banks -> different `account_ref`;
- identical Bank+Account in same source -> same account;
- same Bank+Account in different source dataset -> different identity fixture.

### Transaction reference

- same pinned source row -> same deterministic ref;
- source dataset participates;
- source row ordinal participates;
- timestamp/Decimal/text canonicalization stable;
- hidden label does not participate;
- duplicate ref/collision fails.

### Bank-country enrichment

- same Bank ID -> same country across runs;
- mapping version fixed;
- only versioned country list used;
- no amount/currency/label input affects assignment;
- centroids/ISO valid;
- all runtime banks mapped.

### Runtime schema

- all required safe tables exist;
- `Is Laundering` absent;
- pattern label fields absent;
- no customer country/person/company/KYC fields invented.

## 3. GARG controlled parity tests

Required graph fixtures:

- pure smurfing-like bipartite/block structure;
- chain;
- star;
- triangle/clique;
- disconnected components;
- repeated transactions collapse to edge;
- self-loop removal;
- account-ID collision across two banks.

For each compare with pinned upstream/reference implementation where semantics apply:

- edge set after preprocessing;
- first-order set;
- second-order set;
- block measures;
- final undirected basic GARG score.

Bank+Account collision fixture intentionally differs from upstream Account-only loader topology; document this expected compatibility correction.

## 4. GARG optimization parity tests

If compact scorer contingency is implemented, it cannot become active until:

- all controlled fixtures match;
- sampled canonical IBM-derived graph nodes match reference score within strict configured tolerance;
- sorted score ordering is identical or differences are proven below tolerance without band/rank changes;
- HIGH/MEDIUM/LOW assignment on parity subset matches;
- repeated runs are deterministic.

Keep reference path available for parity testing even if optimized path is used for full preparation.

## 5. Snapshot tests

Create a tiny multi-day fixture.

Verify for snapshot cutoff `D`:

```text
all included timestamps < D
no timestamp >= D
```

Verify:

- cutoffs derived from min/max dates;
- first baseline is COMPLETE, contains zero eligible scores, and canonical accounts are UNSCORED/NOT_YET_OBSERVED;
- COMPLETE vs FAILED status;
- transaction only uses COMPLETE snapshots;
- daily graph cumulative (earlier relationships persist);
- new day's edge appears only after its timestamp is before a later cutoff;
- no label value affects snapshot contents.

## 6. Point-in-time transaction tests

Given snapshots at day boundaries and transactions inside the day:

- transaction at 16:00 uses 00:00 snapshot, not next day;
- transaction exactly at cutoff may use that COMPLETE cutoff snapshot;
- transaction before first non-empty valid snapshot -> UNSCORED;
- later HIGH state never changes earlier transaction review state;
- future account activity absent from historical account detail opened from transaction.

## 7. Review-band policy tests

For deterministic score fixtures:

- eligibility excludes unscored accounts from N;
- sort score DESC then account_ref ASC;
- `ceil(1%)` HIGH count;
- next `ceil(4%)` MEDIUM count;
- rest LOW;
- unscored remains UNSCORED with null rank/percentile;
- ties resolve deterministically;
- IBM label changes have no effect.

## 8. Transaction priority tests

Test every symmetric matrix combination:

```text
HIGH + HIGH
HIGH + MEDIUM
HIGH + LOW
HIGH + UNSCORED
MEDIUM + MEDIUM
MEDIUM + LOW
MEDIUM + UNSCORED
LOW + LOW
LOW + UNSCORED
UNSCORED + UNSCORED
```

Verify deterministic derivation text and applicable snapshot/cutoff.

Verify transaction priority never calls itself a GARG transaction score.

Verify transaction `alert_involvement` uses only alerts whose entry cutoff is on/before the transaction; a future alert never marks an earlier transaction.

## 9. Alert-generation tests

Account band sequence fixtures:

```text
UNSCORED -> HIGH        creates alert
LOW -> HIGH             creates alert
MEDIUM -> HIGH          creates alert
HIGH -> HIGH            no duplicate
HIGH -> MEDIUM          no alert
HIGH -> LOW -> HIGH     second alert on re-entry
HIGH -> UNSCORED -> HIGH second alert on re-entry
LOW -> MEDIUM           no alert
```

Alert ID deterministic from account + entry snapshot.

`relevant_recent_transaction_count` tests:

- count distinct transactions where sender OR receiver is the alerted canonical account in `[entry_cutoff - 24h, entry_cutoff)`;
- include a transaction exactly at `entry_cutoff - 24h`;
- exclude a transaction exactly at `entry_cutoff`;
- count an alerted-account self-transfer once;
- do not match the same raw account ID at another bank.

Review status mutation must not alter immutable alert detector fields.

## 10. Ground-truth firewall tests

These are mandatory release-gate tests.

Inspect:

- runtime DuckDB schema/tables/views;
- runtime domain models;
- REST responses;
- MCP serialized results/errors;
- evidence objects/display evidence;
- AI seed context fixtures;
- AI JSONL traces;
- frontend API fixtures/build-time data.

Assert no runtime field/value is derived from:

```text
Is Laundering
Patterns.txt pattern label
```

A source/offline-evaluation test may prove those inputs exist in the offline boundary. Do not scan documentation strings and falsely report leakage merely because the firewall is documented.

## 11. Deterministic indicator tests

### Amount behavior

Both sender-paid and receiver-received contexts:

- n=0,4,5,19,20;
- median odd/even;
- empirical percentile;
- no currency mixing;
- selected timestamp excluded;
- opposite direction excluded from role-specific population.

### Counterparty novelty

- no prior relationship;
- A→B prior only;
- B→A prior only;
- both directions;
- equal-timestamp relationship excluded;
- first/last prior timestamp.

### Velocity

- exact 1h/24h boundaries;
- incoming/outgoing/total counts;
- selected transaction excluded.

### Fan-in/fan-out

- distinct canonical counterparties;
- duplicate transactions do not inflate distinct count;
- Bank+Account identity respected;
- 24h cutoff.

### Cross-currency

- equal currency false;
- different true;
- no FX inference.

### Optional indicators

If retained, test rapid incoming→outgoing and new bank-country route with exact cutoff semantics.

## 12. Bounded network tests

- one-hop only;
- root always included;
- relevant selected counterparty reserved;
- rank by total interaction count DESC, recent timestamp DESC, ref ASC;
- UI max 24 counterparties;
- truncation metadata correct;
- no future relationship;
- no unrestricted `hops` parameter.

## 13. Evidence V2 tests

For every evidence type:

- stable deterministic ID for identical type/subject/context/parameters;
- ID format is `ev2.<base64url canonical payload>.<full SHA-256 checksum>` and obeys frozen size limits;
- decoding recovers evidence version/type, subject type/ref, authoritative `ContextIdentityV2`, snapshot where applicable, and normalized parameters;
- payload tampering and checksum tampering are rejected;
- non-canonical payload encoding, unknown version/type, and invalid parameter shape are rejected;
- authoritative alert/transaction/COMPLETE-snapshot context is resolved and validated;
- resolver recomputes evidence, regenerates identity, and exact-match verifies the ID;
- correct subject/context/snapshot;
- correct UI target;
- support count exact;
- support refs bounded to 50;
- `support_truncated` correct;
- support selection deterministic;
- no hidden truth;
- cross-context/future-context/unknown evidence IDs are rejected;
- AI validation rejects a syntactically valid ID that was not seed evidence or returned by a successful MCP call in that run;
- historical origin prevents future evidence.

## 14. Runtime-state and investigation-session tests

Required:

- missing `runtime_state.json` initializes valid `runtime-state-v1`;
- alert review progress persists and an absent alert entry reads `NOT_REVIEWED`;
- initial investigation persists subject/ref, nullable origin refs, exact authoritative context identity, `follow_up_used=false`, and creation time;
- runtime state contains no transcript, model reasoning, findings, AML disposition, evidence cache, or hidden IBM truth;
- first follow-up atomically sets `follow_up_used=true` and reloads persisted subject/context;
- second follow-up returns HTTP 409 `FOLLOW_UP_ALREADY_USED`;
- investigation context/follow-up flag survive app restart when the runtime-state path is retained;
- corrupt runtime state is not silently overwritten;
- same-directory temp write + atomic replace behavior is exercised under the single-process MVP assumption.

## 15. API tests

### Pagination

- default/max limits;
- stable cursor ordering;
- invalid cursor rejected;
- filters reset/independent;
- no unbounded result endpoint.

### Transactions

Test search by ref/account/bank and every required filter.

### Accounts

Test direct latest context and historical origin from alert/transaction.

### Alerts

Test list, get, review-status PATCH, invalid status, missing alert.

### Evidence

Test valid ID, wrong/malformed ID, bounded supporting rows.

### AI routes without live model

Mock runner; verify route schemas, one-follow-up constraint, deterministic page routes unaffected when AI is unavailable.

### Safe errors

No raw SQL/filesystem/provider exception text.

## 16. MCP tests

No live LLM required.

### Registration

Exactly seven approved tools. No SQL/general query/arbitrary graph tools.

### Domain projection equality

For each tool:

```text
domain factual result == MCP factual projection
```

MCP may omit internal fields but may not recompute/change them.

### Scope validation

- unrelated account rejected;
- arbitrary future context rejected;
- relationship counterparty must be direct/authorized;
- invented evidence rejected.

### Bounds

- 4/5/8/12 KiB ceilings by tool class;
- network relationships <=12 model-facing;
- support transactions <=8;
- no model-controlled limit/hops.

### Real stdio smoke

Launch the actual MCP server through a test client, list tools, call at least one tool against deterministic V2 fixture DB.

### Firewall

No hidden label/pattern fields in success/error payloads.

## 17. Frontend automated checks

Use existing V1 test framework if already present and economical. Do not add a large new framework solely for appearance.

At minimum:

- TypeScript typecheck;
- production `npm run build`;
- component/interaction tests for critical evidence/priority wording where current setup supports them.

Recommended focused tests:

- routing/default `/alerts`;
- transaction filters generate correct API query;
- LOW never renders “safe”;
- UNSCORED renders Insufficient Network Context;
- Bank Country disclaimer present on route map;
- same-country route does not draw international arc;
- evidence citation click focuses correct UI target;
- review-state selector uses only three statuses;
- historical-context badge shown from origin ref;
- AI error leaves deterministic page visible.

## 18. Integration tests

With a small deterministic V2 test DB:

- FastAPI boots with runtime DB read-only;
- `runtime_state.json` writable and retained across restart;
- React SPA static fallback does not shadow `/api/v2`;
- transaction/account/alert list/detail routes work;
- AI router registers without credential requirement for deterministic startup;
- MCP child can be launched by mocked/live integration path;
- evidence resolves end-to-end;
- hidden-truth schema check runs at startup.

## 19. AI evals

Run the 15 required V2 scenarios from `05_AI_AND_EVALUATION.md` for the final prompt/model configuration.

Required summary metrics:

- scenario pass/fail;
- tool selection;
- tool efficiency;
- evidence validity;
- factual support;
- detector-vs-fact distinction;
- priority explanation;
- abstention;
- bank-country wording;
- AML overclaim;
- label leakage.

Release target:

```text
unsupported criminal/laundering conclusions = 0
evidence validation rate = 100%
label leakage = 0
```

A scenario failing these hard safety/grounding gates blocks AI acceptance even if other metrics are good.

## 20. Offline detector/policy evaluation tests

Prove:

1. detector outputs exist before hidden truth is loaded;
2. evaluation module reads labels only through offline path;
3. band thresholds remain 1%/4% regardless of results;
4. runtime DB checksum/schema unchanged after evaluation;
5. reports contain aggregate metrics, not a hidden-truth runtime join/table.

## 21. Manual acceptance checklist

### Navigation

- [ ] App opens on Alerts.
- [ ] All Transactions and Accounts navigate correctly.
- [ ] No V1 case selector/case terminology remains.

### Alert flow

- [ ] Open a HIGH Network Pattern Alert.
- [ ] Account Detail shows entry snapshot cutoff.
- [ ] HIGH is described as review band, not laundering conclusion.
- [ ] Mark In Review and Reviewed; reload persists progress.
- [ ] Detector outputs remain unchanged.

### Transaction flow

- [ ] Search transaction/account/bank.
- [ ] Apply every required filter.
- [ ] Open transaction.
- [ ] Priority and exact sender/receiver derivation are first.
- [ ] Detector cutoff visible.
- [ ] Map says Bank Country.
- [ ] Same-country route behaves correctly when selected.
- [ ] Sender/receiver account cards navigate with historical origin.

### Account flow

- [ ] Direct account uses latest snapshot.
- [ ] Historical account from transaction/alert does not show future activity.
- [ ] One-hop graph is bounded and clearly truncated where needed.
- [ ] Timeline does not sum unlike currencies.

### AI flow

- [ ] Initial investigation uses actual adaptive MCP tools.
- [ ] Findings show category and evidence citations.
- [ ] Click E# focuses deterministic evidence without a model call.
- [ ] One bounded follow-up works.
- [ ] Second follow-up blocked.
- [ ] “Is this money laundering?” abstains/does not conclude.
- [ ] Bank Country question does not infer customer location.
- [ ] AI failure leaves deterministic UI usable.

### Firewall

- [ ] No runtime page/API/MCP/trace contains `Is Laundering` or pattern labels.
- [ ] Raw IBM dataset is not in the Docker image/repository.
- [ ] Runtime DB does not contain hidden truth.

## 22. Portfolio/demo acceptance criteria

V2 is demo-ready only when:

1. IBM HI-Small is ingested reproducibly without hidden truth entering runtime.
2. Canonical Bank+Account identity is used everywhere.
3. At least the complete expected daily snapshot set is generated and validated.
4. GARG reference/parity tests pass.
5. Account bands and transaction priorities are point-in-time correct.
6. Network Pattern Alerts correctly represent HIGH entry/re-entry.
7. All ~5.08M transactions are queryable with bounded search/filter/pagination.
8. Alerts/Transactions/Accounts and both detail pages work.
9. World map, one-hop graph, and timeline work with correct semantics.
10. Deterministic indicators are evidence-backed and cutoff-correct.
11. AI uses bounded MCP, structured output, and fail-closed evidence validation.
12. 15-scenario AI eval passes hard leakage/overclaim/evidence gates.
13. deterministic UI remains useful with OpenAI unavailable.
14. one Docker runtime builds/runs with mounted read-only analytical DB.
15. README explains synthetic data, GARG scope, review-band semantics, bank-country enrichment, limitations, tests/evals, and demo flow.
16. dead V1 Case/TransXion/Synthetic Region contracts are removed from the active V2 runtime.

## FINAL TEST RESPONSIBILITY MATRIX

Package-level automated tests remain mandatory; user-local validation is only for expensive/credentialed/external-data/manual checks.

| Area | Primary worker | Final Codex responsibility | User-local responsibility |
|---|---|---|---|
| IBM ingestion/firewall/identity | WP01 | rerun practical deterministic tests/audit | full HI-Small preparation and scale timing |
| GARG parity/snapshots/bands/alerts | WP02 Codex | package owner itself + final regression | full-final graph benchmark/long daily run when expensive |
| Investigation domain/Evidence V2 | WP03 | rerun domain/evidence contract tests | inspect representative real historical contexts |
| REST/runtime state | WP04A | rerun API/state tests | restart persistence/manual review-state workflow |
| MCP/AI/evidence validation/telemetry | WP04B | rerun non-live MCP/AI tests and contract audit | credentialed real-model evals/cost |
| Frontend visual foundation | WP05A | production build in final repo | screenshot comparison to approved UI-01..UI-06 |
| Frontend real API behavior | WP05B | route/build/startup checks | end-to-end analyst workflow/visual acceptance |
| Docker/whole repo | WP06 Codex | owns practical integration verification | exhaustive Docker/manual demo where long |

### Required merge gates

**Merge Gate A:** actual WP02 detector artifacts are readable by WP03 contract; GARG parity and the full-final feasibility gate are accepted before API/AI work becomes authoritative.

**Merge Gate B:** WP04A + WP04B coexist without path collision; `/api/v2`, stdio MCP, runtime state, evidence validation, telemetry, and non-live evals pass.

**Merge Gate C:** WP05A overlay builds on R3_BACKEND before real API integration begins.

**Final Codex gate:** practical Python regression, configured lint/type/static checks, frontend production build, import/startup checks, Docker build/smoke where practical, dead-V1 import audit, and ground-truth leakage audit.

**User-local final gate:** full real-data/GARG/model/manual/visual acceptance. A user-local check does not waive an automated test that is practical for a worker or Codex to run.



## Implementation-worker testing authority

Every runnable WP must add focused automated tests for its owned boundary, preserve previously passing relevant regression tests, keep default pytest deterministic/non-live where practical, test the ground-truth firewall at that boundary, and report exact commands/results in its completion report. Manual/user-local validation supplements rather than replaces normal automated tests. AI evals must reuse the production Evidence V2 validator rather than an eval-only weaker validator. Package-specific test ownership and user-local gates are defined in the corresponding runnable WP and `09_IMPLEMENTATION_ROADMAP.md`.
