"""Evidence V2 canonical identity codec."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from trailsight_v2.data.canonical import canonical_decimal
from trailsight_v2.domain.errors import InvalidInputError
from trailsight_v2.domain.models import (
    ContextIdentityV2,
    ContextKind,
    EvidenceIdentityV2,
    EvidenceType,
    SubjectType,
)

EVIDENCE_VERSION = "evidence-v2"
MAX_EVIDENCE_PAYLOAD_BYTES = 1024
MAX_EVIDENCE_ID_CHARS = 2048
_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


def canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is not None:
        raise InvalidInputError("Domain timestamps must be timezone-unspecified")
    if value.microsecond:
        raise InvalidInputError("Domain timestamps must use whole-second precision")
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def parse_canonical_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise InvalidInputError("Evidence context timestamp is not canonical") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%S") != value:
        raise InvalidInputError("Evidence context timestamp is not canonical")
    return parsed


def _normalize_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Decimal):
        return canonical_decimal(value)
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    if isinstance(value, float):
        raise InvalidInputError("Evidence parameters must not use binary floating-point values")
    if isinstance(value, list | tuple):
        return [_normalize_json(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise InvalidInputError("Evidence parameter object keys must be strings")
        normalized_items: dict[str, Any] = {}
        for key in sorted(value):
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized_items:
                raise InvalidInputError("Evidence parameter keys collide after NFC normalization")
            normalized_items[normalized_key] = _normalize_json(value[key])
        return normalized_items
    raise InvalidInputError("Evidence parameters contain an unsupported value type")


def canonical_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_json(parameters)
    if not isinstance(normalized, dict):
        raise InvalidInputError("Evidence parameters must be an object")
    return normalized


def _identity_payload(identity: EvidenceIdentityV2) -> dict[str, Any]:
    return {
        "v": EVIDENCE_VERSION,
        "evidence_type": identity.evidence_type.value,
        "subject_type": identity.subject_type.value,
        "subject_ref": unicodedata.normalize("NFC", identity.subject_ref),
        "context": {
            "kind": identity.context_identity.context_kind.value,
            "ref": unicodedata.normalize("NFC", identity.context_identity.context_ref),
            "time": identity.context_identity.context_time,
            "snapshot_id": identity.context_identity.snapshot_id,
        },
        "parameters": canonical_parameters(identity.parameters),
    }


def canonical_identity_bytes(identity: EvidenceIdentityV2) -> bytes:
    payload = _identity_payload(identity)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(raw) > MAX_EVIDENCE_PAYLOAD_BYTES:
        raise InvalidInputError("Evidence identity payload exceeds 1024 bytes")
    return raw


def encode_evidence_id(identity: EvidenceIdentityV2) -> str:
    payload_bytes = canonical_identity_bytes(identity)
    payload = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    checksum = base64.urlsafe_b64encode(hashlib.sha256(payload_bytes).digest()).decode(
        "ascii"
    ).rstrip("=")
    evidence_id = f"ev2.{payload}.{checksum}"
    if len(evidence_id) > MAX_EVIDENCE_ID_CHARS:
        raise InvalidInputError("Evidence ID exceeds 2048 characters")
    return evidence_id


def _decode_segment(segment: str) -> bytes:
    if not segment or _SEGMENT.fullmatch(segment) is None:
        raise InvalidInputError("Evidence ID contains an invalid base64url segment")
    try:
        return base64.b64decode(
            segment + "=" * (-len(segment) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, base64.binascii.Error) as exc:
        raise InvalidInputError("Evidence ID contains invalid base64url") from exc


def decode_evidence_id(evidence_id: str) -> EvidenceIdentityV2:
    if not isinstance(evidence_id, str) or not evidence_id:
        raise InvalidInputError("Evidence ID must be a non-empty string")
    if len(evidence_id) > MAX_EVIDENCE_ID_CHARS:
        raise InvalidInputError("Evidence ID exceeds 2048 characters")
    parts = evidence_id.split(".")
    if len(parts) != 3 or parts[0] != "ev2":
        raise InvalidInputError("Evidence ID must use ev2.<payload>.<checksum>")
    payload_bytes = _decode_segment(parts[1])
    checksum = _decode_segment(parts[2])
    if len(payload_bytes) > MAX_EVIDENCE_PAYLOAD_BYTES:
        raise InvalidInputError("Evidence identity payload exceeds 1024 bytes")
    if len(checksum) != hashlib.sha256().digest_size:
        raise InvalidInputError("Evidence checksum length is invalid")
    if not hmac.compare_digest(hashlib.sha256(payload_bytes).digest(), checksum):
        raise InvalidInputError("Evidence checksum validation failed")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidInputError("Evidence identity payload is not valid canonical JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "v", "evidence_type", "subject_type", "subject_ref", "context", "parameters"
    }:
        raise InvalidInputError("Evidence identity payload has invalid fields")
    if payload.get("v") != EVIDENCE_VERSION:
        raise InvalidInputError("Evidence version is unknown")
    context = payload.get("context")
    if not isinstance(context, dict) or set(context) != {"kind", "ref", "time", "snapshot_id"}:
        raise InvalidInputError("Evidence context identity has invalid fields")
    parameters = payload.get("parameters")
    if not isinstance(parameters, dict):
        raise InvalidInputError("Evidence parameters must be an object")
    try:
        context_identity = ContextIdentityV2(
            context_kind=ContextKind(context["kind"]),
            context_ref=context["ref"],
            context_time=context["time"],
            snapshot_id=context["snapshot_id"],
        )
        parse_canonical_timestamp(context_identity.context_time)
        identity = EvidenceIdentityV2(
            evidence_type=EvidenceType(payload["evidence_type"]),
            subject_type=SubjectType(payload["subject_type"]),
            subject_ref=payload["subject_ref"],
            context_identity=context_identity,
            parameters=canonical_parameters(parameters),
        )
    except (ValueError, TypeError, ValidationError) as exc:
        raise InvalidInputError("Evidence identity payload contains an unknown or invalid value") from exc
    if canonical_identity_bytes(identity) != payload_bytes:
        raise InvalidInputError("Evidence identity payload is not in canonical representation")
    if encode_evidence_id(identity) != evidence_id:
        raise InvalidInputError("Evidence ID is not canonical")
    return identity
