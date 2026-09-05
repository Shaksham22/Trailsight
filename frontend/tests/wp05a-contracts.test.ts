import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { ROOT_REDIRECT, APP_ROUTES } from "../src/lib/routes.ts";
import { buildAccountDetailHref, buildAccountOriginParams, buildAccountSearchParams, buildTransactionDetailHref, buildTransactionSearchParams } from "../src/api/query.ts";
import { buildCurrencyAmountComparisons, directionAmountLines, formatDetectorStanding, summarizeTransactionCounts } from "../src/lib/accountOverview.ts";
import { formatUtc, formatUtcDate } from "../src/lib/format.ts";
import { REVIEW_STATUSES, reviewBandLabel } from "../src/lib/workflow.ts";
import { BANK_COUNTRY_MAP_GEOMETRY_NAMES, BANK_COUNTRY_OPTIONS, getBankCountryVisualizationCentroid } from "../src/lib/bankCountries.ts";
import { accountBankCountryTooltip, buildAccountBankCountryVisualModel, buildRouteVisualModel, activityBucketsForCurrency, activityCurrencies, graphTruncationText } from "../src/lib/visualization.ts";
import { TXN_SAME_COUNTRY, fixtureGetAccountDetail, fixtureGetTransactionDetail, fixtureStartInvestigation, fixtureSubmitFollowUp, resetFixtureState } from "../src/api/fixtures.ts";
import type { AccountNetwork, ActivityContext, BankCountryFlowRow, BankCountryRoute, CurrencyActivityRow } from "../src/api/types.ts";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const source = async (path: string) => readFile(resolve(root, path), "utf8");

test("root redirects to Alerts and top navigation has exactly the approved three workspaces", () => {
  assert.equal(ROOT_REDIRECT, "/alerts");
  assert.deepEqual(APP_ROUTES.map((route) => [route.path, route.label]), [["/alerts", "Alerts"], ["/transactions", "All Transactions"], ["/accounts", "Accounts"]]);
});

test("priority and band wording never turns LOW into a safety label and UNSCORED uses the approved wording", async () => {
  assert.equal(reviewBandLabel("LOW"), "LOW");
  assert.equal(reviewBandLabel("UNSCORED"), "Insufficient Network Context");
  const styles = await source("src/styles.css");
  const lowRule = styles.match(/\.pill--low\s*\{[^}]+\}/)?.[0] ?? "";
  assert.match(lowRule, /var\(--status-low-text\)/);
  assert.match(lowRule, /var\(--status-low-border\)/);
  assert.match(lowRule, /var\(--status-low-bg\)/);
  assert.doesNotMatch(lowRule.toLowerCase(), /green|safe/);
  for (const priority of ["high", "medium", "low", "unscored"]) {
    assert.match(styles, new RegExp(`--status-${priority}-text:`));
    assert.match(styles, new RegExp(`--status-${priority}-border:`));
    assert.match(styles, new RegExp(`--status-${priority}-bg:`));
  }
});

test("transaction/account browsing constructs server query parameters rather than loaded-page filter state", () => {
  const tx = buildTransactionSearchParams({ q: "txn_", priority: "HIGH", alert_involvement: "true", currency: "CAD", payment_format: "Wire", sending_bank_country: "Canada", receiving_bank_country: "United Kingdom", limit: 50, cursor: "opaque" });
  assert.equal(tx.get("q"), "txn_"); assert.equal(tx.get("priority"), "HIGH"); assert.equal(tx.get("cursor"), "opaque"); assert.equal(tx.get("limit"), "50"); assert.equal(tx.get("sending_bank_country"), "Canada");
  const accounts = buildAccountSearchParams({ q: "bank", band: "MEDIUM", bank_country: "United Kingdom", alert_involvement: "false", limit: 50 });
  assert.equal(accounts.get("band"), "MEDIUM"); assert.equal(accounts.get("bank_country"), "United Kingdom");
});

test("account links preserve exactly one historical origin and reject dual origins", () => {
  assert.equal(buildAccountDetailHref("acct_x", { origin_alert_ref: "ALT-1" }), "/accounts/acct_x?origin_alert_ref=ALT-1");
  assert.equal(buildAccountDetailHref("acct_x", { origin_transaction_ref: "txn_x" }), "/accounts/acct_x?origin_transaction_ref=txn_x");
  assert.equal(buildTransactionDetailHref("txn_x/y"), "/transactions/txn_x%2Fy");
  assert.throws(() => buildAccountOriginParams({ origin_alert_ref: "ALT-1", origin_transaction_ref: "txn_x" }));
});

test("visible transaction and account identifiers use native semantic links", async () => {
  const links = await source("src/components/links.tsx");
  const tables = await source("src/components/tables.tsx");
  const transactionDetail = await source("src/pages/TransactionDetailPage.tsx");
  const accountDetail = await source("src/pages/AccountDetailPage.tsx");
  const ui = await source("src/components/ui.tsx");

  assert.match(links, /import \{ Link \} from "react-router-dom"/);
  assert.match(links, /export function TransactionLink/);
  assert.match(links, /export function AccountLink/);
  assert.match(links, /event\.stopPropagation\(\)/);
  assert.doesNotMatch(links, /preventDefault|target=["']_blank|window\.open/);

  assert.match(tables, /<TransactionLink transactionRef=\{item\.transaction_ref\} \/>/);
  assert.match(tables, /origin_transaction_ref: item\.transaction_ref/);
  assert.match(tables, /origin_alert_ref: item\.alert_ref/);
  assert.match(tables, /<AccountLink value=\{item\} to=\{buildAccountDetailHref\(item\.account_ref\)\} showAccountRef \/>/);
  assert.match(tables, /onClick=\{\(\) => onOpen\(item\)\}/);
  assert.match(tables, /onKeyDown=\{rowKeyboardHandler\(\(\) => onOpen\(item\)\)\}/);

  assert.match(transactionDetail, /const senderHref = buildAccountDetailHref\(facts\.sender\.account_ref, \{ origin_transaction_ref: facts\.transaction_ref \}\)/);
  assert.match(transactionDetail, /const receiverHref = buildAccountDetailHref\(facts\.receiver\.account_ref, \{ origin_transaction_ref: facts\.transaction_ref \}\)/);
  assert.match(transactionDetail, /<AccountLink value=\{facts\.sender\} to=\{senderHref\} \/>/);
  assert.match(transactionDetail, /<AccountLink value=\{facts\.receiver\} to=\{receiverHref\} \/>/);
  assert.match(transactionDetail, /<Link className="button button--secondary button-link" to=\{href\}>View Account<\/Link>/);
  assert.doesNotMatch(transactionDetail, /<button[^>]+>View Account<\/button>/);

  assert.match(accountDetail, /buildAccountDetailHref\(relationship\.counterparty_account_ref\)/);
  assert.match(accountDetail, /<AccountLink value=\{node\} to=\{href\} \/>/);
  assert.match(accountDetail, /<AccountRefLink accountRef=\{relationship\.counterparty_account_ref\} to=\{href\} \/>/);
  assert.match(ui, /if \(event\.target !== event\.currentTarget\) return/);
});

test("historical alert fixture resolves the alert entry cutoff and HIGH entry band", async () => {
  const detail = await fixtureGetAccountDetail("acct_receiver000000000001", { origin_alert_ref: "ALT-2026-000153" });
  assert.equal(detail.context.detector_cutoff, "2026-08-18T00:00:00");
  assert.equal(detail.context.snapshot_id, "snap_2026_08_18");
  assert.equal(detail.network_review_state.network_review_band, "HIGH");
});

test("same-country map produces no fake route arc and preserves the required semantics", async () => {
  const point = { bank_id: "B001", bank_country: "Canada", iso_alpha2: "CA", centroid_latitude: 56.1304, centroid_longitude: -106.3468 };
  const route: BankCountryRoute = { sending: point, receiving: { ...point, bank_id: "B002" }, same_bank_country: true, mapping_version: "bank-country-v1" };
  const model = buildRouteVisualModel(route);
  assert.equal(model.summary, "Same bank-country route"); assert.deepEqual(model.routeLine, []);
  assert.match(await source("src/components/visualizations.tsx"), /Bank countries are deterministic synthetic metadata added by Trailsight\. They are not customer locations\./);
});

test("same-country transaction fixture keeps one unique graph node per account", async () => {
  const detail = await fixtureGetTransactionDetail(TXN_SAME_COUNTRY);
  for (const network of Object.values(detail.local_network_summary)) {
    if (!network) continue;
    const ids = [network.root.account_ref, ...network.counterparties.map((item) => item.account_ref)];
    assert.equal(new Set(ids).size, ids.length);
  }
});

test("bounded graph surfaces backend truncation and no hop-expansion control", async () => {
  const network: AccountNetwork = { root: { account_ref: "a", bank_id: "001", account_id: "A", bank_country: "Canada" }, counterparties: [], relationships: [], total_direct_counterparties: 31, shown_counterparties: 24, truncated: true, selection_rule_version: "ego-one-hop-v1" };
  assert.match(graphTruncationText(network) ?? "", /Showing 24 of 31 direct counterparties/);
  const graphSource = await source("src/components/visualizations.tsx");
  assert.match(graphSource, /One hop only · no expansion/);
  assert.doesNotMatch(graphSource, /expand[- ]?(?:to )?(?:two|2)[- ]?hops/i);
  const graphStart = graphSource.indexOf("export function AccountRelationshipGraph");
  const graphEnd = graphSource.indexOf("export function ActivityTimeline");
  const accountGraph = graphSource.slice(graphStart, graphEnd);
  assert.match(accountGraph, /graphInset = network\.counterparties\.length <= 1 \? "28%"/);
  assert.match(accountGraph, /left: graphInset, right: graphInset, top: graphInset, bottom: graphInset/);
  assert.match(accountGraph, /Selected relationship/);
  assert.doesNotMatch(accountGraph, /Selected transaction/);
});

test("activity timeline separates unlike currencies", () => {
  const activity: ActivityContext = { range_start: "2026-01-01", range_end: "2026-01-02", selected_transaction: null, buckets: [
    { timestamp: "2026-01-01", currency: "CAD", incoming_amount: "10", outgoing_amount: "2", transaction_count: 1 },
    { timestamp: "2026-01-01", currency: "USD", incoming_amount: "20", outgoing_amount: "4", transaction_count: 2 },
  ] };
  assert.deepEqual(activityCurrencies(activity), ["CAD", "USD"]);
  assert.deepEqual(activityBucketsForCurrency(activity, "CAD").map((row) => row.incoming_amount), ["10"]);
});

test("AI investigation renders the direct structured analyst summary contract", async () => {
  resetFixtureState();
  const result = await fixtureStartInvestigation({ subject_type: "TRANSACTION", subject_ref: "txn_x", origin_alert_ref: null, origin_transaction_ref: "txn_x" });
  assert.match(result.summary, /linked to a sender whose wider account connections/);
  assert.match(result.summary, /Smurfing is a pattern where transfers are spread across several accounts/);
  assert.match(result.summary, /12,840\.00 CAD and delivered 6,940\.12 GBP by Wire/);
  assert.doesNotMatch(result.summary, /endpoint account|structural network concern|counterparty|supplied activity/);
  assert.doesNotMatch(result.summary, /Network Pattern Score|rank|percentile|snapshot/);
  assert.equal(result.observations.length, 1);
  assert.equal(result.patterns.length, 1);
  const aiSource = await source("src/components/AIInvestigation.tsx");
  for (const heading of ["Summary", "Key observations", "Patterns noticed", "Limits"]) {
    assert.match(aiSource, new RegExp(heading));
  }
  assert.doesNotMatch(aiSource, /Bounded grounded assistance|AI can select and synthesize deterministic evidence|What to examine|attention_points/);
  assert.match(aiSource, /!!response\.limits\.length/);
  assert.doesNotMatch(aiSource, /EVIDENCE_VALIDATION_FAILED|display_evidence|evidence_ids/);
});

test("exactly one follow-up is accepted and the second is terminal", async () => {
  resetFixtureState();
  const first = await fixtureSubmitFollowUp("inv_fixture_test", "What prior interaction is visible?");
  assert.equal(first.run_status, "SUCCESS");
  await assert.rejects(() => fixtureSubmitFollowUp("inv_fixture_test", "Try again"), (error: { code?: string }) => error.code === "FOLLOW_UP_ALREADY_USED");
});

test("AI error state retains deterministic page structure and uses approved failure wording", async () => {
  const page = await source("src/pages/TransactionDetailPage.tsx");
  const accountPage = await source("src/pages/AccountDetailPage.tsx");
  assert.ok(page.indexOf('title="AML Review Priority"') < page.indexOf('title="AI Assessment"'));
  assert.ok(page.indexOf('title="AI Assessment"') < page.indexOf('title="Transaction Summary + Bank-Country Route"'));
  assert.match(page, /<AIInvestigation subject_type="TRANSACTION"/);
  assert.match(accountPage, /<AIInvestigation subject_type="ACCOUNT"/);
  const ai = await source("src/components/AIInvestigation.tsx");
  assert.match(ai, /AI investigation is unavailable\. Deterministic investigation evidence remains available\./);
  const unavailableStart = ai.indexOf('{status === "UNAVAILABLE"');
  const errorStart = ai.indexOf('{status === "ERROR"');
  const errorEnd = ai.indexOf("{error &&", errorStart);
  assert.ok(unavailableStart >= 0 && errorStart > unavailableStart && errorEnd > errorStart);
  assert.doesNotMatch(ai.slice(unavailableStart, errorStart), /Try again/);
  assert.match(ai.slice(errorStart, errorEnd), /onClick=\{investigate\}>Try again<\/button>/);
});

test("review workflow contains exactly three statuses", () => {
  assert.deepEqual([...REVIEW_STATUSES], ["NOT_REVIEWED", "IN_REVIEW", "REVIEWED"]);
});

test("transaction and account route changes explicitly clear stale subject state", async () => {
  const tx = await source("src/pages/TransactionDetailPage.tsx");
  const account = await source("src/pages/AccountDetailPage.tsx");
  assert.match(tx, /setDetail\(null\).*route ref change clears stale subject state/s);
  assert.match(account, /setDetail\(null\)/);
});


test("Account Investigation uses a canvas overview, integrated AI, and dashboard-first semantic order", async () => {
  const page = await source("src/pages/AccountDetailPage.tsx");
  assert.doesNotMatch(page, /title="\d+\./);
  assert.match(page, /className=\{[^}]+"account-opening evidence-focused"[^}]+"account-opening"\}/);
  assert.doesNotMatch(page, /<Section[^>]+title="Account Overview"/);

  const overviewStart = page.indexOf("<h2>Account Overview</h2>");
  const technicalStart = page.indexOf("<DetectorDetailsDisclosure detail={detail} />");
  const aiStart = page.indexOf("<h2>AI Assessment</h2>");
  const primeOverview = page.slice(overviewStart, technicalStart);
  const technicalDetails = page.slice(page.indexOf("function DetectorDetailsDisclosure"));
  assert.ok(overviewStart >= 0 && technicalStart > overviewStart && aiStart > technicalStart);
  assert.match(primeOverview, /account-identity-band/);
  assert.match(primeOverview, /overview-metric-band/);
  assert.match(primeOverview, /overview-primary-metrics/);
  const primaryMetricsStart = primeOverview.indexOf('<div className="overview-primary-metrics">');
  const comparisonStart = primeOverview.indexOf("<TransactionComparison");
  const primaryMetrics = primeOverview.slice(primaryMetricsStart, comparisonStart);
  assert.ok(primaryMetricsStart >= 0 && comparisonStart > primaryMetricsStart);
  assert.deepEqual([...primaryMetrics.matchAll(/data-overview-metric="([^"]+)"/g)].map((match) => match[1]), [
    "detector-standing",
    "incoming-transactions",
    "outgoing-transactions",
    "counterparties",
  ]);
  assert.match(primeOverview, /Detector standing/);
  assert.match(primeOverview, /Incoming transactions/);
  assert.match(primeOverview, /Outgoing transactions/);
  assert.match(primeOverview, /<span className="overview-transaction-group-title">Transaction activity<\/span>/);
  assert.match(primeOverview, /<TransactionComparison count=\{transactionComparison\} monetaryComparisons=\{monetaryComparisons\} \/>/);
  assert.doesNotMatch(primeOverview, /transactionComparison\.text/);
  const comparisonComponent = page.slice(page.indexOf("function TransactionComparison"), page.indexOf("function shortRef"));
  assert.match(comparisonComponent, /Transaction comparison/);
  assert.match(comparisonComponent, /Total activity/);
  assert.match(comparisonComponent, /Count difference/);
  assert.match(comparisonComponent, /Amount difference/);
  assert.match(comparisonComponent, /count\.totalText/);
  assert.match(comparisonComponent, /count\.differenceText/);
  assert.match(comparisonComponent, /comparison\.difference/);
  assert.doesNotMatch(comparisonComponent, /comparison\.(?:incoming|outgoing)/);
  assert.match(primeOverview, /incomingAmounts/);
  assert.match(primeOverview, /outgoingAmounts/);
  assert.match(primeOverview, /activity\.incoming_count/);
  assert.match(primeOverview, /activity\.outgoing_count/);
  assert.match(primeOverview, /activity\.distinct_counterparties/);
  assert.match(primeOverview, /account-overview__historical-context/);
  assert.match(page, /Data included through/);
  assert.match(page, /From Alert/);
  assert.match(page, /From Transaction/);
  assert.doesNotMatch(primeOverview, /Resolved account|Activity direction|Transaction Flow|network_pattern_score|state\.rank|account\.account_ref|DetectorCutoff/);
  assert.match(technicalDetails, /Canonical Account Ref/);
  assert.match(technicalDetails, /Exact Detector Cutoff/);
  assert.match(technicalDetails, /network_pattern_score/);
  assert.match(technicalDetails, /<dt>Rank<\/dt>/);
  assert.match(technicalDetails, /Eligible Population/);
  assert.match(technicalDetails, /Exact Percentile/);
  assert.match(technicalDetails, /first_order_neighbor_count/);
  assert.match(technicalDetails, /snapshot_id/);
  assert.match(technicalDetails, /Scoring eligibility/);

  const styles = await source("src/styles.css");
  assert.match(styles, /\.overview-primary-metrics\{[^}]*grid-template-columns:repeat\(4,minmax\(0,1fr\)\)/);
  assert.match(styles, /\.overview-metric--incoming\{[^}]*var\(--flow-incoming\)/);
  assert.match(styles, /\.overview-metric--outgoing\{[^}]*var\(--flow-outgoing\)/);
  assert.match(styles, /\.overview-metric__direction-label\{[^}]*color:var\(--direction-color\)[^}]*text-transform:uppercase/);
  assert.match(styles, /\.overview-transaction-group-title\{[^}]*display:block[^}]*font-size:11px[^}]*text-transform:uppercase/);
  assert.doesNotMatch(styles, /\.overview-transaction-group-title\{[^}]*display:none/);
  assert.doesNotMatch(styles.match(/\.overview-metric--incoming\{[^}]+\}/)?.[0] ?? "", /status-(?:high|medium|low)/);
  assert.doesNotMatch(styles.match(/\.overview-metric--outgoing\{[^}]+\}/)?.[0] ?? "", /status-(?:high|medium|low)/);
  assert.doesNotMatch(styles.match(/\.overview-metric--detector\{[^}]+\}/)?.[0] ?? "", /grid-row:1\/3/);
  assert.doesNotMatch(styles.match(/\.overview-metric--counterparties\{[^}]+\}/)?.[0] ?? "", /grid-row:1\/3/);
  assert.match(styles, /\.overview-comparison-stats\{[^}]*grid-template-columns:1fr 1fr 1\.5fr/);
  assert.match(styles, /\.overview-comparison-stats dt\{[^}]*font-size:11px[^}]*font-weight:600[^}]*text-transform:uppercase/);
  assert.match(styles, /@media\(max-width:1099px\)[\s\S]+\.overview-metric--detector\{grid-column:1;grid-row:1[\s\S]+\.overview-metric--counterparties\{grid-column:2;grid-row:1/);
  assert.match(styles, /@media\(max-width:699px\)[\s\S]+\.overview-metric--incoming\{grid-column:1;grid-row:2/);
  assert.match(styles, /@media\(max-width:699px\)[\s\S]+\.overview-metric--outgoing\{grid-column:2;grid-row:2/);

  const networkAnalysis = page.indexOf('title="Network & Flow Analysis"');
  const flowSummary = page.indexOf('title="Bank-Country Flow Summary"');
  const currency = page.indexOf("<h2>Currency Activity</h2>");
  const counterparties = page.indexOf("<h2>Direct Counterparties</h2>");
  const alertHistory = page.indexOf('title="Alert History"');
  const transactions = page.indexOf('title="Transactions"');
  assert.ok(aiStart < networkAnalysis && networkAnalysis < flowSummary);
  assert.ok(flowSummary < currency && currency < alertHistory);
  assert.ok(flowSummary < counterparties && counterparties < alertHistory);
  assert.ok(alertHistory < transactions);
  assert.doesNotMatch(page.slice(transactions + 1), /<Section[^>]+title=/);
  assert.doesNotMatch(page, /Activity Over Time|<ActivityTimeline/);

  const primaryArea = page.slice(networkAnalysis, flowSummary);
  assert.match(primaryArea, /className="primary-analysis-grid"/);
  assert.match(primaryArea, /AccountBankCountryConnectionsMap/);
  assert.match(primaryArea, /AccountRelationshipGraph/);
  assert.match(page, /className="secondary-analysis-grid"/);
  assert.match(styles, /\.primary-analysis-grid\{display:grid;grid-template-columns:minmax\(0,3fr\) minmax\(390px,2fr\)/);
  assert.match(styles, /\.primary-analysis-grid\{[^}]*gap:16px/);
  assert.match(styles, /\.section--analysis\{[^}]*border:0[^}]*background:transparent/);
  assert.match(styles, /\.primary-analysis-grid \.chart\{border:0;border-radius:0\}/);
  assert.match(styles, /\.secondary-analysis-grid\{display:grid;/);
  assert.match(styles, /@media\(max-width:1059px\)[\s\S]+\.primary-analysis-grid\{grid-template-columns:1fr\}/);
});

test("account overview count comparison reports the total and directional difference", () => {
  assert.deepEqual(summarizeTransactionCounts(29, 41), { total: 70, difference: 12, totalText: "70 transactions", differenceText: "12 more outgoing" });
  assert.deepEqual(summarizeTransactionCounts(41, 29), { total: 70, difference: 12, totalText: "70 transactions", differenceText: "12 more incoming" });
  assert.deepEqual(summarizeTransactionCounts(35, 35), { total: 70, difference: 0, totalText: "70 transactions", differenceText: "Balanced transaction count" });
});

test("account overview uses deterministic detector percentile context", () => {
  assert.deepEqual(formatDetectorStanding("99.5724619800"), { primary: "99.57th percentile", secondary: "Top 0.43% of eligible accounts" });
  assert.deepEqual(formatDetectorStanding("99.999"), { primary: "99.999th percentile", secondary: "Top 0.001% of eligible accounts" });
  assert.deepEqual(formatDetectorStanding(null), { primary: "Not scored", secondary: "Relative standing unavailable" });
});

test("account overview keeps per-currency direction totals separate and compares only shared currencies", () => {
  const rows: CurrencyActivityRow[] = [
    { currency: "USD", incoming_count: 29, outgoing_count: 41, incoming_amount: "18420.50", outgoing_amount: "25930.00" },
    { currency: "EUR", incoming_count: 7, outgoing_count: 5, incoming_amount: "3120.00", outgoing_amount: "1500.00" },
    { currency: "CAD", incoming_count: 2, outgoing_count: 0, incoming_amount: "890.00", outgoing_amount: "0.00" },
  ];
  assert.deepEqual(directionAmountLines(rows, "incoming").map((line) => line.text), ["USD 18,420.50", "EUR 3,120.00", "CAD 890.00"]);
  assert.deepEqual(directionAmountLines(rows, "outgoing").map((line) => line.text), ["USD 25,930.00", "EUR 1,500.00"]);
  assert.deepEqual(buildCurrencyAmountComparisons(rows), [
    { currency: "USD", difference: "USD 7,509.50 more outgoing" },
    { currency: "EUR", difference: "EUR 1,620.00 more incoming" },
  ]);
  assert.deepEqual(buildCurrencyAmountComparisons(rows.slice(0, 1)), [
    { currency: "USD", difference: "USD 7,509.50 more outgoing" },
  ]);
  assert.deepEqual(buildCurrencyAmountComparisons([
    { currency: "USD", incoming_count: 2, outgoing_count: 0, incoming_amount: "500.00", outgoing_amount: "0.00" },
    { currency: "EUR", incoming_count: 0, outgoing_count: 3, incoming_amount: "0.00", outgoing_amount: "420.00" },
  ]), []);
});

test("account Bank-Country visualization consumes flow rows and produces multiple bounded country connections", async () => {
  const detail = await fixtureGetAccountDetail("acct_sender000000000000001");
  const model = buildAccountBankCountryVisualModel(detail.account_identity.bank_country, detail.bank_country_flows);
  assert.equal(model.root?.bank_country, "Canada");
  assert.deepEqual(model.connections.map((connection) => connection.bankCountry), ["United Kingdom", "United States", "Singapore"]);
  assert.equal(model.outgoingLines.length, 3);
  assert.equal(model.incomingLines.length, 3);
  assert.equal(model.connections.find((connection) => connection.bankCountry === "United States")?.geometryName, "United States of America");
  assert.deepEqual(model.polygonUnavailableCountries, ["Singapore"]);
  assert.match(model.summary, /Connected Bank Countries \(3\): Singapore, United Kingdom, United States/);
});

test("every configured Bank Country has a centroid and either valid polygon mapping or intentional marker-only handling", async () => {
  const geo = JSON.parse(await source("src/assets/world.geo.json")) as { features: Array<{ properties: { name: string } }> };
  const featureNames = new Set(geo.features.map((feature) => feature.properties.name));
  for (const country of BANK_COUNTRY_OPTIONS) {
    assert.ok(getBankCountryVisualizationCentroid(country), `${country} must have a centroid`);
    const geometryName = BANK_COUNTRY_MAP_GEOMETRY_NAMES[country];
    if (geometryName === null) {
      assert.equal(country, "Singapore");
    } else {
      assert.ok(featureNames.has(geometryName), `${country} must map to bundled GeoJSON`);
    }
  }
});

test("account Bank-Country same-country flow highlights the root without fabricating an international route", () => {
  const flows: BankCountryFlowRow[] = [{ bank_country: "Canada", incoming_transaction_count: 4, outgoing_transaction_count: 7, distinct_counterparties: 2, latest_interaction: "2026-08-20T00:00:00" }];
  const model = buildAccountBankCountryVisualModel("Canada", flows);
  assert.equal(model.connections[0]?.sameCountry, true);
  assert.deepEqual(model.incomingLines, []);
  assert.deepEqual(model.outgoingLines, []);
});

test("account Bank-Country map remains synthetic metadata visualization and introduces no country-risk semantics", async () => {
  const visualizations = await source("src/components/visualizations.tsx");
  assert.match(visualizations, /Bank countries are deterministic synthetic metadata added by Trailsight\. They are not customer locations\./);
  const accountMapStart = visualizations.indexOf("export function AccountBankCountryConnectionsMap");
  const graphStart = visualizations.indexOf("export function AccountRelationshipGraph");
  const accountMap = visualizations.slice(accountMapStart, graphStart);
  assert.doesNotMatch(accountMap, /country risk|risk score|customer geography|nationality/i);
});

test("account Bank-Country map enables bounded zoom/pan and keeps root, connected countries, and flow directions visually distinct", async () => {
  const visualizations = await source("src/components/visualizations.tsx");
  const accountMapStart = visualizations.indexOf("export function AccountBankCountryConnectionsMap");
  const graphStart = visualizations.indexOf("export function AccountRelationshipGraph");
  const accountMap = visualizations.slice(accountMapStart, graphStart);
  assert.match(accountMap, /roam: true/);
  assert.match(accountMap, /scaleLimit: \{ min: 1, max: 6 \}/);
  assert.match(accountMap, /zoom: 1,/);
  assert.match(accountMap, /layoutSize: "96%"/);
  assert.match(accountMap, /ACCOUNT_BANK_COUNTRY_SEMANTICS\.root\.seriesName/);
  assert.match(accountMap, /ACCOUNT_BANK_COUNTRY_SEMANTICS\.connected\.seriesName/);
  assert.match(accountMap, /ACCOUNT_BANK_COUNTRY_SEMANTICS\.outgoing\.seriesName/);
  assert.match(accountMap, /ACCOUNT_BANK_COUNTRY_SEMANTICS\.incoming\.seriesName/);
  assert.match(accountMap, /Scroll\/pinch to zoom · Drag to pan · Hover for details/);
  assert.match(accountMap, /Root: \$\{rootBankCountry\} · Connected:/);
  assert.doesNotMatch(accountMap, /<p className="visual-helper">\{model\.summary\}<\/p>/);
  const styles = await source("src/styles.css");
  assert.match(styles, /\.chart--account-country-map\{height:500px\}/);
  assert.match(styles, /\.legend-country--root\{background:var\(--map-root\)/);
  assert.match(styles, /\.legend-country--connected\{background:var\(--map-connected\)/);
  assert.match(styles, /\.legend-line--outgoing\{border-top-color:var\(--flow-outgoing\)\}/);
  assert.match(styles, /\.legend-line--incoming\{border-top-color:var\(--flow-incoming\)\}/);
  const page = await source("src/pages/AccountDetailPage.tsx");
  assert.match(page, /<AccountBankCountryConnectionsMap key=\{`\$\{account\.account_ref\}\|\$\{detail\.context\.snapshot_id\}\|\$\{detail\.context\.detector_cutoff\}/);
});

test("account Bank-Country hover details remain deterministic and include bounded flow facts", async () => {
  const visualizations = await source("src/components/visualizations.tsx");
  const accountMapStart = visualizations.indexOf("export function AccountBankCountryConnectionsMap");
  const graphStart = visualizations.indexOf("export function AccountRelationshipGraph");
  const accountMap = visualizations.slice(accountMapStart, graphStart);
  assert.match(accountMap, /Incoming transactions:/);
  assert.match(accountMap, /Outgoing transactions:/);
  assert.match(accountMap, /Distinct counterparties:/);
  assert.match(accountMap, /Latest interaction:/);
  assert.match(accountMap, /formatter: \(params: unknown\) => accountBankCountryTooltip\(params, regionTooltips\)/);
  const tooltips = new Map([["Canada", "Root Bank Country · Canada"]]);
  assert.equal(accountBankCountryTooltip({ name: "Canada" }, tooltips), "Root Bank Country · Canada");
  assert.equal(accountBankCountryTooltip({ name: "Somalia" }, tooltips), "");
  assert.equal(accountBankCountryTooltip({ data: { tooltipText: "Incoming flow · 2" } }, tooltips), "Incoming flow · 2");
});

test("transaction activity context is explicitly sender-rooted for the prior 30 days", async () => {
  const page = await source("src/pages/TransactionDetailPage.tsx");
  assert.match(page, /title="Sender Activity — Prior 30 Days"/);
  assert.doesNotMatch(page, /title="\d+\./);
});

test("visible timestamps use a deterministic, human-friendly explicit UTC format", () => {
  const previousTimezone = process.env.TZ;
  try {
    process.env.TZ = "America/Los_Angeles";
    const pacific = formatUtc("2022-09-03T21:17:00Z");
    const pacificDate = formatUtcDate("2022-09-19T00:00:00Z");
    process.env.TZ = "Asia/Tokyo";
    const tokyo = formatUtc("2022-09-03T21:17:00Z");
    const tokyoDate = formatUtcDate("2022-09-19T00:00:00Z");
    assert.equal(pacific, "Sep 3, 2022 · 9:17 PM UTC");
    assert.equal(tokyo, pacific);
    assert.equal(tokyoDate, pacificDate);
    assert.equal(formatUtc("2022-09-19T00:00:00Z"), "Sep 19, 2022 · 12:00 AM UTC");
    assert.equal(formatUtc("2022-09-19T00:00:00"), "Sep 19, 2022 · 12:00 AM UTC");
    assert.equal(formatUtcDate("2022-09-19T00:00:00Z"), "Sep 19, 2022");
    assert.equal(formatUtcDate("not-a-timestamp"), "not-a-timestamp");
    assert.equal(formatUtc("not-a-timestamp"), "not-a-timestamp");
    assert.equal(formatUtc("2022-02-30T00:00:00Z"), "2022-02-30T00:00:00Z");
  } finally {
    if (previousTimezone === undefined) delete process.env.TZ;
    else process.env.TZ = previousTimezone;
  }
});

test("truncated account alert history states the shown and total counts", async () => {
  const page = await source("src/pages/AccountDetailPage.tsx");
  assert.match(page, /Showing latest \{detail\.alert_history\.length\} of \{detail\.alert_history_total\} alerts/);
});
