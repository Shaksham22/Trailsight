export type ReviewBand = "HIGH" | "MEDIUM" | "LOW" | "UNSCORED";
export type ReviewWorkflowStatus = "NOT_REVIEWED" | "IN_REVIEW" | "REVIEWED";
export type SubjectType = "ALERT" | "TRANSACTION" | "ACCOUNT";
export type AIRunStatus =
  | "IDLE"
  | "LOADING"
  | "SUCCESS"
  | "PARTIAL"
  | "UNAVAILABLE"
  | "ERROR";

export interface ApplicationError {
  code: string;
  message: string;
  request_id?: string | null;
  status?: number;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface HealthResponse {
  status: string;
  runtime_db_ready: boolean;
  latest_snapshot_id: string;
  latest_snapshot_cutoff: string;
  ai_configured: boolean;
  product_version: string;
}

export interface BankCountryRoutePoint {
  bank_id: string;
  bank_country: string;
  iso_alpha2: string;
  centroid_latitude: number;
  centroid_longitude: number;
}

export interface AccountIdentity {
  account_ref: string;
  bank_id: string;
  account_id: string;
  bank_country: string;
}

export interface AlertListItem {
  alert_ref: string;
  account_ref: string;
  bank_id: string;
  account_id: string;
  bank_country: string;
  network_review_band: ReviewBand;
  entry_snapshot_id: string;
  entry_cutoff: string;
  primary_reason: string;
  relevant_recent_transaction_count: number;
  review_status: ReviewWorkflowStatus;
}

export interface AlertDetailResponse {
  alert_ref: string;
  account: AccountIdentity;
  review_status: ReviewWorkflowStatus;
  entry_snapshot_id: string;
  entry_cutoff: string;
  reason_code: string;
  network_review_band: ReviewBand;
  network_pattern_score: string | null;
  rank: number | null;
  percentile: string | null;
  scoring_eligible: boolean;
  unscored_reason: string | null;
  evidence_ids: string[];
}

export interface TransactionListItem {
  transaction_ref: string;
  timestamp: string;
  sender: AccountIdentity;
  receiver: AccountIdentity;
  amount_paid: string;
  payment_currency: string;
  amount_received: string;
  receiving_currency: string;
  payment_format: string;
  aml_review_priority: ReviewBand;
  related_alert: boolean;
}

export interface AccountListItem extends AccountIdentity {
  network_review_band: ReviewBand;
  network_pattern_score: string | null;
  latest_snapshot_id: string;
  latest_detector_cutoff: string;
  incoming_count: number;
  outgoing_count: number;
  alert_involvement: boolean;
}

export interface TransactionReviewState {
  aml_review_priority: ReviewBand;
  sender_band: ReviewBand;
  receiver_band: ReviewBand;
  applicable_snapshot_id: string | null;
  detector_cutoff: string;
  derivation_text: string;
  alert_involvement: boolean;
}

export interface TransactionFacts extends TransactionListItem {
  cross_currency: boolean;
  currency_pair: string;
}

export interface BankCountryRoute {
  sending: BankCountryRoutePoint;
  receiving: BankCountryRoutePoint;
  same_bank_country: boolean;
  mapping_version: string;
}

export interface EndpointAccountCard {
  account: AccountIdentity;
  network_review_band: ReviewBand;
  detector_cutoff: string;
  observed_summary: string;
}

export type EvidenceUiTarget =
  | "alert-context"
  | "review-priority"
  | "transaction-facts"
  | "bank-country-route"
  | "sender-account"
  | "receiver-account"
  | "account-review"
  | "investigation-indicators"
  | "activity-context"
  | "account-network"
  | "counterparty-table"
  | "currency-activity"
  | "alert-history"
  | "supporting-evidence";

export type EvidenceType =
  | "ALERT_CONTEXT"
  | "DETECTOR_STATE"
  | "TRANSACTION_FACTS"
  | "TRANSACTION_PRIORITY"
  | "ACCOUNT_ACTIVITY"
  | "AMOUNT_BEHAVIOR"
  | "COUNTERPARTY_RELATIONSHIP"
  | "NETWORK_BEHAVIOR"
  | "CURRENCY_BEHAVIOR"
  | "BANK_COUNTRY_ROUTE"
  | "SUPPORTING_TRANSACTIONS";

export interface InvestigationIndicator {
  key: string;
  title: string;
  observed_text: string;
  detail: string;
  evidence_id: string;
  ui_target: EvidenceUiTarget;
  supporting_transaction_refs: string[];
}

export interface ActivityBucket {
  timestamp: string;
  currency: string;
  incoming_amount: string;
  outgoing_amount: string;
  transaction_count: number;
  direction?: "INCOMING" | "OUTGOING";
}

export interface ActivityContext {
  range_start: string;
  range_end: string;
  buckets: ActivityBucket[];
  selected_transaction: {
    transaction_ref: string;
    timestamp: string;
    currency: string;
    amount: string;
  } | null;
}

export interface NetworkNode extends AccountIdentity {
  is_root: boolean;
}

export interface NetworkRelationship {
  counterparty_account_ref: string;
  incoming_count: number;
  outgoing_count: number;
  total_count: number;
  first_historical_timestamp: string | null;
  last_historical_timestamp: string | null;
  selected_relationship: boolean;
}

export interface AccountNetwork {
  root: AccountIdentity;
  counterparties: NetworkNode[];
  relationships: NetworkRelationship[];
  total_direct_counterparties: number;
  shown_counterparties: number;
  truncated: boolean;
  selection_rule_version: "ego-one-hop-v1";
}

export interface SupportingTransactionRow extends TransactionListItem {
  relationship_to_subject?: string;
}

export interface EvidenceSupportingTransaction {
  transaction_ref: string;
}

export interface EvidenceDisplay {
  label: string | null;
  evidence_id: string;
  evidence_type: EvidenceType;
  subject_type: SubjectType;
  subject_ref: string;
  context_time: string;
  snapshot_id: string | null;
  detector_cutoff: string | null;
  facts: Record<string, unknown>;
  ui_target: EvidenceUiTarget;
  supporting_transaction_count: number;
  supporting_transactions: EvidenceSupportingTransaction[];
  support_truncated: boolean;
}

export interface TransactionEvidenceDisplay extends Omit<EvidenceDisplay, "label" | "supporting_transactions"> {
  label: string;
  supporting_transactions: SupportingTransactionRow[];
}

export interface TransactionDetailResponse {
  review_state: TransactionReviewState;
  transaction_facts: TransactionFacts;
  bank_country_route: BankCountryRoute;
  sender_account_card: EndpointAccountCard;
  receiver_account_card: EndpointAccountCard;
  investigation_indicators: InvestigationIndicator[];
  activity_context: ActivityContext;
  local_network_summary: {
    sender: AccountNetwork | null;
    receiver: AccountNetwork | null;
  };
  supporting_evidence_summary: TransactionEvidenceDisplay[];
}

export interface AccountContext {
  context_time: string;
  snapshot_id: string;
  detector_cutoff: string;
  origin_alert_ref: string | null;
  origin_transaction_ref: string | null;
}

export interface DetectorSupport {
  first_order_neighbor_count: number | null;
  second_order_neighbor_count: number | null;
  community_id_or_stable_snapshot_local_index: string | null;
  block_measure_1: string | null;
  block_measure_2: string | null;
  block_measure_3: string | null;
}

export interface NetworkReviewState {
  network_review_band: ReviewBand;
  network_pattern_score: string | null;
  rank: number | null;
  percentile: string | null;
  scoring_eligible: boolean;
  unscored_reason: string | null;
}

export interface ObservedActivity {
  incoming_count: number;
  outgoing_count: number;
  distinct_counterparties: number;
  incoming_distinct_counterparties: number;
  outgoing_distinct_counterparties: number;
  first_observed_timestamp: string | null;
  most_recent_observed_timestamp: string | null;
}

export interface CurrencyActivityRow {
  currency: string;
  incoming_count: number;
  outgoing_count: number;
  incoming_amount: string;
  outgoing_amount: string;
}

export interface BankCountryFlowRow {
  bank_country: string;
  iso_alpha2?: string;
  incoming_transaction_count: number;
  outgoing_transaction_count: number;
  distinct_counterparties: number;
  latest_interaction: string;
}

export interface AccountAlertHistoryItem {
  alert_ref: string;
  entry_snapshot_id: string;
  entry_cutoff: string;
  primary_reason: string;
  review_status: ReviewWorkflowStatus;
}

export interface AccountDetailResponse {
  account_identity: AccountIdentity;
  context: AccountContext;
  network_review_state: NetworkReviewState;
  detector_support: DetectorSupport | null;
  observed_activity: ObservedActivity;
  activity_over_time: ActivityContext;
  currency_activity: CurrencyActivityRow[];
  bank_country_flows: BankCountryFlowRow[];
  alert_history: AccountAlertHistoryItem[];
  alert_history_total: number;
  alert_history_truncated: boolean;
  account_network: AccountNetwork;
  transactions: CursorPage<SupportingTransactionRow>;
  counterparties: AccountNetwork["relationships"];
}

export interface InvestigationResponse {
  investigation_id: string;
  run_status: Exclude<AIRunStatus, "IDLE" | "LOADING" | "ERROR">;
  subject_type: SubjectType;
  subject_ref: string;
  context: {
    context_time: string;
    snapshot_id: string | null;
    detector_cutoff: string | null;
  };
  summary: string;
  observations: string[];
  patterns: string[];
  limits: string[];
}

export interface InvestigationRequest {
  subject_type: SubjectType;
  subject_ref: string;
  origin_alert_ref: string | null;
  origin_transaction_ref: string | null;
}

export interface AlertQuery {
  cursor?: string | null;
  limit?: number;
  q?: string;
  review_status?: ReviewWorkflowStatus | "";
  bank_country?: string;
}

export interface TransactionQuery {
  cursor?: string | null;
  limit?: number;
  q?: string;
  priority?: ReviewBand | "";
  alert_involvement?: "true" | "false" | "";
  date_from?: string;
  date_to?: string;
  currency?: string;
  payment_format?: string;
  sending_bank_country?: string;
  receiving_bank_country?: string;
}

export interface AccountQuery {
  cursor?: string | null;
  limit?: number;
  q?: string;
  band?: ReviewBand | "";
  bank_country?: string;
  alert_involvement?: "true" | "false" | "";
}

export interface AccountOrigin {
  origin_alert_ref?: string | null;
  origin_transaction_ref?: string | null;
}

export interface AccountTransactionQuery extends AccountOrigin {
  cursor?: string | null;
  limit?: number;
  direction?: "INCOMING" | "OUTGOING" | "BOTH";
  currency?: string;
  counterparty_account_ref?: string;
}
