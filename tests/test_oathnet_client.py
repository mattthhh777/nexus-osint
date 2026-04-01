"""
tests/test_oathnet_client.py — Unit tests for async OathnetClient.

Tests use respx to mock httpx.AsyncClient calls — no real network traffic.
All tests are async via pytest-asyncio.
"""
from __future__ import annotations

import pytest
import httpx
import respx

from modules.oathnet_client import (
    OathnetClient,
    BreachRecord,
    StealerRecord,
    OathnetResult,
    OATHNET_BASE_URL,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def client() -> OathnetClient:
    """Fresh OathnetClient with a test API key (no singleton side-effects)."""
    return OathnetClient(api_key="test-key-abc123")


# ── Test 1: __init__ creates httpx.AsyncClient ─────────────────────────────────

def test_init_creates_async_client(client: OathnetClient) -> None:
    """OathnetClient.__init__ must create an httpx.AsyncClient with base_url and x-api-key."""
    assert hasattr(client, "_client"), "Missing _client attribute"
    assert isinstance(client._client, httpx.AsyncClient), (
        f"Expected httpx.AsyncClient, got {type(client._client)}"
    )
    # Base URL set correctly
    assert str(client._client.base_url).rstrip("/") == OATHNET_BASE_URL.rstrip("/"), (
        f"base_url mismatch: {client._client.base_url!r}"
    )
    # Auth header present
    assert client._client.headers.get("x-api-key") == "test-key-abc123", (
        "x-api-key header not set on AsyncClient"
    )


# ── Test 2: search_breach returns list[BreachRecord] ───────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_search_breach_returns_breach_records(client: OathnetClient) -> None:
    """search_breach parses API response into OathnetResult with BreachRecords."""
    mock_response = {
        "success": True,
        "data": {
            "results_found": 2,
            "results": [
                {
                    "dbname": "TestDB",
                    "email": "test@example.com",
                    "username": "testuser",
                    "password": "secret123",
                    "ip": "1.2.3.4",
                    "domain": "example.com",
                    "date": "2023-01-01",
                    "country": "US",
                },
                {
                    "dbname": "AnotherDB",
                    "email": ["multi@example.com"],
                    "username": ["multiuser"],
                    "country": ["DE"],
                },
            ],
        },
    }
    respx.get(f"{OATHNET_BASE_URL}/service/search-breach").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    result = await client.search_breach("test@example.com")

    assert isinstance(result, OathnetResult)
    assert result.success is True
    assert len(result.breaches) == 2
    assert all(isinstance(b, BreachRecord) for b in result.breaches)
    assert result.breaches[0].dbname == "TestDB"
    assert result.breaches[0].email == "test@example.com"
    assert result.breaches[0].password == "secret123"
    # Multi-value fields unwrapped
    assert result.breaches[1].email == "multi@example.com"
    assert result.breaches[1].username == "multiuser"
    assert result.breaches[1].country == "DE"


# ── Test 3: search_stealer_v2 returns list[StealerRecord] ─────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_search_stealer_v2_returns_stealer_records(client: OathnetClient) -> None:
    """search_stealer_v2 parses stealer API response into OathnetResult with StealerRecords."""
    mock_response = {
        "success": True,
        "data": {
            "meta": {"total": 1},
            "next_cursor": "",
            "items": [
                {
                    "log": "log_abc",
                    "url": "https://example.com/login",
                    "domain": ["example.com"],
                    "username": "victim@example.com",
                    "password": "p@ssw0rd",
                    "email": ["victim@example.com"],
                    "log_id": "abc123",
                    "pwned_at": "2023-06-15",
                }
            ],
        },
    }
    respx.get(f"{OATHNET_BASE_URL}/service/v2/stealer/search").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    result = await client.search_stealer_v2("victim@example.com")

    assert isinstance(result, OathnetResult)
    assert result.success is True
    assert len(result.stealers) == 1
    assert all(isinstance(s, StealerRecord) for s in result.stealers)
    assert result.stealers[0].log == "log_abc"
    assert result.stealers[0].url == "https://example.com/login"
    assert result.stealers[0].username == "victim@example.com"
    assert result.stealers[0].log_id == "abc123"


# ── Test 4: Module-level singleton exists ──────────────────────────────────────

def test_module_level_singleton_exists() -> None:
    """modules.oathnet_client must export an `oathnet_client` module-level instance.

    NOTE: Uses a fresh import of the module without reload to avoid class identity
    corruption that would break subsequent isinstance checks in other tests.
    The singleton is `None` when OATHNET_API_KEY is not set — that is correct behavior.
    We verify the export name exists and that when a key is provided to OathnetClient
    directly it creates a valid instance (matching the singleton pattern).
    """
    import modules.oathnet_client as mod

    # The module must always export `oathnet_client` (may be None if no env key)
    assert hasattr(mod, "oathnet_client"), (
        "Module must export `oathnet_client` at module level"
    )
    # The exported value is either None (no env key) or an OathnetClient instance
    if mod.oathnet_client is not None:
        assert isinstance(mod.oathnet_client, mod.OathnetClient), (
            f"Expected OathnetClient instance, got {type(mod.oathnet_client)}"
        )

    # Verify the pattern works: an instance created with a key is an OathnetClient
    instance = mod.OathnetClient(api_key="test-singleton-key")
    assert isinstance(instance, mod.OathnetClient)
    assert instance._client is not None


# ── Test 5: HTTPStatusError returns empty list, logs warning ───────────────────

@pytest.mark.asyncio
@respx.mock
async def test_search_breach_handles_http_status_error(client: OathnetClient) -> None:
    """Client handles httpx.HTTPStatusError gracefully — returns OathnetResult with error, no raises."""
    respx.get(f"{OATHNET_BASE_URL}/service/search-breach").mock(
        return_value=httpx.Response(429, json={"message": "Too Many Requests"})
    )

    result = await client.search_breach("test@example.com")

    assert isinstance(result, OathnetResult)
    assert result.success is False
    assert result.breaches == []
    assert result.error != "", "error field must be populated on HTTP error"


# ── Test 6: ConnectError returns empty result, logs error ─────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_search_breach_handles_connect_error(client: OathnetClient) -> None:
    """Client handles httpx.ConnectError gracefully — returns OathnetResult with error, no raises."""
    respx.get(f"{OATHNET_BASE_URL}/service/search-breach").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    result = await client.search_breach("test@example.com")

    assert isinstance(result, OathnetResult)
    assert result.success is False
    assert result.breaches == []
    assert result.error != "", "error field must be populated on ConnectError"


# ── Test 7: close() method exists and is awaitable ────────────────────────────

@pytest.mark.asyncio
async def test_client_has_async_close(client: OathnetClient) -> None:
    """OathnetClient must expose an async close() method that awaits aclose() on _client."""
    assert hasattr(client, "close"), "Missing close() method"
    # Should not raise
    await client.close()
