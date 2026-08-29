"""WP02 detector exceptions with runtime-safe messages."""

from __future__ import annotations


class DetectorError(RuntimeError):
    """Base error for deterministic detector preparation failures."""


class DetectorContractError(DetectorError):
    """Raised when persisted state does not match the frozen WP02 contract."""


class DetectorPreparationError(DetectorError):
    """Raised when a detector preparation run cannot complete safely."""

