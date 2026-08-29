"""Frozen WP01 constants from the Trailsight V2 data contract."""

SOURCE_DATASET = "ibm-amlworld-hi-small"
ACCOUNT_REF_VERSION = "account-ref-v1"
TRANSACTION_REF_VERSION = "ibm-txref-v1"
BANK_COUNTRY_VERSION = "bank-country-v1"
DATA_CONTRACT_VERSION = "trailsight-v2-data-contract-v1"
IBM_SOURCE_PATH_ENV = "IBM_HI_SMALL_TRANSACTIONS_PATH"

ASCII_WHITESPACE = " \t\n\r\v\f"

REQUIRED_SOURCE_COLUMNS = (
    "Timestamp",
    "From Bank",
    "Account",
    "To Bank",
    "Account.1",
    "Amount Received",
    "Receiving Currency",
    "Amount Paid",
    "Payment Currency",
    "Payment Format",
    "Is Laundering",
)

RUNTIME_SOURCE_ALLOWLIST = (
    "Timestamp",
    "From Bank",
    "Account",
    "To Bank",
    "Account.1",
    "Amount Received",
    "Receiving Currency",
    "Amount Paid",
    "Payment Currency",
    "Payment Format",
)

FORBIDDEN_RUNTIME_COLUMN_NAMES = frozenset(
    {"is_laundering", "pattern", "pattern_label", "aml_pattern"}
)
