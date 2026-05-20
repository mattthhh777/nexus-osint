"""Unit tests for the R1-5 OathNet connector adapter."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest

from modules.connectors.base import ConnectorRequest, ConnectorStatus, TargetType
from modules.connectors.oathnet_adapter import OathNetAdapter
from modules.oathnet_client import OathnetResult


class FakeOathNetClient:
    def __init__(
        self,
        *,
        breach: OathnetResult | BaseException | None = None,
        stealer: OathnetResult | BaseException | None = None,
        victims: tuple[bool, dict] | BaseException | None = None,
    ) -> None:
        self.breach = breach
        self.stealer = stealer
        self.victims = victims
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def search_breach(self, *args: Any, **kwargs: Any) -> OathnetResult:
        self.calls.append(("breach", args, kwargs))
        if isinstance(self.breach, BaseException):
            raise self.breach
        if self.breach is None:
            raise AssertionError("breach result missing")
        return self.breach

    async def search_stealer_v2(self, *args: Any, **kwargs: Any) -> OathnetResult:
        self.calls.append(("stealer", args, kwargs))
        if isinstance(self.stealer, BaseException):
            raise self.stealer
        if self.stealer is None:
            raise AssertionError("stealer result missing")
        return self.stealer

    async def victims_search(self, *args: Any, **kwargs: Any) -> tuple[bool, dict]:
        self.calls.append(("victims", args, kwargs))
        if isinstance(self.victims, BaseException):
            raise self.victims
        if self.victims is None:
            raise AssertionError("victims result missing")
        return self.victims


def _request(
    target_type: TargetType = TargetType.EMAIL,
    target_value: str = "victim@example.com",
) -> ConnectorRequest:
    return ConnectorRequest(
        target_type=target_type,
        target_value=target_value,
        target_hash="abcdef012345",
        timeout_s=7,
        job_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_oathnet_breach_found_maps_to_connector_result() -> None:
    client = FakeOathNetClient(breach=OathnetResult(success=True, results_found=2))
    adapter = OathNetAdapter("oathnet:breach", client=client)

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(), http)

    assert result.connector == "oathnet:breach"
    assert result.status == ConnectorStatus.FOUND
    assert result.confidence_score == 90
    assert result.confidence_level == "high"
    assert result.raw_url is None
    assert result.data == {
        "source": "oathnet",
        "category": "breach",
        "labels": ["record_count:2"],
    }
    assert client.calls[0][0] == "breach"
    assert client.calls[0][1] == ("victim@example.com",)
    rendered = str(result.model_dump(mode="json"))
    assert "victim@example.com" not in rendered


@pytest.mark.asyncio
async def test_oathnet_stealer_found_maps_to_connector_result() -> None:
    client = FakeOathNetClient(stealer=OathnetResult(success=True, stealers_found=3))
    adapter = OathNetAdapter("stealer", client=client)

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(), http)

    assert result.connector == "oathnet:stealer"
    assert result.status == ConnectorStatus.FOUND
    assert result.confidence_score == 92
    assert result.confidence_level == "high"
    assert result.evidence[0].signal == "stealer_records_found"
    assert result.evidence[0].detail == "records_found=3"
    assert result.raw_url is None
    rendered = str(result.model_dump(mode="json"))
    assert "victim@example.com" not in rendered


@pytest.mark.asyncio
async def test_oathnet_victims_email_found() -> None:
    client = FakeOathNetClient(
        victims=(True, {"items": [{"redacted": True}], "meta": {"total": 1}})
    )
    adapter = OathNetAdapter("victims", client=client)

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(TargetType.EMAIL, "victim@example.com"), http)

    assert result.connector == "oathnet:victims"
    assert result.status == ConnectorStatus.FOUND
    assert result.confidence_score == 85
    assert result.raw_url is None
    call_name, args, kwargs = client.calls[0]
    assert call_name == "victims"
    assert args[:4] == ("", 10, "", "")
    assert kwargs["email"] == "victim@example.com"
    assert "ip" not in kwargs
    rendered = str(result.model_dump(mode="json"))
    assert "victim@example.com" not in rendered


@pytest.mark.asyncio
async def test_oathnet_victims_username_likely_never_found() -> None:
    client = FakeOathNetClient(
        victims=(True, {"items": [{"redacted": True}], "meta": {"total": 1}})
    )
    adapter = OathNetAdapter("oathnet:victims", client=client)

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(TargetType.USERNAME, "rawtarget"), http)

    assert result.status == ConnectorStatus.LIKELY
    assert result.status != ConnectorStatus.FOUND
    assert result.confidence_score == 65
    assert result.confidence_level == "medium"
    assert client.calls[0][2]["username"] == "rawtarget"
    rendered = str(result.model_dump(mode="json"))
    assert "rawtarget" not in rendered


@pytest.mark.asyncio
async def test_oathnet_victims_not_found() -> None:
    client = FakeOathNetClient(victims=(True, {"items": [], "meta": {"total": 0}}))
    adapter = OathNetAdapter("victims", client=client)

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(), http)

    assert result.status == ConnectorStatus.NOT_FOUND
    assert result.confidence_score == 0
    assert result.confidence_level == "none"
    assert result.evidence[0].detail == "records_found=0"


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        ("Invalid or expired API key (HTTP 401)", "auth_blocked"),
        ("Forbidden (HTTP 403)", "access_blocked"),
        ("OathNet rate limit exceeded (HTTP 429)", "rate_limited"),
        ("rate limit exceeded for victim@example.com", "rate_limited"),
        ("Cloudflare challenge for victim@example.com", "challenge_blocked"),
    ],
)
@pytest.mark.asyncio
async def test_oathnet_blocked_error_mapping(error: str, expected_reason: str) -> None:
    client = FakeOathNetClient(breach=OathnetResult(success=False, error=error))
    adapter = OathNetAdapter("breach", client=client)

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(), http)

    assert result.status == ConnectorStatus.BLOCKED
    assert result.warnings == [expected_reason]
    rendered = str(result.model_dump(mode="json"))
    assert "victim@example.com" not in rendered
    assert result.raw_url is None


@pytest.mark.parametrize(
    ("failure", "expected_reason"),
    [
        (httpx.TimeoutException("timeout victim@example.com"), "oathnet_timeout"),
        (
            httpx.ConnectError(
                "network victim@example.com",
                request=httpx.Request("GET", "https://oathnet.test/?q=victim@example.com"),
            ),
            "oathnet_network_error",
        ),
        (OathnetResult(success=False, error="OathNet server error (HTTP 503)."), "oathnet_server_error"),
    ],
)
@pytest.mark.asyncio
async def test_oathnet_error_mapping_without_target_leak(
    failure: OathnetResult | BaseException,
    expected_reason: str,
) -> None:
    client = FakeOathNetClient(breach=failure)
    adapter = OathNetAdapter("breach", client=client)

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(), http)

    assert result.status == ConnectorStatus.ERROR
    assert result.warnings == [expected_reason]
    rendered = str(result.model_dump(mode="json"))
    assert "victim@example.com" not in rendered
    assert "oathnet.test" not in rendered
    assert result.raw_url is None


def test_oathnet_adapter_rejects_invalid_connector_id() -> None:
    with pytest.raises(ValueError, match="unsupported_oathnet_connector"):
        OathNetAdapter("oathnet:freeform")


def test_oathnet_ip_info_deferred_and_not_called() -> None:
    client = FakeOathNetClient()

    with pytest.raises(ValueError, match="oathnet_ip_deferred"):
        OathNetAdapter("ip_info", client=client)
    with pytest.raises(ValueError, match="oathnet_ip_deferred"):
        OathNetAdapter("oathnet:ip", client=client)

    assert client.calls == []


def test_legacy_api_search_route_stays_active() -> None:
    from fastapi.routing import APIRoute

    from api.routes.search import router

    assert any(
        isinstance(route, APIRoute)
        and route.path == "/api/search"
        and route.methods is not None
        and "POST" in route.methods
        for route in router.routes
    )
