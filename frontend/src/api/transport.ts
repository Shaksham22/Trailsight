import type { AIFindingCategory, ReviewBand, ReviewWorkflowStatus, SubjectType } from "./types.ts";

export interface ApiBankCountryV2 {
  bank_id: string;
  mapping_version: string;
  country_name: string;
  iso_alpha2: string;
  centroid_latitude: number;
  centroid_longitude: number;
}

export interface ApiAccountIdentityV2 {
  account_ref: string;
  source_dataset: string;
  bank_id: string;
  account_id: string;
  bank_country: ApiBankCountryV2;
}

export interface ApiContextIdentityV2 {
  context_kind: "ALERT_ENTRY" | "TRANSACTION" | "SNAPSHOT";
  context_ref: string;
  context_time: string;
  snapshot_id: string | null;
}

export interface ApiInvestigationContextV2 {
  subject_type: SubjectType;
  subject_ref: string;
  context_identity: ApiContextIdentityV2;
  context_time: string;
  detector_snapshot_id: string | null;
  detector_cutoff: string | null;
  root_account_refs: string[];
  selected_transaction_ref: string | null;
  alert_ref: string | null;
}

export interface ApiHealthResponseV2 {
  status: string;
  runtime_db_ready: boolean;
  latest_snapshot_id: string;
  latest_snapshot_cutoff: string;
  ai_configured: boolean;
  product_version: string;
}

export interface ApiCursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface ApiAlertListItemV2 {
  alert_ref: string;
  account_ref: string;
  bank_id: string;
  account_id: string;
  bank_country: ApiBankCountryV2;
  network_review_band: ReviewBand;
  entry_snapshot_id: string;
  entry_cutoff: string;
  primary_reason: string;
  relevant_recent_transaction_count: number;
  review_status: ReviewWorkflowStatus;
}

export interface ApiAlertContextFactsV2 {
  alert_ref: string;
  account_ref: string;
  entry_snapshot_id: string;
  entry_cutoff: string;
  entry_score: number | null;
  entry_rank: number | null;
  entry_percentile: number | null;
  reason_code: string;
  created_state: string;
  relevant_recent_transaction_count: number;
}

export interface ApiAccountDetectorStateV2 {
  snapshot_id: string;
  account_ref: string;
  scoring_eligible: boolean;
  network_pattern_score: number | null;
  rank: number | null;
  percentile: number | null;
  network_review_band: ReviewBand;
  unscored_reason: string | null;
}

export interface ApiDetectorSupportV2 {
  snapshot_id: string;
  account_ref: string;
  first_order_neighbor_count: number | null;
  second_order_neighbor_count: number | null;
  community_id_or_stable_snapshot_local_index: string | null;
  block_measure_1: number | null;
  block_measure_2: number | null;
  block_measure_3: number | null;
  network_pattern_score: number | null;
}

export interface ApiAlertDetailResponseV2 {
  context: ApiInvestigationContextV2;
  alert: ApiAlertContextFactsV2;
  account_identity: ApiAccountIdentityV2;
  detector_state: ApiAccountDetectorStateV2;
  detector_support: ApiDetectorSupportV2 | null;
  evidence_ids: string[];
  review_status: ReviewWorkflowStatus;
}

export interface ApiTransactionPartyV2 {
  account_ref: string;
  bank_id: string;
  account_id: string;
  bank_country: ApiBankCountryV2;
}

export interface ApiTransactionListItemV2 {
  transaction_ref: string;
  timestamp: string;
  sender: ApiTransactionPartyV2;
  receiver: ApiTransactionPartyV2;
  amount_paid: string;
  payment_currency: string;
  amount_received: string;
  receiving_currency: string;
  payment_format: string;
  aml_review_priority: ReviewBand;
  related_alert: string | null;
}

export interface ApiTransactionFactsV2 {
  transaction_ref: string;
  transaction_timestamp: string;
  sender: ApiAccountIdentityV2;
  receiver: ApiAccountIdentityV2;
  amount_paid: string;
  payment_currency: string;
  amount_received: string;
  receiving_currency: string;
  payment_format: string;
  cross_currency: boolean;
  currency_pair: string;
}

export interface ApiTransactionReviewStateV2 {
  transaction_ref: string;
  snapshot_id: string | null;
  detector_cutoff: string | null;
  sender_band: ReviewBand;
  receiver_band: ReviewBand;
  aml_review_priority: ReviewBand;
  derivation_code: string;
  derivation_text: string;
  alert_involvement: boolean;
  sender_related_alert_ref: string | null;
  receiver_related_alert_ref: string | null;
}

export interface ApiBankCountryRouteV2 {
  transaction_ref: string;
  sending_bank: ApiBankCountryV2;
  receiving_bank: ApiBankCountryV2;
  same_bank_country: boolean;
  mapping_version: string;
}

export interface ApiEndpointAccountCardV2 {
  account: ApiAccountIdentityV2;
  network_review_band: ReviewBand;
  detector_cutoff: string;
  observed_summary: string;
}

export interface ApiInvestigationIndicatorV2 {
  key: string;
  title: string;
  observed_text: string;
  detail: string;
  evidence_id: string;
  ui_target: string;
  supporting_transaction_refs: string[];
}

export interface ApiTransactionActivityBucketV2 {
  timestamp: string;
  currency: string;
  incoming_amount: string;
  outgoing_amount: string;
  transaction_count: number;
}

export interface ApiActivityContextV2 {
  range_start: string;
  range_end: string;
  buckets: ApiTransactionActivityBucketV2[];
  selected_transaction: {
    transaction_ref: string;
    timestamp: string;
    currency: string;
    amount: string;
  } | null;
}

export interface ApiNetworkRelationshipV2 {
  counterparty: ApiAccountIdentityV2;
  incoming_count: number;
  outgoing_count: number;
  total_count: number;
  first_historical_timestamp: string | null;
  last_historical_timestamp: string | null;
  selected_relationship: boolean;
}

export interface ApiAccountNetworkV2 {
  root: ApiAccountIdentityV2;
  context: ApiContextIdentityV2;
  total_direct_counterparties: number;
  shown_counterparties: number;
  truncated: boolean;
  selection_rule_version: "ego-one-hop-v1";
  relationships: ApiNetworkRelationshipV2[];
}

export interface ApiLocalNetworkSummaryV2 {
  sender: ApiAccountNetworkV2 | null;
  receiver: ApiAccountNetworkV2 | null;
}

export interface ApiSupportingTransactionV2 {
  transaction_ref: string;
  transaction_timestamp: string;
  from_account_ref: string;
  from_bank_id: string;
  to_account_ref: string;
  to_bank_id: string;
  amount_paid: string;
  payment_currency: string;
  amount_received: string;
  receiving_currency: string;
  payment_format: string;
  cross_currency: boolean;
}

export interface ApiDisplayEvidenceV2 {
  evidence_id: string;
  evidence_type: string;
  subject_type: SubjectType;
  subject_ref: string;
  context_time: string;
  snapshot_id: string | null;
  detector_cutoff: string | null;
  facts: Record<string, unknown>;
  ui_target: string;
  supporting_transaction_count: number;
  supporting_transactions: ApiSupportingTransactionV2[];
  support_truncated: boolean;
}

export interface ApiSupportingEvidenceSummaryItemV2 extends ApiDisplayEvidenceV2 {
  label: string;
}

export interface ApiTransactionDetailV2 {
  context: ApiInvestigationContextV2;
  transaction_facts: ApiTransactionFactsV2;
  review_state: ApiTransactionReviewStateV2;
  bank_country_route: ApiBankCountryRouteV2;
  sender_account_card: ApiEndpointAccountCardV2;
  receiver_account_card: ApiEndpointAccountCardV2;
  investigation_indicators: ApiInvestigationIndicatorV2[];
  activity_context: ApiActivityContextV2;
  local_network_summary: ApiLocalNetworkSummaryV2;
  supporting_evidence_summary: ApiSupportingEvidenceSummaryItemV2[];
  evidence_ids: string[];
}

export interface ApiAccountListItemV2 {
  account_ref: string;
  bank_id: string;
  account_id: string;
  bank_country: ApiBankCountryV2;
  network_review_band: ReviewBand;
  network_pattern_score: number | null;
  latest_snapshot_id: string;
  latest_detector_cutoff: string;
  incoming_count: number;
  outgoing_count: number;
  alert_involvement: boolean;
}

export interface ApiAccountActivityV2 {
  account_ref: string;
  incoming_count: number;
  outgoing_count: number;
  distinct_counterparties: number;
  incoming_distinct_counterparties: number;
  outgoing_distinct_counterparties: number;
  first_observed_timestamp: string | null;
  most_recent_observed_timestamp: string | null;
}

export interface ApiActivityBucketV2 {
  day: string;
  direction: "INCOMING" | "OUTGOING";
  currency: string;
  transaction_count: number;
  total_amount: string;
}

export interface ApiCurrencyActivityV2 {
  currency: string;
  incoming_count: number;
  outgoing_count: number;
  incoming_amount: string;
  outgoing_amount: string;
}

export interface ApiBankCountryFlowV2 {
  counterparty_country: string;
  counterparty_iso_alpha2: string;
  incoming_transaction_count: number;
  outgoing_transaction_count: number;
  distinct_counterparties: number;
  latest_interaction: string;
}

export interface ApiAlertHistoryItemV2 {
  alert_ref: string;
  entry_snapshot_id: string;
  entry_cutoff: string;
  reason_code: string;
}

export interface ApiAccountDetailV2 {
  account_identity: ApiAccountIdentityV2;
  context: ApiInvestigationContextV2;
  network_review_state: ApiAccountDetectorStateV2;
  detector_support: ApiDetectorSupportV2 | null;
  observed_activity: ApiAccountActivityV2;
  activity_over_time: ApiActivityBucketV2[];
  currency_activity: ApiCurrencyActivityV2[];
  bank_country_flows: ApiBankCountryFlowV2[];
  alert_history: ApiAlertHistoryItemV2[];
  evidence_ids: string[];
}

export type ApiAccountTransactionPageV2 = ApiCursorPage<ApiSupportingTransactionV2>;

export interface ApiFindingV2 {
  category: AIFindingCategory;
  text: string;
  evidence_ids: string[];
}

export interface ApiDisplayEvidenceItemV2 {
  label: string;
  evidence: ApiDisplayEvidenceV2;
}

export interface ApiInvestigationResponseV2 {
  investigation_id: string;
  run_status: "SUCCESS" | "PARTIAL" | "UNAVAILABLE";
  subject_type: SubjectType;
  subject_ref: string;
  context: ApiInvestigationContextV2;
  findings: ApiFindingV2[];
  limits: string[];
  display_evidence: ApiDisplayEvidenceItemV2[];
}
