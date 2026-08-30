import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import {
  buildApiUrl,
  getAccountDetail,
  getAlertDetail,
  getEvidence,
  getHealth,
  getTransactionDetail,
  listAlerts,
  startInvestigation,
  submitFollowUp,
  updateAlertReviewStatus,
} from "../src/api/client.ts";
import { buildAccountTransactionParams, buildTransactionSearchParams } from "../src/api/query.ts";
import { allowedReviewStatuses } from "../src/lib/workflow.ts";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(here, "..");
const source = (path: string) => readFile(resolve(frontendRoot, path), "utf8");

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function bank(bank_id: string, country_name: string, iso_alpha2: string) {
  return { bank_id, mapping_version: "bank-country-v1", country_name, iso_alpha2, centroid_latitude: 1, centroid_longitude: 2 };
}

function identity(account_ref: string, bank_id: string, account_id: string, country = "Canada", iso = "CA") {
  return { account_ref, source_dataset: "ibm-transactions", bank_id, account_id, bank_country: bank(bank_id, country, iso) };
}

function context(subject_type: "ACCOUNT" | "TRANSACTION" | "ALERT", subject_ref: string, kind: "SNAPSHOT" | "TRANSACTION" | "ALERT_ENTRY" = "SNAPSHOT") {
  return {
    subject_type,
    subject_ref,
    context_identity: { context_kind: kind, context_ref: subject_ref, context_time: "2025-01-03T00:00:00", snapshot_id: "snap_2" },
    context_time: "2025-01-03T00:00:00",
    detector_snapshot_id: "snap_2",
    detector_cutoff: "2025-01-03T00:00:00",
    root_account_refs: ["acct_root"],
    selected_transaction_ref: kind === "TRANSACTION" ? subject_ref : null,
    alert_ref: kind === "ALERT_ENTRY" ? subject_ref : null,
  };
}

function network(rootRef = "acct_root") {
  return {
    root: identity(rootRef, "B1", "ROOT"),
    context: { context_kind: "SNAPSHOT", context_ref: "snap_2", context_time: "2025-01-03T00:00:00", snapshot_id: "snap_2" },
    total_direct_counterparties: 1,
    shown_counterparties: 1,
    truncated: false,
    selection_rule_version: "ego-one-hop-v1",
    relationships: [{ counterparty: identity("acct_cp", "B2", "CP", "United Kingdom", "GB"), incoming_count: 2, outgoing_count: 3, total_count: 5, first_historical_timestamp: "2025-01-01T00:00:00", last_historical_timestamp: "2025-01-02T00:00:00", selected_relationship: true }],
  };
}

function supportingTransaction(ref: string) {
  return { transaction_ref: ref, transaction_timestamp: "2025-01-02T12:00:00", from_account_ref: "acct_root", from_bank_id: "B1", to_account_ref: "acct_cp", to_bank_id: "B2", amount_paid: "100", payment_currency: "CAD", amount_received: "70", receiving_currency: "GBP", payment_format: "Wire", cross_currency: true };
}

function txDetail(ref: string, supportRef: string | null = null) {
  const sender = identity("acct_root", "B1", "ROOT");
  const receiver = identity("acct_cp", "B2", "CP", "United Kingdom", "GB");
  const ctx = { ...context("TRANSACTION", ref, "TRANSACTION"), selected_transaction_ref: ref };
  return {
    context: ctx,
    transaction_facts: { transaction_ref: ref, transaction_timestamp: "2025-01-02T12:00:00", sender, receiver, amount_paid: "100", payment_currency: "CAD", amount_received: "70", receiving_currency: "GBP", payment_format: "Wire", cross_currency: true, currency_pair: "CAD -> GBP" },
    review_state: { transaction_ref: ref, snapshot_id: "snap_1", detector_cutoff: "2025-01-02T00:00:00", sender_band: "HIGH", receiver_band: "MEDIUM", aml_review_priority: "HIGH", derivation_code: "ENDPOINT_MATRIX", derivation_text: "Backend derivation.", alert_involvement: true, sender_related_alert_ref: "alert_a", receiver_related_alert_ref: null },
    bank_country_route: { transaction_ref: ref, sending_bank: sender.bank_country, receiving_bank: receiver.bank_country, same_bank_country: false, mapping_version: "bank-country-v1" },
    sender_account_card: { account: sender, network_review_band: "HIGH", detector_cutoff: "2025-01-02T00:00:00", observed_summary: "Backend sender summary." },
    receiver_account_card: { account: receiver, network_review_band: "MEDIUM", detector_cutoff: "2025-01-02T00:00:00", observed_summary: "Backend receiver summary." },
    investigation_indicators: [{ key: "relationship", title: "Counterparty relationship", observed_text: "Observed", detail: "Backend indicator detail.", evidence_id: "ev2.rel", ui_target: "investigation-indicators", supporting_transaction_refs: supportRef ? [supportRef] : [] }],
    activity_context: { range_start: "2024-12-03T00:00:00", range_end: "2025-01-02T12:00:00", buckets: [{ timestamp: "2025-01-01T00:00:00", currency: "CAD", incoming_amount: "5", outgoing_amount: "10", transaction_count: 2 }], selected_transaction: { transaction_ref: ref, timestamp: "2025-01-02T12:00:00", currency: "CAD", amount: "100" } },
    local_network_summary: { sender: network("acct_root"), receiver: network("acct_cp") },
    supporting_evidence_summary: [{ label: "E1", evidence_id: "ev2.rel", evidence_type: "COUNTERPARTY_RELATIONSHIP", subject_type: "TRANSACTION", subject_ref: ref, context_time: "2025-01-02T12:00:00", snapshot_id: "snap_1", detector_cutoff: "2025-01-02T00:00:00", facts: { seen_before: true }, ui_target: "supporting-evidence", supporting_transaction_count: supportRef ? 1 : 0, supporting_transactions: supportRef ? [supportingTransaction(supportRef)] : [], support_truncated: false }],
    indicators: { context: ctx.context_identity, account_network_behavior: {}, evidence_ids: ["ev2.rel"] },
    evidence_ids: ["ev2.rel"],
  };
}

function alertDetail() {
  return {
    context: { ...context("ALERT", "alert_a", "ALERT_ENTRY"), alert_ref: "alert_a" },
    alert: { alert_ref: "alert_a", account_ref: "acct_root", entry_snapshot_id: "snap_1", entry_cutoff: "2025-01-02T00:00:00", entry_score: 0.9, entry_rank: 4, entry_percentile: 99.2, reason_code: "ENTERED_HIGH", created_state: "NOT_REVIEWED", relevant_recent_transaction_count: 3 },
    account_identity: identity("acct_root", "B1", "ROOT"),
    detector_state: { snapshot_id: "snap_1", account_ref: "acct_root", scoring_eligible: true, network_pattern_score: 0.9, rank: 4, percentile: 99.2, network_review_band: "HIGH", unscored_reason: null },
    detector_support: null,
    evidence_ids: ["ev2.alert"],
    review_status: "IN_REVIEW",
  };
}

function withFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>, fn: () => Promise<void>) {
  const original = globalThis.fetch;
  globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) => handler(String(input), init)) as typeof fetch;
  return fn().finally(() => { globalThis.fetch = original; });
}

test("API base seam, dates, cursor and account transaction query preserve backend semantics", () => {
  assert.equal(buildApiUrl("/api/v2/health", "http://127.0.0.1:8000/"), "http://127.0.0.1:8000/api/v2/health");
  assert.equal(buildTransactionSearchParams({ cursor: "c1", date_from: "2025-01-01", date_to: "2025-01-02", alert_involvement: "false" }).toString(), "cursor=c1&alert_involvement=false&date_from=2025-01-01T00%3A00%3A00&date_to=2025-01-02T00%3A00%3A00");
  assert.equal(buildAccountTransactionParams({ origin_alert_ref: "alert_a", cursor: "next", limit: 25, direction: "BOTH" }).toString(), "origin_alert_ref=alert_a&cursor=next&limit=25&direction=BOTH");
});

test("real alert list uses /api/v2, maps backend Bank Country, and preserves cursor response", async () => {
  await withFetch((url) => {
    assert.match(url, /^\/api\/v2\/alerts\?/);
    return response({ items: [{ alert_ref: "alert_a", account_ref: "acct_root", bank_id: "B1", account_id: "ROOT", bank_country: bank("B1", "Canada", "CA"), network_review_band: "HIGH", entry_snapshot_id: "snap_1", entry_cutoff: "2025-01-02T00:00:00", primary_reason: "ENTERED_HIGH", relevant_recent_transaction_count: 3, review_status: "NOT_REVIEWED" }], next_cursor: "cursor-2", has_more: true });
  }, async () => {
    const page = await listAlerts({ limit: 1 });
    assert.equal(page.items[0].bank_country, "Canada");
    assert.equal(page.next_cursor, "cursor-2");
    assert.equal(page.has_more, true);
  });
});

test("production path never silently falls back to fixture data after network failure", async () => {
  await withFetch(() => Promise.reject(new Error("offline")), async () => {
    await assert.rejects(() => listAlerts({ limit: 1 }), (error: { code?: string }) => error.code === "NETWORK_ERROR");
  });
  const clientSource = await source("src/api/client.ts");
  assert.doesNotMatch(clientSource, /catch[\s\S]{0,160}fixtureList/);
});

test("health and alert detail use authoritative API fields", async () => {
  await withFetch((url) => {
    if (url === "/api/v2/health") return response({ status: "ok", runtime_db_ready: true, latest_snapshot_id: "snap_2", latest_snapshot_cutoff: "2025-01-03T00:00:00", ai_configured: false, product_version: "v2" });
    if (url === "/api/v2/alerts/alert_a") return response(alertDetail());
    return response({ error: { code: "NOT_FOUND", message: "Unexpected" } }, 404);
  }, async () => {
    assert.equal((await getHealth()).runtime_db_ready, true);
    const detail = await getAlertDetail("alert_a");
    assert.equal(detail.review_status, "IN_REVIEW");
    assert.equal(detail.network_pattern_score, "0.9");
    assert.equal(detail.account.bank_country, "Canada");
  });
});

test("review PATCH sends workflow state, propagates 409 conflicts, and UI transition set is forward-only", async () => {
  let calls = 0;
  await withFetch((_url, init) => {
    calls += 1;
    assert.equal(init?.method, "PATCH");
    assert.equal(init?.body, JSON.stringify({ review_status: calls === 1 ? "IN_REVIEW" : "NOT_REVIEWED" }));
    if (calls === 1) return response({ alert_ref: "alert_a", review_status: "IN_REVIEW", updated_at: "2025-01-03T00:00:00Z" });
    return response({ error: { code: "REVIEW_STATE_CONFLICT", message: "Review status transition is not allowed" } }, 409);
  }, async () => {
    assert.equal((await updateAlertReviewStatus("alert_a", "IN_REVIEW")).review_status, "IN_REVIEW");
    await assert.rejects(() => updateAlertReviewStatus("alert_a", "NOT_REVIEWED"), (error: { code?: string; status?: number }) => error.code === "REVIEW_STATE_CONFLICT" && error.status === 409);
  });
  assert.deepEqual(allowedReviewStatuses("NOT_REVIEWED"), ["NOT_REVIEWED", "IN_REVIEW"]);
  assert.deepEqual(allowedReviewStatuses("IN_REVIEW"), ["IN_REVIEW", "REVIEWED"]);
  assert.deepEqual(allowedReviewStatuses("REVIEWED"), ["REVIEWED"]);
});

test("transaction detail consumes corrected backend detail sections and hydrates bounded supporting rows", async () => {
  await withFetch((url) => {
    if (url === "/api/v2/transactions/txn_main") return response(txDetail("txn_main", "txn_support"));
    if (url === "/api/v2/transactions/txn_support") return response(txDetail("txn_support"));
    return response({ error: { code: "NOT_FOUND", message: "Unexpected" } }, 404);
  }, async () => {
    const detail = await getTransactionDetail("txn_main");
    assert.equal(detail.sender_account_card.observed_summary, "Backend sender summary.");
    assert.equal(detail.investigation_indicators[0].evidence_id, "ev2.rel");
    assert.equal(detail.bank_country_route.receiving.bank_country, "United Kingdom");
    assert.equal(detail.local_network_summary.sender?.relationships[0].total_count, 5);
    assert.equal(detail.supporting_evidence_summary[0].supporting_transactions[0].transaction_ref, "txn_support");
    assert.equal(detail.supporting_evidence_summary[0].supporting_transactions[0].aml_review_priority, "HIGH");
  });
});

test("account detail composes real detail, transactions, network, currency activity and alert review status", async () => {
  const rawAccountDetail = {
    account_identity: identity("acct_root", "B1", "ROOT"),
    context: { ...context("ACCOUNT", "acct_root"), alert_ref: "alert_a" },
    network_review_state: { snapshot_id: "snap_2", account_ref: "acct_root", scoring_eligible: true, network_pattern_score: 0.88, rank: 7, percentile: 98.5, network_review_band: "HIGH", unscored_reason: null },
    detector_support: { snapshot_id: "snap_2", account_ref: "acct_root", first_order_neighbor_count: 1, second_order_neighbor_count: 4, community_id_or_stable_snapshot_local_index: "c1", block_measure_1: 0.1, block_measure_2: 0.2, block_measure_3: 0.3, network_pattern_score: 0.88 },
    observed_activity: { account_ref: "acct_root", incoming_count: 4, outgoing_count: 6, distinct_counterparties: 1, incoming_distinct_counterparties: 1, outgoing_distinct_counterparties: 1, first_observed_timestamp: "2025-01-01T00:00:00", most_recent_observed_timestamp: "2025-01-02T12:00:00" },
    activity_over_time: [{ day: "2025-01-01", direction: "INCOMING", currency: "CAD", transaction_count: 2, total_amount: "50" }, { day: "2025-01-01", direction: "OUTGOING", currency: "CAD", transaction_count: 3, total_amount: "75" }],
    currency_activity: [{ currency: "CAD", incoming_count: 2, outgoing_count: 3, incoming_amount: "50", outgoing_amount: "75" }],
    bank_country_flows: [{ counterparty_country: "United Kingdom", counterparty_iso_alpha2: "GB", incoming_transaction_count: 2, outgoing_transaction_count: 3, distinct_counterparties: 1, latest_interaction: "2025-01-02T12:00:00" }],
    alert_history: [{ alert_ref: "alert_a", entry_snapshot_id: "snap_1", entry_cutoff: "2025-01-02T00:00:00", reason_code: "ENTERED_HIGH" }],
    evidence_ids: ["ev2.account"],
  };
  await withFetch((url) => {
    if (url === "/api/v2/accounts/acct_root?origin_alert_ref=alert_a") return response(rawAccountDetail);
    if (url === "/api/v2/accounts/acct_root/transactions?origin_alert_ref=alert_a&limit=50&direction=BOTH") return response({ items: [supportingTransaction("txn_1")], next_cursor: "next-account-tx", has_more: true });
    if (url === "/api/v2/accounts/acct_root/network?origin_alert_ref=alert_a") return response(network());
    if (url === "/api/v2/transactions/txn_1") return response(txDetail("txn_1"));
    if (url === "/api/v2/alerts/alert_a") return response(alertDetail());
    return response({ error: { code: "NOT_FOUND", message: `Unexpected ${url}` } }, 404);
  }, async () => {
    const detail = await getAccountDetail("acct_root", { origin_alert_ref: "alert_a" });
    assert.equal(detail.context.origin_alert_ref, "alert_a");
    assert.equal(detail.network_review_state.network_pattern_score, "0.88");
    assert.equal(detail.detector_support?.second_order_neighbor_count, 4);
    assert.equal(detail.currency_activity[0].outgoing_amount, "75");
    assert.equal(detail.bank_country_flows[0].bank_country, "United Kingdom");
    assert.equal(detail.account_network.relationships[0].counterparty_account_ref, "acct_cp");
    assert.equal(detail.transactions.next_cursor, "next-account-tx");
    assert.equal(detail.transactions.items[0].transaction_ref, "txn_1");
    assert.equal(detail.alert_history[0].review_status, "IN_REVIEW");
    assert.deepEqual(detail.activity_over_time.buckets.map((row) => row.direction), ["INCOMING", "OUTGOING"]);
  });
});

test("Evidence V2 is resolved by GET without client-side decoding or a model call", async () => {
  const rawEvidence = { evidence_id: "ev2.opaque.checksum", evidence_type: "TRANSACTION_FACTS", subject_type: "TRANSACTION", subject_ref: "txn_main", context_time: "2025-01-02T12:00:00", snapshot_id: "snap_1", detector_cutoff: "2025-01-02T00:00:00", facts: { payment_format: "Wire" }, ui_target: "transaction-facts", supporting_transaction_count: 1, supporting_transactions: [supportingTransaction("txn_support")], support_truncated: false };
  await withFetch((url) => {
    assert.equal(url, "/api/v2/evidence/ev2.opaque.checksum");
    return response(rawEvidence);
  }, async () => {
    const evidence = await getEvidence("ev2.opaque.checksum");
    assert.equal(evidence.label, null);
    assert.equal(evidence.supporting_transactions[0].transaction_ref, "txn_support");
  });
  const clientSource = await source("src/api/client.ts");
  assert.doesNotMatch(clientSource, /atob\(.*evidence|decodeEvidence|parseEvidenceId/i);
});

test("AI start uses structured backend response, follow-up uses one endpoint, and terminal 409 is preserved", async () => {
  let stage = 0;
  const aiResponse = {
    investigation_id: "inv_1", run_status: "SUCCESS", subject_type: "TRANSACTION", subject_ref: "txn_main", context: context("TRANSACTION", "txn_main", "TRANSACTION"),
    findings: [{ category: "OBSERVED_FACT", text: "Backend grounded finding.", evidence_ids: ["ev2.ai"] }], limits: [],
    display_evidence: [{ label: "E1", evidence: { evidence_id: "ev2.ai", evidence_type: "TRANSACTION_FACTS", subject_type: "TRANSACTION", subject_ref: "txn_main", context_time: "2025-01-02T12:00:00", snapshot_id: "snap_1", detector_cutoff: "2025-01-02T00:00:00", facts: {}, ui_target: "transaction-facts", supporting_transaction_count: 0, supporting_transactions: [], support_truncated: false } }],
  };
  await withFetch((url, init) => {
    stage += 1;
    if (stage === 1) {
      assert.equal(url, "/api/v2/investigations");
      assert.equal(init?.method, "POST");
      assert.deepEqual(JSON.parse(String(init?.body)), { subject_type: "TRANSACTION", subject_ref: "txn_main", origin_alert_ref: null, origin_transaction_ref: null });
      return response(aiResponse);
    }
    if (stage === 2) {
      assert.equal(url, "/api/v2/investigations/inv_1/follow-up");
      assert.equal(init?.body, JSON.stringify({ question: "What changed?" }));
      return response({ ...aiResponse, investigation_id: "inv_followup" });
    }
    return response({ error: { code: "FOLLOW_UP_ALREADY_USED", message: "The single follow-up for this investigation has already been used" } }, 409);
  }, async () => {
    const initial = await startInvestigation({ subject_type: "TRANSACTION", subject_ref: "txn_main", origin_alert_ref: null, origin_transaction_ref: null });
    assert.equal(initial.display_evidence[0].label, "E1");
    assert.equal((await submitFollowUp(initial.investigation_id, "What changed?")).investigation_id, "inv_followup");
    await assert.rejects(() => submitFollowUp(initial.investigation_id, "Again"), (error: { code?: string }) => error.code === "FOLLOW_UP_ALREADY_USED");
  });
});

test("deterministic detail remains outside the AI failure surface and transaction AI sends no forbidden origin", async () => {
  const txPage = await source("src/pages/TransactionDetailPage.tsx");
  assert.ok(txPage.indexOf('title="1. AML Review Priority"') < txPage.indexOf('title="8. AI Investigation"'));
  assert.match(txPage, /subject_type="TRANSACTION"[^>]+origin_alert_ref=\{null\} origin_transaction_ref=\{null\}/);
  const ai = await source("src/components/AIInvestigation.tsx");
  assert.match(ai, /AI investigation is unavailable\. Deterministic investigation evidence remains available\./);
  const accountPage = await source("src/pages/AccountDetailPage.tsx");
  assert.match(accountPage, /getAccountTransactions/);
  assert.match(accountPage, /<CursorPagination[^>]+hasNext=\{transactionPage\.has_more\}/);
});
