"""Deterministic browser-facing REST resources for Trailsight V2."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request

from trailsight_v2.domain.errors import InvalidContextError, InvalidInputError
from trailsight_v2.domain.models import (
    AccountDetailV2,
    AccountListPageV2,
    AccountListRequestV2,
    AccountNetworkV2,
    AccountTransactionPageV2,
    AlertListRequestV2,
    Direction,
    DisplayEvidenceV2,
    NetworkReviewBand,
    TransactionDetailV2,
    TransactionListPageV2,
    TransactionListRequestV2,
)
from trailsight_v2.domain.service import InvestigationServiceV2

from .models import (
    AlertDetailResponseV2,
    AlertListItemResponseV2,
    AlertListResponseV2,
    HealthResponseV2,
    ReviewStatus,
    ReviewStatusPatchRequestV2,
    ReviewStatusPatchResponseV2,
)
from .runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/v2")
Limit = Annotated[int, Query(ge=1, le=100)]


def _services(request: Request) -> tuple[InvestigationServiceV2, RuntimeStateStore]:
    return request.app.state.investigation_service, request.app.state.runtime_state_store


def _origin_ref(origin_alert_ref: str | None, origin_transaction_ref: str | None) -> str | None:
    if origin_alert_ref is not None and origin_transaction_ref is not None:
        raise InvalidContextError("At most one historical account origin may be supplied")
    return origin_alert_ref or origin_transaction_ref


def _validate_date(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is not None:
        raise InvalidInputError("Date filters must use timezone-unspecified timestamps")
    return value


@router.get("/health", response_model=HealthResponseV2)
def health(request: Request) -> HealthResponseV2:
    service, _ = _services(request)
    metadata = service.get_runtime_metadata()
    ai_configured = bool(os.getenv("OPENAI_API_KEY") and os.getenv("TRAILSIGHT_MODEL"))
    return HealthResponseV2(
        status="ok",
        runtime_db_ready=True,
        latest_snapshot_id=metadata.latest_snapshot_id,
        latest_snapshot_cutoff=metadata.latest_snapshot_cutoff,
        ai_configured=ai_configured,
        product_version="v2",
    )


@router.get("/alerts", response_model=AlertListResponseV2)
def list_alerts(
    request: Request,
    cursor: str | None = None,
    limit: Limit = 50,
    review_status: ReviewStatus | None = None,
    bank_country: str | None = None,
) -> AlertListResponseV2:
    service, state_store = _services(request)
    include_refs: tuple[str, ...] | None = None
    exclude_refs: tuple[str, ...] | None = None
    if review_status is not None:
        include_refs, exclude_refs = state_store.alert_filter_membership(review_status)
    page = service.list_alerts(
        AlertListRequestV2(
            cursor=cursor,
            limit=limit,
            bank_country=bank_country,
            include_alert_refs=include_refs,
            exclude_alert_refs=exclude_refs,
        )
    )
    items = tuple(
        AlertListItemResponseV2(
            **item.model_dump(mode="python"),
            review_status=state_store.get_alert_review_status(item.alert_ref),
        )
        for item in page.items
    )
    return AlertListResponseV2(items=items, next_cursor=page.next_cursor, has_more=page.has_more)


@router.get("/alerts/{alert_ref}", response_model=AlertDetailResponseV2)
def get_alert(alert_ref: str, request: Request) -> AlertDetailResponseV2:
    service, state_store = _services(request)
    detail = service.get_alert_context(alert_ref)
    return AlertDetailResponseV2(
        **detail.model_dump(mode="python"),
        review_status=state_store.get_alert_review_status(alert_ref),
    )


@router.patch(
    "/alerts/{alert_ref}/review-status", response_model=ReviewStatusPatchResponseV2
)
def patch_alert_review_status(
    alert_ref: str, payload: ReviewStatusPatchRequestV2, request: Request
) -> ReviewStatusPatchResponseV2:
    service, state_store = _services(request)
    # Validate immutable alert existence/context before mutating workflow state.
    service.get_alert_context(alert_ref)
    updated = state_store.set_alert_review_status(alert_ref, payload.review_status)
    return ReviewStatusPatchResponseV2(
        alert_ref=updated.alert_ref,
        review_status=updated.review_status,
        updated_at=updated.updated_at,
    )


@router.get("/transactions", response_model=TransactionListPageV2)
def list_transactions(
    request: Request,
    cursor: str | None = None,
    limit: Limit = 50,
    q: str | None = None,
    priority: NetworkReviewBand | None = None,
    alert_involvement: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    currency: str | None = None,
    payment_format: str | None = None,
    sending_bank_country: str | None = None,
    receiving_bank_country: str | None = None,
) -> TransactionListPageV2:
    service, _ = _services(request)
    date_from = _validate_date(date_from)
    date_to = _validate_date(date_to)
    if date_from is not None and date_to is not None and date_from >= date_to:
        raise InvalidInputError("date_from must be earlier than date_to")
    return service.list_transactions(
        TransactionListRequestV2(
            cursor=cursor,
            limit=limit,
            q=q,
            priority=priority,
            alert_involvement=alert_involvement,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
            payment_format=payment_format,
            sending_bank_country=sending_bank_country,
            receiving_bank_country=receiving_bank_country,
        )
    )


@router.get("/transactions/{transaction_ref}", response_model=TransactionDetailV2)
def get_transaction(transaction_ref: str, request: Request) -> TransactionDetailV2:
    service, _ = _services(request)
    return service.get_transaction_detail(transaction_ref)


@router.get("/accounts", response_model=AccountListPageV2)
def list_accounts(
    request: Request,
    cursor: str | None = None,
    limit: Limit = 50,
    q: str | None = None,
    band: NetworkReviewBand | None = None,
    bank_country: str | None = None,
    alert_involvement: bool | None = None,
) -> AccountListPageV2:
    service, _ = _services(request)
    return service.list_accounts(
        AccountListRequestV2(
            cursor=cursor,
            limit=limit,
            q=q,
            band=band,
            bank_country=bank_country,
            alert_involvement=alert_involvement,
        )
    )


@router.get("/accounts/{account_ref}", response_model=AccountDetailV2)
def get_account(
    account_ref: str,
    request: Request,
    origin_alert_ref: str | None = None,
    origin_transaction_ref: str | None = None,
) -> AccountDetailV2:
    service, _ = _services(request)
    return service.get_account_detail(
        account_ref,
        origin_ref=_origin_ref(origin_alert_ref, origin_transaction_ref),
    )


@router.get("/accounts/{account_ref}/transactions", response_model=AccountTransactionPageV2)
def list_account_transactions(
    account_ref: str,
    request: Request,
    origin_alert_ref: str | None = None,
    origin_transaction_ref: str | None = None,
    cursor: str | None = None,
    limit: Limit = 50,
    direction: Direction = Direction.BOTH,
    currency: str | None = None,
    counterparty_account_ref: str | None = None,
) -> AccountTransactionPageV2:
    service, _ = _services(request)
    return service.list_account_transactions(
        account_ref,
        origin_ref=_origin_ref(origin_alert_ref, origin_transaction_ref),
        cursor=cursor,
        limit=limit,
        direction=direction,
        currency=currency,
        counterparty_account_ref=counterparty_account_ref,
    )


@router.get("/accounts/{account_ref}/network", response_model=AccountNetworkV2)
def get_account_network(
    account_ref: str,
    request: Request,
    origin_alert_ref: str | None = None,
    origin_transaction_ref: str | None = None,
) -> AccountNetworkV2:
    service, _ = _services(request)
    return service.get_account_network(
        account_ref,
        origin_ref=_origin_ref(origin_alert_ref, origin_transaction_ref),
    )


@router.get("/evidence/{evidence_id}", response_model=DisplayEvidenceV2)
def get_evidence(evidence_id: str, request: Request) -> DisplayEvidenceV2:
    service, _ = _services(request)
    return service.display_evidence(evidence_id)
