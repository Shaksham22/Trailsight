"""Frozen deterministic models exposed by the V2 investigation domain."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SubjectType(str, Enum):
    ALERT = "ALERT"
    TRANSACTION = "TRANSACTION"
    ACCOUNT = "ACCOUNT"


class ContextKind(str, Enum):
    ALERT_ENTRY = "ALERT_ENTRY"
    TRANSACTION = "TRANSACTION"
    SNAPSHOT = "SNAPSHOT"


class NetworkReviewBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNSCORED = "UNSCORED"


class HistoryQuality(str, Enum):
    INSUFFICIENT = "INSUFFICIENT"
    LIMITED = "LIMITED"
    SUFFICIENT = "SUFFICIENT"


class AmountSide(str, Enum):
    SENDER_PAID = "SENDER_PAID"
    RECEIVER_RECEIVED = "RECEIVER_RECEIVED"


class Direction(str, Enum):
    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"
    BOTH = "BOTH"


class EvidenceType(str, Enum):
    ALERT_CONTEXT = "ALERT_CONTEXT"
    DETECTOR_STATE = "DETECTOR_STATE"
    TRANSACTION_FACTS = "TRANSACTION_FACTS"
    TRANSACTION_PRIORITY = "TRANSACTION_PRIORITY"
    ACCOUNT_ACTIVITY = "ACCOUNT_ACTIVITY"
    AMOUNT_BEHAVIOR = "AMOUNT_BEHAVIOR"
    COUNTERPARTY_RELATIONSHIP = "COUNTERPARTY_RELATIONSHIP"
    NETWORK_BEHAVIOR = "NETWORK_BEHAVIOR"
    CURRENCY_BEHAVIOR = "CURRENCY_BEHAVIOR"
    BANK_COUNTRY_ROUTE = "BANK_COUNTRY_ROUTE"
    SUPPORTING_TRANSACTIONS = "SUPPORTING_TRANSACTIONS"


class UITargetV2(str, Enum):
    ALERT_CONTEXT = "alert-context"
    REVIEW_PRIORITY = "review-priority"
    TRANSACTION_FACTS = "transaction-facts"
    BANK_COUNTRY_ROUTE = "bank-country-route"
    SENDER_ACCOUNT = "sender-account"
    RECEIVER_ACCOUNT = "receiver-account"
    ACCOUNT_REVIEW = "account-review"
    INVESTIGATION_INDICATORS = "investigation-indicators"
    ACTIVITY_CONTEXT = "activity-context"
    ACCOUNT_NETWORK = "account-network"
    COUNTERPARTY_TABLE = "counterparty-table"
    CURRENCY_ACTIVITY = "currency-activity"
    ALERT_HISTORY = "alert-history"
    SUPPORTING_EVIDENCE = "supporting-evidence"


class ContextIdentityV2(FrozenModel):
    context_kind: ContextKind
    context_ref: str
    context_time: str
    snapshot_id: str | None = None


class InvestigationContextV2(FrozenModel):
    subject_type: SubjectType
    subject_ref: str
    context_identity: ContextIdentityV2
    context_time: str
    detector_snapshot_id: str | None = None
    detector_cutoff: str | None = None
    root_account_refs: tuple[str, ...]
    selected_transaction_ref: str | None = None
    alert_ref: str | None = None


class BankCountryV2(FrozenModel):
    bank_id: str
    mapping_version: str
    country_name: str
    iso_alpha2: str
    centroid_latitude: float
    centroid_longitude: float


class AccountIdentityV2(FrozenModel):
    account_ref: str
    source_dataset: str
    bank_id: str
    account_id: str
    bank_country: BankCountryV2


class TransactionFactsV2(FrozenModel):
    transaction_ref: str
    transaction_timestamp: str
    sender: AccountIdentityV2
    receiver: AccountIdentityV2
    amount_paid: str
    payment_currency: str
    amount_received: str
    receiving_currency: str
    payment_format: str
    cross_currency: bool
    currency_pair: str


class DetectorSnapshotV2(FrozenModel):
    snapshot_id: str
    source_dataset: str
    cutoff_timestamp: str
    algorithm_name: str
    algorithm_variant: str
    algorithm_version: str
    upstream_code_provenance: str
    identity_rule_version: str
    eligibility_rule_version: str
    community_algorithm: str
    community_resolution: str
    community_seed: int
    config_hash: str
    status: str
    account_count: int
    eligible_account_count: int
    scored_account_count: int


class AccountDetectorStateV2(FrozenModel):
    snapshot_id: str
    account_ref: str
    scoring_eligible: bool
    network_pattern_score: float | None
    rank: int | None
    percentile: float | None
    network_review_band: NetworkReviewBand
    unscored_reason: str | None

class DetectorStateEvidenceFactsV2(FrozenModel):
    snapshot_id: str
    account_ref: str
    scoring_eligible: bool
    network_pattern_score: float | None
    rank: int | None
    percentile: float | None
    network_review_band: NetworkReviewBand
    unscored_reason: str | None
    first_order_neighbor_count: int | None
    second_order_neighbor_count: int | None
    block_measure_1: float | None
    block_measure_2: float | None
    block_measure_3: float | None


class DetectorSupportV2(FrozenModel):
    snapshot_id: str
    account_ref: str
    first_order_neighbor_count: int | None
    second_order_neighbor_count: int | None
    community_id_or_stable_snapshot_local_index: str | None
    block_measure_1: float | None
    block_measure_2: float | None
    block_measure_3: float | None
    network_pattern_score: float | None


class TransactionReviewStateV2(FrozenModel):
    transaction_ref: str
    snapshot_id: str | None
    detector_cutoff: str | None
    sender_band: NetworkReviewBand
    receiver_band: NetworkReviewBand
    aml_review_priority: NetworkReviewBand
    derivation_code: str
    derivation_text: str
    alert_involvement: bool
    sender_related_alert_ref: str | None
    receiver_related_alert_ref: str | None


class AlertContextFactsV2(FrozenModel):
    alert_ref: str
    account_ref: str
    entry_snapshot_id: str
    entry_cutoff: str
    entry_score: float | None
    entry_rank: int | None
    entry_percentile: float | None
    reason_code: str
    created_state: str
    relevant_recent_transaction_count: int = Field(ge=0)


class AccountActivityV2(FrozenModel):
    account_ref: str
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)
    distinct_counterparties: int = Field(ge=0)
    incoming_distinct_counterparties: int = Field(ge=0)
    outgoing_distinct_counterparties: int = Field(ge=0)
    first_observed_timestamp: str | None
    most_recent_observed_timestamp: str | None


class AmountBehaviorV2(FrozenModel):
    side: AmountSide
    account_ref: str
    history_quality: HistoryQuality
    sample_size: int = Field(ge=0)
    selected_amount: str
    currency: str
    historical_median: str | None
    empirical_percentile: float | None = Field(default=None, ge=0, le=100)


class RelationshipContextV2(FrozenModel):
    account_ref: str
    counterparty_account_ref: str
    seen_before: bool
    new_counterparty: bool
    previous_interaction_count: int = Field(ge=0)
    root_to_counterparty_count: int = Field(ge=0)
    counterparty_to_root_count: int = Field(ge=0)
    first_previous_timestamp: str | None
    most_recent_previous_timestamp: str | None


class VelocityWindowV2(FrozenModel):
    window: Literal["1h", "24h"]
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)
    total_count: int = Field(ge=0)


class NetworkBehaviorV2(FrozenModel):
    account_ref: str
    velocity_1h: VelocityWindowV2
    velocity_24h: VelocityWindowV2
    fan_in_24h: int = Field(ge=0)
    fan_out_24h: int = Field(ge=0)


class CurrencyBehaviorV2(FrozenModel):
    transaction_ref: str
    cross_currency: bool
    currency_pair: str


class BankCountryRouteV2(FrozenModel):
    transaction_ref: str
    sending_bank: BankCountryV2
    receiving_bank: BankCountryV2
    same_bank_country: bool
    mapping_version: str


class NetworkRelationshipV2(FrozenModel):
    counterparty: AccountIdentityV2
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    first_historical_timestamp: str | None
    last_historical_timestamp: str | None
    selected_relationship: bool


class AccountNetworkV2(FrozenModel):
    root: AccountIdentityV2
    context: ContextIdentityV2
    total_direct_counterparties: int = Field(ge=0)
    shown_counterparties: int = Field(ge=0, le=24)
    truncated: bool
    selection_rule_version: Literal["ego-one-hop-v1"] = "ego-one-hop-v1"
    relationships: tuple[NetworkRelationshipV2, ...]


class ActivityBucketV2(FrozenModel):
    day: str
    direction: Direction
    currency: str
    transaction_count: int = Field(ge=0)
    total_amount: str


class BankCountryFlowV2(FrozenModel):
    counterparty_country: str
    counterparty_iso_alpha2: str
    incoming_transaction_count: int = Field(ge=0)
    outgoing_transaction_count: int = Field(ge=0)
    distinct_counterparties: int = Field(ge=0)
    latest_interaction: str


class AlertHistoryItemV2(FrozenModel):
    alert_ref: str
    entry_snapshot_id: str
    entry_cutoff: str
    reason_code: str


class SupportingTransactionV2(FrozenModel):
    transaction_ref: str
    transaction_timestamp: str
    from_account_ref: str
    from_bank_id: str
    to_account_ref: str
    to_bank_id: str
    amount_paid: str
    payment_currency: str
    amount_received: str
    receiving_currency: str
    payment_format: str
    cross_currency: bool


class SupportingTransactionsFactsV2(FrozenModel):
    source_evidence_type: EvidenceType
    transaction_count: int = Field(ge=0)
    transactions: tuple[SupportingTransactionV2, ...]


class EndpointAccountCardV2(FrozenModel):
    account: AccountIdentityV2
    network_review_band: NetworkReviewBand
    detector_cutoff: str
    observed_summary: str


class InvestigationIndicatorV2(FrozenModel):
    key: str
    title: str
    observed_text: str
    detail: str
    evidence_id: str
    ui_target: UITargetV2
    supporting_transaction_refs: tuple[str, ...]


class TransactionActivityBucketV2(FrozenModel):
    timestamp: str
    currency: str
    incoming_amount: str
    outgoing_amount: str
    transaction_count: int = Field(ge=0)


class SelectedTransactionMarkerV2(FrozenModel):
    transaction_ref: str
    timestamp: str
    currency: str
    amount: str


class ActivityContextV2(FrozenModel):
    range_start: str
    range_end: str
    buckets: tuple[TransactionActivityBucketV2, ...]
    selected_transaction: SelectedTransactionMarkerV2 | None


class LocalNetworkSummaryV2(FrozenModel):
    sender: AccountNetworkV2 | None
    receiver: AccountNetworkV2 | None


class CurrencyActivityV2(FrozenModel):
    currency: str
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)
    incoming_amount: str
    outgoing_amount: str


class SupportingEvidenceSummaryItemV2(FrozenModel):
    label: str
    evidence_id: str
    evidence_type: EvidenceType
    subject_type: SubjectType
    subject_ref: str
    context_time: str
    snapshot_id: str | None
    detector_cutoff: str | None
    facts: dict[str, Any]
    ui_target: UITargetV2
    supporting_transaction_count: int = Field(ge=0)
    supporting_transactions: tuple[SupportingTransactionV2, ...]
    support_truncated: bool


class BehavioralIndicatorsV2(FrozenModel):
    context: ContextIdentityV2
    sender_amount_behavior: AmountBehaviorV2 | None = None
    receiver_amount_behavior: AmountBehaviorV2 | None = None
    counterparty_relationship: RelationshipContextV2 | None = None
    account_network_behavior: dict[str, NetworkBehaviorV2]
    cross_currency: CurrencyBehaviorV2 | None = None
    evidence_ids: tuple[str, ...]


class AccountDetailV2(FrozenModel):
    account_identity: AccountIdentityV2
    context: InvestigationContextV2
    network_review_state: AccountDetectorStateV2
    detector_support: DetectorSupportV2 | None
    observed_activity: AccountActivityV2
    activity_over_time: tuple[ActivityBucketV2, ...]
    currency_activity: tuple[CurrencyActivityV2, ...]
    bank_country_flows: tuple[BankCountryFlowV2, ...]
    alert_history: tuple[AlertHistoryItemV2, ...]
    evidence_ids: tuple[str, ...]


class AlertContextV2(FrozenModel):
    context: InvestigationContextV2
    alert: AlertContextFactsV2
    account_identity: AccountIdentityV2
    detector_state: AccountDetectorStateV2
    detector_support: DetectorSupportV2 | None
    evidence_ids: tuple[str, ...]


class TransactionDetailV2(FrozenModel):
    context: InvestigationContextV2
    transaction_facts: TransactionFactsV2
    review_state: TransactionReviewStateV2
    bank_country_route: BankCountryRouteV2
    sender_account_card: EndpointAccountCardV2
    receiver_account_card: EndpointAccountCardV2
    investigation_indicators: tuple[InvestigationIndicatorV2, ...]
    activity_context: ActivityContextV2
    local_network_summary: LocalNetworkSummaryV2
    supporting_evidence_summary: tuple[SupportingEvidenceSummaryItemV2, ...]
    indicators: BehavioralIndicatorsV2
    evidence_ids: tuple[str, ...]


class AlertListRequestV2(FrozenModel):
    cursor: str | None = None
    limit: int = 50
    bank_country: str | None = None
    include_alert_refs: tuple[str, ...] | None = None
    exclude_alert_refs: tuple[str, ...] | None = None


class AlertListItemV2(FrozenModel):
    alert_ref: str
    account_ref: str
    bank_id: str
    account_id: str
    bank_country: BankCountryV2
    network_review_band: NetworkReviewBand
    entry_snapshot_id: str
    entry_cutoff: str
    primary_reason: str
    relevant_recent_transaction_count: int = Field(ge=0)


class AlertListPageV2(FrozenModel):
    items: tuple[AlertListItemV2, ...]
    next_cursor: str | None
    has_more: bool


class TransactionListRequestV2(FrozenModel):
    cursor: str | None = None
    limit: int = 50
    q: str | None = None
    priority: NetworkReviewBand | None = None
    alert_involvement: bool | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    currency: str | None = None
    payment_format: str | None = None
    sending_bank_country: str | None = None
    receiving_bank_country: str | None = None


class TransactionListPartyV2(FrozenModel):
    account_ref: str
    bank_id: str
    account_id: str
    bank_country: BankCountryV2


class TransactionListItemV2(FrozenModel):
    transaction_ref: str
    timestamp: str
    sender: TransactionListPartyV2
    receiver: TransactionListPartyV2
    amount_paid: str
    payment_currency: str
    amount_received: str
    receiving_currency: str
    payment_format: str
    aml_review_priority: NetworkReviewBand
    related_alert: str | None


class TransactionListPageV2(FrozenModel):
    items: tuple[TransactionListItemV2, ...]
    next_cursor: str | None
    has_more: bool


class AccountListRequestV2(FrozenModel):
    cursor: str | None = None
    limit: int = 50
    q: str | None = None
    band: NetworkReviewBand | None = None
    bank_country: str | None = None
    alert_involvement: bool | None = None


class AccountListItemV2(FrozenModel):
    account_ref: str
    bank_id: str
    account_id: str
    bank_country: BankCountryV2
    network_review_band: NetworkReviewBand
    network_pattern_score: float | None
    latest_snapshot_id: str
    latest_detector_cutoff: str
    incoming_count: int = Field(ge=0)
    outgoing_count: int = Field(ge=0)
    alert_involvement: bool


class AccountListPageV2(FrozenModel):
    items: tuple[AccountListItemV2, ...]
    next_cursor: str | None
    has_more: bool


class RuntimeMetadataV2(FrozenModel):
    latest_snapshot_id: str
    latest_snapshot_cutoff: str


class AccountTransactionPageV2(FrozenModel):
    items: tuple[SupportingTransactionV2, ...]
    next_cursor: str | None
    has_more: bool


class EvidenceIdentityV2(FrozenModel):
    evidence_type: EvidenceType
    subject_type: SubjectType
    subject_ref: str
    context_identity: ContextIdentityV2
    parameters: dict[str, Any]


EvidenceFactsV2 = (
    AlertContextFactsV2
    | DetectorStateEvidenceFactsV2
    | TransactionFactsV2
    | TransactionReviewStateV2
    | AccountActivityV2
    | AmountBehaviorV2
    | RelationshipContextV2
    | NetworkBehaviorV2
    | CurrencyBehaviorV2
    | BankCountryRouteV2
    | SupportingTransactionsFactsV2
)


class EvidenceV2(FrozenModel):
    evidence_id: str
    evidence_version: Literal["evidence-v2"] = "evidence-v2"
    evidence_type: EvidenceType
    subject_type: SubjectType
    subject_ref: str
    context_identity: ContextIdentityV2
    context_time: str
    snapshot_id: str | None
    detector_cutoff: str | None
    parameters: dict[str, Any]
    facts: EvidenceFactsV2
    supporting_transaction_count: int = Field(ge=0)
    supporting_transaction_refs: tuple[str, ...]
    support_truncated: bool
    support_selection_rule: str
    ui_target: UITargetV2


class DisplayEvidenceV2(FrozenModel):
    evidence_id: str
    evidence_type: EvidenceType
    subject_type: SubjectType
    subject_ref: str
    context_time: str
    snapshot_id: str | None
    detector_cutoff: str | None
    facts: dict[str, Any]
    ui_target: UITargetV2
    supporting_transaction_count: int = Field(ge=0)
    supporting_transactions: tuple[SupportingTransactionV2, ...]
    support_truncated: bool
