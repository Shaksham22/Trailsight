export interface CaseSummary {
  case_ref: string;
  display_name: string;
}

export interface CaseListResponse {
  cases: CaseSummary[];
}

export interface EntityRef {
  bank: string;
  account: string;
  entity_type: "Person" | "Merchant";
  synthetic_region: number;
}

export interface SelectedTransaction {
  transaction_ref: string;
  timestamp: string;
  sender: EntityRef;
  counterparty: EntityRef;
  amount_paid: string;
  payment_currency: string;
  amount_received: string;
  receiving_currency: string;
  payment_format: string;
  cross_currency: boolean;
  currency_pair: string;
  region_relationship: "same_region" | "cross_region";
}

export interface SenderHistoryContext {
  evidence_id: string;
  prior_outgoing_count: number;
}

export interface AmountHistoryContext {
  evidence_id: string;
  history_quality: "insufficient" | "limited" | "sufficient";
  sample_size: number;
  selected_amount: string;
  payment_currency: string;
  historical_median: string | null;
  empirical_percentile: number | null;
}

export interface CounterpartyHistoryContext {
  evidence_id: string;
  seen_before: boolean;
  previous_interaction_count: number;
  first_previous_timestamp: string | null;
  most_recent_previous_timestamp: string | null;
}

export interface RegionHistoryContext {
  evidence_id: string;
  sender_region: number;
  receiver_region: number;
  region_relationship: "same_region" | "cross_region";
  receiver_region_seen_before: boolean;
  previous_receiver_region_count: number;
}

export interface HistoricalTransactionRow {
  transaction_ref: string;
  timestamp: string;
  counterparty_bank: string;
  counterparty_account: string;
  counterparty_type: "Person" | "Merchant";
  amount_paid: string;
  payment_currency: string;
  receiving_currency: string;
  receiver_region: number;
  payment_format: string;
}

export interface WorkspaceResponse {
  case_ref: string;
  display_name: string;
  selected_transaction: SelectedTransaction;
  sender_history: SenderHistoryContext;
  amount_history: AmountHistoryContext;
  counterparty_history: CounterpartyHistoryContext;
  region_history: RegionHistoryContext | null;
  historical_transactions: HistoricalTransactionRow[];
}

export interface RenderedCitation {
  label: string;
  evidence_id: string;
}

export interface RenderedFinding {
  text: string;
  citations: RenderedCitation[];
}

export interface DisplayEvidence {
  label: string;
  evidence_id: string;
  evidence_type: string;
  ui_target: string;
  supporting_transaction_refs: string[];
}

export interface InvestigationResponse {
  investigation_id: string;
  case_ref: string;
  parent_investigation_id: string | null;
  run_status:
    | "success"
    | "partial"
    | "unavailable"
    | "model_error"
    | "tool_error"
    | "structured_output_invalid"
    | "evidence_validation_failed";
  findings: RenderedFinding[];
  limits: string[];
  evidence: DisplayEvidence[];
}

export interface FollowUpRequest {
  question: string;
  parent_investigation_id: string | null;
}

export interface ApplicationError {
  code: string;
  message: string;
}
