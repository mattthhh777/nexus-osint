"""Unit tests for offline phone carrier lookup."""
from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from modules.connectors.base import ConnectorRequest, ConnectorStatus, TargetType
from modules.connectors.phone.carrier_lookup import CarrierLookup


def _request(target_value: str, target_type: TargetType = TargetType.PHONE) -> ConnectorRequest:
    return ConnectorRequest(
        target_type=target_type,
        target_value=target_value,
        target_hash="abcdef012345",
        timeout_s=5,
        job_id=uuid4(),
    )


async def _run(target_value: str) -> object:
    adapter = CarrierLookup()
    async with httpx.AsyncClient() as http:
        return await adapter.run(_request(target_value), http)


@pytest.mark.asyncio
async def test_carrier_lookup_br_mobile_is_likely_not_found() -> None:
    result = await _run("+5511987654321")

    assert result.connector == "carrier_lookup"
    assert result.target_type == TargetType.PHONE
    assert result.status == ConnectorStatus.LIKELY
    assert result.status != ConnectorStatus.FOUND
    assert result.confidence_score <= 75
    assert result.raw_url is None
    assert result.data["line_type"] == "mobile"
    rendered = str(result.model_dump(mode="json"))
    assert "+5511987654321" not in rendered


@pytest.mark.asyncio
async def test_carrier_lookup_us_landline_is_likely_not_found() -> None:
    result = await _run("+12125551234")

    assert result.status == ConnectorStatus.LIKELY
    assert result.status != ConnectorStatus.FOUND
    assert result.confidence_score <= 75
    assert result.raw_url is None
    assert result.data["line_type"] in {"fixed_line", "fixed_or_mobile", "unknown"}
    rendered = str(result.model_dump(mode="json"))
    assert "+12125551234" not in rendered


@pytest.mark.parametrize("target_value", ["+123", ""])
@pytest.mark.asyncio
async def test_carrier_lookup_invalid_numbers_are_not_found(target_value: str) -> None:
    result = await _run(target_value)

    assert result.status == ConnectorStatus.NOT_FOUND
    assert result.confidence_score == 0
    assert result.confidence_level == "none"
    assert result.evidence == []
    assert result.raw_url is None
    assert result.warnings in (["parse_failure"], ["invalid_number"])


@pytest.mark.asyncio
async def test_carrier_lookup_unknown_e164_prefix_is_uncertain_not_invented() -> None:
    result = await _run("+991234567890")

    assert result.status == ConnectorStatus.UNCERTAIN
    assert result.status != ConnectorStatus.FOUND
    assert result.data == {
        "carrier": "unknown",
        "country": "unknown",
        "line_type": "unknown",
    }
    assert result.warnings == ["unsupported_country_prefix"]
    rendered = str(result.model_dump(mode="json"))
    assert "+991234567890" not in rendered


@pytest.mark.asyncio
async def test_carrier_lookup_rejects_non_phone_target_type() -> None:
    adapter = CarrierLookup()

    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError, match="unsupported_target_type"):
            await adapter.run(_request("rawtarget", TargetType.USERNAME), http)
