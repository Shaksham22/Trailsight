"""Work-package-specific preparation failures."""


class DataPreparationError(RuntimeError):
    """Base class for deterministic preparation failures."""


class SourceValidationError(DataPreparationError):
    """The external source does not match the approved snapshot contract."""


class CanonicalizationError(DataPreparationError):
    """A permitted source value cannot be canonicalized."""


class DuplicateTransactionReferenceError(DataPreparationError):
    """Two source rows generated the same txref-v1 reference."""


class CaseSelectionError(DataPreparationError):
    """A required deterministic case cannot be selected uniquely."""


class EntityMappingError(DataPreparationError):
    """Minimal entity identity/type data is missing or contradictory."""


class RuntimeValidationError(DataPreparationError):
    """The generated runtime database violates the frozen schema or slice rules."""

