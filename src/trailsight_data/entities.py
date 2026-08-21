"""Minimal Person/Merchant identity extraction and validation."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from trailsight_data.errors import EntityMappingError
from trailsight_data.models import RuntimeTransaction
from trailsight_data.source import iter_profile_identities

ENTITY_TYPES = frozenset({"Person", "Merchant"})
NUMERIC_SUFFIX = re.compile(r"(\d+)$")


def synthetic_region_for_account(account: str) -> int:
    match = NUMERIC_SUFFIX.search(account)
    if match is None:
        raise EntityMappingError(
            f"account has no numeric suffix for Synthetic Region derivation: {account!r}"
        )
    return int(match.group(1)) % 20


def build_entity_index(
    person_path: str | Path,
    merchant_path: str | Path,
) -> dict[tuple[str, str], str]:
    entity_index: dict[tuple[str, str], str] = {}
    for path, entity_type in (
        (person_path, "Person"),
        (merchant_path, "Merchant"),
    ):
        for identity in iter_profile_identities(path):
            prior_type = entity_index.get(identity)
            if prior_type is not None and prior_type != entity_type:
                bank, account = identity
                raise EntityMappingError(
                    "conflicting entity types for identity "
                    f"(bank={bank!r}, account={account!r}): {prior_type} vs {entity_type}"
                )
            entity_index[identity] = entity_type
    return entity_index


def select_runtime_entities(
    entity_index: Mapping[tuple[str, str], str],
    transactions: Iterable[RuntimeTransaction],
) -> dict[tuple[str, str], str]:
    required: set[tuple[str, str]] = set()
    for transaction in transactions:
        required.add((transaction.from_bank, transaction.from_account))
        required.add((transaction.to_bank, transaction.to_account))

    missing = sorted(required.difference(entity_index))
    if missing:
        preview = ", ".join(f"({bank}, {account})" for bank, account in missing[:10])
        raise EntityMappingError(f"runtime transaction entities are missing from profiles: {preview}")

    selected: dict[tuple[str, str], str] = {}
    for identity in sorted(required):
        entity_type = entity_index[identity]
        if entity_type not in ENTITY_TYPES:
            raise EntityMappingError(f"unsupported entity type: {entity_type!r}")
        synthetic_region_for_account(identity[1])
        selected[identity] = entity_type
    return selected
