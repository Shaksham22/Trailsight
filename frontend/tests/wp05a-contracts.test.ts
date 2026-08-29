import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { ROOT_REDIRECT, APP_ROUTES } from "../src/lib/routes.ts";
import { buildAccountDetailHref, buildAccountOriginParams, buildAccountSearchParams, buildTransactionSearchParams } from "../src/api/query.ts";
import { REVIEW_STATUSES, reviewBandLabel } from "../src/lib/workflow.ts";
import { buildAccountBankCountryVisualModel, buildRouteVisualModel, activityBucketsForCurrency, activityCurrencies, graphTruncationText } from "../src/lib/visualization.ts";
import { evidenceFocusFromDisplay } from "../src/lib/evidence.ts";
import { fixtureGetAccountDetail, fixtureStartInvestigation, fixtureSubmitFollowUp, resetFixtureState } from "../src/api/fixtures.ts";
import type { AccountNetwork, ActivityContext, BankCountryFlowRow, BankCountryRoute } from "../src/api/types.ts";

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
  assert.match(lowRule, /var\(--low\)/);
  assert.doesNotMatch(lowRule.toLowerCase(), /green|safe/);
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
  assert.throws(() => buildAccountOriginParams({ origin_alert_ref: "ALT-1", origin_transaction_ref: "txn_x" }));
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

test("bounded graph surfaces backend truncation and no hop-expansion control", async () => {
  const network: AccountNetwork = { root: { account_ref: "a", bank_id: "001", account_id: "A", bank_country: "Canada" }, counterparties: [], relationships: [], total_direct_counterparties: 31, shown_counterparties: 24, truncated: true, selection_rule_version: "ego-one-hop-v1" };
  assert.match(graphTruncationText(network) ?? "", /Showing 24 of 31 direct counterparties/);
  const graphSource = await source("src/components/visualizations.tsx");
  assert.match(graphSource, /One hop only · no expansion/);
  assert.doesNotMatch(graphSource, /expand[- ]?(?:to )?(?:two|2)[- ]?hops/i);
});

test("activity timeline separates unlike currencies", () => {
  const activity: ActivityContext = { range_start: "2026-01-01", range_end: "2026-01-02", selected_transaction: null, buckets: [
    { timestamp: "2026-01-01", currency: "CAD", incoming_amount: "10", outgoing_amount: "2", transaction_count: 1 },
    { timestamp: "2026-01-01", currency: "USD", incoming_amount: "20", outgoing_amount: "4", transaction_count: 2 },
  ] };
  assert.deepEqual(activityCurrencies(activity), ["CAD", "USD"]);
  assert.deepEqual(activityBucketsForCurrency(activity, "CAD").map((row) => row.incoming_amount), ["10"]);
});

test("AI findings use only approved categories, backend citation labels, and evidence focus is deterministic", async () => {
  resetFixtureState();
  const result = await fixtureStartInvestigation({ subject_type: "TRANSACTION", subject_ref: "txn_x", origin_alert_ref: null, origin_transaction_ref: "txn_x" });
  assert.deepEqual(new Set(result.findings.map((finding) => finding.category)), new Set(["DETECTOR_OUTPUT", "OBSERVED_FACT", "INTERPRETATION"]));
  assert.deepEqual(result.display_evidence.slice(0, 3).map((evidence) => evidence.label), ["E1", "E2", "E3"]);
  const focus = evidenceFocusFromDisplay(result.display_evidence[0]);
  assert.equal(focus.uiTarget, result.display_evidence[0].ui_target);
  const aiSource = await source("src/components/AIInvestigation.tsx");
  const focusBody = aiSource.slice(aiSource.indexOf("async function focusEvidence"), aiSource.indexOf("async function sendFollowUp"));
  assert.doesNotMatch(focusBody, /startInvestigation/);
});

test("exactly one follow-up is accepted and the second is terminal", async () => {
  resetFixtureState();
  const first = await fixtureSubmitFollowUp("inv_fixture_test", "What prior interaction is visible?");
  assert.equal(first.run_status, "SUCCESS");
  await assert.rejects(() => fixtureSubmitFollowUp("inv_fixture_test", "Try again"), (error: { code?: string }) => error.code === "FOLLOW_UP_ALREADY_USED");
});

test("AI error state retains deterministic page structure and uses approved failure wording", async () => {
  const page = await source("src/pages/TransactionDetailPage.tsx");
  assert.ok(page.indexOf("1. AML Review Priority") < page.indexOf("8. AI Investigation"));
  const ai = await source("src/components/AIInvestigation.tsx");
  assert.match(ai, /AI investigation is unavailable\. Deterministic investigation evidence remains available\./);
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


test("Account Detail Section 4 stacks Transactions above Direct Counterparties at full content width", async () => {
  const page = await source("src/pages/AccountDetailPage.tsx");
  const start = page.indexOf('title="4. Transactions / Counterparties"');
  const end = page.indexOf('title="5. Activity Over Time"');
  const section = page.slice(start, end);
  assert.ok(start >= 0 && end > start);
  assert.match(section, /className="account-table-stack"/);
  assert.doesNotMatch(section, /split-7-5/);
  assert.ok(section.indexOf("<h3>Transactions</h3>") < section.indexOf("<h3>Direct counterparties</h3>"));
  const styles = await source("src/styles.css");
  assert.match(styles, /\.account-table-stack\{display:flex;flex-direction:column;/);
});

test("account Bank-Country visualization consumes flow rows and produces multiple bounded country connections", async () => {
  const detail = await fixtureGetAccountDetail("acct_sender000000000000001");
  const model = buildAccountBankCountryVisualModel(detail.account_identity.bank_country, detail.bank_country_flows);
  assert.equal(model.root?.bank_country, "Canada");
  assert.deepEqual(model.connections.map((connection) => connection.bankCountry), ["United Kingdom", "United States", "Singapore"]);
  assert.equal(model.outgoingLines.length, 3);
  assert.equal(model.incomingLines.length, 3);
  assert.match(model.summary, /Connected Bank Countries \(3\): Singapore, United Kingdom, United States/);
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
  assert.match(accountMap, /name: "Root Bank Country"/);
  assert.match(accountMap, /name: "Connected Bank Countries"/);
  assert.match(accountMap, /name: "Outgoing"/);
  assert.match(accountMap, /name: "Incoming"/);
  assert.match(accountMap, /scroll or pinch to zoom, drag to pan/);
  const styles = await source("src/styles.css");
  assert.match(styles, /\.chart--account-country-map\{height:500px\}/);
  assert.match(styles, /\.legend-country--root\{background:#D7B95B/);
  assert.match(styles, /\.legend-country--connected\{background:#287E98/);
  assert.match(styles, /\.legend-line--outgoing\{border-top-color:#B69CFF\}/);
  assert.match(styles, /\.legend-line--incoming\{border-top-color:#67D3A5\}/);
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
});

