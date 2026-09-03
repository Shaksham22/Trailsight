"""Deterministic guard that prevents generated prose from contradicting GARG."""

from __future__ import annotations

import re
from typing import Any

from trailsight_v2.domain.models import NetworkReviewBand, SubjectType

from .context import SeedContextV2
from .models import InvestigationSummaryV2


class BandAlignmentViolation(ValueError):
    """Raised when generated prose does not align with the supplied review band."""


_LOW_OPPOSITION = re.compile(
    r"\b(?:however|instead|regardless|despite|although|yet|nevertheless|nonetheless)\b"
    r"|\bon the other hand\b|\bin contrast\b",
    re.IGNORECASE,
)
_LOW_CONCERN_LANGUAGE = re.compile(
    r"\b(?:notable|concerning|suspicious|unusual|abnormal|concentrated)\b"
    r"|\braises? concern\b|\bincreases? concern\b",
    re.IGNORECASE,
)
_LOW_SUPPORT = (
    "rather than spread across",
    "not spread across",
    "focused on one",
    "focused on a small number",
    "within a single relationship",
    "limited relationship spread",
    "stable activity",
    "activity remained stable",
    "relationships are established",
    "established relationships",
    "few other accounts",
)


def validate_band_alignment(
    seed: SeedContextV2,
    output: InvestigationSummaryV2,
) -> None:
    """Reject output that weakens, disputes, or recasts the authoritative GARG band."""

    band = _expected_band(seed)
    summary = _normalize(output.summary)
    all_text = _normalize(
        "\n".join(
            (
                output.summary,
                *output.observations,
                *output.patterns,
                *output.limits,
            )
        )
    )

    if seed.context.subject_type in {SubjectType.ACCOUNT, SubjectType.ALERT}:
        _validate_account_or_alert_summary(band, summary)
    else:
        _validate_transaction_summary(band, summary)

    if band is NetworkReviewBand.HIGH and any(
        phrase in all_text
        for phrase in ("garg found little evidence", "not a strong match", "low result")
    ):
        raise BandAlignmentViolation("HIGH output weakens the supplied GARG result")
    if band is NetworkReviewBand.MEDIUM and any(
        phrase in all_text
        for phrase in ("garg found strong evidence", "garg found little evidence")
    ):
        raise BandAlignmentViolation("MEDIUM output recasts the supplied GARG result")
    if band is NetworkReviewBand.LOW:
        if _LOW_OPPOSITION.search(all_text):
            raise BandAlignmentViolation("LOW output uses a contradictory contrast pivot")
        if _LOW_CONCERN_LANGUAGE.search(all_text):
            raise BandAlignmentViolation("LOW output introduces a competing concern narrative")
        if not any(phrase in all_text for phrase in _LOW_SUPPORT):
            raise BandAlignmentViolation("LOW output does not explain limited pattern spread")
        if "garg found strong evidence" in all_text or "increase concern" in all_text:
            raise BandAlignmentViolation("LOW output contradicts the supplied GARG result")
    if band is NetworkReviewBand.UNSCORED and any(
        phrase in all_text
        for phrase in (
            "garg found strong evidence",
            "garg found some similarities",
            "garg found little evidence",
        )
    ):
        raise BandAlignmentViolation("UNSCORED output invents a GARG band interpretation")


def _expected_band(seed: SeedContextV2) -> NetworkReviewBand:
    packet = seed.model_summary
    raw: Any
    if seed.context.subject_type is SubjectType.TRANSACTION:
        raw = packet.get("transaction_review_priority", {}).get("aml_review_priority")
    else:
        raw = packet.get("account_investigation", {}).get("detector", {}).get(
            "network_review_band"
        )
    try:
        return NetworkReviewBand(str(raw))
    except ValueError as exc:
        raise BandAlignmentViolation("The investigation packet has no valid GARG band") from exc


def _validate_account_or_alert_summary(
    band: NetworkReviewBand,
    summary: str,
) -> None:
    required = {
        NetworkReviewBand.HIGH: "garg found strong evidence",
        NetworkReviewBand.MEDIUM: "garg found some similarities",
        NetworkReviewBand.LOW: "garg found little evidence",
        NetworkReviewBand.UNSCORED: "garg could not",
    }[band]
    if required not in summary:
        raise BandAlignmentViolation(f"{band.value} account output lacks its required conclusion")
    if band is NetworkReviewBand.MEDIUM and not (
        "evidence is mixed" in summary or "no strong balancing fact" in summary
    ):
        raise BandAlignmentViolation("MEDIUM account output is not balanced")


def _validate_transaction_summary(
    band: NetworkReviewBand,
    summary: str,
) -> None:
    aligned = {
        NetworkReviewBand.HIGH: (
            "strongly resemble smurfing" in summary
            or "garg found strong evidence" in summary
        ),
        NetworkReviewBand.MEDIUM: (
            "medium priority" in summary and "some similarities" in summary
        ),
        NetworkReviewBand.LOW: (
            "low priority" in summary or "garg found little evidence" in summary
        ),
        NetworkReviewBand.UNSCORED: (
            "could not produce an overall priority" in summary
            or "not enough connection data" in summary
        ),
    }[band]
    if not aligned:
        raise BandAlignmentViolation(
            f"{band.value} transaction output lacks its required conclusion"
        )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("’", "'").split())
