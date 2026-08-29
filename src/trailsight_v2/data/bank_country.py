"""Deterministic risk-neutral bank-country-v1 metadata mapping."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from trailsight_v2.data.canonical import normalize_source_id
from trailsight_v2.data.constants import BANK_COUNTRY_VERSION
from trailsight_v2.data.errors import CanonicalizationError


@dataclass(frozen=True, slots=True)
class BankCountry:
    country_name: str
    iso_alpha2: str
    centroid_latitude: float
    centroid_longitude: float


BANK_COUNTRY_V1: tuple[BankCountry, ...] = (
    BankCountry("Canada", "CA", 56.1304, -106.3468),
    BankCountry("United States", "US", 37.0902, -95.7129),
    BankCountry("Mexico", "MX", 23.6345, -102.5528),
    BankCountry("Brazil", "BR", -14.2350, -51.9253),
    BankCountry("United Kingdom", "GB", 55.3781, -3.4360),
    BankCountry("France", "FR", 46.2276, 2.2137),
    BankCountry("Germany", "DE", 51.1657, 10.4515),
    BankCountry("Netherlands", "NL", 52.1326, 5.2913),
    BankCountry("Switzerland", "CH", 46.8182, 8.2275),
    BankCountry("Spain", "ES", 40.4637, -3.7492),
    BankCountry("United Arab Emirates", "AE", 23.4241, 53.8478),
    BankCountry("Saudi Arabia", "SA", 23.8859, 45.0792),
    BankCountry("India", "IN", 20.5937, 78.9629),
    BankCountry("Pakistan", "PK", 30.3753, 69.3451),
    BankCountry("Bangladesh", "BD", 23.6850, 90.3563),
    BankCountry("Singapore", "SG", 1.3521, 103.8198),
    BankCountry("China", "CN", 35.8617, 104.1954),
    BankCountry("Japan", "JP", 36.2048, 138.2529),
    BankCountry("South Korea", "KR", 35.9078, 127.7669),
    BankCountry("Australia", "AU", -25.2744, 133.7751),
    BankCountry("South Africa", "ZA", -30.5595, 22.9375),
    BankCountry("Nigeria", "NG", 9.0820, 8.6753),
    BankCountry("Kenya", "KE", -0.0236, 37.9062),
    BankCountry("Philippines", "PH", 12.8797, 121.7740),
)


def bank_country_for(bank_id: object) -> BankCountry:
    """Map an already-canonical bank_id without changing its representation."""
    normalized_bank_id = normalize_source_id(bank_id, field="bank_id")
    if normalized_bank_id != bank_id:
        raise CanonicalizationError("bank_country_for requires the canonical normalized bank_id")
    digest = hashlib.sha256(
        f"{BANK_COUNTRY_VERSION}|{bank_id}".encode("utf-8")
    ).digest()
    index = int.from_bytes(digest[:8], byteorder="big", signed=False) % len(BANK_COUNTRY_V1)
    return BANK_COUNTRY_V1[index]
