# TRAILSIGHT V2 — FRONTEND AND UX DESIGN

**Status: APPROVED FRONTEND VISUAL/INTERACTION CONTRACT.**

This document is the authoritative integrated visual/interaction contract. Product/domain/system semantics remain higher authority than visual treatment. Approved UI-01 through UI-06 references remain useful visual context; the executable implementation is under `frontend/src/`.

## 1. LEGACY UX REMOVAL RECORD

The integrated frontend retained only compatible low-level ideas from the former UI:

- a thin typed API-client pattern;
- clear loading/error states instead of silently retaining stale subject data;
- an AI panel that keeps deterministic content visible when AI fails;
- a direct structured analyst summary that remains subordinate to deterministic page content;
- readable identifier-first tables and modest visual styling.

Case selection, `case_ref` navigation, Person/Merchant types, Synthetic Region, V1 evidence, and `/api/cases` were removed. The active information architecture is Alerts → Accounts/Transactions → deterministic evidence → bounded AI assistance.

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
Use a calm neutral analyst workspace in both Light and Dark modes, with:
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
8. AI displays the model's structured summary, observations, patterns, attention points, and limits directly.
9. Analyst may use one follow-up.
10. Review workflow progress is changed only on the Network Pattern Alert: NOT_REVIEWED → IN_REVIEW → REVIEWED.

`REVIEWED` is deliberately terminal in V2. Reopening is not offered because V2 has no workflow event/audit history capable of recording that transition safely.

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
Neutral, restrained, high-contrast, dense, technical, and calm. Trailsight supports **System / Light / Dark** appearance modes. Light uses a white/cool-gray enterprise hierarchy; Dark uses graphite/charcoal rather than blue-tinted surfaces. Blue is reserved primarily for interaction. Surfaces are differentiated through luminance, borders, and very restrained shadows rather than gradients. Color communicates type/state and is always paired with text.

The preference persists in local storage. `System` follows `prefers-color-scheme` live and does not store a forced light/dark value. Charts, maps, graphs, tooltips, browser theme color, and all semantic UI tokens update with the resolved mode.

### Typography
- Primary UI: **Inter**, fallback `ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif`
- Identifiers/timestamps: **IBM Plex Mono**, fallback `"SFMono-Regular", Consolas, monospace`
- Tabular monetary numbers: `font-variant-numeric: tabular-nums`

### Surface hierarchy
- Light page: cool gray background with white primary surfaces and clear gray insets
- Dark page: near-black graphite background with charcoal primary/elevated surfaces
- Header: primary surface with a subtle border in both modes
- Hover/focus: neutral surface lift plus the interactive-blue focus ring, never a glow-heavy effect

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
The control exposes only `NOT_REVIEWED -> IN_REVIEW -> REVIEWED`; `REVIEWED` has no reopening option in V2.

### AI summary treatment
AI uses direct report sections—Summary, Key observations, Patterns noticed, and optional Limits—never message bubbles, procedural advice, or raw Evidence V2 identifiers.

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
- search submits `q` to the server for Alert Ref, Account Ref/ID, or Bank ID prefix matching;
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

6. **Sender Activity — Prior 30 Days**
   - sender-rooted and strictly prior to the resolved historical context;
   - fixed 30-day V2 window; no 7D/30D/90D or sender/receiver selector;
   - currency-separated ECharts timeline;
   - selected transaction marker.

7. **Local Account Network**
   - sender/receiver toggle if both payloads exist;
   - one bounded graph shown at a time.

8. **AI Investigation**
   - idle/loading/success/partial/unavailable/error;
   - direct structured analyst-summary sections;
   - Limits;
   - one follow-up.

9. **Supporting Transactions / Evidence**
   - bounded dense table rendered from display-ready supporting rows;
   - no per-row full Transaction Detail hydration;
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

The Transactions table renders the display-ready Account Transactions response directly; only a genuinely selected historical transaction may require one Transaction Detail request. Bank-Country Flows show every aggregate returned for the resolved context. Alert History shows the latest 100 rows with current review status and, when truncated, explicit copy such as “Showing latest 100 of 137 alerts.”

### UI-06 — AI Investigation
This is not a separate route. It is a focused state of a detail page.

State shown:
- Summary;
- Key observations;
- Patterns noticed;
- Limits;
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
- **Graph node click:** select/highlight node and show bounded relationship detail; “View Account” navigation only; never expand hops.
- **Graph hover:** tooltip with canonical short Bank+Account, direction/relationship counts, Bank Country metadata if provided.
- **Map hover:** show Sending/Receiving Bank Country + Bank IDs only.
- **Chart hover:** show timestamp/day, currency-specific amount, count, and selected-transaction marker where relevant.
- **AI invocation:** button changes to deterministic loading state; existing page remains intact.
- **AI failure:** inline panel text: “AI investigation is unavailable. Deterministic investigation evidence remains available.”
- **Follow-up:** 1–500 chars; reserve one submission while in progress and disable permanently only after a successful follow-up. Configuration/provider/infrastructure failure restores the available control.
- **Follow-up exhausted:** show “Follow-up already used”; do not auto-retry 409.
- **Historical alert context:** visible badge beside cutoff, e.g. “Historical context from Alert ALT-…”.
- **Detector detail expansion:** accordion under Account identity; no raw technical values dominate initial view.

---

## 9. EXACT DESIGN TOKENS

The executable token source is `frontend/src/styles.css`; chart/map tokens are composed in `frontend/src/theme/chartTheme.ts`. Representative frozen semantic values are:

```css
:root {
  /* Dark / default: neutral graphite */
  --bg-app: #0F1216;
  --bg-surface: #171B21;
  --bg-surface-subtle: #1D222A;
  --border-subtle: #2C333D;
  --text-primary: #F1F5F9;
  --text-secondary: #AAB4C0;
  --accent: #4EA1D3;
  --focus-ring: #60A5FA;

  --status-high-text: #FDA29B;
  --status-medium-text: #FDB022;
  --status-low-text: #A9C0D3;
  --status-unscored-text: #98A2B3;

  --font-ui: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --header-height: 56px;
  --content-max: 1480px;
  --control-height: 36px;
}

[data-theme="light"] {
  --bg-app: #F4F6F8;
  --bg-surface: #FFFFFF;
  --bg-surface-subtle: #F8FAFC;
  --border-subtle: #E2E8F0;
  --text-primary: #172033;
  --text-secondary: #526071;
  --accent: #1677C8;
  --focus-ring: #2F8ED6;

  --status-high-text: #B42318;
  --status-medium-text: #B54708;
  --status-low-text: #4F6B83;
  --status-unscored-text: #475467;
}
```

LOW is intentionally cool blue-gray and UNSCORED is neutral gray in both modes; LOW is never green and UNSCORED never masquerades as LOW. Map root/connected-country and incoming/outgoing meanings remain separately tokenized and unchanged across modes.

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
- AI: full width with direct analyst-summary sections;
- evidence table: full width.

### Account Detail
- identity strip: full width;
- observed activity: 4 equal compact metric cells;
- account network: full width 380px;
- transactions/counterparties: 7/5 columns at ≥1280;
- activity/currency: 8/4 columns;
- country flows/alert history: 6/6 columns;
- AI: full width.

### AI Investigation state
- detail content remains the page;
- AI summary remains within the existing full-width detail-page section;
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
| `InvestigationSummary` | summary + observations + patterns + attention points + limits | success/partial | AI |
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
- **UI-06 AI Investigation** defines: direct structured summary sections and follow-up states.

Implementation screenshots should be compared against these six approved references at approximately 1440px whenever the image files are supplied to the worker/user.

---

## 14. INTEGRATED IMPLEMENTATION CONSTRAINTS

- Do not reintroduce CaseSelector, `case_ref`, Person/Merchant, Synthetic Region, or V1 evidence semantics.
- Preserve deterministic Evidence V2 components outside the AI summary and AI-failure resilience.
- Do not calculate detector or investigation facts in TypeScript.
- Keep list filters in URL query parameters where practical.
- Normal runtime uses real `/api/v2` endpoints.
- Typed V2 fixtures are available only through the explicit fixture-development entrypoint.
- Bundle world GeoJSON locally.
- Prefer DOM labels around ECharts for critical semantics/accessibility.

---

## 16. DESIGN RISKS / OPEN QUESTIONS

1. **Alerts count summary:** do not add dashboard-style KPI cards unless the V2 list API explicitly provides cheap trustworthy aggregate counts. The approved design does not require them.
2. **Account high-level volume summaries:** show only fields supported by the final `/api/v2` contract. Do not synthesize totals client-side.
3. **Bank flags:** optional. Country names/ISO are authoritative; flags should not become the primary semantic cue.
4. **Map labels:** ECharts text can become cramped; critical route labels should live in DOM outside the map.
5. **Graph density:** max-25 still gets dense at laptop widths; prioritise labels for root/selected relationship and use tooltips for the rest.
6. **AI summary hierarchy:** generated synthesis must remain visually subordinate to authoritative deterministic detail sections.
7. **Historical account context:** UI must make historical origin/cutoff visible enough that users do not mistake it for current state.

No frozen-design contradiction remains in the integrated V2 frontend contract.

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
- [ ] AI visibly separates Summary, Key observations, Patterns noticed, and optional Limits without an advice section.
- [ ] AI loading/error does not hide deterministic content.
- [ ] Exactly one follow-up is supported.
- [ ] System / Light / Dark modes render the same layouts and semantic meanings, and the explicit choice persists.
- [ ] Normal development and production builds contain no fixture fallback; fixture mode is an explicit development command.
- [ ] Detail workspaces are route-level lazy-loaded so the initial list-route bundle does not import both detail pages.
- [ ] Design is readable around 1440px and usable on narrower laptops.
- [ ] Design is implementable with React + TypeScript + Vite + ECharts without inventing backend facts.

## 18. IMPLEMENTATION AUTHORITY

The integrated frontend under `frontend/src/` is authoritative for executable V2 behavior and is constrained by this design contract. Historical WP05 job tickets document delivery history only. Normal runtime connects to `/api/v2`; explicit fixture mode exists only for isolated development and contract work.
