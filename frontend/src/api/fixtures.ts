import type {
  AccountDetailResponse,
  AccountIdentity,
  AccountListItem,
  AccountOrigin,
  AccountQuery,
  AccountTransactionQuery,
  AccountNetwork,
  AlertDetailResponse,
  AlertListItem,
  AlertQuery,
  BankCountryRoutePoint,
  CursorPage,
  EvidenceDisplay,
  HealthResponse,
  InvestigationRequest,
  InvestigationResponse,
  ReviewBand,
  ReviewWorkflowStatus,
  SupportingTransactionRow,
  TransactionDetailResponse,
  TransactionListItem,
  TransactionQuery,
} from "./types.ts";

const wait = () => new Promise((resolve) => setTimeout(resolve, 80));
const snapshotId = "snap_2026_08_20";
const cutoff = "2026-08-20T00:00:00";

const countryRoutePoints: Record<string, Omit<BankCountryRoutePoint, "bank_id">> = {
  CA: { bank_country: "Canada", iso_alpha2: "CA", centroid_latitude: 56.1304, centroid_longitude: -106.3468 },
  GB: { bank_country: "United Kingdom", iso_alpha2: "GB", centroid_latitude: 55.3781, centroid_longitude: -3.436 },
  US: { bank_country: "United States", iso_alpha2: "US", centroid_latitude: 37.0902, centroid_longitude: -95.7129 },
  SG: { bank_country: "Singapore", iso_alpha2: "SG", centroid_latitude: 1.3521, centroid_longitude: 103.8198 },
};

const account = (accountRef: string, bankId: string, accountId: string, iso: keyof typeof countryRoutePoints): AccountIdentity => ({
  account_ref: accountRef,
  bank_id: bankId,
  account_id: accountId,
  bank_country: countryRoutePoints[iso].bank_country,
});

const bankRoutePoint = (identity: AccountIdentity): BankCountryRoutePoint => {
  const metadata = Object.values(countryRoutePoints).find((country) => country.bank_country === identity.bank_country);
  if (!metadata) throw new Error(`Fixture bank-country metadata missing for ${identity.bank_country}.`);
  return { bank_id: identity.bank_id, ...metadata };
};

export const ACCOUNTS = {
  sender: account("acct_sender000000000000001", "B105", "A016568", "CA"),
  receiver: account("acct_receiver000000000001", "B220", "A013644", "GB"),
  sameCountry: account("acct_samecountry000000001", "B310", "A010240", "CA"),
  other: account("acct_other00000000000001", "B440", "A019330", "US"),
  sg: account("acct_sg00000000000000001", "B550", "A011450", "SG"),
};

export const TXN_MAIN = `txn_${"a".repeat(64)}`;
export const TXN_SAME_COUNTRY = `txn_${"b".repeat(64)}`;
export const TXN_OTHER = `txn_${"c".repeat(64)}`;

const transaction = (
  transaction_ref: string,
  timestamp: string,
  sender: AccountIdentity,
  receiver: AccountIdentity,
  amount_paid: string,
  payment_currency: string,
  amount_received: string,
  receiving_currency: string,
  payment_format: string,
  aml_review_priority: TransactionListItem["aml_review_priority"],
  related_alert: boolean,
): TransactionListItem => ({
  transaction_ref,
  timestamp,
  sender,
  receiver,
  amount_paid,
  payment_currency,
  amount_received,
  receiving_currency,
  payment_format,
  aml_review_priority,
  related_alert,
});

const transactions: TransactionListItem[] = [
  transaction(TXN_MAIN, "2026-08-20T14:36:00", ACCOUNTS.sender, ACCOUNTS.receiver, "12840.00", "CAD", "6940.12", "GBP", "Wire", "HIGH", true),
  transaction(TXN_SAME_COUNTRY, "2026-08-20T12:10:00", ACCOUNTS.sender, ACCOUNTS.sameCountry, "4200.00", "CAD", "4200.00", "CAD", "ACH", "MEDIUM", true),
  transaction(TXN_OTHER, "2026-08-19T18:42:00", ACCOUNTS.other, ACCOUNTS.sender, "2100.00", "USD", "2861.14", "CAD", "Wire", "LOW", false),
  transaction(`txn_${"d".repeat(64)}`, "2026-08-19T09:22:00", ACCOUNTS.sg, ACCOUNTS.receiver, "8450.00", "SGD", "4930.00", "GBP", "Card", "UNSCORED", false),
];

const accountRows: AccountListItem[] = [
  { ...ACCOUNTS.sender, network_review_band: "HIGH", network_pattern_score: "0.88421", latest_snapshot_id: snapshotId, latest_detector_cutoff: cutoff, incoming_count: 148, outgoing_count: 231, alert_involvement: true },
  { ...ACCOUNTS.receiver, network_review_band: "MEDIUM", network_pattern_score: "0.61108", latest_snapshot_id: snapshotId, latest_detector_cutoff: cutoff, incoming_count: 202, outgoing_count: 91, alert_involvement: true },
  { ...ACCOUNTS.sameCountry, network_review_band: "LOW", network_pattern_score: "0.18772", latest_snapshot_id: snapshotId, latest_detector_cutoff: cutoff, incoming_count: 31, outgoing_count: 44, alert_involvement: false },
  { ...ACCOUNTS.other, network_review_band: "UNSCORED", network_pattern_score: null, latest_snapshot_id: snapshotId, latest_detector_cutoff: cutoff, incoming_count: 3, outgoing_count: 1, alert_involvement: false },
];

let alertStatuses: Record<string, ReviewWorkflowStatus> = {
  "ALT-2026-000184": "NOT_REVIEWED",
  "ALT-2026-000153": "IN_REVIEW",
  "ALT-2026-000122": "REVIEWED",
};

const baseAlerts: Omit<AlertListItem, "review_status">[] = [
  { alert_ref: "ALT-2026-000184", ...ACCOUNTS.sender, network_review_band: "HIGH" as const, entry_snapshot_id: snapshotId, entry_cutoff: cutoff, primary_reason: "ENTERED_HIGH", relevant_recent_transaction_count: 18 },
  { alert_ref: "ALT-2026-000153", ...ACCOUNTS.receiver, network_review_band: "HIGH" as const, entry_snapshot_id: "snap_2026_08_18", entry_cutoff: "2026-08-18T00:00:00", primary_reason: "RE-ENTERED_HIGH", relevant_recent_transaction_count: 9 },
  { alert_ref: "ALT-2026-000122", ...ACCOUNTS.other, network_review_band: "HIGH" as const, entry_snapshot_id: "snap_2026_08_16", entry_cutoff: "2026-08-16T00:00:00", primary_reason: "ENTERED_HIGH", relevant_recent_transaction_count: 4 },
].map(({ account_ref, bank_id, account_id, bank_country, ...rest }) => ({ account_ref, bank_id, account_id, bank_country, ...rest }));

const evidenceIds = {
  priority: "ev2.fixture.transaction-priority.1",
  facts: "ev2.fixture.transaction-facts.2",
  route: "ev2.fixture.bank-country-route.3",
  network: "ev2.fixture.network-behavior.4",
  activity: "ev2.fixture.account-activity.5",
  relationship: "ev2.fixture.counterparty-relationship.6",
};

const supportingRows: SupportingTransactionRow[] = transactions.slice(1).map((row) => ({ ...row, relationship_to_subject: "Direct one-hop relationship" }));

function evidence(label: string, evidence_id: string, evidence_type: EvidenceDisplay["evidence_type"], ui_target: EvidenceDisplay["ui_target"], facts: EvidenceDisplay["facts"]): EvidenceDisplay {
  return {
    label,
    evidence_id,
    evidence_type,
    subject_type: ui_target === "account-network" || ui_target === "activity-context" ? "ACCOUNT" : "TRANSACTION",
    subject_ref: ui_target === "account-network" || ui_target === "activity-context" ? ACCOUNTS.sender.account_ref : TXN_MAIN,
    context_time: "2026-08-20T14:36:00",
    snapshot_id: snapshotId,
    detector_cutoff: cutoff,
    facts,
    ui_target,
    supporting_transaction_count: supportingRows.length,
    supporting_transactions: supportingRows,
    support_truncated: false,
  };
}

const evidenceCatalog: EvidenceDisplay[] = [
  evidence("E1", evidenceIds.priority, "TRANSACTION_PRIORITY", "review-priority", { priority: "HIGH", sender_band: "HIGH", receiver_band: "MEDIUM" }),
  evidence("E2", evidenceIds.facts, "TRANSACTION_FACTS", "transaction-facts", { payment_format: "Wire", payment_currency: "CAD", receiving_currency: "GBP" }),
  evidence("E3", evidenceIds.route, "BANK_COUNTRY_ROUTE", "bank-country-route", { sending_bank_country: "Canada", receiving_bank_country: "United Kingdom", same_bank_country: false }),
  evidence("E4", evidenceIds.network, "NETWORK_BEHAVIOR", "account-network", { total_direct_counterparties: 31, shown_counterparties: 4, truncated: true }),
  evidence("E5", evidenceIds.activity, "ACCOUNT_ACTIVITY", "activity-context", { prior_24h_count: 18, fan_out_24h: 7 }),
  evidence("E6", evidenceIds.relationship, "COUNTERPARTY_RELATIONSHIP", "investigation-indicators", { seen_before: false, previous_interaction_count: 0 }),
];

const activityBuckets = [
  { timestamp: "2026-08-14T00:00:00", currency: "CAD", incoming_amount: "8200", outgoing_amount: "11250", transaction_count: 9 },
  { timestamp: "2026-08-15T00:00:00", currency: "CAD", incoming_amount: "9400", outgoing_amount: "6800", transaction_count: 7 },
  { timestamp: "2026-08-16T00:00:00", currency: "CAD", incoming_amount: "4200", outgoing_amount: "15400", transaction_count: 11 },
  { timestamp: "2026-08-17T00:00:00", currency: "CAD", incoming_amount: "10800", outgoing_amount: "12500", transaction_count: 10 },
  { timestamp: "2026-08-18T00:00:00", currency: "CAD", incoming_amount: "5100", outgoing_amount: "18100", transaction_count: 14 },
  { timestamp: "2026-08-19T00:00:00", currency: "CAD", incoming_amount: "2861.14", outgoing_amount: "8700", transaction_count: 12 },
  { timestamp: "2026-08-20T00:00:00", currency: "CAD", incoming_amount: "4500", outgoing_amount: "12840", transaction_count: 18 },
  { timestamp: "2026-08-18T00:00:00", currency: "USD", incoming_amount: "1500", outgoing_amount: "2400", transaction_count: 3 },
  { timestamp: "2026-08-19T00:00:00", currency: "USD", incoming_amount: "2100", outgoing_amount: "0", transaction_count: 2 },
  { timestamp: "2026-08-20T00:00:00", currency: "GBP", incoming_amount: "0", outgoing_amount: "6940.12", transaction_count: 1 },
];

function network(root: AccountIdentity, selectedCounterparty: AccountIdentity) {
  const cps = [selectedCounterparty, ACCOUNTS.sameCountry, ACCOUNTS.other, ACCOUNTS.sg].filter((a) => a.account_ref !== root.account_ref);
  return {
    root,
    counterparties: cps.map((cp) => ({ ...cp, is_root: false })),
    relationships: cps.map((cp, index) => ({
      counterparty_account_ref: cp.account_ref,
      incoming_count: index + 2,
      outgoing_count: (index + 1) * 3,
      total_count: index + 2 + (index + 1) * 3,
      first_historical_timestamp: `2026-07-${String(10 + index).padStart(2, "0")}T09:00:00`,
      last_historical_timestamp: `2026-08-${String(15 + index).padStart(2, "0")}T18:20:00`,
      selected_relationship: cp.account_ref === selectedCounterparty.account_ref,
    })),
    total_direct_counterparties: 31,
    shown_counterparties: cps.length,
    truncated: true,
    selection_rule_version: "ego-one-hop-v1" as const,
  };
}

function detailFor(tx: TransactionListItem): TransactionDetailResponse {
  const same = tx.sender.bank_country === tx.receiver.bank_country;
  const senderBand: ReviewBand = tx.transaction_ref === TXN_MAIN ? "HIGH" : tx.aml_review_priority;
  const receiverBand: ReviewBand = tx.transaction_ref === TXN_MAIN ? "MEDIUM" : "LOW";
  return {
    review_state: {
      aml_review_priority: tx.aml_review_priority,
      sender_band: senderBand,
      receiver_band: receiverBand,
      applicable_snapshot_id: snapshotId,
      detector_cutoff: cutoff,
      alert_involvement: tx.related_alert,
      derivation_text: tx.aml_review_priority === "HIGH"
        ? "HIGH review priority because the sender was in the HIGH Network Review Band at the applicable historical detector snapshot."
        : tx.aml_review_priority === "UNSCORED"
          ? "Insufficient network context at the applicable historical detector snapshot."
          : `${tx.aml_review_priority} review priority from the backend-returned endpoint-band matrix at the applicable historical detector snapshot.`,
    },
    transaction_facts: { ...tx, cross_currency: tx.payment_currency !== tx.receiving_currency, currency_pair: `${tx.payment_currency} → ${tx.receiving_currency}` },
    bank_country_route: {
      sending: bankRoutePoint(tx.sender),
      receiving: bankRoutePoint(tx.receiver),
      same_bank_country: same,
      mapping_version: "bank-country-v1",
    },
    sender_account_card: { account: tx.sender, network_review_band: senderBand, detector_cutoff: cutoff, observed_summary: "18 transactions in the prior 24h; 7 distinct outgoing counterparties in the same bounded context." },
    receiver_account_card: { account: tx.receiver, network_review_band: receiverBand, detector_cutoff: cutoff, observed_summary: "11 transactions in the prior 24h; 5 distinct incoming counterparties in the same bounded context." },
    investigation_indicators: [
      { key: "velocity", title: "Prior 24h activity", observed_text: "18 transactions before context time", detail: "Incoming and outgoing activity is counted in the fixed prior-24-hour window; this is an observed fact, not a threshold verdict.", evidence_id: evidenceIds.activity, ui_target: "investigation-indicators", supporting_transaction_refs: supportingRows.map((r) => r.transaction_ref) },
      { key: "relationship", title: "Counterparty relationship", observed_text: "No prior interaction in the resolved context", detail: "The selected sender and receiver have no earlier transaction before this transaction timestamp in the bounded relationship evidence.", evidence_id: evidenceIds.relationship, ui_target: "investigation-indicators", supporting_transaction_refs: [] },
      { key: "currency", title: "Currency route", observed_text: tx.payment_currency === tx.receiving_currency ? "Same-currency transfer" : `${tx.payment_currency} → ${tx.receiving_currency}`, detail: "Currency is displayed exactly as returned by deterministic transaction facts. No FX-rate or fee inference is made.", evidence_id: evidenceIds.facts, ui_target: "investigation-indicators", supporting_transaction_refs: [] },
    ],
    activity_context: { range_start: "2026-08-14T00:00:00", range_end: tx.timestamp, buckets: activityBuckets, selected_transaction: { transaction_ref: tx.transaction_ref, timestamp: tx.timestamp, currency: tx.payment_currency, amount: tx.amount_paid } },
    local_network_summary: { sender: network(tx.sender, tx.receiver), receiver: network(tx.receiver, tx.sender) },
    supporting_evidence_summary: evidenceCatalog.map((item) => ({ ...item, label: item.label ?? "Resolved evidence", supporting_transactions: supportingRows })),
  };
}

function accountDetailFor(identity: AccountIdentity, origin: AccountOrigin = {}): AccountDetailResponse {
  const historical = Boolean(origin.origin_alert_ref || origin.origin_transaction_ref);
  const originAlert = origin.origin_alert_ref ? baseAlerts.find((alert) => alert.alert_ref === origin.origin_alert_ref) : undefined;
  const resolvedCutoff = originAlert?.entry_cutoff ?? cutoff;
  const resolvedSnapshot = originAlert?.entry_snapshot_id ?? snapshotId;
  const contextTime = origin.origin_transaction_ref ? "2026-08-20T14:36:00" : originAlert?.entry_cutoff ?? "2026-08-21T00:00:00";
  const latestBand: ReviewBand = identity.account_ref === ACCOUNTS.sender.account_ref ? "HIGH" : identity.account_ref === ACCOUNTS.receiver.account_ref ? "MEDIUM" : identity.account_ref === ACCOUNTS.sameCountry.account_ref ? "LOW" : "UNSCORED";
  const band: ReviewBand = originAlert ? "HIGH" : latestBand;
  const accountNetwork = network(identity, identity.account_ref === ACCOUNTS.sender.account_ref ? ACCOUNTS.receiver : ACCOUNTS.sender);
  return {
    account_identity: identity,
    context: { context_time: contextTime, snapshot_id: resolvedSnapshot, detector_cutoff: resolvedCutoff, origin_alert_ref: origin.origin_alert_ref ?? null, origin_transaction_ref: origin.origin_transaction_ref ?? null },
    network_review_state: {
      network_review_band: band,
      network_pattern_score: band === "UNSCORED" ? null : band === "HIGH" ? "0.88421" : band === "MEDIUM" ? "0.61108" : "0.18772",
      rank: band === "UNSCORED" ? null : band === "HIGH" ? 42 : band === "MEDIUM" ? 3200 : 48000,
      percentile: band === "UNSCORED" ? null : band === "HIGH" ? "99.84" : band === "MEDIUM" ? "96.41" : "58.20",
      scoring_eligible: band !== "UNSCORED",
      unscored_reason: band === "UNSCORED" ? "INSUFFICIENT_NETWORK_CONTEXT" : null,
    },
    detector_support: {
      first_order_neighbor_count: 31,
      second_order_neighbor_count: 112,
      community_id_or_stable_snapshot_local_index: "fixture-community-7",
      block_measure_1: "0.42",
      block_measure_2: "0.31",
      block_measure_3: "0.27",
    },
    observed_activity: {
      incoming_count: 148,
      outgoing_count: 231,
      distinct_counterparties: 31,
      incoming_distinct_counterparties: 19,
      outgoing_distinct_counterparties: 24,
      first_observed_timestamp: "2026-07-01T00:00:00",
      most_recent_observed_timestamp: contextTime,
    },
    activity_over_time: { range_start: "2026-08-14T00:00:00", range_end: contextTime, buckets: activityBuckets, selected_transaction: origin.origin_transaction_ref ? { transaction_ref: origin.origin_transaction_ref, timestamp: contextTime, currency: "CAD", amount: "12840.00" } : null },
    currency_activity: [
      { currency: "CAD", incoming_count: 92, outgoing_count: 142, incoming_amount: "182410.14", outgoing_amount: "266441.00" },
      { currency: "USD", incoming_count: 21, outgoing_count: 18, incoming_amount: "42210.00", outgoing_amount: "38410.25" },
      { currency: "GBP", incoming_count: 9, outgoing_count: 11, incoming_amount: "15400.00", outgoing_amount: "22940.12" },
    ],
    bank_country_flows: [
      { bank_country: "United Kingdom", incoming_transaction_count: 18, outgoing_transaction_count: 26, distinct_counterparties: 8, latest_interaction: "2026-08-20T14:36:00" },
      { bank_country: "United States", incoming_transaction_count: 16, outgoing_transaction_count: 11, distinct_counterparties: 5, latest_interaction: "2026-08-19T18:42:00" },
      { bank_country: "Singapore", incoming_transaction_count: 4, outgoing_transaction_count: 8, distinct_counterparties: 3, latest_interaction: "2026-08-18T10:10:00" },
    ],
    alert_history: baseAlerts.slice(0, 2).map((a) => ({ ...a, review_status: alertStatuses[a.alert_ref] })),
    alert_history_total: baseAlerts.length,
    alert_history_truncated: baseAlerts.length > 2,
    account_network: accountNetwork,
    transactions: { items: supportingRows, next_cursor: null, has_more: false },
    counterparties: accountNetwork.relationships,
  };
}

function page<T>(items: T[], cursor?: string | null, limit = 50): CursorPage<T> {
  const offset = cursor ? Number(atob(cursor)) || 0 : 0;
  const sliced = items.slice(offset, offset + limit);
  const nextOffset = offset + sliced.length;
  return { items: sliced, next_cursor: nextOffset < items.length ? btoa(String(nextOffset)) : null, has_more: nextOffset < items.length };
}


export async function fixtureGetHealth(): Promise<HealthResponse> {
  await wait();
  return { status: "ok", runtime_db_ready: true, latest_snapshot_id: snapshotId, latest_snapshot_cutoff: cutoff, ai_configured: true, product_version: "v2-fixture" };
}

export async function fixtureGetAlertDetail(alertRef: string): Promise<AlertDetailResponse> {
  await wait();
  const alert = baseAlerts.find((item) => item.alert_ref === alertRef);
  if (!alert) throw { code: "NOT_FOUND", message: "Alert not found.", status: 404 };
  return {
    alert_ref: alert.alert_ref,
    account: { account_ref: alert.account_ref, bank_id: alert.bank_id, account_id: alert.account_id, bank_country: alert.bank_country },
    review_status: alertStatuses[alert.alert_ref] ?? "NOT_REVIEWED",
    entry_snapshot_id: alert.entry_snapshot_id,
    entry_cutoff: alert.entry_cutoff,
    reason_code: alert.primary_reason,
    network_review_band: alert.network_review_band,
    network_pattern_score: "0.88421",
    rank: 42,
    percentile: "99.84",
    scoring_eligible: true,
    unscored_reason: null,
    evidence_ids: [evidenceIds.priority, evidenceIds.activity],
  };
}

export async function fixtureListAlerts(query: AlertQuery): Promise<CursorPage<AlertListItem>> {
  await wait();
  let items = baseAlerts.map((a) => ({ ...a, review_status: alertStatuses[a.alert_ref] }));
  const q = query.q?.trim();
  if (q) items = items.filter((a) => (
    a.alert_ref.startsWith(q)
    || a.account_ref.startsWith(q)
    || a.account_id.startsWith(q)
    || a.bank_id.startsWith(q)
  ));
  if (query.review_status) items = items.filter((a) => a.review_status === query.review_status);
  if (query.bank_country) items = items.filter((a) => a.bank_country === query.bank_country);
  return page(items, query.cursor, query.limit);
}

export async function fixtureUpdateAlertReviewStatus(alertRef: string, reviewStatus: ReviewWorkflowStatus) {
  await wait();
  if (!baseAlerts.some((a) => a.alert_ref === alertRef)) throw { code: "NOT_FOUND", message: "Alert not found.", status: 404 };
  const current = alertStatuses[alertRef] ?? "NOT_REVIEWED";
  const allowed: Record<ReviewWorkflowStatus, readonly ReviewWorkflowStatus[]> = {
    NOT_REVIEWED: ["NOT_REVIEWED", "IN_REVIEW"],
    IN_REVIEW: ["IN_REVIEW", "REVIEWED"],
    REVIEWED: ["REVIEWED"],
  };
  if (!allowed[current].includes(reviewStatus)) throw { code: "REVIEW_STATE_CONFLICT", message: "Review status cannot move backward.", status: 409 };
  alertStatuses = { ...alertStatuses, [alertRef]: reviewStatus };
  return { alert_ref: alertRef, review_status: reviewStatus, updated_at: "2026-08-26T17:20:00-04:00" };
}

export async function fixtureListTransactions(query: TransactionQuery): Promise<CursorPage<TransactionListItem>> {
  await wait();
  let items = [...transactions];
  const q = query.q?.trim().toLowerCase();
  if (q) items = items.filter((t) => [t.transaction_ref, t.sender.account_id, t.sender.bank_id, t.receiver.account_id, t.receiver.bank_id].some((v) => v.toLowerCase().startsWith(q)));
  if (query.priority) items = items.filter((t) => t.aml_review_priority === query.priority);
  if (query.alert_involvement) items = items.filter((t) => String(t.related_alert) === query.alert_involvement);
  if (query.currency) items = items.filter((t) => t.payment_currency === query.currency || t.receiving_currency === query.currency);
  if (query.payment_format) items = items.filter((t) => t.payment_format === query.payment_format);
  if (query.sending_bank_country) items = items.filter((t) => t.sender.bank_country === query.sending_bank_country);
  if (query.receiving_bank_country) items = items.filter((t) => t.receiver.bank_country === query.receiving_bank_country);
  if (query.date_from) items = items.filter((t) => t.timestamp >= query.date_from!);
  if (query.date_to) items = items.filter((t) => t.timestamp < query.date_to!);
  return page(items, query.cursor, query.limit);
}

export async function fixtureGetTransactionDetail(transactionRef: string): Promise<TransactionDetailResponse> {
  await wait();
  const tx = transactions.find((t) => t.transaction_ref === transactionRef);
  if (!tx) throw { code: "NOT_FOUND", message: "Transaction not found.", status: 404 };
  return detailFor(tx);
}

export async function fixtureListAccounts(query: AccountQuery): Promise<CursorPage<AccountListItem>> {
  await wait();
  let items = [...accountRows];
  const q = query.q?.trim().toLowerCase();
  if (q) items = items.filter((a) => a.account_id.toLowerCase().startsWith(q) || a.bank_id.toLowerCase().startsWith(q));
  if (query.band) items = items.filter((a) => a.network_review_band === query.band);
  if (query.bank_country) items = items.filter((a) => a.bank_country === query.bank_country);
  if (query.alert_involvement) items = items.filter((a) => String(a.alert_involvement) === query.alert_involvement);
  return page(items, query.cursor, query.limit);
}


export async function fixtureGetAccountTransactions(accountRef: string, query: AccountTransactionQuery = {}): Promise<CursorPage<SupportingTransactionRow>> {
  await wait();
  const identity = Object.values(ACCOUNTS).find((item) => item.account_ref === accountRef);
  if (!identity) throw { code: "NOT_FOUND", message: "Account not found.", status: 404 };
  let items = supportingRows.filter((row) => row.sender.account_ref === accountRef || row.receiver.account_ref === accountRef);
  if (query.currency) items = items.filter((row) => row.payment_currency === query.currency || row.receiving_currency === query.currency);
  if (query.counterparty_account_ref) items = items.filter((row) => row.sender.account_ref === query.counterparty_account_ref || row.receiver.account_ref === query.counterparty_account_ref);
  return page(items, query.cursor, query.limit);
}

export async function fixtureGetAccountNetwork(accountRef: string, origin: AccountOrigin = {}): Promise<AccountNetwork> {
  const detail = await fixtureGetAccountDetail(accountRef, origin);
  return detail.account_network;
}

export async function fixtureGetAccountDetail(accountRef: string, origin: AccountOrigin = {}): Promise<AccountDetailResponse> {
  await wait();
  if (origin.origin_alert_ref && origin.origin_transaction_ref) throw { code: "INVALID_CONTEXT", message: "Only one origin reference may be supplied.", status: 400 };
  const identity = Object.values(ACCOUNTS).find((a) => a.account_ref === accountRef);
  if (!identity) throw { code: "NOT_FOUND", message: "Account not found.", status: 404 };
  return accountDetailFor(identity, origin);
}

export async function fixtureGetEvidence(evidenceId: string): Promise<EvidenceDisplay> {
  await wait();
  const item = evidenceCatalog.find((e) => e.evidence_id === evidenceId);
  if (!item) throw { code: "NOT_FOUND", message: "Evidence not found.", status: 404 };
  return item;
}

export async function fixtureStartInvestigation(body: InvestigationRequest): Promise<InvestigationResponse> {
  await wait();
  const transactionSubject = body.subject_type === "TRANSACTION";
  return {
    investigation_id: `inv_fixture_${body.subject_type.toLowerCase()}`,
    run_status: "SUCCESS",
    subject_type: body.subject_type,
    subject_ref: body.subject_ref,
    context: { context_time: body.origin_transaction_ref ? "2026-08-20T14:36:00" : cutoff, snapshot_id: snapshotId, detector_cutoff: cutoff },
    summary: transactionSubject
      ? "This transaction is linked to a sender whose wider account connections strongly resemble smurfing under GARG’s analysis. Smurfing is a pattern where transfers are spread across several accounts to make the money trail harder to follow. This transfer sent 12,840.00 CAD and delivered 6,940.12 GBP by Wire."
      : "GARG found strong evidence that this account’s wider connections resemble smurfing—a pattern where transfers are spread across several accounts to make the money trail harder to follow. Six new accounts appeared in its recent activity, and three outgoing transfers were for similar amounts. Together, these facts strengthen the concern.",
    observations: transactionSubject
      ? ["The transfer is cross-currency, between accounts whose bank metadata maps to Canada and the United Kingdom."]
      : ["The account sent or received money with 31 other accounts across 379 transfers: 148 incoming and 231 outgoing."],
    patterns: transactionSubject
      ? ["The cross-currency wire appears alongside the stronger smurfing-like pattern found in the sender’s wider account connections."]
      : ["Six new relationships and repeated similar-size outgoing transfers appear alongside more outgoing than incoming activity."],
    limits: [],
  };
}

let followUpUsed = new Set<string>();
export async function fixtureSubmitFollowUp(investigationId: string, question: string): Promise<InvestigationResponse> {
  await wait();
  if (question.trim().length < 1 || question.trim().length > 500) throw { code: "INVALID_INPUT", message: "Follow-up must contain 1–500 characters.", status: 400 };
  if (followUpUsed.has(investigationId)) throw { code: "FOLLOW_UP_ALREADY_USED", message: "Follow-up already used.", status: 409 };
  followUpUsed.add(investigationId);
  return {
    investigation_id: investigationId,
    run_status: "SUCCESS",
    subject_type: "TRANSACTION",
    subject_ref: TXN_MAIN,
    context: { context_time: "2026-08-20T14:36:00", snapshot_id: snapshotId, detector_cutoff: cutoff },
    summary: "The selected sender and receiver have no earlier interaction in the resolved historical context.",
    observations: ["No earlier interaction is present in the supplied relationship context."],
    patterns: [],
    limits: [],
  };
}

export function resetFixtureState() {
  followUpUsed = new Set<string>();
  alertStatuses = { "ALT-2026-000184": "NOT_REVIEWED", "ALT-2026-000153": "IN_REVIEW", "ALT-2026-000122": "REVIEWED" };
}
