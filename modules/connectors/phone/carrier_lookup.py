"""Offline phone metadata lookup with a small E.164 parser.

Carrier metadata is a weak signal. This connector never returns FOUND and does
not download numbering databases or call external services.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

import httpx

from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    Evidence,
    TargetType,
    derive_confidence_level,
)

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_SUPPORTED_COUNTRIES = {
    "1": {"country": "United States/Canada", "national_lengths": {10}},
    "44": {"country": "United Kingdom", "national_lengths": {9, 10}},
    "55": {"country": "Brazil", "national_lengths": {10, 11}},
    "351": {"country": "Portugal", "national_lengths": {9}},
}
_COUNTRY_CODES = tuple(sorted(_SUPPORTED_COUNTRIES, key=len, reverse=True))


class ParsedPhone:
    def __init__(
        self,
        *,
        country_code: str,
        national_number: str,
        country: str,
        supported: bool,
    ) -> None:
        self.country_code = country_code
        self.national_number = national_number
        self.country = country
        self.supported = supported


class CarrierLookup:
    """Offline connector for phone metadata."""

    name = "carrier_lookup"
    target_types = (TargetType.PHONE,)
    default_timeout_s = 5
    rate_limit_cps = 100.0

    async def run(
        self,
        req: ConnectorRequest,
        http: httpx.AsyncClient,
    ) -> ConnectorResult:
        del http
        if req.target_type != TargetType.PHONE:
            raise ValueError("unsupported_target_type")

        parsed = self._parse_e164(req.target_value)
        if parsed is None:
            return self._not_found(reason="invalid_number")

        carrier_name = "unknown"
        country = parsed.country
        line_type = self._line_type(parsed)

        evidence: list[Evidence] = []
        score = 0
        if not parsed.supported:
            evidence.append(Evidence(signal="e164_format_valid", weight=10, detail="unknown_prefix"))
            return ConnectorResult(
                connector=self.name,
                target_type=TargetType.PHONE,
                status=ConnectorStatus.UNCERTAIN,
                confidence_score=10,
                confidence_level=derive_confidence_level(10),
                evidence=evidence,
                warnings=["unsupported_country_prefix"],
                raw_url=None,
                data={
                    "carrier": carrier_name,
                    "country": country,
                    "line_type": line_type,
                },
                fetched_at=datetime.now(timezone.utc),
                cache_hit=False,
                elapsed_ms=0,
            )

        if country:
            evidence.append(Evidence(signal="country_known", weight=20, detail=country))
            score += 20
        if line_type:
            evidence.append(Evidence(signal="line_type_known", weight=15, detail=line_type))
            score += 15

        capped_score = min(score, 75)
        status = ConnectorStatus.LIKELY if capped_score > 0 else ConnectorStatus.NOT_FOUND

        return ConnectorResult(
            connector=self.name,
            target_type=TargetType.PHONE,
            status=status,
            confidence_score=capped_score,
            confidence_level=derive_confidence_level(capped_score),
            evidence=evidence,
            warnings=[],
            raw_url=None,
            data={
                "carrier": carrier_name,
                "country": country,
                "line_type": line_type,
            },
            fetched_at=datetime.now(timezone.utc),
            cache_hit=False,
            elapsed_ms=0,
        )

    def _not_found(self, *, reason: str) -> ConnectorResult:
        return ConnectorResult(
            connector=self.name,
            target_type=TargetType.PHONE,
            status=ConnectorStatus.NOT_FOUND,
            confidence_score=0,
            confidence_level="none",
            evidence=[],
            warnings=[reason],
            raw_url=None,
            data={},
            fetched_at=datetime.now(timezone.utc),
            cache_hit=False,
            elapsed_ms=0,
        )

    @staticmethod
    def _parse_e164(value: str) -> ParsedPhone | None:
        candidate = str(value or "").strip()
        if not _E164_RE.fullmatch(candidate):
            return None
        digits = candidate[1:]
        for country_code in _COUNTRY_CODES:
            if not digits.startswith(country_code):
                continue
            national = digits[len(country_code):]
            metadata = _SUPPORTED_COUNTRIES[country_code]
            if len(national) not in metadata["national_lengths"]:
                return None
            return ParsedPhone(
                country_code=country_code,
                national_number=national,
                country=str(metadata["country"]),
                supported=True,
            )
        return ParsedPhone(
            country_code="unknown",
            national_number=digits,
            country="unknown",
            supported=False,
        )

    @staticmethod
    def _line_type(parsed: ParsedPhone) -> str:
        if parsed.country_code == "55":
            subscriber = parsed.national_number[2:]
            if len(parsed.national_number) == 11 and subscriber.startswith("9"):
                return "mobile"
            if len(parsed.national_number) == 10:
                return "fixed_line"
            return "unknown"
        if parsed.country_code == "351":
            if parsed.national_number.startswith("9"):
                return "mobile"
            return "fixed_line"
        if parsed.country_code in {"1", "44"}:
            return "fixed_or_mobile"
        return "unknown"
