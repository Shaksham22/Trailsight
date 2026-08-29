# TRAILSIGHT V2 — FRONTEND AND UX DESIGN

**Status: APPROVED FRONTEND VISUAL/INTERACTION CONTRACT.**

This document incorporates the approved UX/UI handoff into the authoritative system-design bundle. Product/domain/system semantics remain higher authority than visual treatment. Approved UI-01 through UI-06 images, when supplied to an implementation worker, are authoritative visual references; no mockup images were included in the current final-design input, so this document contains the complete text contract needed to implement without redesign.

## 1. V1 UX REVIEW

### What the current V1 frontend does well
The current repository has a few implementation ideas worth preserving:
- a thin typed API-client pattern;
- clear loading/error states instead of silently retaining stale subject data;
- an existing AI panel that keeps deterministic content visible when AI fails;
- evidence citations that can focus a deterministic UI target and highlight supporting transaction rows;
- readable identifier-first tables and modest visual styling.

### What must be discarded or replaced
The V1 information architecture is structurally wrong for V2:
- the application is built around a `CaseSelector` and one selected case;
- `case_ref` is a primary navigation concept;
- Person/Merchant entity types appear in the UI;
- Synthetic Region is presented as investigation context;
- there is no Alerts → Accounts → Transactions workspace;
- there are no scalable server-driven account/transaction browsers;
- there is no account-native Network Pattern Alert queue;
- there is no Bank Country route map, bounded canonical account graph, or snapshot-aware account investigation page.

The active V2 frontend should therefore replace the V1 shell and page composition, while reusing only compatible low-level concepts such as error handling, evidence-focus behavior, and a small typed fetch layer.

---

## 2. REFERENCE IMAGE REVIEW

### Strong patterns to adopt
Across the supplied references, the strongest ideas are:
- dense analyst-first tables rather than oversized dashboard cards;
- clear use of hierarchy on investigation pages;
- compact, persistent product navigation;
- dark surfaces that make long investigation sessions feel focused;
- visually distinct priority labels, workflow labels, filters, and technical metadata;
- local network graphs and activity charts embedded where they answer a concrete question;
- summary blocks that lead directly into evidence rather than decorative metrics.

### Patterns to reject
- bright red full-width “danger” banners that make HIGH look like guilt;
- glowing/cyberpunk accents;
- giant sidebar navigation that steals horizontal space from large tables;
- overly card-heavy layouts;
- global graph-browser aesthetics;
- decorative maps;
- green LOW labels that read as “safe”;
- general-purpose AI chat layouts.

### Chosen visual direction
Use a calm dark navy analyst workspace inspired mostly by the best density of references 1, 3, and 4, but with:
- top navigation, because the frozen contract requires it;
- less red;
- no neon;
- no glassmorphism;
- fewer decorative cards;
- stronger table hierarchy;
- explicit semantic helper text wherever AML meaning can be misread.

---

## 3. V2 UX MODEL

The primary workflow is:

**Alerts → Account investigation → related transactions → deterministic evidence → AI assistance → analyst review progress**

1. Analyst lands on **Alerts**.
2. Analyst filters the account-native Network Pattern Alert queue.
3. Opening an alert navigates to **Account Detail** with historical origin context preserved.
4. Account Detail shows the account’s Network Review Band, detector cutoff, observed activity, bounded one-hop relationships, transactions, indicators, and alert history.
5. Analyst opens one or more related transactions.
6. **Transaction Detail** first explains AML Review Priority and its endpoint-band derivation, then shows exact transaction facts and deterministic indicators.
7. AI can be invoked after deterministic context is visible.
8. AI findings cite Evidence V2 and citations focus the corresponding deterministic section or supporting record.
9. Analyst may use one follow-up.
10. Review workflow progress is changed only on the Network Pattern Alert: NOT_REVIEWED → IN_REVIEW → REVIEWED.

Direct browsing is equally valid:
- **All Transactions → Transaction Detail → Account Detail**
- **Accounts → Account Detail → Transaction Detail**

The product never answers “is this laundering?”

---

## 4. INFORMATION ARCHITECTURE

### Routes
- `/` → redirect `/alerts`
- `/alerts`
- `/transactions`
- `/transactions/:transactionRef`
- `/accounts`
- `/accounts/:accountRef`

Account detail may preserve exactly one origin:
- `?origin_alert_ref=...`
- `?origin_transaction_ref=...`

### Global application shell
A 56px sticky top header:
- TRAILSIGHT V2
- Alerts
- All Transactions
- Accounts
- right side: analyst identity if already supported + **SYNTHETIC DATA** indicator

Under the header, every page has:
- title;
- short purpose text;
- relevant detector cutoff/snapshot context;
- compact synthetic-data notice available from the header.

No dashboard route, Case route, chat route, standalone map, or global graph.

---

## 5. DESIGN SYSTEM

### Overall direction
Dark, restrained, high-contrast, dense, technical, and calm. Surfaces are differentiated mostly by luminance and borders, not gradients. Color communicates type/state and is always paired with text.

### Typography
- Primary UI: **Inter**, fallback `ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif`
- Identifiers/timestamps: **IBM Plex Mono**, fallback `"SFMono-Regular", Consolas, monospace`
- Tabular monetary numbers: `font-variant-numeric: tabular-nums`

### Surface hierarchy
- Page background: very dark navy
- Header: slightly lighter than page
- Primary section: dark slate
- Secondary/inset section: darker inset slate
- Hover/focus: lighter border/surface, not glow

### Priority treatment
AML Review Priority and Network Review Band share category colors but never rely only on them.
- HIGH: warm coral/red outline + text, no large red background
- MEDIUM: amber
- LOW: cool slate/cyan-gray, never green
- UNSCORED: muted outlined pill reading **Insufficient Network Context**

### Workflow treatment
Review workflow is visually different from priority:
- NOT_REVIEWED: neutral gray
- IN_REVIEW: blue
- REVIEWED: violet/teal
No green “resolved” semantics.

### AI category treatment
- DETECTOR_OUTPUT: indigo
- OBSERVED_FACT: cyan
- INTERPRETATION: violet
AI uses subtle category chips and evidence citations, never message bubbles.

### Evidence focus
Evidence focus uses a high-contrast cyan border + soft inset background and a small “Evidence E#” marker. The highlighted deterministic row/section remains readable without animation.

---

## 6. SCREEN SPECIFICATIONS

### UI-01 — Alerts
**Purpose:** primary analyst queue.

Layout:
1. page title + concise description + detector snapshot context;
2. one-line queue toolbar;
3. filters/search row;
4. dense alert table;
5. cursor pagination footer.

Required columns:
- Alert Ref
- Account (Bank + Account)
- Bank Country
- Network Review Band
- Reason
- Detector Cutoff
- Relevant recent transactions
- Review Status

Interactions:
- row click → Account Detail with `origin_alert_ref`;
- review-status control is interactive without opening the row;
- filter/search requests are server-side;
- changing filter resets cursor;
- no raw Network Pattern Score in queue.

Empty state:
“No Network Pattern Alerts match these filters.”

### UI-02 — All Transactions
Layout:
1. title + brief semantics (“review priority, not verdict”);
2. search + dense filter bar;
3. scalable server-driven table;
4. cursor pagination.

Columns:
- Transaction Ref
- Time
- Sender Bank + Account / Bank Country
- Receiver Bank + Account / Bank Country
- Amount Paid + Currency
- Amount Received + Currency
- Payment Format
- AML Review Priority
- Alert involvement

Row click → Transaction Detail.

### UI-03 — Accounts
Layout:
1. title + latest detector snapshot;
2. search/filter bar;
3. account table;
4. cursor pagination.

Columns:
- Bank + Account
- Bank Country
- Network Review Band
- Detector Cutoff
- Incoming Count
- Outgoing Count
- Alert indicator

Account click → Account Detail in latest completed detector context.

### UI-04 — Transaction Detail / Investigation
Render in this exact high-level order:

1. **AML Review Priority**
   - compact priority label;
   - backend-returned derivation;
   - endpoint band contribution;
   - detector cutoff;
   - explicit “review priority, not verdict” helper.

2. **Transaction Summary + Bank-Country Route**
   - left: amount/format/from/to summary;
   - right: ECharts Bank-Country route map.

3. **Transaction Facts**
   - ref, timestamp, sender/receiver bank+account, both amounts/currencies, format.

4. **Sender / Receiver Account Cards**
   - two equal cards;
   - Bank + Account;
   - Bank Country;
   - Network Review Band;
   - observed bounded summary;
   - cutoff;
   - “View Account”.

5. **Deterministic Investigation Indicators**
   - compact rows/cards;
   - every indicator says what was observed.

6. **Activity Context**
   - currency-separated ECharts timeline;
   - selected transaction marker.

7. **Local Account Network**
   - sender/receiver toggle if both payloads exist;
   - one bounded graph shown at a time.

8. **AI Investigation**
   - idle/loading/success/partial/unavailable/error/evidence-validation-failure;
   - category labels;
   - Evidence V2 citations;
   - Limits;
   - one follow-up.

9. **Supporting Transactions / Evidence**
   - bounded dense table;
   - evidence-focused rows can highlight.

### UI-05 — Account Detail / Investigation
Render in frozen order:
1. Account identity + Network Review
2. Observed Activity
3. Account Network
4. Transactions / Counterparties
5. Activity Over Time
6. Currency Activity
7. Bank-Country Flows
8. Alert History
9. AI Investigation

The top identity strip contains:
- Bank + Account
- Bank Country
- Network Review Band
- detector cutoff
- structural explanation
- historical-origin badge when applicable

Detector technical details are collapsed by default.

### UI-06 — AI Investigation + Evidence Focus
This is not a separate route. It is a focused state of a detail page.

State shown:
- AI finding list on the right;
- category chip per finding;
- citation `[E1]`, `[E2]`;
- clicked citation highlighted;
- matching deterministic indicator/supporting transaction on the left focused with evidence outline;
- a compact Evidence detail strip showing evidence type, subject, context/cutoff, and bounded supporting refs;
- one follow-up control at bottom;
- after use: disabled input + “Follow-up already used”.

No chat bubbles, no unrestricted conversation history.

---

## 7. GENERATED UI MOCKUP IMAGE PLAN

The generated mockups are authoritative visual references after user approval:

- **UI-01** Alerts
- **UI-02** All Transactions
- **UI-03** Accounts
- **UI-04** Transaction Detail / Investigation
- **UI-05** Account Detail / Investigation
- **UI-06** AI Investigation + Evidence Focus

All use the same top navigation, dark navy design tokens, table density, semantic labels, and synthetic-data language.

---

## 8. INTERACTION + STATE SPECIFICATION

- **Table row click:** entire row is keyboard-focusable; hover changes surface/border; Enter/Space opens detail.
- **Account click:** opens canonical account; from transaction uses `origin_transaction_ref`; from alert uses `origin_alert_ref`.
- **Transaction click:** opens canonical transaction detail.
- **Filters:** server-side; selected values shown in controls; cursor reset on change.
- **Search:** submit or 300–400ms debounce; never client-filter only the loaded page.
- **Pagination:** opaque cursor Next/Previous; default 50 rows; max 100 if API supports.
- **Review workflow change:** save previous value until PATCH succeeds; show inline “Saving…”; on failure retain previous status and show concise inline error.
- **Evidence citation click:** focus citation, scroll/focus deterministic `ui_target`, highlight matching support rows; no model call.
- **Graph node click:** select/highlight node and show bounded relationship detail; “View Account” navigation only; never expand hops.
- **Graph hover:** tooltip with canonical short Bank+Account, direction/relationship counts, Bank Country metadata if provided.
- **Map hover:** show Sending/Receiving Bank Country + Bank IDs only.
- **Chart hover:** show timestamp/day, currency-specific amount, count, and selected-transaction marker where relevant.
- **AI invocation:** button changes to deterministic loading state; existing page remains intact.
- **AI failure:** inline panel text: “AI investigation is unavailable. Deterministic investigation evidence remains available.”
- **Evidence validation failure:** do not render unvalidated generated findings; show validation failure state.
- **Follow-up:** 1–500 chars, one submit; after accepted, disable permanently for that investigation.
- **Follow-up exhausted:** show “Follow-up already used”; do not auto-retry 409.
- **Historical alert context:** visible badge beside cutoff, e.g. “Historical context from Alert ALT-…”.
- **Detector detail expansion:** accordion under Account identity; no raw technical values dominate initial view.

---

## 9. EXACT DESIGN TOKENS

```css
:root {
  --bg-page: #07111D;
  --bg-header: #0A1624;
  --bg-surface: #0D1B2A;
  --bg-surface-2: #102235;
  --bg-inset: #081522;
  --bg-hover: #132A3E;

  --border-subtle: #1C3448;
  --border-strong: #2A4A62;

  --text-primary: #F3F7FA;
  --text-secondary: #B9C7D3;
  --text-muted: #7F94A6;
  --text-disabled: #587083;

  --interactive: #58BCEB;
  --interactive-hover: #7DD0F3;
  --focus: #79D5FF;
  --evidence-focus: #53E0D2;
  --evidence-focus-bg: #0C2A2B;

  --high: #FF6B6B;
  --high-bg: #2A171C;
  --medium: #F6B94D;
  --medium-bg: #2A2214;
  --low: #8FA9BA;
  --low-bg: #172531;
  --unscored: #9AA9B5;
  --unscored-bg: #111B25;

  --status-not-reviewed: #98A8B6;
  --status-in-review: #5CA9FF;
  --status-reviewed: #9A8CFF;

  --ai-detector: #7F8CFF;
  --ai-observed: #55C7E8;
  --ai-interpretation: #B58AF2;

  --font-ui: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;

  --fs-11: 11px;
  --fs-12: 12px;
  --fs-13: 13px;
  --fs-14: 14px;
  --fs-16: 16px;
  --fs-20: 20px;
  --fs-24: 24px;
  --fs-30: 30px;

  --weight-regular: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;

  --lh-tight: 1.2;
  --lh-normal: 1.45;
  --lh-reading: 1.6;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;

  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;

  --border-width: 1px;
  --shadow-raised: 0 8px 24px rgba(0,0,0,.22);
  --shadow-focus: 0 0 0 3px rgba(121,213,255,.20);

  --header-height: 56px;
  --content-max: 1480px;
  --table-row-height: 44px;
  --control-height: 36px;
  --button-height: 36px;
}
```

Body: 14px/1.45. Detail prose: 14–16px. Page titles: 24px/1.2/700. IDs: 12–13px mono. Avoid body text below 12px.

---

## 10. EXACT LAYOUT SPECIFICATION

### Global
- primary desktop target: 1440px viewport;
- sticky header: 56px;
- content max-width: 1480px;
- horizontal page padding: 20px at ≥1280, 16px at 1100–1279, 12px below 1100;
- page top/bottom padding: 20px / 32px;
- major section gap: 20px;
- card/section internal padding: 16px;
- grid gap: 12px;
- filter/control height: 36px;
- table header: 36px;
- table row: 44px;
- detail dense table row: 40px.

### Alerts
- header/purpose row: full width;
- toolbar: 1 row, min 36px;
- filters: CSS grid `minmax(260px,2fr) repeat(3,minmax(150px,1fr)) auto`;
- table: full width, horizontal scroll only below ~1180px;
- sticky table header inside page scroll where practical.

### All Transactions
- filters: two-row grid at 1440px; search spans 2 columns;
- table minimum width: 1220px;
- sender/receiver each min 190px;
- amount columns 125px;
- priority 120px.

### Accounts
- filters: `minmax(280px,2fr) repeat(3,minmax(160px,1fr))`;
- table minimum width: 980px.

### Transaction Detail
- priority summary: 12-column full-width strip;
- summary/map: 12-column grid, left 5 columns / right 7 columns;
- facts: 4-column fact grid;
- endpoint account cards: 2 equal columns;
- indicators: 3 columns at ≥1280, 2 columns 1000–1279, 1 below;
- activity chart: full width, height 300px;
- local network: full width, height 380px;
- AI: full width with inner 7/5 split only after successful findings if evidence preview is open;
- evidence table: full width.

### Account Detail
- identity strip: full width;
- observed activity: 4 equal compact metric cells;
- account network: full width 380px;
- transactions/counterparties: 7/5 columns at ≥1280;
- activity/currency: 8/4 columns;
- country flows/alert history: 6/6 columns;
- AI: full width.

### AI Investigation / Evidence state
- detail content remains the page;
- AI section becomes 5-column findings + 7-column deterministic/evidence focus region at ≥1280;
- at narrower widths stack deterministic focus first, AI second;
- no modal that hides the deterministic page.

### Breakpoints
- ≥1280: full desktop grids;
- 1100–1279: reduce column counts; summary/map becomes 5/7 or 1/1 depending available width;
- 820–1099: stack major visuals, top nav remains;
- <820: table horizontal scrolling is allowed; no separate mobile redesign.

---

## 11. COMPONENT INVENTORY

| Component | Purpose / information | Important states / interaction | Shared |
|---|---|---|---|
| `AppShell` | header, content frame, global synthetic notice | route active state | all |
| `PrimaryNavigation` | Alerts / All Transactions / Accounts | active, focus | all |
| `SyntheticDataNotice` | semantic disclaimer | compact / expanded | all |
| `PageHeader` | title, purpose, cutoff/context | loading metadata | all |
| `FilterBar` | search + filters | loading, active filters | list pages |
| `SearchInput` | server-side search | clear, submit, disabled | list pages |
| `FilterSelect` | server filter | selected, disabled | list pages |
| `CursorPagination` | bounded paging | prev/next disabled/loading | list tables |
| `ReviewPriority` | HIGH/MEDIUM/LOW/UNSCORED review priority | all enums | transaction/list |
| `NetworkReviewBand` | account detector band | all enums | account/list |
| `ReviewWorkflowStatus` | alert progress | save/saving/error | alerts/history |
| `BankCountry` | country name + ISO, explicit bank metadata | tooltip | all |
| `DetectorCutoff` | historical validity | historical-origin variant | detail/list |
| `AlertsTable` | work queue | loading/empty/error | Alerts |
| `TransactionsTable` | scalable transaction browser | loading/empty/error | lists/details |
| `AccountsTable` | account directory | loading/empty/error | Accounts |
| `TransactionPrioritySummary` | priority + derivation + endpoint contribution | unscored | Tx detail |
| `TransactionFacts` | exact deterministic transaction fields | focusable evidence target | Tx detail |
| `EndpointAccountCard` | sender/receiver identity and network band | clickable | Tx detail |
| `InvestigationIndicatorList` | deterministic observed indicators | evidence-focused | both details |
| `BankCountryRouteMap` | bank-country route only | same-country/loading/error | Tx detail |
| `AccountRelationshipGraph` | bounded one-hop canonical graph | root/selected/truncated | both details |
| `ActivityTimeline` | amount/count history | currency selection/empty | both details |
| `CounterpartiesTable` | concrete relationship records | pagination/focus | Account detail |
| `EvidenceTable` | bounded supporting evidence records | focused rows | both details |
| `AIInvestigation` | bounded grounded assistant | idle/loading/success/partial/unavailable/error | both details |
| `AIFinding` | category + text + citations | focused citation | AI |
| `EvidenceCitation` | backend label → evidence target | pressed/focus | AI |
| `EvidenceFocusState` | accessible deterministic highlight | active/clear | details |
| `FollowUpControl` | one bounded follow-up | idle/loading/used/error | AI |
| `DetectorDetailsDisclosure` | score/rank/percentile/version/policy | collapsed/expanded | Account |
| `LoadingState` | deterministic section/page loading | accessible live region | all |
| `EmptyState` | no records/context | never implies safe | all |
| `UnavailableState` | AI or optional data unavailable | deterministic content retained | all |
| `InlineError` | scoped failure | retry where safe | all |

---

## 12. VISUALIZATION IMPLEMENTATION SPECIFICATION

### Bank-Country Route Map
Engine: ECharts map with bundled simplified world GeoJSON.

Appearance:
- ocean/background transparent against `--bg-inset`;
- non-selected countries: `#122334`, borders `#294156`;
- sending country: `#4DB7E5`;
- receiving country: `#9A8CFF`;
- route line: `#6CC8EE`, 2px, directional arrow;
- marker size: 9px;
- labels rendered outside/near the map in normal DOM as the authoritative textual summary.

Cross-country:
- two centroid markers;
- one directional curved line;
- `<Sending Bank Country> → <Receiving Bank Country>`;
- sender and receiver Bank IDs.

Same-country:
- one highlighted country and one centroid marker;
- no fake arc;
- label **Same bank-country route**.

Tooltip:
- role: Sending / Receiving Bank Country;
- country;
- Bank ID;
- no customer-location wording.

Required visible helper:
“Bank countries are deterministic synthetic metadata added by Trailsight. They are not customer locations.”

Empty/error:
- preserve transaction summary;
- show “Bank-Country route unavailable” inside map region, never infer coordinates.

### Account Relationship Graph
Engine: ECharts `graph` series, deterministic/circular layout.

- root node: 56px, centered, strong border;
- counterparty: 30–36px;
- maximum visual node count: render backend payload only, contract max 25 nodes;
- incoming edge: arrow toward root;
- outgoing edge: arrow away from root;
- bidirectional: two thin curved directional edges or one visually double-arrow edge if unambiguous;
- selected transaction relationship: 3px accent edge + small “Selected transaction” legend item;
- root label: Bank + shortened Account;
- node tooltip: canonical short Bank+Account, Bank Country, relationship counts;
- edge tooltip: incoming/outgoing counts + selected relation marker;
- if `truncated=true`, show backend-supported “Showing 24 of N direct counterparties…” message;
- no expand-hops interaction.

### Activity Timeline
- x-axis: UTC date/time;
- left y-axis: amount in selected currency;
- optional right y-axis: transaction count;
- incoming/outgoing amounts are distinct line/bar series;
- count series uses a separate visual encoding and axis;
- never sum unlike currencies;
- currency selector changes amount series only;
- selected transaction: vertical dashed marker + labelled point;
- tooltip: UTC time, amount/currency, direction, count;
- zero state: “No prior activity in this currency at the selected cutoff.”
- accessibility: DOM summary gives date range, selected currency, total points, selected transaction timestamp/amount.

---

## 13. APPROVED MOCKUP REFERENCE MAP

- **UI-01 Alerts** defines: global header, list-page title treatment, filter controls, alert table density, priority/workflow distinction, pagination.
- **UI-02 All Transactions** defines: transaction browser filter density, canonical sender/receiver display, money formatting, route text, priority labels.
- **UI-03 Accounts** defines: account directory identity pattern, Bank Country display, band labels, activity-count columns.
- **UI-04 Transaction Detail** defines: exact investigation hierarchy, priority summary, route map, facts, account cards, indicators, timeline, graph, AI, evidence.
- **UI-05 Account Detail** defines: account identity strip, historical context badge, observed activity, one-hop graph, transaction/counterparty split, charts, alert history, AI.
- **UI-06 AI + Evidence Focus** defines: finding categories, citation controls, evidence focus treatment, supporting-row highlight, follow-up states.

Implementation screenshots should be compared against these six approved references at approximately 1440px whenever the image files are supplied to the worker/user.

---

## 14. IMPLEMENTATION NOTES FOR WP05A

- Replace the V1 CaseSelector/one-case page architecture.
- Remove active `case_ref`, Person/Merchant, and Synthetic Region UI semantics.
- Preserve only reusable infrastructure patterns that do not conflict with V2.
- The existing V1 evidence-click → deterministic target focus pattern is worth adapting.
- The existing AI-failure principle is worth retaining.
- Do not copy V1 factual types into V2.
- Do not calculate detector or investigation facts in TypeScript.
- Keep list filters in URL query parameters where practical.
- Use real `/api/v2` endpoints whenever available.
- Use typed V2 mocks only where the frozen WP05A contract explicitly permits them.
- Bundle world GeoJSON locally.
- Prefer DOM labels around ECharts for critical semantics/accessibility.

---

## 16. DESIGN RISKS / OPEN QUESTIONS

1. **Alerts count summary:** do not add dashboard-style KPI cards unless the V2 list API explicitly provides cheap trustworthy aggregate counts. The approved design does not require them.
2. **Account high-level volume summaries:** show only fields supported by the final `/api/v2` contract. Do not synthesize totals client-side.
3. **Bank flags:** optional. Country names/ISO are authoritative; flags should not become the primary semantic cue.
4. **Map labels:** ECharts text can become cramped; critical route labels should live in DOM outside the map.
5. **Graph density:** max-25 still gets dense at laptop widths; prioritise labels for root/selected relationship and use tooltips for the rest.
6. **AI evidence focus across page sections:** a persistent but non-modal focus indicator is required so the analyst can see both the citation source and deterministic target.
7. **Historical account context:** UI must make historical origin/cutoff visible enough that users do not mistake it for current state.

No frozen-design contradiction was found in the inspected required V2 documents. The current V1 implementation is incompatible mainly at the information-architecture and domain-type level, not because its low-level React patterns are unusable.

---

## 17. APPROVAL CHECKLIST

Approve only if all are true:

- [ ] Default landing is Alerts.
- [ ] Primary nav is exactly Alerts / All Transactions / Accounts.
- [ ] No Case / Synthetic Region / Person / Merchant V1 UX remains active.
- [ ] HIGH is clearly review priority, never laundering.
- [ ] LOW never reads as safe.
- [ ] Bank Country is clearly bank metadata, not customer location.
- [ ] Alerts are account-native.
- [ ] Review workflow has exactly NOT_REVIEWED / IN_REVIEW / REVIEWED.
- [ ] Transaction Detail follows the frozen 1–9 hierarchy.
- [ ] Account Detail follows the frozen hierarchy.
- [ ] Route map is bank-country only and handles same-country correctly.
- [ ] Account graph is bounded one-hop only.
- [ ] Timeline separates currencies.
- [ ] AI is subordinate to deterministic evidence.
- [ ] Evidence citations visibly focus deterministic UI/supporting rows.
- [ ] AI loading/error does not hide deterministic content.
- [ ] Exactly one follow-up is supported.
- [ ] Design is readable around 1440px and usable on narrower laptops.
- [ ] Design is implementable with React + TypeScript + Vite + ECharts without inventing backend facts.

## 18. IMPLEMENTATION AUTHORITY

Frontend delivery is split into the runnable job tickets `implementation/WP05A_FRONTEND_FOUNDATION.md` and `implementation/WP05B_FRONTEND_API_INTEGRATION.md`. WP05A reproduces this approved design against typed V2 mocks; WP05B connects the same UI to real `/api/v2` responses. Neither package may redesign this file. Backend mismatches are reported to the owning backend package/Manager.
