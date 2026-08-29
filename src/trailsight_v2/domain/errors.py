"""Machine-stable, display-safe errors for the V2 investigation domain."""

from __future__ import annotations

from enum import Enum


class DomainErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_CONTEXT = "INVALID_CONTEXT"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INSUFFICIENT_NETWORK_CONTEXT = "INSUFFICIENT_NETWORK_CONTEXT"
    DATA_INTEGRITY_ERROR = "DATA_INTEGRITY_ERROR"
    RESULT_TOO_LARGE = "RESULT_TOO_LARGE"


class InvestigationDomainError(Exception):
    """Base expected domain failure with a safe public message."""

    code: DomainErrorCode

    def __init__(self, code: DomainErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


class NotFoundError(InvestigationDomainError):
    def __init__(self, message: str = "Requested Trailsight resource was not found") -> None:
        super().__init__(DomainErrorCode.NOT_FOUND, message)


class InvalidInputError(InvestigationDomainError):
    def __init__(self, message: str = "The request input is invalid") -> None:
        super().__init__(DomainErrorCode.INVALID_INPUT, message)


class InvalidContextError(InvestigationDomainError):
    def __init__(self, message: str = "The requested historical context is invalid") -> None:
        super().__init__(DomainErrorCode.INVALID_CONTEXT, message)


class InsufficientHistoryError(InvestigationDomainError):
    def __init__(self, message: str = "Insufficient prior history is available") -> None:
        super().__init__(DomainErrorCode.INSUFFICIENT_HISTORY, message)


class InsufficientNetworkContextError(InvestigationDomainError):
    def __init__(self, message: str = "Insufficient network context is available") -> None:
        super().__init__(DomainErrorCode.INSUFFICIENT_NETWORK_CONTEXT, message)


class DataIntegrityError(InvestigationDomainError):
    def __init__(self, message: str = "Runtime data failed the Trailsight integrity contract") -> None:
        super().__init__(DomainErrorCode.DATA_INTEGRITY_ERROR, message)


class ResultTooLargeError(InvestigationDomainError):
    def __init__(self, message: str = "Requested result exceeds the deterministic bound") -> None:
        super().__init__(DomainErrorCode.RESULT_TOO_LARGE, message)
