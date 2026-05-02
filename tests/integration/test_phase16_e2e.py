"""
tests/integration/test_phase16_e2e.py
======================================
End-to-end integration tests for Phase 16 SSE contract.

Covers:
1. Confirmed-only result (3 found, 0 likely)
2. Mixed found + likely (2 found + 3 likely)
3. proxy_used=True reflected in SSE
4. Budget exceeded -> module_error before Sherlock invocation
5. Invalid username -> module_error before Sherlock invocation
6. D-H2/D-H3 audit: no internal scoring fields in SSE bytes
7. D-H13 audit log: username_hash= present, plaintext username absent
8. PlatformResult serialization tightness: exactly 6 allowed keys

All Sherlock outbound calls are mocked -- no real HTTP.
Reuses fixture patterns from test_phase16_routes.py.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

# JWT_SECRET must be set before importing api.main
_TEST_SECRET = "test-secret-phase16-e2e-only-never-prod-abcdef654321"
os.environ.setdefault("JWT_SECRET", _TEST_SECRET)

import pytest

import api.budget as budget
from api.config import THORDATA_DAILY_BUDGET_BYTES
from api.db import DatabaseManager
from api.orchestrator import DegradationMode, TaskOrchestrator
from api.schemas import SearchRequest
from api.services.search_service import _stream_search
from modules.sherlock_wrapper import PlatformResult, SherlockResult


# ── Stub builders ─────────────────────────────────────────────────────────────


def _make_platform(platform: str, state: str, confidence: int) -> PlatformResult:
    """Build a minimal PlatformResult for tests."""
    return PlatformResult(
        platform=platform,
        url=f"https://{platform.lower()}.example/{platform}42",
        category="Test",
        icon="T",
        state=state,
        confidence=confidence,
        found=(state != "not_found"),
    )


def build_sherlock_stub(
    found_count: int,
    likely_count: int,
    proxy_used: bool = False,
    username: str = "alice42",
) -> SherlockResult:
    """Build a SherlockResult stub exercising the full serializer path."""
    return SherlockResult(
        username=username,
        success=True,
        found=[
            _make_platform(f"P{i}", "confirmed", 85)
            for i in range(found_count)
        ],
        likely=[
            _make_platform(f"L{i}", "likely", 55)
            for i in range(likely_count)
        ],
        not_found=[],
        errors=[],
        source="internal",
        proxy_used=proxy_used,
    )


# ── Shared helpers (mirror test_phase16_routes.py pattern) ────────────────────


def _parse_sse(content: bytes) -> list[dict]:
    """Parse SSE text/event-stream body into list of event dicts."""
    events = []
    for line in content.decode("utf-8", errors="replace").splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def _make_mock_db() -> MagicMock:
    db = MagicMock(spec=DatabaseManager)
    db.write = AsyncMock()
    db.read_one = AsyncMock(return_value=None)
    return db


def _make_mock_orch() -> MagicMock:
    orch = MagicMock(spec=TaskOrchestrator)
    orch.degradation_mode = DegradationMode.NORMAL
    orch.active_count = 0
    orch.semaphore_slots_free = 5
    orch.submit = MagicMock()
    return orch


async def _collect_sse(req: SearchRequest) -> list[dict]:
    """Run _stream_search and collect all parsed SSE events."""
    chunks = []
    async for chunk in _stream_search(
        req, "alice42", "127.0.0.1", db=_make_mock_db(), orch=_make_mock_orch()
    ):
        chunks.append(chunk)
    raw = b"".join(c.encode() if isinstance(c, str) else c for c in chunks)
    return _parse_sse(raw)


async def _collect_sse_raw(req: SearchRequest) -> bytes:
    """Run _stream_search and return raw SSE bytes (for D-H2/D-H3 byte-level check)."""
    chunks = []
    async for chunk in _stream_search(
        req, "alice42", "127.0.0.1", db=_make_mock_db(), orch=_make_mock_orch()
    ):
        chunks.append(chunk)
    return b"".join(c.encode() if isinstance(c, str) else c for c in chunks)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_budget(monkeypatch):
    """Reset budget module state before each test (mirror of test_phase16_routes.py)."""
    monkeypatch.setattr(budget, "_bytes_today", 0)
    monkeypatch.setattr(budget, "_requests_today", 0)
    monkeypatch.setattr(budget, "_current_day", datetime.now(timezone.utc).date())
    monkeypatch.setattr(budget, "_proxy_active", False)


# ── Test 1: Confirmed-only result ─────────────────────────────────────────────


def test_confirmed_only_sse_shape(monkeypatch):
    """Test 1: mock returns 3 found, 0 likely -> SSE found_count=3, likely_count=0, likely=[].

    Verifies the serializer correctly separates confirmed from likely=[] when
    sherlock_wrapper returns no likely-state results.
    """
    import modules.sherlock_wrapper as sw

    stub = build_sherlock_stub(found_count=3, likely_count=0)
    monkeypatch.setattr(sw, "search_username", AsyncMock(return_value=stub))

    req = SearchRequest(query="alice42", mode="manual", modules=["sherlock"])
    events = asyncio.get_event_loop().run_until_complete(_collect_sse(req))

    sherlock_event = next(
        (e for e in events if e.get("type") == "sherlock"),
        None,
    )
    assert sherlock_event is not None, f"No sherlock event in SSE: {events}"
    assert sherlock_event["found_count"] == 3, f"Expected found_count=3, got {sherlock_event}"
    assert sherlock_event["likely_count"] == 0, f"Expected likely_count=0, got {sherlock_event}"
    assert sherlock_event["likely"] == [], f"Expected likely=[], got {sherlock_event}"
    assert len(sherlock_event["found"]) == 3, f"Expected 3 found items, got {sherlock_event}"


# ── Test 2: Mixed found + likely ─────────────────────────────────────────────


def test_mixed_found_and_likely_sse_shape(monkeypatch):
    """Test 2: 2 found + 3 likely -> SSE found_count=2, likely_count=3, both arrays populated.

    Verifies the extended SSE serializer populates both found and likely lists.
    """
    import modules.sherlock_wrapper as sw

    stub = build_sherlock_stub(found_count=2, likely_count=3)
    monkeypatch.setattr(sw, "search_username", AsyncMock(return_value=stub))

    req = SearchRequest(query="alice42", mode="manual", modules=["sherlock"])
    events = asyncio.get_event_loop().run_until_complete(_collect_sse(req))

    sherlock_event = next(
        (e for e in events if e.get("type") == "sherlock"),
        None,
    )
    assert sherlock_event is not None, f"No sherlock event: {events}"
    assert sherlock_event["found_count"] == 2, f"found_count mismatch: {sherlock_event}"
    assert sherlock_event["likely_count"] == 3, f"likely_count mismatch: {sherlock_event}"
    assert len(sherlock_event["found"]) == 2, f"found array mismatch: {sherlock_event}"
    assert len(sherlock_event["likely"]) == 3, f"likely array mismatch: {sherlock_event}"

    for item in sherlock_event["found"]:
        assert item["state"] == "confirmed", f"found item has wrong state: {item}"
    for item in sherlock_event["likely"]:
        assert item["state"] == "likely", f"likely item has wrong state: {item}"


# ── Test 3: proxy_used reflected ─────────────────────────────────────────────


def test_proxy_used_true_reflected_in_sse(monkeypatch):
    """Test 3: mock returns proxy_used=True -> SSE event reflects proxy_used=True."""
    import modules.sherlock_wrapper as sw

    stub = build_sherlock_stub(found_count=1, likely_count=0, proxy_used=True)
    monkeypatch.setattr(sw, "search_username", AsyncMock(return_value=stub))

    req = SearchRequest(query="alice42", mode="manual", modules=["sherlock"])
    events = asyncio.get_event_loop().run_until_complete(_collect_sse(req))

    sherlock_event = next(
        (e for e in events if e.get("type") == "sherlock"),
        None,
    )
    assert sherlock_event is not None, f"No sherlock event: {events}"
    assert sherlock_event.get("proxy_used") is True, (
        f"Expected proxy_used=True, got: {sherlock_event.get('proxy_used')}"
    )


# ── Test 4: Budget exceeded ───────────────────────────────────────────────────


def test_budget_exceeded_yields_module_error_before_sherlock(monkeypatch):
    """Test 4: _bytes_today over hard limit -> module_error; Sherlock NOT invoked.

    Verifies D-H12: circuit breaker fires before any outbound Sherlock work.
    """
    import modules.sherlock_wrapper as sw

    monkeypatch.setattr(budget, "_bytes_today", THORDATA_DAILY_BUDGET_BYTES + 1)

    call_count = {"n": 0}

    async def spy_search_username(*args, **kwargs):
        call_count["n"] += 1
        return build_sherlock_stub(0, 0)

    monkeypatch.setattr(sw, "search_username", spy_search_username)

    req = SearchRequest(query="alice42", mode="manual", modules=["sherlock"])
    events = asyncio.get_event_loop().run_until_complete(_collect_sse(req))

    sherlock_error = next(
        (e for e in events if e.get("type") == "module_error" and e.get("module") == "sherlock"),
        None,
    )
    assert sherlock_error is not None, f"No sherlock module_error: {events}"
    assert sherlock_error["error"] == "budget_exceeded", (
        f"Expected error=budget_exceeded, got: {sherlock_error}"
    )
    assert sherlock_error.get("retry_after") == 86400, (
        f"Expected retry_after=86400, got: {sherlock_error}"
    )
    assert call_count["n"] == 0, (
        f"search_username called despite budget exceeded (count={call_count['n']})"
    )


# ── Test 5: Invalid username ──────────────────────────────────────────────────


def test_invalid_username_yields_module_error_before_sherlock(monkeypatch):
    """Test 5: query containing / -> module_error invalid_username; Sherlock NOT invoked.

    Verifies D-H8/D-H9: validator rejects at boundary; input not echoed.
    """
    import modules.sherlock_wrapper as sw

    call_count = {"n": 0}

    async def spy_search_username(*args, **kwargs):
        call_count["n"] += 1
        return build_sherlock_stub(0, 0)

    monkeypatch.setattr(sw, "search_username", spy_search_username)

    req = SearchRequest(query="bad/value", mode="manual", modules=["sherlock"])
    events = asyncio.get_event_loop().run_until_complete(_collect_sse(req))

    sherlock_error = next(
        (e for e in events if e.get("type") == "module_error" and e.get("module") == "sherlock"),
        None,
    )
    assert sherlock_error is not None, f"No sherlock module_error: {events}"
    assert sherlock_error["error"] == "invalid_username", (
        f"Expected error=invalid_username, got: {sherlock_error}"
    )
    # D-H9: raw input must NOT appear in the module_error event
    assert "bad/value" not in json.dumps(sherlock_error), (
        f"Input 'bad/value' leaked into sherlock module_error event: {sherlock_error}"
    )
    assert call_count["n"] == 0, (
        f"search_username called despite invalid username (count={call_count['n']})"
    )


# ── Test 6: D-H2/D-H3 SSE bytes audit ────────────────────────────────────────


def test_dh2_dh3_no_internal_scoring_fields_in_sse_bytes(monkeypatch):
    """Test 6: raw SSE payload bytes must not contain internal scoring field names.

    D-H2: status_pts, text_pts, size_pts, confidence_breakdown never in payload.
    D-H3: negative_markers never in payload.
    Byte-level: if the string appears anywhere in the raw SSE stream it fails.
    """
    import modules.sherlock_wrapper as sw

    stub = build_sherlock_stub(found_count=2, likely_count=2)
    monkeypatch.setattr(sw, "search_username", AsyncMock(return_value=stub))

    req = SearchRequest(query="alice42", mode="manual", modules=["sherlock"])
    raw_bytes = asyncio.get_event_loop().run_until_complete(_collect_sse_raw(req))

    forbidden = [
        b"negative_markers",
        b"status_pts",
        b"text_pts",
        b"size_pts",
        b"confidence_breakdown",
    ]
    for field in forbidden:
        assert field not in raw_bytes, (
            f"Forbidden field {field!r} found in raw SSE bytes (D-H2/D-H3 violation)"
        )


# ── Test 7: D-H13 audit log ──────────────────────────────────────────────────


def test_dh13_audit_log_uses_hash_not_plaintext(monkeypatch):
    """Test 7: Sherlock audit log contains username_hash= and NOT plaintext username.

    D-H13: per-search log line uses SHA256-truncated hash; username never plaintext.
    Uses stdlib logging capture on nexusosint.sherlock logger.
    Patches _check_platform to avoid real network calls.
    """
    import modules.sherlock_wrapper as sw

    test_username = "alice42"

    async def fake_check_platform(client, username, platform, counter):
        return PlatformResult(
            platform=platform["name"],
            url=platform["url"].format(username=username),
            category=platform.get("category", ""),
            icon=platform.get("icon", ""),
            state="not_found",
            confidence=0,
            found=False,
        )

    async def fake_check_with_retry(primary, rotate, username, platform, counter):
        return await fake_check_platform(primary, username, platform, counter)

    monkeypatch.setattr(sw, "_check_platform", fake_check_platform)
    monkeypatch.setattr(sw, "_check_platform_with_retry", fake_check_with_retry)

    # Capture stdlib logging output from nexusosint.sherlock
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    sherlock_logger = logging.getLogger("nexusosint.sherlock")
    original_level = sherlock_logger.level
    sherlock_logger.addHandler(handler)
    sherlock_logger.setLevel(logging.DEBUG)

    try:
        req = SearchRequest(query=test_username, mode="manual", modules=["sherlock"])
        asyncio.get_event_loop().run_until_complete(_collect_sse(req))
        log_output = log_capture.getvalue()
    finally:
        sherlock_logger.removeHandler(handler)
        sherlock_logger.setLevel(original_level)

    assert "username_hash=" in log_output, (
        f"Expected 'username_hash=' in sherlock log. Got: {log_output[:500]}"
    )
    assert test_username not in log_output, (
        f"Plaintext username '{test_username}' leaked into sherlock log. Got: {log_output[:500]}"
    )


# ── Test 8: Serialization tightness ──────────────────────────────────────────


def test_platform_result_serialization_exact_keys(monkeypatch):
    """Test 8: found and likely items have EXACTLY the 6 allowed keys.

    Allowed: {platform, url, category, icon, state, confidence}
    Forbidden: found, error, negative_markers, or any internal field.
    D-H2: internal scoring signals must not leak to client.
    """
    import modules.sherlock_wrapper as sw

    stub = build_sherlock_stub(found_count=2, likely_count=2)
    monkeypatch.setattr(sw, "search_username", AsyncMock(return_value=stub))

    req = SearchRequest(query="alice42", mode="manual", modules=["sherlock"])
    events = asyncio.get_event_loop().run_until_complete(_collect_sse(req))

    sherlock_event = next(
        (e for e in events if e.get("type") == "sherlock"),
        None,
    )
    assert sherlock_event is not None, f"No sherlock event: {events}"

    allowed_keys = {"platform", "url", "category", "icon", "state", "confidence"}
    all_items = sherlock_event.get("found", []) + sherlock_event.get("likely", [])
    assert len(all_items) == 4, f"Expected 4 total items (2+2), got {len(all_items)}"

    for item in all_items:
        item_keys = set(item.keys())
        extra = item_keys - allowed_keys
        missing = allowed_keys - item_keys
        assert not extra, (
            f"Platform item contains forbidden extra keys: {extra} -- item: {item}"
        )
        assert not missing, (
            f"Platform item missing required keys: {missing} -- item: {item}"
        )
