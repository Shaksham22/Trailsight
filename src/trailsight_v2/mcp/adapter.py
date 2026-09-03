"""Strict MCP projections over the WP03 deterministic InvestigationServiceV2."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar, cast

from trailsight_v2.domain.errors import InvestigationDomainError, InvalidContextError
from trailsight_v2.domain.evidence import encode_evidence_id
from trailsight_v2.domain.models import (
    EvidenceIdentityV2,
    EvidenceType,
    InvestigationContextV2,
    SubjectType,
)
from trailsight_v2.domain.service import InvestigationServiceV2

from .contracts import (
    AccountContextResult,
    AccountDisplaySummary,
    AlertContextResult,
    AmountBehaviorSummary,
    BehavioralIndicatorsResult,
    BlockMeasureSupport,
    CrossCurrencySummary,
    McpContractModel,
    McpResult,
    NetworkBehaviorSummary,
    NetworkContextResult,
    RelationshipContextResult,
    RelationshipNoveltySummary,
    RelationshipSummary,
    SupportingEvidenceResult,
    SupportingTransactionSummary,
    TransactionContextResult,
    VelocitySummary,
    serialize_result,
)
from .scope import InvestigationScopeV2


class RuntimeStateReader(Protocol):
    def get_alert_review_status(self, alert_ref: str): ...


_ResultT = TypeVar("_ResultT", bound=McpContractModel)


class InvestigationToolAdapterV2:
    """Expose only the frozen seven bounded tools within one authoritative context."""

    def __init__(
        self,
        service: InvestigationServiceV2,
        runtime_state_store: RuntimeStateReader,
        scope: InvestigationScopeV2,
    ) -> None:
        self._service = service
        self._runtime_state_store = runtime_state_store
        self._scope = scope
        self._context = service.resolve_context(
            scope.subject_type,
            scope.subject_ref,
            scope.origin_ref,
        )
        if self._context.context_identity != scope.context_identity:
            raise InvalidContextError("MCP scope no longer matches authoritative context")
        self._available_evidence_ids: set[str] = set()
        self._authorized_transactions: set[str] = set()
        if self._context.selected_transaction_ref is not None:
            self._authorized_transactions.add(self._context.selected_transaction_ref)
        self._network_counterparties: dict[str, set[str]] = {}
        for evidence_id in scope.seed_evidence_ids:
            resolved = service.resolve_evidence(evidence_id)
            if resolved.context_identity != self._context.context_identity:
                raise InvalidContextError("Seed evidence is outside the MCP run context")
            self._available_evidence_ids.add(evidence_id)

    @property
    def available_evidence_ids(self) -> frozenset[str]:
        return frozenset(self._available_evidence_ids)

    def get_alert_context(self, alert_ref: str) -> AlertContextResult:
        def build() -> AlertContextResult:
            allowed = {
                ref
                for ref in (self._context.alert_ref, self._scope.origin_alert_ref)
                if ref is not None
            }
            if alert_ref not in allowed:
                raise InvalidContextError("Alert is outside the current investigation context")
            detail = self._service.get_alert_context(alert_ref)
            if detail.context.context_identity != self._context.context_identity:
                raise InvalidContextError("Alert context does not match the MCP run context")
            alert_evidence_id = detail.evidence_ids[0]
            self._available_evidence_ids.update(detail.evidence_ids)
            review_status = self._runtime_state_store.get_alert_review_status(alert_ref)
            review_value = getattr(review_status, "value", str(review_status))
            return AlertContextResult(
                status="OK",
                evidence_id=alert_evidence_id,
                alert_ref=alert_ref,
                account_ref=detail.alert.account_ref,
                entry_snapshot_id=detail.alert.entry_snapshot_id,
                entry_cutoff=detail.alert.entry_cutoff,
                network_review_band=detail.detector_state.network_review_band.value,
                network_pattern_score=detail.detector_state.network_pattern_score,
                rank=detail.detector_state.rank,
                percentile=detail.detector_state.percentile,
                reason=detail.alert.reason_code,
                review_status=review_value,
            )

        return self._execute(AlertContextResult, build, 4 * 1024)

    def get_transaction_context(self, transaction_ref: str) -> TransactionContextResult:
        def build() -> TransactionContextResult:
            if transaction_ref not in self._authorized_transactions:
                raise InvalidContextError(
                    "Transaction was not authorized by the current subject or supporting evidence"
                )
            detail = self._service.get_transaction_detail(transaction_ref)
            if (
                transaction_ref == self._context.selected_transaction_ref
                and detail.context.context_identity != self._context.context_identity
            ):
                raise InvalidContextError("Selected transaction context changed during the run")
            self._available_evidence_ids.update(detail.evidence_ids)
            facts = detail.transaction_facts
            review = detail.review_state
            route = detail.bank_country_route
            return TransactionContextResult(
                status="OK",
                evidence_ids=detail.evidence_ids,
                transaction_ref=transaction_ref,
                timestamp=facts.transaction_timestamp,
                sender=AccountDisplaySummary(
                    account_ref=facts.sender.account_ref,
                    bank_id=facts.sender.bank_id,
                    account_id=facts.sender.account_id,
                ),
                receiver=AccountDisplaySummary(
                    account_ref=facts.receiver.account_ref,
                    bank_id=facts.receiver.bank_id,
                    account_id=facts.receiver.account_id,
                ),
                amount_paid=facts.amount_paid,
                payment_currency=facts.payment_currency,
                amount_received=facts.amount_received,
                receiving_currency=facts.receiving_currency,
                payment_format=facts.payment_format,
                cross_currency=facts.cross_currency,
                sender_band=review.sender_band.value,
                receiver_band=review.receiver_band.value,
                aml_review_priority=review.aml_review_priority.value,
                snapshot_id=review.snapshot_id,
                detector_cutoff=review.detector_cutoff,
                derivation_text=review.derivation_text,
                sending_bank_country=route.sending_bank.country_name,
                receiving_bank_country=route.receiving_bank.country_name,
                same_bank_country=route.same_bank_country,
            )

        return self._execute(TransactionContextResult, build, 4 * 1024)

    def get_account_context(self, account_ref: str) -> AccountContextResult:
        def build() -> AccountContextResult:
            self._require_root_account(account_ref)
            origin_ref = (
                self._scope.origin_ref
                if self._scope.subject_type is SubjectType.ACCOUNT
                else self._scope.subject_ref
            )
            detail = self._service.get_account_detail(account_ref, origin_ref=origin_ref)
            if detail.context.context_identity != self._context.context_identity:
                raise InvalidContextError("Account context does not match the MCP run context")
            detector_evidence_id, activity_evidence_id = detail.evidence_ids[:2]
            detector_evidence = self._service.resolve_evidence(detector_evidence_id)
            evidence_ids = (detector_evidence_id, activity_evidence_id)
            self._available_evidence_ids.update(evidence_ids)
            account = detail.account_identity
            state = detail.network_review_state
            activity = detail.observed_activity
            return AccountContextResult(
                status="OK",
                evidence_ids=evidence_ids,
                account_ref=account_ref,
                bank_id=account.bank_id,
                account_id=account.account_id,
                bank_country=account.bank_country.country_name,
                snapshot_id=state.snapshot_id,
                detector_cutoff=self._context.detector_cutoff,
                network_review_band=state.network_review_band.value,
                network_pattern_score=state.network_pattern_score,
                rank=state.rank,
                eligible_account_count=detector_evidence.facts.eligible_account_count,
                percentile=state.percentile,
                unscored_reason=state.unscored_reason,
                incoming_count=activity.incoming_count,
                outgoing_count=activity.outgoing_count,
                distinct_counterparties=activity.distinct_counterparties,
                first_observed=activity.first_observed_timestamp,
                most_recent_observed=activity.most_recent_observed_timestamp,
            )

        return self._execute(AccountContextResult, build, 5 * 1024)

    def get_behavioral_indicators(
        self, account_ref: str | None = None
    ) -> BehavioralIndicatorsResult:
        def build() -> BehavioralIndicatorsResult:
            if self._scope.subject_type is SubjectType.TRANSACTION:
                if account_ref is not None:
                    self._require_root_account(account_ref)
                indicators = self._service.get_behavioral_indicators(
                    SubjectType.TRANSACTION,
                    self._scope.subject_ref,
                    context=self._context,
                    account_ref=account_ref,
                )
            else:
                if account_ref is not None:
                    root = account_ref
                elif self._scope.subject_type is SubjectType.ACCOUNT:
                    root = self._scope.subject_ref
                else:
                    root = self._context.root_account_refs[0]
                self._require_root_account(root)
                indicators = self._service.get_behavioral_indicators(
                    self._scope.subject_type,
                    self._scope.subject_ref,
                    context=self._context,
                    account_ref=root,
                )
            self._available_evidence_ids.update(indicators.evidence_ids)
            amount_items = []
            for item in (
                indicators.sender_amount_behavior,
                indicators.receiver_amount_behavior,
            ):
                if item is not None:
                    amount_items.append(
                        AmountBehaviorSummary(
                            side=item.side.value,
                            account_ref=item.account_ref,
                            history_quality=item.history_quality.value,
                            sample_size=item.sample_size,
                            selected_amount=item.selected_amount,
                            currency=item.currency,
                            historical_median=item.historical_median,
                            empirical_percentile=item.empirical_percentile,
                        )
                    )
            relationship = indicators.counterparty_relationship
            relationship_summary = (
                RelationshipNoveltySummary(
                    account_ref=relationship.account_ref,
                    counterparty_account_ref=relationship.counterparty_account_ref,
                    seen_before=relationship.seen_before,
                    new_counterparty=relationship.new_counterparty,
                    previous_interaction_count=relationship.previous_interaction_count,
                    root_to_counterparty_count=relationship.root_to_counterparty_count,
                    counterparty_to_root_count=relationship.counterparty_to_root_count,
                    first_previous_timestamp=relationship.first_previous_timestamp,
                    most_recent_previous_timestamp=relationship.most_recent_previous_timestamp,
                )
                if relationship is not None
                else None
            )
            network_items = tuple(
                NetworkBehaviorSummary(
                    account_ref=item.account_ref,
                    velocity_1h=VelocitySummary(
                        incoming_count=item.velocity_1h.incoming_count,
                        outgoing_count=item.velocity_1h.outgoing_count,
                        total_count=item.velocity_1h.total_count,
                    ),
                    velocity_24h=VelocitySummary(
                        incoming_count=item.velocity_24h.incoming_count,
                        outgoing_count=item.velocity_24h.outgoing_count,
                        total_count=item.velocity_24h.total_count,
                    ),
                    fan_in_24h=item.fan_in_24h,
                    fan_out_24h=item.fan_out_24h,
                )
                for item in indicators.account_network_behavior.values()
            )
            currency = indicators.cross_currency
            return BehavioralIndicatorsResult(
                status="OK",
                evidence_ids=indicators.evidence_ids,
                amount_behavior=tuple(amount_items) if amount_items else None,
                counterparty_novelty=relationship_summary,
                network_behavior=network_items,
                cross_currency=(
                    CrossCurrencySummary(
                        transaction_ref=currency.transaction_ref,
                        cross_currency=currency.cross_currency,
                        currency_pair=currency.currency_pair,
                    )
                    if currency is not None
                    else None
                ),
            )

        return self._execute(BehavioralIndicatorsResult, build, 8 * 1024)

    def get_relationship_context(
        self,
        account_ref: str,
        counterparty_account_ref: str,
    ) -> RelationshipContextResult:
        def build() -> RelationshipContextResult:
            self._require_root_account(account_ref)
            allowed = self._network_counterparties.get(account_ref)
            selected = self._selected_counterparty_for_root(account_ref)
            if counterparty_account_ref != selected and (
                allowed is None or counterparty_account_ref not in allowed
            ):
                raise InvalidContextError(
                    "Counterparty was not returned by the bounded network context"
                )
            facts = self._service.get_relationship_context(
                account_ref,
                counterparty_account_ref,
                context=self._context,
            )
            evidence_id = self._issue_existing_evidence(
                EvidenceType.COUNTERPARTY_RELATIONSHIP,
                SubjectType.ACCOUNT,
                account_ref,
                {"counterparty_ref": counterparty_account_ref},
            )
            self._available_evidence_ids.add(evidence_id)
            return RelationshipContextResult(
                status="OK",
                evidence_id=evidence_id,
                seen_before=facts.seen_before,
                previous_interaction_count=facts.previous_interaction_count,
                root_to_counterparty_count=facts.root_to_counterparty_count,
                counterparty_to_root_count=facts.counterparty_to_root_count,
                first_previous_timestamp=facts.first_previous_timestamp,
                most_recent_previous_timestamp=facts.most_recent_previous_timestamp,
            )

        return self._execute(RelationshipContextResult, build, 4 * 1024)

    def get_network_context(self, account_ref: str) -> NetworkContextResult:
        def build() -> NetworkContextResult:
            self._require_root_account(account_ref)
            network = self._service.get_account_network(account_ref, context=self._context)
            detector_evidence = self._resolve_account_evidence(
                EvidenceType.DETECTOR_STATE, account_ref
            )
            network_evidence = self._resolve_account_evidence(
                EvidenceType.NETWORK_BEHAVIOR, account_ref
            )
            activity_evidence = self._resolve_account_evidence(
                EvidenceType.ACCOUNT_ACTIVITY, account_ref
            )
            evidence_ids = (
                detector_evidence.evidence_id,
                network_evidence.evidence_id,
                activity_evidence.evidence_id,
            )
            self._available_evidence_ids.update(evidence_ids)
            support = detector_evidence.facts
            block_values = (
                support.block_measure_1,
                support.block_measure_2,
                support.block_measure_3,
            )
            block_support = (
                None
                if all(value is None for value in block_values)
                else BlockMeasureSupport(
                    block_measure_1=support.block_measure_1,
                    block_measure_2=support.block_measure_2,
                    block_measure_3=support.block_measure_3,
                )
            )
            shown = network.relationships[:12]
            self._network_counterparties[account_ref] = {
                item.counterparty.account_ref for item in shown
            }
            return NetworkContextResult(
                status="OK",
                evidence_ids=evidence_ids,
                account_ref=account_ref,
                snapshot_id=support.snapshot_id,
                detector_cutoff=self._context.detector_cutoff,
                network_review_band=support.network_review_band.value,
                eligible_account_count=support.eligible_account_count,
                first_order_neighbor_count=support.first_order_neighbor_count,
                second_order_neighbor_count=support.second_order_neighbor_count,
                block_measure_support=block_support,
                total_direct_counterparties=network.total_direct_counterparties,
                shown_counterparties=len(shown),
                truncated=network.total_direct_counterparties > len(shown),
                relationships=tuple(
                    RelationshipSummary(
                        counterparty_account_ref=item.counterparty.account_ref,
                        incoming_count=item.incoming_count,
                        outgoing_count=item.outgoing_count,
                        total_count=item.total_count,
                        first_historical_timestamp=item.first_historical_timestamp,
                        last_historical_timestamp=item.last_historical_timestamp,
                        selected_relationship=item.selected_relationship,
                    )
                    for item in shown
                ),
            )

        return self._execute(NetworkContextResult, build, 12 * 1024)

    def get_supporting_evidence(self, evidence_id: str) -> SupportingEvidenceResult:
        def build() -> SupportingEvidenceResult:
            if evidence_id not in self._available_evidence_ids:
                raise InvalidContextError("Evidence was not issued in the current MCP run")
            source = self._service.resolve_evidence(evidence_id)
            if source.context_identity != self._context.context_identity:
                raise InvalidContextError("Evidence is outside the current MCP run context")
            display = self._service.get_supporting_evidence(evidence_id)
            transactions = display.supporting_transactions[:8]
            self._available_evidence_ids.add(display.evidence_id)
            for item in transactions:
                self._authorized_transactions.add(item.transaction_ref)
            return SupportingEvidenceResult(
                status="OK",
                evidence_id=display.evidence_id,
                supporting_transaction_count=display.supporting_transaction_count,
                transactions=tuple(
                    SupportingTransactionSummary(
                        transaction_ref=item.transaction_ref,
                        transaction_timestamp=item.transaction_timestamp,
                        from_account_ref=item.from_account_ref,
                        from_bank_id=item.from_bank_id,
                        to_account_ref=item.to_account_ref,
                        to_bank_id=item.to_bank_id,
                        amount_paid=item.amount_paid,
                        payment_currency=item.payment_currency,
                        amount_received=item.amount_received,
                        receiving_currency=item.receiving_currency,
                        payment_format=item.payment_format,
                        cross_currency=item.cross_currency,
                    )
                    for item in transactions
                ),
                truncated=(
                    display.support_truncated
                    or display.supporting_transaction_count > len(transactions)
                ),
            )

        return self._execute(SupportingEvidenceResult, build, 12 * 1024)

    def _resolve_account_evidence(self, evidence_type: EvidenceType, account_ref: str):
        evidence_id = self._issue_existing_evidence(
            evidence_type, SubjectType.ACCOUNT, account_ref, {}
        )
        resolved = self._service.resolve_evidence(evidence_id)
        if resolved.context_identity != self._context.context_identity:
            raise InvalidContextError("Account evidence is outside the MCP run context")
        return resolved

    def _require_root_account(self, account_ref: str) -> None:
        if account_ref not in self._context.root_account_refs:
            raise InvalidContextError("Account is not an authorized root in this investigation")

    def _selected_counterparty_for_root(self, account_ref: str) -> str | None:
        transaction_ref = self._context.selected_transaction_ref
        if transaction_ref is None:
            return None
        detail = self._service.get_transaction_detail(transaction_ref)
        facts = detail.transaction_facts
        if account_ref == facts.sender.account_ref:
            return facts.receiver.account_ref
        if account_ref == facts.receiver.account_ref:
            return facts.sender.account_ref
        return None

    def _issue_existing_evidence(
        self,
        evidence_type: EvidenceType,
        subject_type: SubjectType,
        subject_ref: str,
        parameters: dict[str, object],
    ) -> str:
        """Use the WP03 Evidence V2 identity format, then force WP03 to resolve/recompute it."""
        candidate = encode_evidence_id(
            EvidenceIdentityV2(
                evidence_type=evidence_type,
                subject_type=subject_type,
                subject_ref=subject_ref,
                context_identity=self._context.context_identity,
                parameters=parameters,
            )
        )
        return self._service.resolve_evidence(candidate).evidence_id

    @staticmethod
    def _execute(
        result_model: type[_ResultT],
        call: Callable[[], _ResultT],
        max_result_bytes: int,
    ) -> _ResultT:
        try:
            result = call()
        except InvestigationDomainError as exc:
            code = exc.code.value
            if code not in {
                "NOT_FOUND",
                "INVALID_INPUT",
                "INVALID_CONTEXT",
                "DATA_INTEGRITY_ERROR",
                "RESULT_TOO_LARGE",
            }:
                code = "DATA_INTEGRITY_ERROR"
            return result_model(status="ERROR", error_code=code)
        except Exception:
            return result_model(status="ERROR", error_code="DATA_INTEGRITY_ERROR")
        if len(serialize_result(cast(McpResult, result))) > max_result_bytes:
            return result_model(status="ERROR", error_code="RESULT_TOO_LARGE")
        return result
