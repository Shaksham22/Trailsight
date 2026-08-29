"""Frozen endpoint-band to transaction AML Review Priority matrix."""

from __future__ import annotations

from trailsight_v2.detector.models import PriorityDerivation, ReviewBand


def derive_transaction_priority(
    sender_band: ReviewBand | str,
    receiver_band: ReviewBand | str,
) -> PriorityDerivation:
    sender = ReviewBand(sender_band)
    receiver = ReviewBand(receiver_band)
    if sender is ReviewBand.HIGH and receiver is ReviewBand.HIGH:
        return PriorityDerivation(
            ReviewBand.HIGH,
            "BOTH_ENDPOINTS_HIGH",
            "Sender and receiver are HIGH in the latest valid network snapshot; transaction review priority is HIGH.",
        )
    if sender is ReviewBand.HIGH:
        return PriorityDerivation(
            ReviewBand.HIGH,
            "SENDER_HIGH",
            "Sender is HIGH in the latest valid network snapshot; transaction review priority is HIGH.",
        )
    if receiver is ReviewBand.HIGH:
        return PriorityDerivation(
            ReviewBand.HIGH,
            "RECEIVER_HIGH",
            "Receiver is HIGH in the latest valid network snapshot; transaction review priority is HIGH.",
        )
    if sender is ReviewBand.MEDIUM and receiver is ReviewBand.MEDIUM:
        return PriorityDerivation(
            ReviewBand.MEDIUM,
            "BOTH_ENDPOINTS_MEDIUM",
            "Sender and receiver are MEDIUM in the latest valid network snapshot; transaction review priority is MEDIUM.",
        )
    if sender is ReviewBand.MEDIUM:
        return PriorityDerivation(
            ReviewBand.MEDIUM,
            "SENDER_MEDIUM",
            "Sender is MEDIUM and neither endpoint is HIGH in the latest valid network snapshot; transaction review priority is MEDIUM.",
        )
    if receiver is ReviewBand.MEDIUM:
        return PriorityDerivation(
            ReviewBand.MEDIUM,
            "RECEIVER_MEDIUM",
            "Receiver is MEDIUM and neither endpoint is HIGH in the latest valid network snapshot; transaction review priority is MEDIUM.",
        )
    if sender is ReviewBand.LOW and receiver is ReviewBand.LOW:
        return PriorityDerivation(
            ReviewBand.LOW,
            "BOTH_ENDPOINTS_LOW",
            "Sender and receiver are LOW in the latest valid network snapshot; transaction review priority is LOW.",
        )
    return PriorityDerivation(
        ReviewBand.UNSCORED,
        "INSUFFICIENT_NETWORK_CONTEXT",
        "Neither endpoint is HIGH or MEDIUM and at least one endpoint is UNSCORED; transaction review priority has insufficient network context.",
    )

