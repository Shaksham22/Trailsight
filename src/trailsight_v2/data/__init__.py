"""Public WP01 data-foundation contract for Trailsight V2."""

from __future__ import annotations

from trailsight_v2.data.bank_country import BANK_COUNTRY_V1, BankCountry, bank_country_for
from trailsight_v2.data.canonical import (
    CanonicalAccount,
    CanonicalTransaction,
    account_ref_for,
    canonical_account,
    canonical_account_tuple,
    canonical_decimal,
    canonical_timestamp,
    canonicalize_transaction,
    normalize_source_id,
    transaction_identity_payload,
    transaction_ref_for,
)
from trailsight_v2.data.constants import (
    ACCOUNT_REF_VERSION,
    BANK_COUNTRY_VERSION,
    DATA_CONTRACT_VERSION,
    IBM_SOURCE_PATH_ENV,
    SOURCE_DATASET,
    TRANSACTION_REF_VERSION,
)
from trailsight_v2.data.queries import DETECTOR_EDGE_DAY_SQL, fetch_detector_edge_day_deltas
from trailsight_v2.data.schema import WP01_RUNTIME_TABLES, assert_ground_truth_firewall
from trailsight_v2.data.source import (
    SourceValidationResult,
    iter_canonical_transactions,
    read_source_header,
    validate_source,
    validate_source_header,
)

__all__ = [
    "ACCOUNT_REF_VERSION",
    "BANK_COUNTRY_V1",
    "BANK_COUNTRY_VERSION",
    "BankCountry",
    "CanonicalAccount",
    "CanonicalTransaction",
    "DATA_CONTRACT_VERSION",
    "DETECTOR_EDGE_DAY_SQL",
    "IBM_SOURCE_PATH_ENV",
    "PreparationSummary",
    "SOURCE_DATASET",
    "SourceValidationResult",
    "TRANSACTION_REF_VERSION",
    "WP01_RUNTIME_TABLES",
    "account_ref_for",
    "assert_ground_truth_firewall",
    "bank_country_for",
    "canonical_account",
    "canonical_account_tuple",
    "canonical_decimal",
    "canonical_timestamp",
    "canonicalize_transaction",
    "fetch_detector_edge_day_deltas",
    "iter_canonical_transactions",
    "normalize_source_id",
    "prepare_runtime_database",
    "read_source_header",
    "resolve_source_path",
    "transaction_identity_payload",
    "transaction_ref_for",
    "validate_source",
    "validate_source_header",
]


def __getattr__(name: str):
    if name in {"PreparationSummary", "prepare_runtime_database", "resolve_source_path"}:
        from trailsight_v2.data.prepare import (
            PreparationSummary,
            prepare_runtime_database,
            resolve_source_path,
        )

        exports = {
            "PreparationSummary": PreparationSummary,
            "prepare_runtime_database": prepare_runtime_database,
            "resolve_source_path": resolve_source_path,
        }
        return exports[name]
    raise AttributeError(name)
