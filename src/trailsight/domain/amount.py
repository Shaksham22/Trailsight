"""Exact monetary helpers for deterministic amount history."""

from __future__ import annotations

from decimal import Decimal

from trailsight.errors import DataIntegrityError


def normalize_decimal(value: Decimal) -> str:
    """Return a non-exponent canonical base-10 representation."""

    if not isinstance(value, Decimal):
        raise DataIntegrityError("Runtime monetary values must use exact decimals")
    if not value.is_finite():
        raise DataIntegrityError("Runtime monetary values must be finite")
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def exact_median(values: list[Decimal]) -> Decimal:
    """Calculate a deterministic median without binary floating point."""

    if not values:
        raise ValueError("median requires at least one value")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)
