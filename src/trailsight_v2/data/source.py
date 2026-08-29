"""Validation and streaming reads for the external IBM AMLworld HI-Small CSV."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from trailsight_v2.data.canonical import CanonicalTransaction, canonicalize_transaction
from trailsight_v2.data.constants import REQUIRED_SOURCE_COLUMNS, RUNTIME_SOURCE_ALLOWLIST
from trailsight_v2.data.errors import CanonicalizationError, SourceValidationError

_RAW_DUPLICATE_ACCOUNT_HEADER = tuple(
    "Account" if name == "Account.1" else name for name in REQUIRED_SOURCE_COLUMNS
)


@dataclass(frozen=True, slots=True)
class SourceValidationResult:
    source_path: Path
    header: tuple[str, ...]
    sha256: str


def read_source_header(path: str | Path) -> tuple[str, ...]:
    source_path = Path(path).expanduser().resolve()
    try:
        with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle), None)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SourceValidationError(f"cannot read IBM transaction CSV: {source_path}") from exc
    if not header:
        raise SourceValidationError(f"IBM transaction CSV is empty: {source_path}")
    return tuple(header)


def _source_positions(header: tuple[str, ...]) -> dict[str, int]:
    """Resolve the two supported IBM header spellings to frozen logical fields.

    The original IBM CSV can contain two physical ``Account`` header cells. Some
    parsers disambiguate the second one to ``Account.1`` before presenting the
    header. Those are the only two accepted layouts, and both must match the
    frozen schema position-for-position so that sender/receiver identity is
    never guessed from duplicate names.
    """
    if header == REQUIRED_SOURCE_COLUMNS or header == _RAW_DUPLICATE_ACCOUNT_HEADER:
        return {
            logical_name: index
            for index, logical_name in enumerate(REQUIRED_SOURCE_COLUMNS)
            if logical_name in RUNTIME_SOURCE_ALLOWLIST
        }

    raise SourceValidationError(
        "IBM HI-Small source header mismatch; expected the frozen IBM column order "
        "with either a raw duplicate second 'Account' header or a uniquely "
        "disambiguated second 'Account.1' header"
    )


def validate_source_header(header: tuple[str, ...]) -> None:
    _source_positions(header)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source(path: str | Path) -> SourceValidationResult:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise SourceValidationError(f"IBM HI-Small transaction file does not exist: {source_path}")
    header = read_source_header(source_path)
    validate_source_header(header)
    return SourceValidationResult(source_path=source_path, header=header, sha256=sha256_file(source_path))


def iter_canonical_transactions(
    path: str | Path,
) -> Iterator[CanonicalTransaction]:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise SourceValidationError(f"IBM HI-Small transaction file does not exist: {source_path}")
    validated_header = read_source_header(source_path)
    positions = _source_positions(validated_header)
    try:
        with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is None:
                raise SourceValidationError("IBM HI-Small source is missing a header")
            for ordinal, values in enumerate(reader, start=1):
                if len(values) != len(validated_header):
                    raise SourceValidationError(
                        f"source row {ordinal} has {len(values)} fields; "
                        f"validated header has {len(validated_header)}"
                    )
                safe_row = {name: values[index] for name, index in positions.items()}
                try:
                    yield canonicalize_transaction(
                        safe_row,
                        source_row_ordinal=ordinal,
                    )
                except CanonicalizationError as exc:
                    raise SourceValidationError(f"source row {ordinal}: {exc}") from exc
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SourceValidationError(f"cannot stream IBM transaction CSV: {source_path}") from exc
