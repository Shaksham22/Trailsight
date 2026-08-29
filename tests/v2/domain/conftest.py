from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import duckdb
import pytest

from trailsight_v2.data.bank_country import bank_country_for
from trailsight_v2.data.canonical import account_ref_for
from trailsight_v2.data.constants import BANK_COUNTRY_VERSION, DATA_CONTRACT_VERSION, SOURCE_DATASET
from trailsight_v2.data.schema import create_wp01_schema
from trailsight_v2.domain.service import InvestigationServiceV2, create_investigation_service_v2


S0 = datetime(2024, 12, 30, 0, 0, 0)
S1 = datetime(2025, 1, 2, 0, 0, 0)
S2 = datetime(2025, 1, 3, 0, 0, 0)
SELECTED_TIME = datetime(2025, 1, 2, 12, 0, 0)
SNAPSHOTS = (("snap_0", S0), ("snap_1", S1), ("snap_2", S2))


@dataclass(frozen=True)
class TxSpec:
    ref: str
    timestamp: datetime
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount_paid: str = "10"
    payment_currency: str = "USD"
    amount_received: str = "10"
    receiving_currency: str = "USD"
    payment_format: str = "ACH"

    @property
    def from_ref(self) -> str:
        return account_ref_for(self.from_bank, self.from_account)

    @property
    def to_ref(self) -> str:
        return account_ref_for(self.to_bank, self.to_account)


@dataclass(frozen=True)
class AlertSpec:
    ref: str
    account_ref: str
    snapshot_id: str = "snap_1"
    cutoff: datetime = S1
    score: float = 0.987654321
    rank: int = 2
    percentile: float = 98.7654321


def txref(index: int) -> str:
    return f"txn_{index:064x}"


def selected_tx(index: int = 9999) -> TxSpec:
    return TxSpec(
        ref=txref(index),
        timestamp=SELECTED_TIME,
        from_bank="B1",
        from_account="ROOT",
        to_bank="B2",
        to_account="PEER",
        amount_paid="50",
        payment_currency="USD",
        amount_received="60",
        receiving_currency="EUR",
        payment_format="Cash",
    )


def _create_detector_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE detector_snapshots (
            snapshot_id VARCHAR PRIMARY KEY,
            source_dataset VARCHAR NOT NULL,
            cutoff_timestamp TIMESTAMP NOT NULL,
            algorithm_name VARCHAR NOT NULL,
            algorithm_variant VARCHAR NOT NULL,
            algorithm_version VARCHAR NOT NULL,
            upstream_code_provenance VARCHAR NOT NULL,
            identity_rule_version VARCHAR NOT NULL,
            eligibility_rule_version VARCHAR NOT NULL,
            community_algorithm VARCHAR NOT NULL,
            community_resolution VARCHAR NOT NULL,
            community_seed BIGINT NOT NULL,
            config_hash VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            account_count BIGINT NOT NULL,
            eligible_account_count BIGINT NOT NULL,
            scored_account_count BIGINT NOT NULL,
            failure_message_safe VARCHAR
        );
        CREATE TABLE account_detector_states (
            snapshot_id VARCHAR NOT NULL,
            account_ref VARCHAR NOT NULL,
            scoring_eligible BOOLEAN NOT NULL,
            network_pattern_score DOUBLE,
            rank BIGINT,
            percentile DOUBLE,
            network_review_band VARCHAR NOT NULL,
            unscored_reason VARCHAR,
            PRIMARY KEY(snapshot_id, account_ref)
        );
        CREATE TABLE account_detector_support (
            snapshot_id VARCHAR NOT NULL,
            account_ref VARCHAR NOT NULL,
            first_order_neighbor_count BIGINT,
            second_order_neighbor_count BIGINT,
            community_id_or_stable_snapshot_local_index VARCHAR,
            block_measure_1 DOUBLE,
            block_measure_2 DOUBLE,
            block_measure_3 DOUBLE,
            network_pattern_score DOUBLE,
            PRIMARY KEY(snapshot_id, account_ref)
        );
        CREATE TABLE transaction_review_states (
            transaction_ref VARCHAR PRIMARY KEY,
            snapshot_id VARCHAR,
            detector_cutoff TIMESTAMP,
            sender_band VARCHAR NOT NULL,
            receiver_band VARCHAR NOT NULL,
            aml_review_priority VARCHAR NOT NULL,
            derivation_code VARCHAR NOT NULL,
            derivation_text VARCHAR NOT NULL,
            alert_involvement BOOLEAN NOT NULL,
            sender_related_alert_ref VARCHAR,
            receiver_related_alert_ref VARCHAR
        );
        CREATE TABLE network_alerts (
            alert_ref VARCHAR PRIMARY KEY,
            account_ref VARCHAR NOT NULL,
            entry_snapshot_id VARCHAR NOT NULL,
            entry_cutoff TIMESTAMP NOT NULL,
            entry_score DOUBLE,
            entry_rank BIGINT,
            entry_percentile DOUBLE,
            reason_code VARCHAR NOT NULL,
            created_state VARCHAR NOT NULL
        );
        """
    )


def build_runtime_db(
    path: Path,
    transactions: Iterable[TxSpec],
    *,
    alerts: Iterable[AlertSpec] = (),
    extra_accounts: Iterable[tuple[str, str]] = (),
) -> Path:
    txs = list(transactions)
    if not txs:
        raise ValueError("fixture needs at least one transaction")
    alerts = list(alerts)
    connection = duckdb.connect(str(path))
    create_wp01_schema(connection)
    _create_detector_schema(connection)

    bank_ids = {tx.from_bank for tx in txs} | {tx.to_bank for tx in txs}
    account_pairs = {(tx.from_bank, tx.from_account) for tx in txs} | {
        (tx.to_bank, tx.to_account) for tx in txs
    } | set(extra_accounts)
    bank_ids |= {bank for bank, _ in account_pairs}
    for bank in sorted(bank_ids):
        country = bank_country_for(bank)
        connection.execute(
            "INSERT INTO banks VALUES (?, ?, ?, ?, ?, ?)",
            [
                bank,
                BANK_COUNTRY_VERSION,
                country.country_name,
                country.iso_alpha2,
                country.centroid_latitude,
                country.centroid_longitude,
            ],
        )
    for bank, account in sorted(account_pairs):
        ref = account_ref_for(bank, account)
        country = bank_country_for(bank)
        connection.execute(
            "INSERT INTO accounts VALUES (?, ?, ?, ?, ?)",
            [ref, SOURCE_DATASET, bank, account, country.iso_alpha2],
        )

    for ordinal, tx in enumerate(txs, 1):
        connection.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                tx.ref,
                SOURCE_DATASET,
                ordinal,
                tx.timestamp,
                tx.from_bank,
                tx.from_account,
                tx.from_ref,
                tx.to_bank,
                tx.to_account,
                tx.to_ref,
                Decimal(tx.amount_received),
                tx.receiving_currency,
                Decimal(tx.amount_paid),
                tx.payment_currency,
                tx.payment_format,
                tx.payment_currency != tx.receiving_currency,
            ],
        )

    account_refs = [account_ref_for(bank, account) for bank, account in sorted(account_pairs)]
    for snapshot_id, cutoff in SNAPSHOTS:
        connection.execute(
            "INSERT INTO detector_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                snapshot_id,
                SOURCE_DATASET,
                cutoff,
                "GARG-AML",
                "undirected-basic",
                "garg-fixture-v1",
                "fixture",
                "account-ref-v1",
                "garg-eligibility-v1",
                "louvain",
                "1.0",
                7,
                "cfg_fixture",
                "COMPLETE",
                cutoff,
                cutoff,
                len(account_refs),
                len(account_refs),
                len(account_refs),
                None,
            ],
        )
        for pos, account_ref in enumerate(account_refs, 1):
            is_root = account_ref == account_ref_for("B1", "ROOT")
            is_peer = account_ref == account_ref_for("B2", "PEER")
            score = 0.987654321 if is_root and snapshot_id == "snap_1" else 0.1 + pos / 1000
            rank = 2 if is_root and snapshot_id == "snap_1" else pos
            percentile = 98.7654321 if is_root and snapshot_id == "snap_1" else 50.0
            if is_root and snapshot_id == "snap_1":
                band = "HIGH"
            elif is_peer:
                band = "MEDIUM"
            else:
                band = "LOW"
            connection.execute(
                "INSERT INTO account_detector_states VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [snapshot_id, account_ref, True, score, rank, percentile, band, None],
            )
            connection.execute(
                "INSERT INTO account_detector_support VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [snapshot_id, account_ref, 11, 22, f"c{pos}", 1.1, 2.2, 3.3, score],
            )

    for tx in txs:
        applicable = max((item for item in SNAPSHOTS if item[1] <= tx.timestamp), key=lambda x: x[1])
        sender_alert = next(
            (
                alert.ref
                for alert in sorted(alerts, key=lambda a: a.cutoff, reverse=True)
                if alert.account_ref == tx.from_ref and alert.cutoff <= tx.timestamp
            ),
            None,
        )
        receiver_alert = next(
            (
                alert.ref
                for alert in sorted(alerts, key=lambda a: a.cutoff, reverse=True)
                if alert.account_ref == tx.to_ref and alert.cutoff <= tx.timestamp
            ),
            None,
        )
        connection.execute(
            "INSERT INTO transaction_review_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                tx.ref,
                applicable[0],
                applicable[1],
                "HIGH" if tx.from_ref == account_ref_for("B1", "ROOT") and applicable[0] == "snap_1" else "LOW",
                "MEDIUM" if tx.to_ref == account_ref_for("B2", "PEER") else "LOW",
                "HIGH" if tx.from_ref == account_ref_for("B1", "ROOT") and applicable[0] == "snap_1" else "LOW",
                "fixture-priority-v1",
                "Persisted fixture derivation text; returned unchanged.",
                bool(sender_alert or receiver_alert),
                sender_alert,
                receiver_alert,
            ],
        )

    for alert in alerts:
        connection.execute(
            "INSERT INTO network_alerts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                alert.ref,
                alert.account_ref,
                alert.snapshot_id,
                alert.cutoff,
                alert.score,
                alert.rank,
                alert.percentile,
                "ENTERED_HIGH",
                "NOT_REVIEWED",
            ],
        )

    connection.execute(
        "INSERT INTO source_manifest VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            SOURCE_DATASET,
            "/external/HI-Small_Trans.csv",
            "0" * 64,
            len(txs),
            min(tx.timestamp for tx in txs),
            max(tx.timestamp for tx in txs),
            datetime(2026, 8, 28, 0, 0, 0),
            DATA_CONTRACT_VERSION,
        ],
    )
    connection.close()
    return path


@pytest.fixture
def root_ref() -> str:
    return account_ref_for("B1", "ROOT")


@pytest.fixture
def peer_ref() -> str:
    return account_ref_for("B2", "PEER")


@pytest.fixture
def service_factory(tmp_path: Path):
    services: list[InvestigationServiceV2] = []

    def factory(transactions: Iterable[TxSpec], *, alerts: Iterable[AlertSpec] = ()) -> InvestigationServiceV2:
        path = build_runtime_db(tmp_path / f"runtime_{len(services)}.duckdb", transactions, alerts=alerts)
        service = create_investigation_service_v2(path)
        services.append(service)
        return service

    yield factory
    for service in services:
        service.close()
