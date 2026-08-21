"""Deterministic error vocabulary for the Trailsight backend."""


class TrailsightError(Exception):
    """Base class for expected deterministic failures."""


class ConfigurationError(TrailsightError):
    """Raised when deterministic runtime configuration is invalid."""


class DataIntegrityError(TrailsightError):
    """Raised when the frozen runtime database contract is violated."""


class CaseNotFoundError(TrailsightError):
    """Raised when a requested Trailsight case does not exist."""

    def __init__(self, case_ref: str) -> None:
        super().__init__(f"Case {case_ref!r} was not found")
        self.case_ref = case_ref


class DomainInputError(TrailsightError):
    """Raised when a bounded deterministic-domain input is invalid."""


class EvidenceResolutionError(DomainInputError):
    """Raised when an evidence ID is not one of the frozen formats."""
