import {
  buildAccountOriginParams,
  buildAccountSearchParams,
  buildAccountTransactionParams,
  buildAlertSearchParams,
  buildTransactionSearchParams,
} from "./query.ts";
import { fixtureApi } from "./fixtureBoundary.ts";
import type {
  AccountDetailResponse,
  AccountIdentity,
  AccountNetwork,
  AccountOrigin,
  AccountQuery,
  AccountListItem,
  AccountTransactionQuery,
  AlertDetailResponse,
  AlertListItem,
  AlertQuery,
  ApplicationError,
  CursorPage,
  EvidenceDisplay,
  EvidenceType,
  EvidenceUiTarget,
  HealthResponse,
  InvestigationRequest,
  InvestigationResponse,
  ReviewWorkflowStatus,
  SupportingTransactionRow,
  TransactionDetailResponse,
  TransactionEvidenceDisplay,
  TransactionListItem,
  TransactionQuery,
} from "./types.ts";
import type {
  ApiAccountDetailV2,
  ApiAccountIdentityV2,
  ApiAccountListItemV2,
  ApiAccountNetworkV2,
  ApiAccountTransactionPageV2,
  ApiAlertDetailResponseV2,
  ApiAlertListItemV2,
  ApiBankCountryV2,
  ApiCursorPage,
  ApiDisplayEvidenceV2,
  ApiHealthResponseV2,
  ApiInvestigationResponseV2,
  ApiSupportingTransactionV2,
  ApiSupportingEvidenceSummaryItemV2,
  ApiTransactionDetailV2,
  ApiTransactionListItemV2,
} from "./transport.ts";

interface ViteLikeEnv {
  VITE_TRAILSIGHT_API_BASE_URL?: string;
}

const viteEnv = ((import.meta as ImportMeta & { env?: ViteLikeEnv }).env ?? {}) as ViteLikeEnv;
const configuredApiBaseUrl = (viteEnv.VITE_TRAILSIGHT_API_BASE_URL ?? "").trim().replace(/\/+$/, "");

/**
 * The empty default deliberately uses the Vite /api proxy in local development.
 * vite.config.ts proxies that path to http://127.0.0.1:8000, avoiding a CORS-only
 * frontend/backend coupling while retaining one explicit production base-URL seam.
 */
export const API_BASE_URL = configuredApiBaseUrl;

export function buildApiUrl(path: string, baseUrl = API_BASE_URL): string {
  if (!path.startsWith("/")) throw new Error("Trailsight API paths must start with '/'.");
  const normalizedBase = baseUrl.trim().replace(/\/+$/, "");
  return normalizedBase ? `${normalizedBase}${path}` : path;
}

function appError(code: string, message: string, status?: number): ApplicationError {
  return { code, message, status };
}

function isErrorEnvelope(value: unknown): value is { error: { code: string; message: string; request_id?: string | null } } {
  if (!value || typeof value !== "object" || !("error" in value)) return false;
  const error = (value as { error?: unknown }).error;
  return Boolean(error && typeof error === "object" && "code" in error && "message" in error);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildApiUrl(path), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw appError("NETWORK_ERROR", "Trailsight could not reach the application service.");
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    throw appError("INVALID_RESPONSE", "Trailsight received an invalid application response.", response.status);
  }

  if (!response.ok) {
    if (isErrorEnvelope(payload)) {
      throw { ...payload.error, status: response.status } satisfies ApplicationError;
    }
    throw appError("REQUEST_FAILED", "Trailsight could not complete the request.", response.status);
  }
  return payload as T;
}

export async function getHealth(): Promise<HealthResponse> {
  if (fixtureApi) return fixtureApi.fixtureGetHealth();
  return request<ApiHealthResponseV2>("/api/v2/health");
}

export async function listAlerts(query: AlertQuery): Promise<CursorPage<AlertListItem>> {
  if (fixtureApi) return fixtureApi.fixtureListAlerts(query);
  const raw = await request<ApiCursorPage<ApiAlertListItemV2>>(`/api/v2/alerts?${buildAlertSearchParams(query)}`);
  return mapPage(raw, adaptAlertListItem);
}

export async function getAlertDetail(alertRef: string): Promise<AlertDetailResponse> {
  if (fixtureApi) return fixtureApi.fixtureGetAlertDetail(alertRef);
  const raw = await request<ApiAlertDetailResponseV2>(`/api/v2/alerts/${encodeURIComponent(alertRef)}`);
  return adaptAlertDetail(raw);
}

export async function updateAlertReviewStatus(alertRef: string, reviewStatus: ReviewWorkflowStatus) {
  if (fixtureApi) return fixtureApi.fixtureUpdateAlertReviewStatus(alertRef, reviewStatus);
  return request<{ alert_ref: string; review_status: ReviewWorkflowStatus; updated_at: string }>(
    `/api/v2/alerts/${encodeURIComponent(alertRef)}/review-status`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ review_status: reviewStatus }) },
  );
}

export async function listTransactions(query: TransactionQuery): Promise<CursorPage<TransactionListItem>> {
  if (fixtureApi) return fixtureApi.fixtureListTransactions(query);
  const raw = await request<ApiCursorPage<ApiTransactionListItemV2>>(`/api/v2/transactions?${buildTransactionSearchParams(query)}`);
  return mapPage(raw, adaptTransactionListItem);
}

async function requestRawTransactionDetail(transactionRef: string): Promise<ApiTransactionDetailV2> {
  return request<ApiTransactionDetailV2>(`/api/v2/transactions/${encodeURIComponent(transactionRef)}`);
}

export async function getTransactionDetail(transactionRef: string): Promise<TransactionDetailResponse> {
  if (fixtureApi) return fixtureApi.fixtureGetTransactionDetail(transactionRef);
  const raw = await requestRawTransactionDetail(transactionRef);
  return adaptTransactionDetail(raw);
}

export async function listAccounts(query: AccountQuery): Promise<CursorPage<AccountListItem>> {
  if (fixtureApi) return fixtureApi.fixtureListAccounts(query);
  const raw = await request<ApiCursorPage<ApiAccountListItemV2>>(`/api/v2/accounts?${buildAccountSearchParams(query)}`);
  return mapPage(raw, adaptAccountListItem);
}

export async function getAccountTransactions(accountRef: string, query: AccountTransactionQuery = {}): Promise<CursorPage<SupportingTransactionRow>> {
  if (fixtureApi) return fixtureApi.fixtureGetAccountTransactions(accountRef, query);
  const params = buildAccountTransactionParams(query);
  const raw = await request<ApiAccountTransactionPageV2>(`/api/v2/accounts/${encodeURIComponent(accountRef)}/transactions?${params}`);
  return {
    items: raw.items.map((item) => ({ ...adaptTransactionListItem(item), relationship_to_subject: "Account transaction" })),
    next_cursor: raw.next_cursor,
    has_more: raw.has_more,
  };
}

export async function getAccountNetwork(accountRef: string, origin: AccountOrigin = {}): Promise<AccountNetwork> {
  if (fixtureApi) return fixtureApi.fixtureGetAccountNetwork(accountRef, origin);
  const params = buildAccountOriginParams(origin);
  const suffix = params.toString();
  const raw = await request<ApiAccountNetworkV2>(`/api/v2/accounts/${encodeURIComponent(accountRef)}/network${suffix ? `?${suffix}` : ""}`);
  return adaptAccountNetwork(raw);
}

export async function getAccountDetail(accountRef: string, origin: AccountOrigin = {}): Promise<AccountDetailResponse> {
  if (fixtureApi) return fixtureApi.fixtureGetAccountDetail(accountRef, origin);
  const params = buildAccountOriginParams(origin);
  const suffix = params.toString();
  const [raw, transactions, accountNetwork] = await Promise.all([
    request<ApiAccountDetailV2>(`/api/v2/accounts/${encodeURIComponent(accountRef)}${suffix ? `?${suffix}` : ""}`),
    getAccountTransactions(accountRef, { ...origin, limit: 50, direction: "BOTH" }),
    getAccountNetwork(accountRef, origin),
  ]);

  const selectedTransaction = raw.context.selected_transaction_ref
    ? await requestRawTransactionDetail(raw.context.selected_transaction_ref)
    : null;

  return adaptAccountDetail(raw, accountNetwork, transactions, selectedTransaction);
}

export async function getEvidence(evidenceId: string): Promise<EvidenceDisplay> {
  if (fixtureApi) return fixtureApi.fixtureGetEvidence(evidenceId);
  const raw = await request<ApiDisplayEvidenceV2>(`/api/v2/evidence/${encodeURIComponent(evidenceId)}`);
  return adaptEvidence(raw, null);
}

export async function startInvestigation(body: InvestigationRequest): Promise<InvestigationResponse> {
  if (fixtureApi) return fixtureApi.fixtureStartInvestigation(body);
  const raw = await request<ApiInvestigationResponseV2>("/api/v2/investigations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return adaptInvestigationResponse(raw);
}

export async function submitFollowUp(investigationId: string, question: string): Promise<InvestigationResponse> {
  if (fixtureApi) return fixtureApi.fixtureSubmitFollowUp(investigationId, question);
  const raw = await request<ApiInvestigationResponseV2>(`/api/v2/investigations/${encodeURIComponent(investigationId)}/follow-up`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return adaptInvestigationResponse(raw);
}

function adaptAccountIdentity(raw: Pick<ApiAccountIdentityV2, "account_ref" | "bank_id" | "account_id" | "bank_country">): AccountIdentity {
  return {
    account_ref: raw.account_ref,
    bank_id: raw.bank_id,
    account_id: raw.account_id,
    bank_country: raw.bank_country.country_name,
  };
}

function adaptAlertListItem(raw: ApiAlertListItemV2): AlertListItem {
  return {
    alert_ref: raw.alert_ref,
    account_ref: raw.account_ref,
    bank_id: raw.bank_id,
    account_id: raw.account_id,
    bank_country: raw.bank_country.country_name,
    network_review_band: raw.network_review_band,
    entry_snapshot_id: raw.entry_snapshot_id,
    entry_cutoff: raw.entry_cutoff,
    primary_reason: raw.primary_reason,
    relevant_recent_transaction_count: raw.relevant_recent_transaction_count,
    review_status: raw.review_status,
  };
}

function adaptAlertDetail(raw: ApiAlertDetailResponseV2): AlertDetailResponse {
  return {
    alert_ref: raw.alert.alert_ref,
    account: adaptAccountIdentity(raw.account_identity),
    review_status: raw.review_status,
    entry_snapshot_id: raw.alert.entry_snapshot_id,
    entry_cutoff: raw.alert.entry_cutoff,
    reason_code: raw.alert.reason_code,
    network_review_band: raw.detector_state.network_review_band,
    network_pattern_score: numberText(raw.detector_state.network_pattern_score),
    rank: raw.detector_state.rank,
    percentile: numberText(raw.detector_state.percentile),
    scoring_eligible: raw.detector_state.scoring_eligible,
    unscored_reason: raw.detector_state.unscored_reason,
    evidence_ids: [...raw.evidence_ids],
  };
}

function adaptTransactionListItem(raw: ApiTransactionListItemV2): TransactionListItem {
  return {
    transaction_ref: raw.transaction_ref,
    timestamp: raw.timestamp,
    sender: adaptAccountIdentity(raw.sender),
    receiver: adaptAccountIdentity(raw.receiver),
    amount_paid: raw.amount_paid,
    payment_currency: raw.payment_currency,
    amount_received: raw.amount_received,
    receiving_currency: raw.receiving_currency,
    payment_format: raw.payment_format,
    aml_review_priority: raw.aml_review_priority,
    related_alert: raw.related_alert !== null,
  };
}

function transactionListItemFromDetail(raw: ApiTransactionDetailV2): TransactionListItem {
  const facts = raw.transaction_facts;
  return {
    transaction_ref: facts.transaction_ref,
    timestamp: facts.transaction_timestamp,
    sender: adaptAccountIdentity(facts.sender),
    receiver: adaptAccountIdentity(facts.receiver),
    amount_paid: facts.amount_paid,
    payment_currency: facts.payment_currency,
    amount_received: facts.amount_received,
    receiving_currency: facts.receiving_currency,
    payment_format: facts.payment_format,
    aml_review_priority: raw.review_state.aml_review_priority,
    related_alert: raw.review_state.alert_involvement,
  };
}

function adaptSupportingTransaction(raw: ApiSupportingTransactionV2): SupportingTransactionRow {
  return {
    transaction_ref: raw.transaction_ref,
    timestamp: raw.transaction_timestamp,
    sender: {
      account_ref: raw.from_account_ref,
      bank_id: raw.from_bank_id,
      account_id: raw.from_account_id,
      bank_country: raw.from_bank_country.country_name,
    },
    receiver: {
      account_ref: raw.to_account_ref,
      bank_id: raw.to_bank_id,
      account_id: raw.to_account_id,
      bank_country: raw.to_bank_country.country_name,
    },
    amount_paid: raw.amount_paid,
    payment_currency: raw.payment_currency,
    amount_received: raw.amount_received,
    receiving_currency: raw.receiving_currency,
    payment_format: raw.payment_format,
    aml_review_priority: raw.aml_review_priority,
    related_alert: raw.related_alert !== null,
    relationship_to_subject: "Supporting evidence",
  };
}

function adaptAccountListItem(raw: ApiAccountListItemV2): AccountListItem {
  return {
    account_ref: raw.account_ref,
    bank_id: raw.bank_id,
    account_id: raw.account_id,
    bank_country: raw.bank_country.country_name,
    network_review_band: raw.network_review_band,
    network_pattern_score: numberText(raw.network_pattern_score),
    latest_snapshot_id: raw.latest_snapshot_id,
    latest_detector_cutoff: raw.latest_detector_cutoff,
    incoming_count: raw.incoming_count,
    outgoing_count: raw.outgoing_count,
    alert_involvement: raw.alert_involvement,
  };
}

function adaptAccountNetwork(raw: ApiAccountNetworkV2): AccountNetwork {
  return {
    root: adaptAccountIdentity(raw.root),
    counterparties: raw.relationships.map((relationship) => ({ ...adaptAccountIdentity(relationship.counterparty), is_root: false })),
    relationships: raw.relationships.map((relationship) => ({
      counterparty_account_ref: relationship.counterparty.account_ref,
      incoming_count: relationship.incoming_count,
      outgoing_count: relationship.outgoing_count,
      total_count: relationship.total_count,
      first_historical_timestamp: relationship.first_historical_timestamp,
      last_historical_timestamp: relationship.last_historical_timestamp,
      selected_relationship: relationship.selected_relationship,
    })),
    total_direct_counterparties: raw.total_direct_counterparties,
    shown_counterparties: raw.shown_counterparties,
    truncated: raw.truncated,
    selection_rule_version: raw.selection_rule_version,
  };
}

function adaptTransactionDetail(raw: ApiTransactionDetailV2): TransactionDetailResponse {
  const base = transactionListItemFromDetail(raw);
  if (!raw.review_state.detector_cutoff) {
    throw appError("INVALID_RESPONSE", "Transaction detail did not include its applicable detector cutoff.");
  }
  return {
    review_state: {
      aml_review_priority: raw.review_state.aml_review_priority,
      sender_band: raw.review_state.sender_band,
      receiver_band: raw.review_state.receiver_band,
      applicable_snapshot_id: raw.review_state.snapshot_id,
      detector_cutoff: raw.review_state.detector_cutoff,
      derivation_text: raw.review_state.derivation_text,
      alert_involvement: raw.review_state.alert_involvement,
    },
    transaction_facts: {
      ...base,
      cross_currency: raw.transaction_facts.cross_currency,
      currency_pair: raw.transaction_facts.currency_pair,
    },
    bank_country_route: {
      sending: adaptBankCountryRoutePoint(raw.bank_country_route.sending_bank),
      receiving: adaptBankCountryRoutePoint(raw.bank_country_route.receiving_bank),
      same_bank_country: raw.bank_country_route.same_bank_country,
      mapping_version: raw.bank_country_route.mapping_version,
    },
    sender_account_card: {
      account: adaptAccountIdentity(raw.sender_account_card.account),
      network_review_band: raw.sender_account_card.network_review_band,
      detector_cutoff: raw.sender_account_card.detector_cutoff,
      observed_summary: raw.sender_account_card.observed_summary,
    },
    receiver_account_card: {
      account: adaptAccountIdentity(raw.receiver_account_card.account),
      network_review_band: raw.receiver_account_card.network_review_band,
      detector_cutoff: raw.receiver_account_card.detector_cutoff,
      observed_summary: raw.receiver_account_card.observed_summary,
    },
    investigation_indicators: raw.investigation_indicators.map((item) => ({
      key: item.key,
      title: item.title,
      observed_text: item.observed_text,
      detail: item.detail,
      evidence_id: item.evidence_id,
      ui_target: item.ui_target as EvidenceUiTarget,
      supporting_transaction_refs: [...item.supporting_transaction_refs],
    })),
    activity_context: {
      range_start: raw.activity_context.range_start,
      range_end: raw.activity_context.range_end,
      buckets: raw.activity_context.buckets.map((bucket) => ({ ...bucket })),
      selected_transaction: raw.activity_context.selected_transaction ? { ...raw.activity_context.selected_transaction } : null,
    },
    local_network_summary: {
      sender: raw.local_network_summary.sender ? adaptAccountNetwork(raw.local_network_summary.sender) : null,
      receiver: raw.local_network_summary.receiver ? adaptAccountNetwork(raw.local_network_summary.receiver) : null,
    },
    supporting_evidence_summary: raw.supporting_evidence_summary.map(adaptTransactionEvidence),
  };
}

function adaptTransactionEvidence(raw: ApiSupportingEvidenceSummaryItemV2): TransactionEvidenceDisplay {
  return {
    label: raw.label,
    evidence_id: raw.evidence_id,
    evidence_type: raw.evidence_type as EvidenceType,
    subject_type: raw.subject_type,
    subject_ref: raw.subject_ref,
    context_time: raw.context_time,
    snapshot_id: raw.snapshot_id,
    detector_cutoff: raw.detector_cutoff,
    facts: raw.facts,
    ui_target: raw.ui_target as EvidenceUiTarget,
    supporting_transaction_count: raw.supporting_transaction_count,
    supporting_transactions: raw.supporting_transactions.map(adaptSupportingTransaction),
    support_truncated: raw.support_truncated,
  };
}

function adaptAccountDetail(
  raw: ApiAccountDetailV2,
  accountNetwork: AccountNetwork,
  transactions: CursorPage<SupportingTransactionRow>,
  selectedTransaction: ApiTransactionDetailV2 | null,
): AccountDetailResponse {
  const detectorSnapshotId = raw.context.detector_snapshot_id ?? raw.context.context_identity.snapshot_id;
  if (!detectorSnapshotId || !raw.context.detector_cutoff) {
    throw appError("INVALID_RESPONSE", "Account detail did not include its resolved detector context.");
  }
  const rawBuckets = raw.activity_over_time;
  const rangeStart = rawBuckets[0]?.day ?? raw.context.context_time;
  return {
    account_identity: adaptAccountIdentity(raw.account_identity),
    context: {
      context_time: raw.context.context_time,
      snapshot_id: detectorSnapshotId,
      detector_cutoff: raw.context.detector_cutoff,
      origin_alert_ref: raw.context.alert_ref,
      origin_transaction_ref: raw.context.selected_transaction_ref,
    },
    network_review_state: {
      network_review_band: raw.network_review_state.network_review_band,
      network_pattern_score: numberText(raw.network_review_state.network_pattern_score),
      rank: raw.network_review_state.rank,
      percentile: numberText(raw.network_review_state.percentile),
      scoring_eligible: raw.network_review_state.scoring_eligible,
      unscored_reason: raw.network_review_state.unscored_reason,
    },
    detector_support: raw.detector_support ? {
      first_order_neighbor_count: raw.detector_support.first_order_neighbor_count,
      second_order_neighbor_count: raw.detector_support.second_order_neighbor_count,
      community_id_or_stable_snapshot_local_index: raw.detector_support.community_id_or_stable_snapshot_local_index,
      block_measure_1: numberText(raw.detector_support.block_measure_1),
      block_measure_2: numberText(raw.detector_support.block_measure_2),
      block_measure_3: numberText(raw.detector_support.block_measure_3),
    } : null,
    observed_activity: { ...raw.observed_activity },
    activity_over_time: {
      range_start: rangeStart,
      range_end: raw.context.context_time,
      buckets: rawBuckets.map((bucket) => ({
        timestamp: bucket.day,
        currency: bucket.currency,
        incoming_amount: bucket.direction === "INCOMING" ? bucket.total_amount : "0",
        outgoing_amount: bucket.direction === "OUTGOING" ? bucket.total_amount : "0",
        transaction_count: bucket.transaction_count,
        direction: bucket.direction,
      })),
      selected_transaction: selectedTransaction ? {
        transaction_ref: selectedTransaction.transaction_facts.transaction_ref,
        timestamp: selectedTransaction.transaction_facts.transaction_timestamp,
        currency: selectedTransaction.transaction_facts.payment_currency,
        amount: selectedTransaction.transaction_facts.amount_paid,
      } : null,
    },
    currency_activity: raw.currency_activity.map((row) => ({ ...row })),
    bank_country_flows: raw.bank_country_flows.map((row) => ({
      bank_country: row.counterparty_country,
      iso_alpha2: row.counterparty_iso_alpha2,
      incoming_transaction_count: row.incoming_transaction_count,
      outgoing_transaction_count: row.outgoing_transaction_count,
      distinct_counterparties: row.distinct_counterparties,
      latest_interaction: row.latest_interaction,
    })),
    alert_history: raw.alert_history.map((item) => ({
      alert_ref: item.alert_ref,
      entry_snapshot_id: item.entry_snapshot_id,
      entry_cutoff: item.entry_cutoff,
      primary_reason: item.reason_code,
      review_status: item.review_status,
    })),
    alert_history_total: raw.alert_history_total,
    alert_history_truncated: raw.alert_history_truncated,
    account_network: accountNetwork,
    transactions,
    counterparties: accountNetwork.relationships,
  };
}

function adaptEvidence(raw: ApiDisplayEvidenceV2, label: string | null): EvidenceDisplay {
  return {
    label,
    evidence_id: raw.evidence_id,
    evidence_type: raw.evidence_type as EvidenceType,
    subject_type: raw.subject_type,
    subject_ref: raw.subject_ref,
    context_time: raw.context_time,
    snapshot_id: raw.snapshot_id,
    detector_cutoff: raw.detector_cutoff,
    facts: raw.facts,
    ui_target: raw.ui_target as EvidenceUiTarget,
    supporting_transaction_count: raw.supporting_transaction_count,
    supporting_transactions: raw.supporting_transactions.map((row) => ({ transaction_ref: row.transaction_ref })),
    support_truncated: raw.support_truncated,
  };
}

function adaptInvestigationResponse(raw: ApiInvestigationResponseV2): InvestigationResponse {
  return {
    investigation_id: raw.investigation_id,
    run_status: raw.run_status,
    subject_type: raw.subject_type,
    subject_ref: raw.subject_ref,
    context: {
      context_time: raw.context.context_time,
      snapshot_id: raw.context.detector_snapshot_id ?? raw.context.context_identity.snapshot_id,
      detector_cutoff: raw.context.detector_cutoff,
    },
    summary: raw.summary,
    observations: [...raw.observations],
    patterns: [...raw.patterns],
    limits: [...raw.limits],
  };
}

function adaptBankCountryRoutePoint(raw: ApiBankCountryV2) {
  return {
    bank_id: raw.bank_id,
    bank_country: raw.country_name,
    iso_alpha2: raw.iso_alpha2,
    centroid_latitude: raw.centroid_latitude,
    centroid_longitude: raw.centroid_longitude,
  };
}

function mapPage<Raw, UI>(page: ApiCursorPage<Raw>, adapter: (value: Raw) => UI): CursorPage<UI> {
  return { items: page.items.map(adapter), next_cursor: page.next_cursor, has_more: page.has_more };
}

function numberText(value: number | null): string | null {
  return value === null ? null : String(value);
}
