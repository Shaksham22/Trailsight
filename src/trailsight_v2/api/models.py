"""HTTP-only models for the Trailsight V2 deterministic API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from trailsight_v2.domain.models import (
    AccountIdentityV2,
    AlertContextFactsV2,
    BankCountryV2,
    DetectorSupportV2,
    InvestigationContextV2,
    NetworkReviewBand,
    AccountDetectorStateV2,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewStatus(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    IN_REVIEW = "IN_REVIEW"
    REVIEWED = "REVIEWED"


class ErrorDetailV2(ApiModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorEnvelopeV2(ApiModel):
    error: ErrorDetailV2


class HealthResponseV2(ApiModel):
    status: str
    runtime_db_ready: bool
    latest_snapshot_id: str
    latest_snapshot_cutoff: str
    ai_configured: bool
    product_version: str


class AlertListItemResponseV2(ApiModel):
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
    review_status: ReviewStatus


class AlertListResponseV2(ApiModel):
    items: tuple[AlertListItemResponseV2, ...]
    next_cursor: str | None
    has_more: bool


class AlertDetailResponseV2(ApiModel):
    context: InvestigationContextV2
    alert: AlertContextFactsV2
    account_identity: AccountIdentityV2
    detector_state: AccountDetectorStateV2
    detector_support: DetectorSupportV2 | None
    evidence_ids: tuple[str, ...]
    review_status: ReviewStatus


class ReviewStatusPatchRequestV2(ApiModel):
    review_status: ReviewStatus


class ReviewStatusPatchResponseV2(ApiModel):
    alert_ref: str
    review_status: ReviewStatus
    updated_at: str
