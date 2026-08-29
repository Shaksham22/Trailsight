"""WP01 data-foundation errors."""


class V2DataError(Exception):
    """Base exception for Trailsight V2 data foundation failures."""


class SourceValidationError(V2DataError):
    """Raised when the external IBM HI-Small source violates the frozen contract."""


class CanonicalizationError(V2DataError):
    """Raised when a source value cannot be canonicalized safely."""


class DataPreparationError(V2DataError):
    """Raised when runtime-safe DuckDB preparation cannot complete."""


class GroundTruthLeakageError(V2DataError):
    """Raised when hidden truth is detected in a runtime-safe schema."""
