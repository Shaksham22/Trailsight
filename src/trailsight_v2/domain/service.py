"""Authoritative deterministic Trailsight V2 investigation service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from trailsight_v2.data.canonical import canonical_decimal
from trailsight_v2.domain.evidence import (
    canonical_parameters,
    canonical_timestamp,
    decode_evidence_id,
    encode_evidence_id,
    parse_canonical_timestamp,
)
from trailsight_v2.domain.errors import DataIntegrityError, InvalidContextError, InvalidInputError
from trailsight_v2.domain.models import (
    AccountActivityV2,
    AccountDetailV2,
    AccountDetectorStateV2,
    AccountIdentityV2,
    AccountListItemV2,
    AccountListPageV2,
    AccountListRequestV2,
    AccountNetworkV2,
    AccountTransactionPageV2,
    ActivityBucketV2,
    ActivityContextV2,
    AlertContextFactsV2,
    AlertContextV2,
    AlertListItemV2,
    AlertListPageV2,
    AlertListRequestV2,
    AlertHistoryItemV2,
    AmountBehaviorV2,
    AmountSide,
    BankCountryFlowV2,
    BankCountryRouteV2,
    BankCountryV2,
    BehavioralIndicatorsV2,
    ContextIdentityV2,
    ContextKind,
    CurrencyActivityV2,
    CurrencyBehaviorV2,
    DetectorSnapshotV2,
    DetectorStateEvidenceFactsV2,
    DetectorSupportV2,
    Direction,
    DisplayEvidenceV2,
    EndpointAccountCardV2,
    EvidenceIdentityV2,
    EvidenceType,
    EvidenceV2,
    HistoryQuality,
    InvestigationContextV2,
    InvestigationIndicatorV2,
    LocalNetworkSummaryV2,
    NetworkBehaviorV2,
    NetworkRelationshipV2,
    NetworkReviewBand,
    RelationshipContextV2,
    RuntimeMetadataV2,
    SelectedTransactionMarkerV2,
    SubjectType,
    SupportingEvidenceSummaryItemV2,
    SupportingTransactionV2,
    SupportingTransactionsFactsV2,
    TransactionActivityBucketV2,
    TransactionDetailV2,
    TransactionFactsV2,
    TransactionListItemV2,
    TransactionListPageV2,
    TransactionListPartyV2,
    TransactionListRequestV2,
    TransactionReviewStateV2,
    UITargetV2,
    VelocityWindowV2,
)
from trailsight_v2.domain.repository import DuckDBInvestigationRepositoryV2


SUPPORT_LIMIT = 50
NETWORK_LIMIT = 24
MAX_LIST_QUERY_TEXT = 256
TRANSACTION_ACTIVITY_DAYS = 30


@dataclass(frozen=True, slots=True)
class _TransactionBehavioralBundle:
    indicators: BehavioralIndicatorsV2
    evidence: tuple[EvidenceV2, ...]



class InvestigationServiceV2:
    """Sole factual facade used by later REST, MCP, AI validation, and UI APIs."""

    def __init__(self, repository: DuckDBInvestigationRepositoryV2) -> None:
        self._repository = repository

    def close(self) -> None:
        self._repository.close()

    def list_alerts(self, request: AlertListRequestV2 | None = None) -> AlertListPageV2:
        request = request or AlertListRequestV2()
        q = request.q.strip() if request.q is not None else None
        self._validate_query_text(q)
        q = q or None
        include_refs = self._normalize_alert_membership(request.include_alert_refs)
        exclude_refs = self._normalize_alert_membership(request.exclude_alert_refs)
        rows, next_cursor, has_more = self._repository.list_alert_rows(
            cursor=request.cursor,
            limit=request.limit,
            q=q,
            bank_country=request.bank_country,
            include_alert_refs=include_refs,
            exclude_alert_refs=exclude_refs,
        )
        items: list[AlertListItemV2] = []
        for row in rows:
            try:
                band = NetworkReviewBand(str(row[9]))
            except ValueError as exc:
                raise DataIntegrityError("Alert queue contains an unknown persisted review band") from exc
            if band is not NetworkReviewBand.HIGH:
                raise DataIntegrityError("Network alert queue contains a non-HIGH entry state")
            items.append(
                AlertListItemV2(
                    alert_ref=str(row[0]),
                    account_ref=str(row[1]),
                    bank_id=str(row[2]),
                    account_id=str(row[3]),
                    bank_country=BankCountryV2(
                        bank_id=str(row[2]),
                        mapping_version=str(row[4]),
                        country_name=str(row[5]),
                        iso_alpha2=str(row[6]),
                        centroid_latitude=float(row[7]),
                        centroid_longitude=float(row[8]),
                    ),
                    network_review_band=band,
                    entry_snapshot_id=str(row[10]),
                    entry_cutoff=self._ts(row[11]),
                    primary_reason=str(row[12]),
                    relevant_recent_transaction_count=int(row[13] or 0),
                )
            )
        return AlertListPageV2(items=tuple(items), next_cursor=next_cursor, has_more=has_more)

    def list_transactions(
        self, request: TransactionListRequestV2 | None = None
    ) -> TransactionListPageV2:
        request = request or TransactionListRequestV2()
        self._validate_query_text(request.q)
        rows, next_cursor, has_more = self._repository.list_transaction_rows(
            cursor=request.cursor,
            limit=request.limit,
            q=request.q,
            priority=request.priority.value if request.priority is not None else None,
            alert_involvement=request.alert_involvement,
            date_from=request.date_from,
            date_to=request.date_to,
            currency=request.currency,
            payment_format=request.payment_format,
            sending_bank_country=request.sending_bank_country,
            receiving_bank_country=request.receiving_bank_country,
        )
        items = tuple(self._transaction_list_item(row) for row in rows)
        return TransactionListPageV2(items=items, next_cursor=next_cursor, has_more=has_more)

    def list_accounts(self, request: AccountListRequestV2 | None = None) -> AccountListPageV2:
        request = request or AccountListRequestV2()
        self._validate_query_text(request.q)
        snapshot = self._snapshot_from_row(self._repository.latest_complete_snapshot_row())
        rows, next_cursor, has_more = self._repository.list_account_rows(
            snapshot_id=snapshot.snapshot_id,
            cursor=request.cursor,
            limit=request.limit,
            q=request.q,
            band=request.band.value if request.band is not None else None,
            bank_country=request.bank_country,
            alert_involvement=request.alert_involvement,
        )
        items: list[AccountListItemV2] = []
        for row in rows:
            try:
                band = NetworkReviewBand(str(row[8]))
            except ValueError as exc:
                raise DataIntegrityError("Account list contains an unknown persisted review band") from exc
            items.append(
                AccountListItemV2(
                    account_ref=str(row[0]),
                    bank_id=str(row[1]),
                    account_id=str(row[2]),
                    bank_country=BankCountryV2(
                        bank_id=str(row[1]),
                        mapping_version=str(row[3]),
                        country_name=str(row[4]),
                        iso_alpha2=str(row[5]),
                        centroid_latitude=float(row[6]),
                        centroid_longitude=float(row[7]),
                    ),
                    network_review_band=band,
                    network_pattern_score=float(row[9]) if row[9] is not None else None,
                    latest_snapshot_id=str(row[10]),
                    latest_detector_cutoff=self._ts(row[11]),
                    incoming_count=int(row[12] or 0),
                    outgoing_count=int(row[13] or 0),
                    alert_involvement=bool(row[14]),
                )
            )
        return AccountListPageV2(items=tuple(items), next_cursor=next_cursor, has_more=has_more)

    def get_runtime_metadata(self) -> RuntimeMetadataV2:
        snapshot = self._snapshot_from_row(self._repository.latest_complete_snapshot_row())
        return RuntimeMetadataV2(
            latest_snapshot_id=snapshot.snapshot_id,
            latest_snapshot_cutoff=snapshot.cutoff_timestamp,
        )

    def resolve_context(
        self,
        subject_type: SubjectType | str,
        subject_ref: str,
        origin_ref: str | None = None,
    ) -> InvestigationContextV2:
        try:
            subject_type = SubjectType(subject_type)
        except ValueError as exc:
            raise InvalidInputError("Unknown investigation subject type") from exc
        if not subject_ref:
            raise InvalidInputError("subject_ref must be non-empty")
        if subject_type is SubjectType.ALERT:
            if origin_ref is not None:
                raise InvalidContextError("Alerts do not accept a separate historical origin")
            return self._context_for_alert(subject_ref)
        if subject_type is SubjectType.TRANSACTION:
            if origin_ref is not None:
                raise InvalidContextError("Transactions do not accept a separate historical origin")
            return self._context_for_transaction(subject_ref)
        if origin_ref is None:
            return self._context_for_latest_account(subject_ref)
        if origin_ref.startswith("alert_"):
            return self._context_for_account_from_alert(subject_ref, origin_ref)
        if origin_ref.startswith("txn_"):
            return self._context_for_account_from_transaction(subject_ref, origin_ref)
        raise InvalidContextError("Account origin must be an alert or transaction reference")

    def get_alert_context(self, alert_ref: str) -> AlertContextV2:
        context = self._context_for_alert(alert_ref)
        alert = self._alert_facts(alert_ref)
        account = self._account_identity(alert.account_ref)
        state = self._account_detector_state(alert.entry_snapshot_id, alert.account_ref)
        support = self._detector_support(alert.entry_snapshot_id, alert.account_ref)
        evidence = [
            self._make_evidence(
                EvidenceType.ALERT_CONTEXT,
                SubjectType.ALERT,
                alert_ref,
                context.context_identity,
                {},
            ),
            self._make_evidence(
                EvidenceType.DETECTOR_STATE,
                SubjectType.ACCOUNT,
                alert.account_ref,
                context.context_identity,
                {},
            ),
        ]
        return AlertContextV2(
            context=context,
            alert=alert,
            account_identity=account,
            detector_state=state,
            detector_support=support,
            evidence_ids=tuple(item.evidence_id for item in evidence),
        )

    def get_transaction_detail(self, transaction_ref: str) -> TransactionDetailV2:
        context, facts, review = self._transaction_context_bundle(transaction_ref)
        route = self._bank_country_route(facts)
        behavioral = self._transaction_behavioral_bundle(facts, context)
        indicators = behavioral.indicators
        evidences = (
            self._evidence_from_authoritative_parts(
                EvidenceType.TRANSACTION_FACTS,
                SubjectType.TRANSACTION,
                transaction_ref,
                context,
                {},
                facts,
                [transaction_ref],
                1,
                "selected-transaction-v1",
                UITargetV2.TRANSACTION_FACTS,
            ),
            self._evidence_from_authoritative_parts(
                EvidenceType.TRANSACTION_PRIORITY,
                SubjectType.TRANSACTION,
                transaction_ref,
                context,
                {},
                review,
                [transaction_ref],
                1,
                "selected-transaction-v1",
                UITargetV2.REVIEW_PRIORITY,
            ),
            self._evidence_from_authoritative_parts(
                EvidenceType.BANK_COUNTRY_ROUTE,
                SubjectType.TRANSACTION,
                transaction_ref,
                context,
                {},
                route,
                [transaction_ref],
                1,
                "selected-transaction-v1",
                UITargetV2.BANK_COUNTRY_ROUTE,
            ),
        )
        sender_card = self._endpoint_account_card(
            facts.sender,
            context,
            Direction.OUTGOING,
            behavior=indicators.account_network_behavior[facts.sender.account_ref],
        )
        receiver_card = self._endpoint_account_card(
            facts.receiver,
            context,
            Direction.INCOMING,
            behavior=indicators.account_network_behavior[facts.receiver.account_ref],
        )
        investigation_indicators = self._transaction_investigation_indicators(
            indicators, behavioral.evidence
        )
        activity_context = self._transaction_activity_context(facts, context)
        local_network_summary = LocalNetworkSummaryV2(
            sender=self._account_network_from_resolved(
                facts.sender, facts.receiver.account_ref, context
            ),
            receiver=self._account_network_from_resolved(
                facts.receiver, facts.sender.account_ref, context
            ),
        )
        evidence_by_id = {
            item.evidence_id: item for item in (*evidences, *behavioral.evidence)
        }
        summary_evidence: list[EvidenceV2] = []
        seen_ids: set[str] = set()
        for evidence_id in [
            *(item.evidence_id for item in evidences),
            *(item.evidence_id for item in investigation_indicators),
        ]:
            if evidence_id not in seen_ids:
                summary_evidence.append(evidence_by_id[evidence_id])
                seen_ids.add(evidence_id)
        support_refs = list(
            dict.fromkeys(
                ref
                for evidence in summary_evidence
                for ref in evidence.supporting_transaction_refs
            )
        )
        support_rows = self._repository.supporting_transaction_rows(
            support_refs,
            max_refs=SUPPORT_LIMIT * len(summary_evidence),
        )
        support_by_ref = {str(row[0]): row for row in support_rows}
        supporting_evidence_summary = tuple(
            self._supporting_evidence_summary_item(
                self._display_evidence_from_rows(
                    evidence,
                    [support_by_ref[ref] for ref in evidence.supporting_transaction_refs],
                ),
                f"E{index}",
            )
            for index, evidence in enumerate(summary_evidence, 1)
        )
        return TransactionDetailV2(
            context=context,
            transaction_facts=facts,
            review_state=review,
            bank_country_route=route,
            sender_account_card=sender_card,
            receiver_account_card=receiver_card,
            investigation_indicators=investigation_indicators,
            activity_context=activity_context,
            local_network_summary=local_network_summary,
            supporting_evidence_summary=supporting_evidence_summary,
            indicators=indicators,
            evidence_ids=tuple(item.evidence_id for item in evidences),
        )

    def get_account_detail(self, account_ref: str, origin_ref: str | None = None) -> AccountDetailV2:
        context = self.resolve_context(SubjectType.ACCOUNT, account_ref, origin_ref)
        account = self._account_identity(account_ref)
        if context.detector_snapshot_id is None:
            raise DataIntegrityError("Resolved account context has no detector snapshot")
        state = self._account_detector_state(context.detector_snapshot_id, account_ref)
        support = self._detector_support(context.detector_snapshot_id, account_ref)
        activity = self._account_activity(account_ref, context)
        activity_over_time = tuple(self._activity_buckets(account_ref, context))
        currency_activity = self._currency_activity(activity_over_time)
        flows = tuple(self._bank_country_flows(account_ref, context))
        history, history_total = self._alert_history(account_ref, context)
        evidence_ids = (
            self._make_evidence(
                EvidenceType.DETECTOR_STATE,
                SubjectType.ACCOUNT,
                account_ref,
                context.context_identity,
                {},
            ).evidence_id,
            self._make_evidence(
                EvidenceType.ACCOUNT_ACTIVITY,
                SubjectType.ACCOUNT,
                account_ref,
                context.context_identity,
                {},
            ).evidence_id,
            self._make_evidence(
                EvidenceType.NETWORK_BEHAVIOR,
                SubjectType.ACCOUNT,
                account_ref,
                context.context_identity,
                {},
            ).evidence_id,
        )
        return AccountDetailV2(
            account_identity=account,
            context=context,
            network_review_state=state,
            detector_support=support,
            observed_activity=activity,
            activity_over_time=activity_over_time,
            currency_activity=currency_activity,
            bank_country_flows=flows,
            alert_history=tuple(history),
            alert_history_total=history_total,
            alert_history_truncated=history_total > len(history),
            evidence_ids=evidence_ids,
        )

    def list_account_transactions(
        self,
        account_ref: str,
        *,
        origin_ref: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        direction: Direction | str = Direction.BOTH,
        currency: str | None = None,
        counterparty_account_ref: str | None = None,
    ) -> AccountTransactionPageV2:
        context = self.resolve_context(SubjectType.ACCOUNT, account_ref, origin_ref)
        try:
            direction = Direction(direction)
        except ValueError as exc:
            raise InvalidInputError("Unknown transaction direction") from exc
        rows, next_cursor, has_more = self._repository.list_account_transaction_rows(
            account_ref=account_ref,
            context_time=parse_canonical_timestamp(context.context_time),
            limit=limit,
            direction=direction,
            currency=currency,
            counterparty_account_ref=counterparty_account_ref,
            cursor=cursor,
        )
        return AccountTransactionPageV2(
            items=tuple(self._transaction_list_item(row) for row in rows),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def get_account_network(
        self,
        account_ref: str,
        *,
        origin_ref: str | None = None,
        context: InvestigationContextV2 | None = None,
    ) -> AccountNetworkV2:
        context = context or self.resolve_context(SubjectType.ACCOUNT, account_ref, origin_ref)
        self._validate_account_in_context(account_ref, context)
        selected_cp = self._selected_counterparty(account_ref, context)
        root = self._account_identity(account_ref)
        return self._account_network_from_resolved(root, selected_cp, context)

    def _account_network_from_resolved(
        self,
        root: AccountIdentityV2,
        selected_cp: str | None,
        context: InvestigationContextV2,
    ) -> AccountNetworkV2:
        account_ref = root.account_ref
        self._validate_account_in_context(account_ref, context)
        context_time = parse_canonical_timestamp(context.context_time)
        historical_count = self._repository.network_counterparty_count(account_ref, context_time)
        selected_row: tuple[Any, ...] | None = None
        selected_is_historical = False
        if selected_cp is not None and selected_cp != account_ref:
            selected_row = self._repository.network_relationship_row(
                account_ref, selected_cp, context_time
            )
            selected_is_historical = int(selected_row[11] or 0) > 0
        reserve = 1 if selected_row is not None else 0
        historical_rows = self._repository.network_rows(
            account_ref, context_time, limit=NETWORK_LIMIT - reserve,
            exclude_counterparty_ref=selected_cp if selected_row is not None else None,
        )
        rows: list[tuple[Any, ...]] = []
        if selected_row is not None:
            rows.append(selected_row)
        rows.extend(historical_rows)
        relationships = [self._network_relationship(row, selected_cp) for row in rows]
        total_counterparties = historical_count + (1 if selected_row is not None and not selected_is_historical else 0)
        return AccountNetworkV2(
            root=root,
            context=context.context_identity,
            total_direct_counterparties=total_counterparties,
            shown_counterparties=len(relationships),
            truncated=total_counterparties > NETWORK_LIMIT,
            relationships=tuple(relationships),
        )

    def get_behavioral_indicators(
        self,
        subject_type: SubjectType | str,
        subject_ref: str,
        *,
        context: InvestigationContextV2 | None = None,
        origin_ref: str | None = None,
        account_ref: str | None = None,
    ) -> BehavioralIndicatorsV2:
        try:
            subject_type = SubjectType(subject_type)
        except ValueError as exc:
            raise InvalidInputError("Unknown investigation subject type") from exc
        if subject_type is SubjectType.TRANSACTION:
            if context is None:
                context, facts, _ = self._transaction_context_bundle(subject_ref)
            else:
                facts = self._transaction_facts(subject_ref)
            return self._transaction_behavioral_bundle(facts, context).indicators

        context = context or self.resolve_context(subject_type, subject_ref, origin_ref)
        root = account_ref or (
            context.root_account_refs[0] if context.root_account_refs else subject_ref
        )
        self._validate_account_in_context(root, context)
        behavior = self._network_behavior(root, context)
        evidence = self._make_evidence(
            EvidenceType.NETWORK_BEHAVIOR,
            SubjectType.ACCOUNT,
            root,
            context.context_identity,
            {},
        )
        return BehavioralIndicatorsV2(
            context=context.context_identity,
            account_network_behavior={root: behavior},
            evidence_ids=(evidence.evidence_id,),
        )

    def _transaction_behavioral_bundle(
        self, facts: TransactionFactsV2, context: InvestigationContextV2
    ) -> _TransactionBehavioralBundle:
        context_time = parse_canonical_timestamp(context.context_time)
        sender_amount = self._amount_behavior(facts, AmountSide.SENDER_PAID, context)
        receiver_amount = self._amount_behavior(
            facts, AmountSide.RECEIVER_RECEIVED, context
        )
        relationship = self._relationship(
            facts.sender.account_ref, facts.receiver.account_ref, context
        )
        currency = CurrencyBehaviorV2(
            transaction_ref=facts.transaction_ref,
            cross_currency=facts.cross_currency,
            currency_pair=facts.currency_pair,
        )
        behaviors = {
            root: self._network_behavior(root, context)
            for root in context.root_account_refs
        }

        evidence: list[EvidenceV2] = []
        for side, amount in (
            (AmountSide.SENDER_PAID, sender_amount),
            (AmountSide.RECEIVER_RECEIVED, receiver_amount),
        ):
            evidence.append(
                self._evidence_from_authoritative_parts(
                    EvidenceType.AMOUNT_BEHAVIOR,
                    SubjectType.TRANSACTION,
                    facts.transaction_ref,
                    context,
                    {"side": side.value},
                    amount,
                    self._repository.support_refs_for_amount(
                        account_ref=amount.account_ref,
                        context_time=context_time,
                        side=side.value,
                        currency=amount.currency,
                    ),
                    amount.sample_size,
                    "most-recent-same-side-currency-v1",
                    UITargetV2.INVESTIGATION_INDICATORS,
                )
            )
        evidence.append(
            self._evidence_from_authoritative_parts(
                EvidenceType.COUNTERPARTY_RELATIONSHIP,
                SubjectType.ACCOUNT,
                facts.sender.account_ref,
                context,
                {"counterparty_ref": facts.receiver.account_ref},
                relationship,
                self._repository.support_refs_for_relationship(
                    facts.sender.account_ref, facts.receiver.account_ref, context_time
                ),
                relationship.previous_interaction_count,
                "most-recent-relationship-v1",
                UITargetV2.COUNTERPARTY_TABLE,
            )
        )
        evidence.append(
            self._evidence_from_authoritative_parts(
                EvidenceType.CURRENCY_BEHAVIOR,
                SubjectType.TRANSACTION,
                facts.transaction_ref,
                context,
                {},
                currency,
                [facts.transaction_ref],
                1,
                "selected-transaction-v1",
                UITargetV2.CURRENCY_ACTIVITY,
            )
        )
        for root, behavior in behaviors.items():
            evidence.append(
                self._evidence_from_authoritative_parts(
                    EvidenceType.NETWORK_BEHAVIOR,
                    SubjectType.ACCOUNT,
                    root,
                    context,
                    {},
                    behavior,
                    self._repository.support_refs_for_network_behavior(root, context_time),
                    behavior.velocity_24h.total_count,
                    "most-recent-prior-24h-v1",
                    UITargetV2.ACCOUNT_NETWORK,
                )
            )
        indicators = BehavioralIndicatorsV2(
            context=context.context_identity,
            sender_amount_behavior=sender_amount,
            receiver_amount_behavior=receiver_amount,
            counterparty_relationship=relationship,
            account_network_behavior=behaviors,
            cross_currency=currency,
            evidence_ids=tuple(item.evidence_id for item in evidence),
        )
        return _TransactionBehavioralBundle(indicators=indicators, evidence=tuple(evidence))

    def get_relationship_context(
        self,
        account_ref: str,
        counterparty_ref: str,
        *,
        origin_ref: str | None = None,
        context: InvestigationContextV2 | None = None,
    ) -> RelationshipContextV2:
        context = context or self.resolve_context(SubjectType.ACCOUNT, account_ref, origin_ref)
        self._validate_account_in_context(account_ref, context)
        network = self.get_account_network(account_ref, context=context)
        if counterparty_ref not in {item.counterparty.account_ref for item in network.relationships}:
            raise InvalidContextError("Counterparty is not authorized by the bounded direct network")
        return self._relationship(account_ref, counterparty_ref, context)

    def get_supporting_evidence(self, evidence_id: str) -> DisplayEvidenceV2:
        evidence = self.resolve_evidence(evidence_id)
        support_evidence = self._make_evidence(
            EvidenceType.SUPPORTING_TRANSACTIONS,
            evidence.subject_type,
            evidence.subject_ref,
            evidence.context_identity,
            {
                "source_evidence_type": evidence.evidence_type.value,
                "source_parameters": evidence.parameters,
            },
        )
        return self._display_evidence(support_evidence)

    def resolve_evidence(self, evidence_id: str) -> EvidenceV2:
        identity = decode_evidence_id(evidence_id)
        context = self._resolve_embedded_context(identity)
        self._validate_subject_context(identity.subject_type, identity.subject_ref, context)
        recomputed = self._make_evidence(
            identity.evidence_type,
            identity.subject_type,
            identity.subject_ref,
            context.context_identity,
            identity.parameters,
        )
        if recomputed.evidence_id != evidence_id:
            raise InvalidContextError("Evidence identity does not match recomputed authoritative facts")
        return recomputed

    def display_evidence(self, evidence_id: str) -> DisplayEvidenceV2:
        return self._display_evidence(self.resolve_evidence(evidence_id))

    @staticmethod
    def _validate_query_text(value: str | None) -> None:
        if value is not None and len(value) > MAX_LIST_QUERY_TEXT:
            raise InvalidInputError(f"q must be at most {MAX_LIST_QUERY_TEXT} characters")

    @staticmethod
    def _normalize_alert_membership(values: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if values is None:
            return None
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value:
                raise InvalidInputError("Alert membership refs must be non-empty strings")
            if value not in seen:
                normalized.append(value)
                seen.add(value)
        return tuple(normalized)

    # ---------- Context resolution ----------

    def _context_for_alert(self, alert_ref: str) -> InvestigationContextV2:
        alert = self._alert_facts(alert_ref)
        snapshot = self._snapshot(alert.entry_snapshot_id)
        if snapshot.status != "COMPLETE" or snapshot.cutoff_timestamp != alert.entry_cutoff:
            raise DataIntegrityError("Alert entry snapshot/cutoff is inconsistent")
        identity = ContextIdentityV2(
            context_kind=ContextKind.ALERT_ENTRY,
            context_ref=alert_ref,
            context_time=alert.entry_cutoff,
            snapshot_id=alert.entry_snapshot_id,
        )
        return InvestigationContextV2(
            subject_type=SubjectType.ALERT,
            subject_ref=alert_ref,
            context_identity=identity,
            context_time=alert.entry_cutoff,
            detector_snapshot_id=alert.entry_snapshot_id,
            detector_cutoff=alert.entry_cutoff,
            root_account_refs=(alert.account_ref,),
            alert_ref=alert_ref,
        )

    def _context_for_transaction(self, transaction_ref: str) -> InvestigationContextV2:
        context, _, _ = self._transaction_context_bundle(transaction_ref)
        return context

    def _transaction_context_bundle(
        self, transaction_ref: str
    ) -> tuple[InvestigationContextV2, TransactionFactsV2, TransactionReviewStateV2]:
        facts = self._transaction_facts(transaction_ref)
        review = self._transaction_review_state(transaction_ref)
        context_dt = parse_canonical_timestamp(facts.transaction_timestamp)
        snapshot_id = review.snapshot_id
        detector_cutoff = review.detector_cutoff
        if snapshot_id is None or detector_cutoff is None:
            raise DataIntegrityError("Transaction review state has no applicable detector snapshot")
        snapshot = self._snapshot(snapshot_id)
        if snapshot.status != "COMPLETE":
            raise DataIntegrityError("Transaction refers to a non-COMPLETE detector snapshot")
        if snapshot.cutoff_timestamp != detector_cutoff:
            raise DataIntegrityError("Transaction detector cutoff does not match its snapshot")
        if parse_canonical_timestamp(detector_cutoff) > context_dt:
            raise InvalidContextError("Transaction review state points to a future detector snapshot")
        latest = self._snapshot_from_row(self._repository.latest_complete_snapshot_row(context_dt))
        if latest.snapshot_id != snapshot_id:
            raise DataIntegrityError("Transaction review state does not use the latest COMPLETE snapshot <= T")
        identity = ContextIdentityV2(
            context_kind=ContextKind.TRANSACTION,
            context_ref=transaction_ref,
            context_time=facts.transaction_timestamp,
            snapshot_id=snapshot_id,
        )
        context = InvestigationContextV2(
            subject_type=SubjectType.TRANSACTION,
            subject_ref=transaction_ref,
            context_identity=identity,
            context_time=facts.transaction_timestamp,
            detector_snapshot_id=snapshot_id,
            detector_cutoff=detector_cutoff,
            root_account_refs=(facts.sender.account_ref, facts.receiver.account_ref),
            selected_transaction_ref=transaction_ref,
        )
        return context, facts, review

    def _context_for_latest_account(self, account_ref: str) -> InvestigationContextV2:
        self._account_identity(account_ref)
        snapshot = self._snapshot_from_row(self._repository.latest_complete_snapshot_row())
        identity = ContextIdentityV2(
            context_kind=ContextKind.SNAPSHOT,
            context_ref=snapshot.snapshot_id,
            context_time=snapshot.cutoff_timestamp,
            snapshot_id=snapshot.snapshot_id,
        )
        return InvestigationContextV2(
            subject_type=SubjectType.ACCOUNT,
            subject_ref=account_ref,
            context_identity=identity,
            context_time=snapshot.cutoff_timestamp,
            detector_snapshot_id=snapshot.snapshot_id,
            detector_cutoff=snapshot.cutoff_timestamp,
            root_account_refs=(account_ref,),
        )

    def _context_for_account_from_alert(self, account_ref: str, alert_ref: str) -> InvestigationContextV2:
        self._account_identity(account_ref)
        base = self._context_for_alert(alert_ref)
        if account_ref not in base.root_account_refs:
            raise InvalidContextError("Alert origin does not authorize this account")
        return base.model_copy(
            update={"subject_type": SubjectType.ACCOUNT, "subject_ref": account_ref}
        )

    def _context_for_account_from_transaction(
        self, account_ref: str, transaction_ref: str
    ) -> InvestigationContextV2:
        self._account_identity(account_ref)
        base = self._context_for_transaction(transaction_ref)
        if account_ref not in base.root_account_refs:
            raise InvalidContextError("Transaction origin does not authorize this account")
        return base.model_copy(
            update={"subject_type": SubjectType.ACCOUNT, "subject_ref": account_ref}
        )

    def _resolve_embedded_context(self, identity: EvidenceIdentityV2) -> InvestigationContextV2:
        embedded = identity.context_identity
        if embedded.context_kind is ContextKind.ALERT_ENTRY:
            context = self._context_for_alert(embedded.context_ref)
        elif embedded.context_kind is ContextKind.TRANSACTION:
            context = self._context_for_transaction(embedded.context_ref)
        else:
            snapshot = self._snapshot(embedded.context_ref)
            if snapshot.status != "COMPLETE":
                raise InvalidContextError("Evidence snapshot context is not COMPLETE")
            context = InvestigationContextV2(
                subject_type=identity.subject_type,
                subject_ref=identity.subject_ref,
                context_identity=ContextIdentityV2(
                    context_kind=ContextKind.SNAPSHOT,
                    context_ref=snapshot.snapshot_id,
                    context_time=snapshot.cutoff_timestamp,
                    snapshot_id=snapshot.snapshot_id,
                ),
                context_time=snapshot.cutoff_timestamp,
                detector_snapshot_id=snapshot.snapshot_id,
                detector_cutoff=snapshot.cutoff_timestamp,
                root_account_refs=(identity.subject_ref,) if identity.subject_type is SubjectType.ACCOUNT else (),
            )
        if context.context_identity != embedded:
            raise InvalidContextError("Evidence embedded context does not match authoritative context")
        return context

    # ---------- Deterministic facts ----------

    def _account_identity(self, account_ref: str) -> AccountIdentityV2:
        row = self._repository.get_account_row(account_ref)
        return AccountIdentityV2(
            account_ref=str(row[0]),
            source_dataset=str(row[1]),
            bank_id=str(row[2]),
            account_id=str(row[3]),
            bank_country=BankCountryV2(
                bank_id=str(row[2]),
                mapping_version=str(row[4]),
                country_name=str(row[5]),
                iso_alpha2=str(row[6]),
                centroid_latitude=float(row[7]),
                centroid_longitude=float(row[8]),
            ),
        )

    def _transaction_facts(self, transaction_ref: str) -> TransactionFactsV2:
        row = self._repository.get_transaction_row(transaction_ref)
        timestamp = self._ts(row[1])
        sender = AccountIdentityV2(
            account_ref=str(row[2]), source_dataset=str(row[24]), bank_id=str(row[3]), account_id=str(row[4]),
            bank_country=BankCountryV2(
                bank_id=str(row[3]), mapping_version=str(row[5]), country_name=str(row[6]),
                iso_alpha2=str(row[7]), centroid_latitude=float(row[8]), centroid_longitude=float(row[9]),
            ),
        )
        receiver = AccountIdentityV2(
            account_ref=str(row[10]), source_dataset=str(row[24]), bank_id=str(row[11]), account_id=str(row[12]),
            bank_country=BankCountryV2(
                bank_id=str(row[11]), mapping_version=str(row[13]), country_name=str(row[14]),
                iso_alpha2=str(row[15]), centroid_latitude=float(row[16]), centroid_longitude=float(row[17]),
            ),
        )
        payment_currency = str(row[19])
        receiving_currency = str(row[21])
        cross_currency = bool(row[23])
        if cross_currency != (payment_currency != receiving_currency):
            raise DataIntegrityError("Transaction cross-currency materialization is inconsistent")
        return TransactionFactsV2(
            transaction_ref=str(row[0]), transaction_timestamp=timestamp, sender=sender, receiver=receiver,
            amount_paid=canonical_decimal(row[18]), payment_currency=payment_currency,
            amount_received=canonical_decimal(row[20]), receiving_currency=receiving_currency,
            payment_format=str(row[22]), cross_currency=cross_currency,
            currency_pair=f"{payment_currency} -> {receiving_currency}",
        )

    def _transaction_review_state(self, transaction_ref: str) -> TransactionReviewStateV2:
        row = self._repository.get_transaction_review_row(transaction_ref)
        return TransactionReviewStateV2(
            transaction_ref=str(row[0]), snapshot_id=self._str_or_none(row[1]),
            detector_cutoff=self._ts_or_none(row[2]), sender_band=self._band(row[3]),
            receiver_band=self._band(row[4]), aml_review_priority=self._band(row[5]),
            derivation_code=str(row[6]), derivation_text=str(row[7]), alert_involvement=bool(row[8]),
            sender_related_alert_ref=self._str_or_none(row[9]),
            receiver_related_alert_ref=self._str_or_none(row[10]),
        )

    def _snapshot(self, snapshot_id: str) -> DetectorSnapshotV2:
        return self._snapshot_from_row(self._repository.get_snapshot_row(snapshot_id))

    def _snapshot_from_row(self, row: tuple[Any, ...]) -> DetectorSnapshotV2:
        return DetectorSnapshotV2(
            snapshot_id=str(row[0]), source_dataset=str(row[1]), cutoff_timestamp=self._ts(row[2]),
            algorithm_name=str(row[3]), algorithm_variant=str(row[4]), algorithm_version=str(row[5]),
            upstream_code_provenance=str(row[6]), identity_rule_version=str(row[7]),
            eligibility_rule_version=str(row[8]), community_algorithm=str(row[9]),
            community_resolution=str(row[10]), community_seed=int(row[11]), config_hash=str(row[12]),
            status=str(row[13]), account_count=int(row[14]), eligible_account_count=int(row[15]),
            scored_account_count=int(row[16]),
        )

    def _account_detector_state(self, snapshot_id: str, account_ref: str) -> AccountDetectorStateV2:
        row = self._repository.get_account_detector_state_row(snapshot_id, account_ref)
        return AccountDetectorStateV2(
            snapshot_id=str(row[0]), account_ref=str(row[1]), scoring_eligible=bool(row[2]),
            network_pattern_score=float(row[3]) if row[3] is not None else None,
            rank=int(row[4]) if row[4] is not None else None,
            percentile=float(row[5]) if row[5] is not None else None,
            network_review_band=self._band(row[6]), unscored_reason=self._str_or_none(row[7]),
        )

    def _detector_support(self, snapshot_id: str, account_ref: str) -> DetectorSupportV2 | None:
        row = self._repository.get_account_detector_support_row(snapshot_id, account_ref)
        if row is None:
            return None
        return DetectorSupportV2(
            snapshot_id=str(row[0]), account_ref=str(row[1]),
            first_order_neighbor_count=int(row[2]) if row[2] is not None else None,
            second_order_neighbor_count=int(row[3]) if row[3] is not None else None,
            community_id_or_stable_snapshot_local_index=self._str_or_none(row[4]),
            block_measure_1=float(row[5]) if row[5] is not None else None,
            block_measure_2=float(row[6]) if row[6] is not None else None,
            block_measure_3=float(row[7]) if row[7] is not None else None,
            network_pattern_score=float(row[8]) if row[8] is not None else None,
        )

    def _detector_state_evidence_facts(
        self, snapshot_id: str, account_ref: str
    ) -> DetectorStateEvidenceFactsV2:
        snapshot = self._snapshot(snapshot_id)
        state = self._account_detector_state(snapshot_id, account_ref)
        support = self._detector_support(snapshot_id, account_ref)
        return DetectorStateEvidenceFactsV2(
            snapshot_id=state.snapshot_id,
            account_ref=state.account_ref,
            scoring_eligible=state.scoring_eligible,
            eligible_account_count=snapshot.eligible_account_count,
            network_pattern_score=state.network_pattern_score,
            rank=state.rank,
            percentile=state.percentile,
            network_review_band=state.network_review_band,
            unscored_reason=state.unscored_reason,
            first_order_neighbor_count=(
                support.first_order_neighbor_count if support is not None else None
            ),
            second_order_neighbor_count=(
                support.second_order_neighbor_count if support is not None else None
            ),
            block_measure_1=support.block_measure_1 if support is not None else None,
            block_measure_2=support.block_measure_2 if support is not None else None,
            block_measure_3=support.block_measure_3 if support is not None else None,
        )

    def _alert_facts(self, alert_ref: str) -> AlertContextFactsV2:
        row = self._repository.get_alert_row(alert_ref)
        cutoff = self._require_datetime(row[3])
        recent_count = self._repository.recent_alert_transaction_count(str(row[1]), cutoff)
        return AlertContextFactsV2(
            alert_ref=str(row[0]), account_ref=str(row[1]), entry_snapshot_id=str(row[2]),
            entry_cutoff=canonical_timestamp(cutoff),
            entry_score=float(row[4]) if row[4] is not None else None,
            entry_rank=int(row[5]) if row[5] is not None else None,
            entry_percentile=float(row[6]) if row[6] is not None else None,
            reason_code=str(row[7]), created_state=str(row[8]),
            relevant_recent_transaction_count=recent_count,
        )

    def _account_activity(
        self, account_ref: str, context: InvestigationContextV2
    ) -> AccountActivityV2:
        row = self._repository.account_activity_row(
            account_ref, parse_canonical_timestamp(context.context_time)
        )
        return AccountActivityV2(
            account_ref=account_ref,
            incoming_count=int(row[0] or 0), outgoing_count=int(row[1] or 0),
            distinct_counterparties=int(row[2] or 0),
            incoming_distinct_counterparties=int(row[3] or 0),
            outgoing_distinct_counterparties=int(row[4] or 0),
            first_observed_timestamp=self._ts_or_none(row[5]),
            most_recent_observed_timestamp=self._ts_or_none(row[6]),
        )

    def _amount_behavior(
        self, facts: TransactionFactsV2, side: AmountSide, context: InvestigationContextV2
    ) -> AmountBehaviorV2:
        context_time = parse_canonical_timestamp(context.context_time)
        if side is AmountSide.SENDER_PAID:
            account_ref = facts.sender.account_ref
            currency = facts.payment_currency
            selected_amount = Decimal(facts.amount_paid)
        else:
            account_ref = facts.receiver.account_ref
            currency = facts.receiving_currency
            selected_amount = Decimal(facts.amount_received)
        n, median_value, at_or_below = self._repository.amount_history_stats(
            account_ref=account_ref, context_time=context_time, side=side.value, currency=currency,
            selected_amount=selected_amount,
        )
        if n < 5:
            quality = HistoryQuality.INSUFFICIENT
            median = percentile = None
        elif n < 20:
            quality = HistoryQuality.LIMITED
            if median_value is None:
                raise DataIntegrityError("Amount history median is missing for non-empty history")
            median = canonical_decimal(median_value)
            percentile = None
        else:
            quality = HistoryQuality.SUFFICIENT
            if median_value is None:
                raise DataIntegrityError("Amount history median is missing for non-empty history")
            median = canonical_decimal(median_value)
            percentile = float(Decimal(100) * Decimal(at_or_below) / Decimal(n))
        return AmountBehaviorV2(
            side=side, account_ref=account_ref, history_quality=quality, sample_size=n,
            selected_amount=canonical_decimal(selected_amount), currency=currency,
            historical_median=median, empirical_percentile=percentile,
        )

    def _relationship(
        self, account_ref: str, counterparty_ref: str, context: InvestigationContextV2
    ) -> RelationshipContextV2:
        row = self._repository.relationship_row(
            account_ref, counterparty_ref, parse_canonical_timestamp(context.context_time)
        )
        total = int(row[0] or 0)
        return RelationshipContextV2(
            account_ref=account_ref, counterparty_account_ref=counterparty_ref,
            seen_before=total > 0, new_counterparty=total == 0,
            previous_interaction_count=total, root_to_counterparty_count=int(row[1] or 0),
            counterparty_to_root_count=int(row[2] or 0),
            first_previous_timestamp=self._ts_or_none(row[3]),
            most_recent_previous_timestamp=self._ts_or_none(row[4]),
        )

    def _network_behavior(
        self, account_ref: str, context: InvestigationContextV2
    ) -> NetworkBehaviorV2:
        context_time = parse_canonical_timestamp(context.context_time)
        one = self._repository.velocity_row(account_ref, context_time, timedelta(hours=1))
        day = self._repository.velocity_row(account_ref, context_time, timedelta(hours=24))
        fan_in, fan_out = self._repository.fan_row(account_ref, context_time)
        return NetworkBehaviorV2(
            account_ref=account_ref,
            velocity_1h=VelocityWindowV2(window="1h", incoming_count=one[0], outgoing_count=one[1], total_count=one[2]),
            velocity_24h=VelocityWindowV2(window="24h", incoming_count=day[0], outgoing_count=day[1], total_count=day[2]),
            fan_in_24h=fan_in, fan_out_24h=fan_out,
        )

    def _bank_country_route(self, facts: TransactionFactsV2) -> BankCountryRouteV2:
        sender = facts.sender.bank_country
        receiver = facts.receiver.bank_country
        if sender.mapping_version != receiver.mapping_version:
            raise DataIntegrityError("Bank Country mapping versions do not match")
        return BankCountryRouteV2(
            transaction_ref=facts.transaction_ref,
            sending_bank=sender, receiving_bank=receiver,
            same_bank_country=sender.iso_alpha2 == receiver.iso_alpha2,
            mapping_version=sender.mapping_version,
        )

    def _endpoint_account_card(
        self,
        account: AccountIdentityV2,
        context: InvestigationContextV2,
        primary_direction: Direction,
        *,
        behavior: NetworkBehaviorV2 | None = None,
    ) -> EndpointAccountCardV2:
        if context.detector_snapshot_id is None or context.detector_cutoff is None:
            raise DataIntegrityError("Transaction context has no applicable detector snapshot")
        state = self._account_detector_state(context.detector_snapshot_id, account.account_ref)
        behavior = behavior or self._network_behavior(account.account_ref, context)
        if primary_direction is Direction.OUTGOING:
            counterparty_count = behavior.fan_out_24h
            direction_text = "outgoing"
        elif primary_direction is Direction.INCOMING:
            counterparty_count = behavior.fan_in_24h
            direction_text = "incoming"
        else:
            raise InvalidInputError("Endpoint account card direction must be incoming or outgoing")
        summary = (
            f"{behavior.velocity_24h.total_count} transactions in the prior 24h; "
            f"{counterparty_count} distinct {direction_text} counterparties in the same bounded context."
        )
        return EndpointAccountCardV2(
            account=account,
            network_review_band=state.network_review_band,
            detector_cutoff=context.detector_cutoff,
            observed_summary=summary,
        )

    def _transaction_investigation_indicators(
        self,
        indicators: BehavioralIndicatorsV2,
        evidence_items: tuple[EvidenceV2, ...],
    ) -> tuple[InvestigationIndicatorV2, ...]:
        resolved: dict[tuple[EvidenceType, str, str], EvidenceV2] = {}
        for evidence in evidence_items:
            side = str(evidence.parameters.get("side", ""))
            resolved[(evidence.evidence_type, evidence.subject_ref, side)] = evidence

        def require_evidence(
            evidence_type: EvidenceType, subject_ref: str, side: str = ""
        ) -> EvidenceV2:
            try:
                return resolved[(evidence_type, subject_ref, side)]
            except KeyError as exc:
                raise DataIntegrityError(
                    "Behavioral indicator is missing its application-issued Evidence V2"
                ) from exc

        result: list[InvestigationIndicatorV2] = []

        def add_amount(
            *, key: str, title: str, facts: AmountBehaviorV2, evidence: EvidenceV2
        ) -> None:
            if facts.sample_size == 0:
                observed = (
                    f"No earlier {facts.currency} transactions matched this account, "
                    f"direction, and amount-comparison side."
                )
            elif facts.historical_median is None:
                observed = (
                    f"{facts.selected_amount} {facts.currency} with "
                    f"{facts.sample_size} earlier comparable transactions."
                )
            elif facts.empirical_percentile is None:
                observed = (
                    f"{facts.selected_amount} {facts.currency}; earlier median "
                    f"{facts.historical_median} {facts.currency}."
                )
            else:
                observed = (
                    f"{facts.selected_amount} {facts.currency}; earlier median "
                    f"{facts.historical_median} {facts.currency}; empirical percentile "
                    f"{facts.empirical_percentile:.2f}."
                )
            detail = (
                f"Comparison uses {facts.sample_size} strictly earlier transactions on the same "
                f"currency and direction side. History quality: {facts.history_quality.value}."
            )
            result.append(
                InvestigationIndicatorV2(
                    key=key,
                    title=title,
                    observed_text=observed,
                    detail=detail,
                    evidence_id=evidence.evidence_id,
                    ui_target=UITargetV2.INVESTIGATION_INDICATORS,
                    supporting_transaction_refs=evidence.supporting_transaction_refs,
                )
            )

        if indicators.sender_amount_behavior is not None:
            facts = indicators.sender_amount_behavior
            add_amount(
                key="sender-amount-history",
                title="Sender amount versus earlier history",
                facts=facts,
                evidence=require_evidence(
                    EvidenceType.AMOUNT_BEHAVIOR,
                    indicators.context.context_ref,
                    AmountSide.SENDER_PAID.value,
                ),
            )
        if indicators.receiver_amount_behavior is not None:
            facts = indicators.receiver_amount_behavior
            add_amount(
                key="receiver-amount-history",
                title="Receiver amount versus earlier history",
                facts=facts,
                evidence=require_evidence(
                    EvidenceType.AMOUNT_BEHAVIOR,
                    indicators.context.context_ref,
                    AmountSide.RECEIVER_RECEIVED.value,
                ),
            )

        if indicators.counterparty_relationship is not None:
            facts = indicators.counterparty_relationship
            evidence = require_evidence(
                EvidenceType.COUNTERPARTY_RELATIONSHIP, facts.account_ref
            )
            observed = (
                "No prior interaction before the selected transaction."
                if facts.new_counterparty
                else f"{facts.previous_interaction_count} prior interactions before the selected transaction."
            )
            detail = (
                f"Earlier direction counts: {facts.root_to_counterparty_count} from sender to receiver "
                f"and {facts.counterparty_to_root_count} from receiver to sender."
            )
            result.append(
                InvestigationIndicatorV2(
                    key="counterparty-relationship",
                    title="Counterparty relationship",
                    observed_text=observed,
                    detail=detail,
                    evidence_id=evidence.evidence_id,
                    ui_target=UITargetV2.INVESTIGATION_INDICATORS,
                    supporting_transaction_refs=evidence.supporting_transaction_refs,
                )
            )

        for index, (account_ref, facts) in enumerate(
            indicators.account_network_behavior.items()
        ):
            evidence = require_evidence(EvidenceType.NETWORK_BEHAVIOR, account_ref)
            role = "Sender" if index == 0 else "Receiver"
            result.append(
                InvestigationIndicatorV2(
                    key=f"{role.lower()}-recent-network",
                    title=f"{role} recent velocity and fan",
                    observed_text=(
                        f"{facts.velocity_24h.total_count} prior transactions in 24h; "
                        f"fan-in {facts.fan_in_24h}, fan-out {facts.fan_out_24h}."
                    ),
                    detail=(
                        f"Prior 1h activity: {facts.velocity_1h.incoming_count} incoming and "
                        f"{facts.velocity_1h.outgoing_count} outgoing transactions. "
                        "All counts use the resolved historical cutoff."
                    ),
                    evidence_id=evidence.evidence_id,
                    ui_target=UITargetV2.INVESTIGATION_INDICATORS,
                    supporting_transaction_refs=evidence.supporting_transaction_refs,
                )
            )

        if indicators.cross_currency is not None:
            facts = indicators.cross_currency
            evidence = require_evidence(
                EvidenceType.CURRENCY_BEHAVIOR, facts.transaction_ref
            )
            observed = (
                facts.currency_pair
                if facts.cross_currency
                else f"Same-currency transfer: {facts.currency_pair.split(' -> ')[0]}"
            )
            result.append(
                InvestigationIndicatorV2(
                    key="currency-route",
                    title="Currency route",
                    observed_text=observed,
                    detail=(
                        "Currency comparison is direct deterministic inequality only; "
                        "no FX-rate, spread, fee, or geography inference is made."
                    ),
                    evidence_id=evidence.evidence_id,
                    ui_target=UITargetV2.INVESTIGATION_INDICATORS,
                    supporting_transaction_refs=evidence.supporting_transaction_refs,
                )
            )
        return tuple(result)

    def _transaction_activity_context(
        self, facts: TransactionFactsV2, context: InvestigationContextV2
    ) -> ActivityContextV2:
        context_time = parse_canonical_timestamp(context.context_time)
        range_start = context_time - timedelta(days=TRANSACTION_ACTIVITY_DAYS)
        source = self._activity_buckets(
            facts.sender.account_ref, context, range_start=range_start
        )
        combined: dict[tuple[str, str], dict[str, Any]] = {}
        for bucket in source:
            key = (bucket.day, bucket.currency)
            item = combined.setdefault(
                key,
                {
                    "incoming_amount": Decimal(0),
                    "outgoing_amount": Decimal(0),
                    "transaction_count": 0,
                },
            )
            amount = Decimal(bucket.total_amount)
            if bucket.direction is Direction.INCOMING:
                item["incoming_amount"] += amount
            else:
                item["outgoing_amount"] += amount
            item["transaction_count"] += bucket.transaction_count
        buckets = tuple(
            TransactionActivityBucketV2(
                timestamp=f"{day}T00:00:00",
                currency=currency,
                incoming_amount=canonical_decimal(values["incoming_amount"]),
                outgoing_amount=canonical_decimal(values["outgoing_amount"]),
                transaction_count=int(values["transaction_count"]),
            )
            for (day, currency), values in sorted(combined.items())
        )
        return ActivityContextV2(
            range_start=canonical_timestamp(range_start),
            range_end=context.context_time,
            buckets=buckets,
            selected_transaction=SelectedTransactionMarkerV2(
                transaction_ref=facts.transaction_ref,
                timestamp=facts.transaction_timestamp,
                currency=facts.payment_currency,
                amount=facts.amount_paid,
            ),
        )

    @staticmethod
    def _currency_activity(
        buckets: tuple[ActivityBucketV2, ...]
    ) -> tuple[CurrencyActivityV2, ...]:
        totals: dict[str, dict[str, Any]] = {}
        for bucket in buckets:
            item = totals.setdefault(
                bucket.currency,
                {
                    "incoming_count": 0,
                    "outgoing_count": 0,
                    "incoming_amount": Decimal(0),
                    "outgoing_amount": Decimal(0),
                },
            )
            if bucket.direction is Direction.INCOMING:
                item["incoming_count"] += bucket.transaction_count
                item["incoming_amount"] += Decimal(bucket.total_amount)
            else:
                item["outgoing_count"] += bucket.transaction_count
                item["outgoing_amount"] += Decimal(bucket.total_amount)
        return tuple(
            CurrencyActivityV2(
                currency=currency,
                incoming_count=int(values["incoming_count"]),
                outgoing_count=int(values["outgoing_count"]),
                incoming_amount=canonical_decimal(values["incoming_amount"]),
                outgoing_amount=canonical_decimal(values["outgoing_amount"]),
            )
            for currency, values in sorted(totals.items())
        )

    @staticmethod
    def _supporting_evidence_summary_item(
        display: DisplayEvidenceV2, label: str
    ) -> SupportingEvidenceSummaryItemV2:
        return SupportingEvidenceSummaryItemV2(
            label=label,
            evidence_id=display.evidence_id,
            evidence_type=display.evidence_type,
            subject_type=display.subject_type,
            subject_ref=display.subject_ref,
            context_time=display.context_time,
            snapshot_id=display.snapshot_id,
            detector_cutoff=display.detector_cutoff,
            facts=display.facts,
            ui_target=display.ui_target,
            supporting_transaction_count=display.supporting_transaction_count,
            supporting_transactions=display.supporting_transactions,
            support_truncated=display.support_truncated,
        )

    def _activity_buckets(
        self,
        account_ref: str,
        context: InvestigationContextV2,
        *,
        range_start: datetime | None = None,
    ) -> list[ActivityBucketV2]:
        rows = self._repository.activity_bucket_rows(
            account_ref,
            parse_canonical_timestamp(context.context_time),
            range_start=range_start,
        )
        return [
            ActivityBucketV2(
                day=row[0].isoformat(), direction=Direction(str(row[1])), currency=str(row[2]),
                transaction_count=int(row[3]), total_amount=canonical_decimal(row[4]),
            )
            for row in rows
        ]

    def _bank_country_flows(
        self, account_ref: str, context: InvestigationContextV2
    ) -> list[BankCountryFlowV2]:
        rows = self._repository.bank_country_flow_rows(
            account_ref, parse_canonical_timestamp(context.context_time)
        )
        return [
            BankCountryFlowV2(
                counterparty_country=str(row[0]), counterparty_iso_alpha2=str(row[1]),
                incoming_transaction_count=int(row[2]), outgoing_transaction_count=int(row[3]),
                distinct_counterparties=int(row[4]), latest_interaction=self._ts(row[5]),
            )
            for row in rows
        ]

    def _alert_history(
        self, account_ref: str, context: InvestigationContextV2
    ) -> tuple[list[AlertHistoryItemV2], int]:
        rows, total = self._repository.alert_history_rows(
            account_ref, parse_canonical_timestamp(context.context_time)
        )
        return (
            [
                AlertHistoryItemV2(
                    alert_ref=str(row[0]), entry_snapshot_id=str(row[1]),
                    entry_cutoff=self._ts(row[2]), reason_code=str(row[3]),
                )
                for row in rows
            ],
            total,
        )

    # ---------- Evidence ----------

    def _make_evidence(
        self,
        evidence_type: EvidenceType,
        subject_type: SubjectType,
        subject_ref: str,
        context_identity: ContextIdentityV2,
        parameters: dict[str, Any],
    ) -> EvidenceV2:
        parameters = canonical_parameters(parameters)
        context = self._context_for_identity_and_subject(context_identity, subject_type, subject_ref)
        self._validate_subject_context(subject_type, subject_ref, context)
        facts, support_refs, support_total, selection_rule, ui_target = self._evidence_facts(
            evidence_type, subject_type, subject_ref, context, parameters
        )
        return self._evidence_from_authoritative_parts(
            evidence_type,
            subject_type,
            subject_ref,
            context,
            parameters,
            facts,
            support_refs,
            support_total,
            selection_rule,
            ui_target,
        )

    def _evidence_from_authoritative_parts(
        self,
        evidence_type: EvidenceType,
        subject_type: SubjectType,
        subject_ref: str,
        context: InvestigationContextV2,
        parameters: dict[str, Any],
        facts: Any,
        support_refs: list[str] | tuple[str, ...],
        support_total: int,
        selection_rule: str,
        ui_target: UITargetV2,
    ) -> EvidenceV2:
        parameters = canonical_parameters(parameters)
        self._validate_resolved_subject_context(subject_type, subject_ref, context)
        identity = EvidenceIdentityV2(
            evidence_type=evidence_type, subject_type=subject_type, subject_ref=subject_ref,
            context_identity=context.context_identity, parameters=parameters,
        )
        refs = tuple(support_refs[:SUPPORT_LIMIT])
        return EvidenceV2(
            evidence_id=encode_evidence_id(identity), evidence_type=evidence_type,
            subject_type=subject_type, subject_ref=subject_ref,
            context_identity=context.context_identity, context_time=context.context_time,
            snapshot_id=context.detector_snapshot_id, detector_cutoff=context.detector_cutoff,
            parameters=parameters, facts=facts, supporting_transaction_count=support_total,
            supporting_transaction_refs=refs, support_truncated=support_total > len(refs),
            support_selection_rule=selection_rule, ui_target=ui_target,
        )

    def _context_for_identity_and_subject(
        self, embedded: ContextIdentityV2, subject_type: SubjectType, subject_ref: str
    ) -> InvestigationContextV2:
        identity = EvidenceIdentityV2(
            evidence_type=EvidenceType.ACCOUNT_ACTIVITY,
            subject_type=subject_type, subject_ref=subject_ref,
            context_identity=embedded, parameters={},
        )
        return self._resolve_embedded_context(identity)

    def _evidence_facts(
        self,
        evidence_type: EvidenceType,
        subject_type: SubjectType,
        subject_ref: str,
        context: InvestigationContextV2,
        parameters: dict[str, Any],
    ) -> tuple[Any, list[str], int, str, UITargetV2]:
        if evidence_type is EvidenceType.ALERT_CONTEXT:
            self._require_signature(subject_type, SubjectType.ALERT, parameters, set())
            facts = self._alert_facts(subject_ref)
            refs = self._repository.support_refs_for_alert(
                facts.account_ref, parse_canonical_timestamp(facts.entry_cutoff)
            )
            return (
                facts, refs, facts.relevant_recent_transaction_count,
                "most-recent-relevant-v1", UITargetV2.ALERT_CONTEXT,
            )
        if evidence_type is EvidenceType.DETECTOR_STATE:
            self._require_signature(subject_type, SubjectType.ACCOUNT, parameters, set())
            if context.detector_snapshot_id is None:
                raise InvalidContextError("Detector evidence requires a detector snapshot")
            facts = self._detector_state_evidence_facts(
                context.detector_snapshot_id, subject_ref
            )
            return facts, [], 0, "detector-structural-support-only-v1", UITargetV2.ACCOUNT_REVIEW
        if evidence_type is EvidenceType.TRANSACTION_FACTS:
            self._require_signature(subject_type, SubjectType.TRANSACTION, parameters, set())
            facts = self._transaction_facts(subject_ref)
            return facts, [subject_ref], 1, "selected-transaction-v1", UITargetV2.TRANSACTION_FACTS
        if evidence_type is EvidenceType.TRANSACTION_PRIORITY:
            self._require_signature(subject_type, SubjectType.TRANSACTION, parameters, set())
            facts = self._transaction_review_state(subject_ref)
            return facts, [subject_ref], 1, "selected-transaction-v1", UITargetV2.REVIEW_PRIORITY
        if evidence_type is EvidenceType.ACCOUNT_ACTIVITY:
            self._require_signature(subject_type, SubjectType.ACCOUNT, parameters, set())
            facts = self._account_activity(subject_ref, context)
            refs = self._repository.support_refs_for_account(subject_ref, parse_canonical_timestamp(context.context_time))
            total = facts.incoming_count + facts.outgoing_count
            # self-transfers are present in both direction counts but are one supporting transaction.
            support_count = self._count_account_involvement(subject_ref, context)
            return facts, refs, support_count, "most-recent-relevant-v1", UITargetV2.ACTIVITY_CONTEXT
        if evidence_type is EvidenceType.AMOUNT_BEHAVIOR:
            self._require_signature(subject_type, SubjectType.TRANSACTION, parameters, {"side"})
            try:
                side = AmountSide(parameters["side"])
            except (KeyError, ValueError) as exc:
                raise InvalidInputError("Amount evidence side is invalid") from exc
            selected = self._transaction_facts(subject_ref)
            facts = self._amount_behavior(selected, side, context)
            refs = self._repository.support_refs_for_amount(
                account_ref=facts.account_ref,
                context_time=parse_canonical_timestamp(context.context_time),
                side=side.value,
                currency=facts.currency,
            )
            return facts, refs, facts.sample_size, "most-recent-same-side-currency-v1", UITargetV2.INVESTIGATION_INDICATORS
        if evidence_type is EvidenceType.COUNTERPARTY_RELATIONSHIP:
            self._require_signature(subject_type, SubjectType.ACCOUNT, parameters, {"counterparty_ref"})
            cp = str(parameters["counterparty_ref"])
            self._account_identity(cp)
            facts = self._relationship(subject_ref, cp, context)
            refs = self._repository.support_refs_for_relationship(
                subject_ref, cp, parse_canonical_timestamp(context.context_time)
            )
            return facts, refs, facts.previous_interaction_count, "most-recent-relationship-v1", UITargetV2.COUNTERPARTY_TABLE
        if evidence_type is EvidenceType.NETWORK_BEHAVIOR:
            self._require_signature(subject_type, SubjectType.ACCOUNT, parameters, set())
            facts = self._network_behavior(subject_ref, context)
            refs = self._repository.support_refs_for_network_behavior(
                subject_ref, parse_canonical_timestamp(context.context_time)
            )
            support_count = facts.velocity_24h.total_count
            return facts, refs, support_count, "most-recent-prior-24h-v1", UITargetV2.ACCOUNT_NETWORK
        if evidence_type is EvidenceType.CURRENCY_BEHAVIOR:
            self._require_signature(subject_type, SubjectType.TRANSACTION, parameters, set())
            selected = self._transaction_facts(subject_ref)
            facts = CurrencyBehaviorV2(
                transaction_ref=subject_ref, cross_currency=selected.cross_currency,
                currency_pair=selected.currency_pair,
            )
            return facts, [subject_ref], 1, "selected-transaction-v1", UITargetV2.CURRENCY_ACTIVITY
        if evidence_type is EvidenceType.BANK_COUNTRY_ROUTE:
            self._require_signature(subject_type, SubjectType.TRANSACTION, parameters, set())
            facts = self._bank_country_route(self._transaction_facts(subject_ref))
            return facts, [subject_ref], 1, "selected-transaction-v1", UITargetV2.BANK_COUNTRY_ROUTE
        if evidence_type is EvidenceType.SUPPORTING_TRANSACTIONS:
            self._require_signature(
                subject_type, subject_type, parameters, {"source_evidence_type", "source_parameters"}
            )
            try:
                source_type = EvidenceType(str(parameters["source_evidence_type"]))
            except ValueError as exc:
                raise InvalidInputError("Supporting evidence source type is invalid") from exc
            if source_type is EvidenceType.SUPPORTING_TRANSACTIONS:
                raise InvalidInputError("Supporting evidence cannot recursively support itself")
            source_params = parameters["source_parameters"]
            if not isinstance(source_params, dict):
                raise InvalidInputError("Supporting evidence source parameters are invalid")
            source = self._make_evidence(
                source_type, subject_type, subject_ref, context.context_identity, source_params
            )
            rows = self._repository.supporting_transaction_rows(source.supporting_transaction_refs)
            transactions = tuple(self._supporting_transaction(row) for row in rows)
            facts = SupportingTransactionsFactsV2(
                source_evidence_type=source_type,
                transaction_count=source.supporting_transaction_count,
                transactions=transactions,
            )
            return (
                facts,
                list(source.supporting_transaction_refs),
                source.supporting_transaction_count,
                source.support_selection_rule,
                UITargetV2.SUPPORTING_EVIDENCE,
            )
        raise InvalidInputError("Unknown Evidence V2 type")

    def _display_evidence(self, evidence: EvidenceV2) -> DisplayEvidenceV2:
        rows = self._repository.supporting_transaction_rows(evidence.supporting_transaction_refs)
        return self._display_evidence_from_rows(evidence, rows)

    def _display_evidence_from_rows(
        self, evidence: EvidenceV2, rows: list[tuple[Any, ...]]
    ) -> DisplayEvidenceV2:
        return DisplayEvidenceV2(
            evidence_id=evidence.evidence_id, evidence_type=evidence.evidence_type,
            subject_type=evidence.subject_type, subject_ref=evidence.subject_ref,
            context_time=evidence.context_time, snapshot_id=evidence.snapshot_id,
            detector_cutoff=evidence.detector_cutoff,
            facts=evidence.facts.model_dump(mode="json"), ui_target=evidence.ui_target,
            supporting_transaction_count=evidence.supporting_transaction_count,
            supporting_transactions=tuple(self._supporting_transaction(row) for row in rows),
            support_truncated=evidence.support_truncated,
        )

    def _count_account_involvement(self, account_ref: str, context: InvestigationContextV2) -> int:
        return self._repository.account_involvement_count(
            account_ref, parse_canonical_timestamp(context.context_time)
        )

    # ---------- validation/helpers ----------

    def _validate_subject_context(
        self, subject_type: SubjectType, subject_ref: str, context: InvestigationContextV2
    ) -> None:
        self._validate_resolved_subject_context(subject_type, subject_ref, context)
        if subject_type is SubjectType.ALERT:
            self._alert_facts(subject_ref)
        elif subject_type is SubjectType.TRANSACTION:
            self._transaction_facts(subject_ref)
        else:
            self._account_identity(subject_ref)

    def _validate_resolved_subject_context(
        self, subject_type: SubjectType, subject_ref: str, context: InvestigationContextV2
    ) -> None:
        if subject_type is SubjectType.ALERT:
            if (
                context.context_identity.context_kind is not ContextKind.ALERT_ENTRY
                or context.alert_ref != subject_ref
            ):
                raise InvalidContextError(
                    "Alert evidence is outside its authoritative entry context"
                )
        elif subject_type is SubjectType.TRANSACTION:
            if (
                context.context_identity.context_kind is not ContextKind.TRANSACTION
                or context.selected_transaction_ref != subject_ref
            ):
                raise InvalidContextError(
                    "Transaction evidence is outside its authoritative transaction context"
                )
        else:
            self._validate_account_in_context(subject_ref, context)

    def _validate_account_in_context(
        self, account_ref: str, context: InvestigationContextV2
    ) -> None:
        if context.context_identity.context_kind is ContextKind.SNAPSHOT:
            if context.subject_type is not SubjectType.ACCOUNT or context.subject_ref != account_ref:
                raise InvalidContextError("Snapshot account context does not authorize this account")
            return
        if account_ref not in context.root_account_refs:
            raise InvalidContextError("Account is not a root subject in the historical context")

    @staticmethod
    def _require_signature(
        actual_subject: SubjectType,
        required_subject: SubjectType,
        parameters: dict[str, Any],
        keys: set[str],
    ) -> None:
        if actual_subject is not required_subject:
            raise InvalidInputError("Evidence subject type is invalid for evidence type")
        if set(parameters) != keys:
            raise InvalidInputError("Evidence parameters are invalid for evidence type")

    def _selected_counterparty(
        self, account_ref: str, context: InvestigationContextV2
    ) -> str | None:
        if context.selected_transaction_ref is None:
            return None
        facts = self._transaction_facts(context.selected_transaction_ref)
        if account_ref == facts.sender.account_ref:
            return facts.receiver.account_ref
        if account_ref == facts.receiver.account_ref:
            return facts.sender.account_ref
        raise InvalidContextError("Selected transaction does not involve requested root account")

    @staticmethod
    def _transaction_list_item(row: tuple[Any, ...]) -> TransactionListItemV2:
        try:
            priority = NetworkReviewBand(str(row[23]))
        except ValueError as exc:
            raise DataIntegrityError(
                "Transaction list contains an unknown persisted AML review priority"
            ) from exc
        return TransactionListItemV2(
            transaction_ref=str(row[0]),
            timestamp=InvestigationServiceV2._ts(row[1]),
            sender=TransactionListPartyV2(
                account_ref=str(row[2]),
                bank_id=str(row[3]),
                account_id=str(row[4]),
                bank_country=BankCountryV2(
                    bank_id=str(row[3]), mapping_version=str(row[5]),
                    country_name=str(row[6]), iso_alpha2=str(row[7]),
                    centroid_latitude=float(row[8]), centroid_longitude=float(row[9]),
                ),
            ),
            receiver=TransactionListPartyV2(
                account_ref=str(row[10]),
                bank_id=str(row[11]),
                account_id=str(row[12]),
                bank_country=BankCountryV2(
                    bank_id=str(row[11]), mapping_version=str(row[13]),
                    country_name=str(row[14]), iso_alpha2=str(row[15]),
                    centroid_latitude=float(row[16]), centroid_longitude=float(row[17]),
                ),
            ),
            amount_paid=canonical_decimal(row[18]),
            payment_currency=str(row[19]),
            amount_received=canonical_decimal(row[20]),
            receiving_currency=str(row[21]),
            payment_format=str(row[22]),
            aml_review_priority=priority,
            related_alert=InvestigationServiceV2._str_or_none(row[24]),
        )

    @staticmethod
    def _network_relationship(
        row: tuple[Any, ...], selected_counterparty_ref: str | None
    ) -> NetworkRelationshipV2:
        counterparty_ref = str(row[0])
        return NetworkRelationshipV2(
            counterparty=AccountIdentityV2(
                account_ref=counterparty_ref,
                source_dataset=str(row[1]),
                bank_id=str(row[2]),
                account_id=str(row[3]),
                bank_country=BankCountryV2(
                    bank_id=str(row[2]), mapping_version=str(row[4]),
                    country_name=str(row[5]), iso_alpha2=str(row[6]),
                    centroid_latitude=float(row[7]), centroid_longitude=float(row[8]),
                ),
            ),
            incoming_count=int(row[9] or 0),
            outgoing_count=int(row[10] or 0),
            total_count=int(row[11] or 0),
            first_historical_timestamp=InvestigationServiceV2._ts_or_none(row[12]),
            last_historical_timestamp=InvestigationServiceV2._ts_or_none(row[13]),
            selected_relationship=counterparty_ref == selected_counterparty_ref,
        )

    @staticmethod
    def _supporting_transaction(row: tuple[Any, ...]) -> SupportingTransactionV2:
        item = InvestigationServiceV2._transaction_list_item(row)
        return SupportingTransactionV2(
            transaction_ref=item.transaction_ref,
            transaction_timestamp=item.timestamp,
            from_account_ref=item.sender.account_ref,
            from_bank_id=item.sender.bank_id,
            from_account_id=item.sender.account_id,
            from_bank_country=item.sender.bank_country,
            to_account_ref=item.receiver.account_ref,
            to_bank_id=item.receiver.bank_id,
            to_account_id=item.receiver.account_id,
            to_bank_country=item.receiver.bank_country,
            amount_paid=item.amount_paid,
            payment_currency=item.payment_currency,
            amount_received=item.amount_received,
            receiving_currency=item.receiving_currency,
            payment_format=item.payment_format,
            cross_currency=bool(row[25]),
            aml_review_priority=item.aml_review_priority,
            related_alert=item.related_alert,
        )

    @staticmethod
    def _require_datetime(value: Any) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is not None or value.microsecond:
            raise DataIntegrityError("Runtime timestamp violates canonical whole-second semantics")
        return value

    @staticmethod
    def _ts(value: Any) -> str:
        return canonical_timestamp(InvestigationServiceV2._require_datetime(value))

    @staticmethod
    def _ts_or_none(value: Any) -> str | None:
        return None if value is None else InvestigationServiceV2._ts(value)

    @staticmethod
    def _str_or_none(value: Any) -> str | None:
        return None if value is None else str(value)

    @staticmethod
    def _band(value: Any) -> NetworkReviewBand:
        try:
            return NetworkReviewBand(str(value))
        except ValueError as exc:
            raise DataIntegrityError("Persisted network review band is invalid") from exc


def create_investigation_service_v2(
    database_path: str | Path,
) -> InvestigationServiceV2:
    """Downstream construction boundary for the merged V2 runtime database."""
    return InvestigationServiceV2(DuckDBInvestigationRepositoryV2(database_path))
