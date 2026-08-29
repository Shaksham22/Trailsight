"""Per-run MCP authorization scope passed from the AI runner to its stdio child."""

from __future__ import annotations

import json
import os

from pydantic import BaseModel, ConfigDict, Field

from trailsight_v2.domain.models import ContextIdentityV2, SubjectType


MCP_SCOPE_ENV = "TRAILSIGHT_MCP_SCOPE_JSON"


class InvestigationScopeV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_type: SubjectType
    subject_ref: str = Field(min_length=1)
    origin_alert_ref: str | None = Field(default=None, min_length=1)
    origin_transaction_ref: str | None = Field(default=None, min_length=1)
    context_identity: ContextIdentityV2
    seed_evidence_ids: tuple[str, ...] = ()

    @property
    def origin_ref(self) -> str | None:
        if self.origin_alert_ref is not None and self.origin_transaction_ref is not None:
            raise ValueError("MCP scope cannot contain two historical origins")
        return self.origin_alert_ref or self.origin_transaction_ref


def scope_to_json(scope: InvestigationScopeV2) -> str:
    return scope.model_dump_json()


def scope_from_environment() -> InvestigationScopeV2:
    raw = os.environ.get(MCP_SCOPE_ENV, "").strip()
    if not raw:
        raise RuntimeError("Trailsight MCP investigation scope is missing")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Trailsight MCP investigation scope is invalid") from exc
    return InvestigationScopeV2.model_validate(payload)
