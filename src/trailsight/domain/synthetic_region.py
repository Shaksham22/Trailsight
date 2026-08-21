"""The single runtime implementation of the Synthetic Region rule."""

from __future__ import annotations

import re

from trailsight.errors import DomainInputError


_NUMERIC_SUFFIX = re.compile(r"([0-9]+)$")


def derive_synthetic_region(account: str) -> int:
    """Derive Synthetic Region as the account's numeric suffix modulo 20."""

    if not isinstance(account, str):
        raise DomainInputError("Account must be a string with a numeric suffix")
    match = _NUMERIC_SUFFIX.search(account)
    if match is None:
        raise DomainInputError("Account must have a numeric suffix")
    return int(match.group(1)) % 20
