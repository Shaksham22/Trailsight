# TRAILSIGHT — 05 FRONTEND

# ROLE

You are the **Trailsight Investigation Workspace Frontend Implementer**.

# GOAL

Implement the frozen one-screen analyst experience using React + TypeScript + Vite against the HTTP contracts in `00_SHARED_CONTRACTS.md`.

Keep this implementation deliberately small enough to fit the approved **4-hour frontend budget**.

# SOURCE OF TRUTH

Read before changing anything:

1. `docs/implementation/00_SHARED_CONTRACTS.md`
2. this file

The frontend contract is already frozen. Do not inspect backend internals and invent additional API fields because they would be convenient.

# DEPENDENCIES

The frontend can start after `00_SHARED_CONTRACTS.md` is frozen.

It may run in parallel with WP01/WP02 using typed mock fixtures matching the shared HTTP contract.

Before completion, validate against a running WP02/WP04 API.

WP06 depends on the production Vite build.

# FILE / DIRECTORY OWNERSHIP

## You own

Everything under:

```text
frontend/
```

Recommended structure:

```text
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   ├── client.ts
    │   └── types.ts
    ├── components/
    │   ├── CaseSelector.tsx
    │   ├── TransactionOverview.tsx
    │   ├── HistoricalContext.tsx
    │   ├── AmountPosition.tsx
    │   ├── HistoricalEvidenceTable.tsx
    │   └── AIInvestigationPanel.tsx
    └── styles.css
```

Do not split one-screen sections into dozens of micro-components.

## You may read

```text
docs/implementation/
```

Once WP02/WP04 are available, you may read their public HTTP schemas/tests only to confirm the frozen contract was implemented correctly.

## You must not modify

```text
src/
scripts/
data/
prompts/
evals/
tests/backend/
tests/mcp/
tests/ai/
pyproject.toml
uv.lock
Dockerfile
README.md
```

# INPUTS

HTTP API only:

```text
GET  /api/cases
GET  /api/cases/{case_ref}
POST /api/cases/{case_ref}/investigations
POST /api/cases/{case_ref}/follow-up
```

During local Vite development, configure a Vite dev proxy for `/api` to the local FastAPI server.

Do not add runtime API-base environment complexity unless required. Final deployment is same-origin FastAPI + static frontend.

# REQUIRED IMPLEMENTATION

## 1. Create the minimal Vite React TypeScript project

Use only the dependencies needed for:

- React;
- React DOM;
- Vite;
- TypeScript;
- Vite React plugin.

Do not add:

- React Router;
- Redux;
- Zustand;
- TanStack Query;
- Material UI;
- Chakra;
- Ant Design;
- charting libraries;
- CSS frameworks;
- animation libraries.

Use normal React state/effects and plain CSS.

---

## 2. Create API types that mirror the frozen HTTP contract

Create:

```text
frontend/src/api/types.ts
```

Define TypeScript types/interfaces for exactly:

```text
CaseSummary
CaseListResponse
EntityRef
SelectedTransaction
SenderHistoryContext
AmountHistoryContext
CounterpartyHistoryContext
RegionHistoryContext
HistoricalTransactionRow
WorkspaceResponse
RenderedCitation
RenderedFinding
DisplayEvidence
InvestigationResponse
FollowUpRequest
ApplicationError
```

Use the exact field names from `00_SHARED_CONTRACTS.md`.

Do not:

- rename fields for frontend preference;
- add derived backend fields;
- use `any` for API responses;
- model decimal strings as numbers.

Amounts remain strings in API types.

---

## 3. Create one API client boundary

Create:

```text
frontend/src/api/client.ts
```

Expose only these functions:

```text
listCases()
getCase(caseRef)
investigateCase(caseRef)
submitFollowUp(caseRef, question, parentInvestigationId)
```

Responsibilities:

- call same-origin `/api` routes;
- parse JSON;
- throw/return one normalized frontend error type for non-2xx responses;
- not transform factual values;
- not calculate history;
- not retry automatically.

Do not call MCP/OpenAI.

---

## 4. Keep application state in `App.tsx`

Do not create a global store.

Required state:

```text
cases
selectedCaseRef
workspace
caseLoading
caseError

investigation
investigationLoading
investigationRequestError

followUpQuestion
followUpResult
followUpLoading
followUpSubmitted

focusedEvidenceId
highlightedTransactionRefs
```

On selected case change, reset:

```text
investigation
follow-up state
focused evidence
highlighted rows
```

Do not retain AI conversation state across cases.

---

# 5. CASE SELECTION

Create `CaseSelector.tsx`.

On app startup:

1. fetch `/api/cases`;
2. if `demo-01` exists, select it by default;
3. otherwise select the first returned case;
4. fetch the selected case workspace.

Render in the top workspace header:

```text
TRAILSIGHT
Review Case [<display name>]
SYNTHETIC DATA
```

Use a compact select/dropdown or equivalent control.

Do not create a case-management page.

---

# 6. TRANSACTION OVERVIEW

Create `TransactionOverview.tsx`.

Render the frozen transaction block using `workspace.selected_transaction`.

Show:

```text
Sender
  account

Counterparty
  account · Person|Merchant

Time
  human-readable selected timestamp

Amount Paid + Payment Currency
  ->
Amount Received + Receiving Currency

CROSS-CURRENCY when cross_currency=true

Payment Format

Synthetic Region <sender> -> Synthetic Region <receiver>
SAME-REGION or CROSS-REGION
```

Do not display hidden/raw IDs unless they are part of the approved UI information.

Bank identifiers may remain available in accessible/title detail if needed for identity clarity, but do not redesign the main locked layout around them.

Do not display:

- fraud/laundering status;
- demographics;
- FX spread;
- fees;
- expected receive amount.

Assign a DOM section target that can be focused for:

```text
selected_transaction
```

---

# 7. HISTORICAL CONTEXT AREA

Create `HistoricalContext.tsx` as the left-side deterministic context container.

It must render four conceptual blocks using backend values only:

1. sender history;
2. amount comparison;
3. counterparty history;
4. synthetic-region/currency context.

Do not recompute any statistics.

---

## 7.1 Sender history

Display:

```text
Previous sender activity: <prior_outgoing_count>
```

DOM target:

```text
sender_history
```

---

## 7.2 Amount position

Create `AmountPosition.tsx`.

Use only:

```text
history_quality
sample_size
selected_amount
payment_currency
historical_median
empirical_percentile
```

### Insufficient

When:

```text
history_quality = insufficient
```

show:

```text
Amount vs previous <currency> activity
N = <sample_size>
Insufficient same-currency history.
```

Do not show median or percentile.

### Limited

Show:

```text
N
historical median
Limited history
```

Do not show percentile.

### Sufficient

Show:

```text
N
historical median
selected amount
Historical position: <percentile>%
```

Use the percentile only as a simple horizontal position indicator if desired.

Do not create a statistical chart library dependency.

A simple CSS bar/line with a selected marker is sufficient.

The visual must not imply a suspiciousness threshold. Do not color a region "danger" or add P95 markers.

DOM target:

```text
amount_context
```

---

## 7.3 Counterparty history

Display:

```text
Previous interactions: <count>
```

If count is zero:

```text
Not previously seen in sender history
```

If count > 0, display:

```text
First previous interaction
Most recent previous interaction
```

DOM target:

```text
counterparty_history
```

Do not label a new counterparty as risky/suspicious.

---

## 7.4 Synthetic Region context

Always show selected transaction facts:

```text
Synthetic Region <sender> -> <receiver>
Same-region | Cross-region
```

If `workspace.region_history` is present, also show:

```text
Region <receiver> previously seen: Yes|No
```

and optionally previous count when useful.

If the Manager has invoked the destination-region-novelty cut and `region_history=null`, do not invent a replacement value.

DOM target:

```text
synthetic_region_history
```

Always call it **Synthetic Region**.

---

## 7.5 Currency context

Use selected transaction fields only:

```text
<payment_currency> -> <receiving_currency>
Cross-currency | Same-currency
```

Do not query currency history during normal page load.

Do not calculate FX.

Currency context can live inside `HistoricalContext.tsx`; no separate route/component is required.

---

# 8. HISTORICAL EVIDENCE TABLE

Create `HistoricalEvidenceTable.tsx`.

Input:

```text
workspace.historical_transactions
```

Render exactly these visible columns:

```text
Date
Counterparty
Type
Amount
Currency
Region
Format
```

Map fields:

```text
Date         <- timestamp
Counterparty <- counterparty_account
Type         <- counterparty_type
Amount       <- amount_paid
Currency     <- payment_currency
Region       <- receiver_region as "Synthetic Region N"
Format       <- payment_format
```

Keep `transaction_ref` as the stable row key and for evidence highlighting; it does not need to be a visible column.

The backend already returns deterministic order. Do not re-sort based on CSV order.

Do not add pagination/search/filter unless the Manager later approves it. The runtime case slice is bounded.

DOM target for table container:

```text
historical_evidence
```

---

# 9. AI INVESTIGATION PANEL

Create `AIInvestigationPanel.tsx`.

Initial state displays:

```text
[INVESTIGATE TRANSACTION]
```

Do not call AI automatically when the case loads.

When clicked:

1. set AI loading state;
2. call `investigateCase(caseRef)`;
3. preserve all deterministic workspace content;
4. render the returned AI state only in the right panel.

Disable duplicate investigate clicks while one request is pending.

Do not automatically retry.

---

# 10. AI FINDINGS

For run statuses:

```text
success
partial
```

render:

```text
Relevant context
```

followed by the backend-provided findings in order.

The backend already provides citation labels and evidence IDs.

For each `RenderedCitation` render a clickable:

```text
[E1]
```

using its provided `label`.

Do not generate citation labels in frontend.

Do not parse evidence IDs from model prose.

---

# 11. LIMITS / ABSTENTION

If `limits` is non-empty, render:

```text
Limits
```

followed by the returned concise limit strings.

For:

```text
run_status = unavailable
```

render no fabricated finding area; show the Limits explanation.

Example expected product behavior:

```text
Trailsight cannot determine this because stated transaction purpose is unavailable.
```

Do not rephrase an unavailable result into a risk conclusion.

---

# 12. AI FAILURE STATES

For:

```text
model_error
tool_error
structured_output_invalid
evidence_validation_failed
```

show a compact message such as:

```text
AI investigation is unavailable. The deterministic transaction and historical evidence remain available.
```

Do not expose:

- stack traces;
- model provider exception text;
- internal evidence IDs as error diagnostics;
- raw MCP errors.

Keep the existing transaction/history workspace visible and usable.

---

# 13. EVIDENCE CLICK BEHAVIOR

When the analyst clicks a citation:

1. find the corresponding `DisplayEvidence` by `evidence_id`;
2. set `focusedEvidenceId`;
3. set `highlightedTransactionRefs` to that evidence object's `supporting_transaction_refs`;
4. locate the DOM section represented by `ui_target`;
5. scroll/focus that section into view;
6. apply a simple temporary or persistent focused-border/background class;
7. highlight any history table rows whose `transaction_ref` is in `supporting_transaction_refs`.

If `supporting_transaction_refs` is empty, focus/highlight the deterministic section only.

Do not call the backend or model again when `[E1]` is clicked.

Do not animate beyond simple CSS focus/highlight unless there is spare time. Evidence animation/polish is an approved cut before core functionality.

---

# 14. FOLLOW-UP

After a completed initial investigation (`success`, `partial`, or `unavailable`), render:

```text
Ask about available history
[____________________] [Ask]
```

Use one text input.

On submit:

1. trim the question;
2. require 1–500 characters;
3. call `submitFollowUp` with:

```text
case_ref
question
parent_investigation_id = initial investigation_id
```

4. set `followUpSubmitted=true` once the request has been sent successfully to the API;
5. disable/hide further follow-up submission for that selected case;
6. display the follow-up result separately below the initial result.

Do not build a message list/chat transcript.

Do not send the previous AI output back to the API.

On case change, reset follow-up state.

---

# 15. LOADING STATES

Required visible states:

## Case list loading

Show a small workspace loading indicator.

## Case workspace loading

Show a loading state in the main workspace. Do not show stale previous-case data under a new selected case label.

## AI investigation loading

Keep deterministic context visible. Change button/panel to a clear loading state.

## Follow-up loading

Keep initial AI findings and deterministic context visible.

Do not add skeleton libraries.

---

# 16. CASE/API FAILURE STATES

## `/api/cases` failure

Show a clear page-level error that Trailsight cases could not be loaded.

## selected case 404/failure

Do not show stale transaction facts. Show the returned safe error message.

## AI request network failure

Treat as AI-panel failure only; deterministic workspace remains visible.

Do not automatically retry.

---

# 17. ACCESSIBILITY / BASIC INTERACTION

Keep this minimal but correct:

- buttons are actual buttons;
- input has a label;
- case selector has a label;
- citation links/buttons are keyboard focusable;
- focused evidence section can receive programmatic focus where practical;
- do not rely only on color to identify the selected/focused evidence.

Do not spend the 4-hour budget on elaborate accessibility infrastructure; implement standard semantic HTML correctly.

---

# 18. STYLING

Use one small `styles.css` or a few colocated plain CSS files.

Match the frozen layout conceptually:

```text
header
transaction block
historical context | AI investigation
historical evidence table
```

Desktop interview demo is primary.

Provide reasonable narrow-screen stacking, but do not turn this into a mobile-design project.

Use restrained styling. Do not use red/amber "risk" semantics for normal contextual facts.

---

# REQUIRED TESTS

## Build and smoke expectations

Do not add a frontend test framework solely for this 4-hour package.

Required automated checks:

```text
npm run build
```

The build must include TypeScript type checking as part of the script or an adjacent script invoked by it.

Also run the Vite dev server against the FastAPI API when available and manually smoke these exact flows:

1. app loads case list;
2. `demo-01` selected by default;
3. deterministic transaction/history render before AI;
4. amount sufficient/limited/insufficient state renders from fixture/API values;
5. investigate button sends one request;
6. returned findings show backend-provided `[E1]` labels;
7. clicking evidence focuses the correct section;
8. supporting table rows highlight when refs exist;
9. evidence with zero refs still focuses its context section;
10. AI error leaves deterministic workspace visible;
11. unavailable result shows Limits;
12. one follow-up can be submitted;
13. second follow-up is disabled for the case;
14. changing case resets AI/follow-up/focus state.

If backend is not yet available during initial implementation, create one local development mock object/file **inside `frontend/` only** matching the shared API types. Remove any mock interception from the production path before returning completion.

# DO NOT CHANGE

Do not:

- add routes/pages;
- add dashboard views;
- add generic chat UI;
- add graph/timeline views;
- call OpenAI;
- call MCP;
- calculate any historical fact;
- derive Synthetic Region;
- parse raw transaction CSV;
- change API contracts;
- add hidden/source-only data;
- add Redux/router/query libraries;
- add a large UI framework;
- add chart libraries;
- add risk colors/thresholds;
- add repeated follow-up conversation;
- edit backend/Python files;
- exceed scope for visual polish.

# ACCEPTANCE CRITERIA

This package is complete only when:

1. one Vite React TypeScript application exists under `frontend/`.
2. it has no router/global state/UI framework.
3. API types exactly match shared contracts.
4. app defaults to `demo-01` when present.
5. deterministic workspace renders without any AI call.
6. transaction overview matches frozen content categories.
7. amount states obey backend-provided insufficient/limited/sufficient values without frontend calculations.
8. counterparty/currency/Synthetic Region context renders correctly.
9. historical evidence table uses stable transaction refs as row keys.
10. AI runs only on button click.
11. backend-provided findings/citations render without citation parsing/invention.
12. `[E1]` click focuses/highlights application-owned evidence.
13. AI failures do not remove deterministic workspace.
14. unavailable result shows Limits.
15. exactly one bounded follow-up is available per selected case UI state.
16. `npm run build` succeeds.
17. no files outside `frontend/` were modified.

# COMMANDS TO RUN

From `frontend/`:

```text
npm install
npm run build
```

Development smoke when FastAPI is running:

```text
npm run dev
```

Use the Vite `/api` proxy to the FastAPI development server.

Do not run or modify Python tests from this package.

# RETURN WITH

Return to the Manager:

1. files created/modified under `frontend/`;
2. component list and what frozen UI section each owns;
3. exact frontend application state kept in `App.tsx`;
4. confirmation that no calculations are implemented in React;
5. `npm run build` result;
6. manual smoke checklist results;
7. evidence-click behavior result;
8. one-follow-up behavior result;
9. any API contract mismatch found against WP02/WP04;
10. any requested change outside WP05 ownership;
11. explicit statement: **No product/architecture redesign was made.**
