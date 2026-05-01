"""
tests/unit/test_sherlock_wrapper.py
=====================================
Unit tests for Phase 16 sherlock_wrapper.py changes:

Task 1 (tests 1-10): confidence scoring, dataclass extensions, negative_markers,
    body-cap streaming, bug fixes.
Task 2 (tests 11-20): Thordata proxy injection, sticky session, retry logic,
    audit log, budget accounting.

Uses respx to mock httpx; monkeypatch for env-driven constants.
No real network calls. No loguru (stdlib logging only).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

import api.budget as _budget
import modules.sherlock_wrapper as sw
from modules.sherlock_wrapper import (
    PLATFORMS,
    PlatformResult,
    SherlockResult,
    _build_rotate_url,
    _build_sticky_url,
    _check_platform,
    _check_platform_with_retry,
    _compute_confidence,
    _fetch_with_cap,
    _masked_proxy_log,
    search_username,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_platform(
    claim_type: str = "status_code",
    claim_value: int | str = 200,
    negative_markers: list[str] | None = None,
) -> dict:
    return {
        "name": "TestPlatform",
        "url": "https://example.com/{username}",
        "claim_type": claim_type,
        "claim_value": claim_value,
        "category": "Test",
        "icon": "🧪",
        "negative_markers": negative_markers if negative_markers is not None else [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 1 TESTS — confidence scoring, dataclasses, negative_markers, body cap
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeConfidence:

    def test_1_negative_marker_short_circuits_to_not_found(self):
        """Negative marker present -> (0, 'not_found') regardless of status match."""
        platform = _make_platform(
            claim_type="status_code",
            claim_value=200,
            negative_markers=["page not found"],
        )
        score, state = _compute_confidence(
            resp_status=200,
            resp_body="Page not found — this user does not exist",
            resp_body_bytes=5000,
            platform=platform,
        )
        assert score == 0
        assert state == "not_found"

    def test_2_status_match_plus_size_gives_likely(self):
        """status=200 + status_code claim + body 5KB -> score 60, state='likely'."""
        platform = _make_platform(claim_type="status_code", claim_value=200)
        # score = 40 (status) + 20 (size) = 60 -> likely (threshold 70)
        score, state = _compute_confidence(
            resp_status=200,
            resp_body="some user profile content here username",
            resp_body_bytes=5000,
            platform=platform,
        )
        assert score == 60
        assert state == "likely"

    def test_3_full_text_present_plus_status_plus_size_gives_confirmed(self):
        """text_present hit + status 200 + 5KB -> score 100, state='confirmed'."""
        platform = _make_platform(
            claim_type="text_present",
            claim_value="profile_identifier",
        )
        score, state = _compute_confidence(
            resp_status=200,
            resp_body="welcome to your profile_identifier page",
            resp_body_bytes=5000,
            platform=platform,
        )
        assert score == 100
        assert state == "confirmed"

    def test_4_text_absent_positive_scores_text_signal(self):
        """text_absent: claim_value NOT in body -> +40 text signal."""
        platform = _make_platform(
            claim_type="text_absent",
            claim_value="this account doesn't exist",
        )
        score, state = _compute_confidence(
            resp_status=200,
            resp_body="welcome to the profile page of the user",
            resp_body_bytes=5000,
            platform=platform,
        )
        # +40 status (200) + +40 text (absent matches) + +20 size = 100
        assert score == 100
        assert state == "confirmed"

    def test_5_size_gate_under_3kb_no_size_points(self):
        """body_bytes < 3072 -> no +20 size bonus."""
        platform = _make_platform(claim_type="status_code", claim_value=200)
        score, state = _compute_confidence(
            resp_status=200,
            resp_body="short body",
            resp_body_bytes=2000,  # under 3KB
            platform=platform,
        )
        # +40 status only (no size bonus)
        assert score == 40
        assert state == "likely"

    def test_6_confirmed_threshold_custom_via_monkeypatch(self, monkeypatch):
        """With CONFIRMED_THRESHOLD=80, score=60 returns state='likely' not 'confirmed'."""
        monkeypatch.setattr(sw, "SHERLOCK_CONFIRMED_THRESHOLD", 80)
        platform = _make_platform(claim_type="status_code", claim_value=200)
        # score = 40 (status) + 20 (size) = 60 -> below threshold 80 -> likely
        score, state = _compute_confidence(
            resp_status=200,
            resp_body="some user profile content here and more text",
            resp_body_bytes=5000,
            platform=platform,
        )
        assert score == 60
        assert state == "likely"

    @pytest.mark.asyncio
    @respx.mock
    async def test_7_timeout_exception_returns_error_not_propagated(self):
        """httpx.TimeoutException in _check_platform -> PlatformResult.error='timeout'."""
        platform = _make_platform()
        respx.get("https://example.com/testuser").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        async with httpx.AsyncClient() as client:
            result = await _check_platform(
                client, "testuser", platform, {"bytes": 0}
            )
        assert result.error == "timeout"
        assert result.state == "not_found"
        assert result.found is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_8_body_cap_real_256kb(self):
        """_fetch_with_cap returns at most 256KB even when server sends 5MB."""
        large_body = b"X" * (5 * 1024 * 1024)  # 5MB
        respx.get("https://example.com/testuser").mock(
            return_value=httpx.Response(200, content=large_body)
        )
        async with httpx.AsyncClient() as client:
            status, headers, body, bytes_read = await _fetch_with_cap(
                client,
                "https://example.com/testuser",
                cap_bytes=sw._SHERLOCK_BODY_CAP,  # 256KB
            )
        # Must not exceed 256KB + one chunk (8192 bytes)
        assert bytes_read <= sw._SHERLOCK_BODY_CAP + 8192
        assert len(body) <= sw._SHERLOCK_BODY_CAP + 8192
        # Critical: must be MUCH less than 5MB
        assert bytes_read < 1_000_000

    @pytest.mark.asyncio
    @respx.mock
    async def test_9_cf_mitigated_challenge_detection(self):
        """cf-mitigated:challenge header -> error='cf_challenge', confidence=0, state='not_found'."""
        platform = _make_platform(
            claim_type="text_absent",
            claim_value="account doesn't exist",
        )
        # Mock: 200 status + cf-mitigated header + a body that would otherwise score positively
        respx.get("https://example.com/testuser").mock(
            return_value=httpx.Response(
                200,
                headers={"cf-mitigated": "challenge"},
                content=b"Some user profile content here " * 200,
            )
        )
        async with httpx.AsyncClient() as client:
            result = await _check_platform(
                client, "testuser", platform, {"bytes": 0}
            )
        assert result.error == "cf_challenge"
        assert result.confidence == 0
        assert result.state == "not_found"
        assert result.found is False

    def test_10_all_25_platforms_have_negative_markers_key(self):
        """Every PLATFORMS entry has 'negative_markers' key (list, backward compat)."""
        assert len(PLATFORMS) == 25, f"Expected 25 platforms, got {len(PLATFORMS)}"
        for p in PLATFORMS:
            assert "negative_markers" in p, f"Platform '{p['name']}' missing negative_markers"
            assert isinstance(p["negative_markers"], list), (
                f"Platform '{p['name']}' negative_markers must be list"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 2 TESTS — Thordata proxy, sticky session, retry, audit log, budget
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildStickyUrl:

    def test_11_sticky_url_username_starts_with_sessid_suffix(self):
        """_build_sticky_url injects sessid + sesstime-2 into proxy username."""
        import urllib.parse
        base = "http://td-customer-TESTUSER:TESTPASS@t.pr.thordata.net:9999"
        result = _build_sticky_url(base, "abc123")
        parsed = urllib.parse.urlparse(result)
        assert "sessid-abc123-sesstime-2" in parsed.username
        assert "sesstime-2" in parsed.username
        assert "abc123" in parsed.username

    def test_12_rotate_url_differs_from_sticky(self):
        """_build_rotate_url produces different sessid than _build_sticky_url."""
        import urllib.parse
        base = "http://td-customer-USER:PASS@t.pr.thordata.net:9999"
        sticky = _build_sticky_url(base, "mysessid")
        rotate = _build_rotate_url(base, "mysessid")
        # Rotate appends 'r' -> different username component
        assert sticky != rotate
        sticky_user = urllib.parse.urlparse(sticky).username
        rotate_user = urllib.parse.urlparse(rotate).username
        assert sticky_user != rotate_user

    def test_13_masked_proxy_log_hides_credentials(self):
        """_masked_proxy_log returns 'host:port' only — no user, no password."""
        result = _masked_proxy_log("http://u:p@host.example.com:9999")
        assert result == "host.example.com:9999"
        assert "u:p" not in result
        assert ":p@" not in result

    @pytest.mark.asyncio
    @respx.mock
    async def test_14_proxy_retry_on_proxy_error_succeeds_second_attempt(self):
        """First request raises ProxyError, second (rotate) succeeds -> confirmed result."""
        platform = {
            "name": "TestPlatform",
            "url": "https://example.com/{username}",
            "claim_type": "text_present",
            "claim_value": "profile_data",
            "category": "Test",
            "icon": "🧪",
            "negative_markers": [],
        }

        call_count = {"n": 0}

        async def side_effect_first_then_ok(request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise httpx.ProxyError("proxy fail")
            # Second call succeeds with large body containing claim_value
            return httpx.Response(200, content=b"profile_data " * 400)

        respx.get("https://example.com/testuser").mock(side_effect=side_effect_first_then_ok)

        per_counter: dict = {"bytes": 0}
        async with httpx.AsyncClient() as primary, httpx.AsyncClient() as rotate:
            result = await _check_platform_with_retry(
                primary, rotate, "testuser", platform, per_counter
            )

        assert result.error is None
        assert result.state == "confirmed"
        assert result.found is True
        assert call_count["n"] == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_15_proxy_fails_twice_returns_proxy_unavailable(self):
        """Both attempts raise ProxyError -> error='proxy_unavailable', state='not_found'."""
        platform = _make_platform()
        respx.get("https://example.com/testuser").mock(
            side_effect=httpx.ProxyError("proxy fail")
        )
        per_counter: dict = {"bytes": 0}
        async with httpx.AsyncClient() as primary, httpx.AsyncClient() as rotate:
            result = await _check_platform_with_retry(
                primary, rotate, "testuser", platform, per_counter
            )
        assert result.error == "proxy_unavailable"
        assert result.state == "not_found"
        assert result.found is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_16_no_proxy_when_thordata_url_is_none(self, monkeypatch):
        """When THORDATA_PROXY_URL=None, search runs without proxy, proxy_used=False."""
        monkeypatch.setattr(sw, "THORDATA_PROXY_URL", None)
        monkeypatch.setattr(_budget, "_proxy_active", False)

        # Mock all platform URLs to return 404 quickly
        respx.get(url__regex=r"https?://.*").mock(
            return_value=httpx.Response(404, content=b"not found")
        )

        result = await search_username("testnoprxyuser")
        assert result.proxy_used is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_17_proxy_used_when_thordata_url_set_and_active(self, monkeypatch):
        """When THORDATA_PROXY_URL is set and _proxy_active=True, proxy_used=True."""
        fake_proxy = "http://td-customer-TEST:PASS@t.pr.thordata.net:9999"
        monkeypatch.setattr(sw, "THORDATA_PROXY_URL", fake_proxy)
        monkeypatch.setattr(_budget, "_proxy_active", True)

        respx.get(url__regex=r"https?://.*").mock(
            return_value=httpx.Response(404, content=b"not found")
        )

        result = await search_username("testproxyuser")
        assert result.proxy_used is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_18_budget_record_usage_called_after_search(self, monkeypatch):
        """After search_username, _budget.record_usage called at least once."""
        monkeypatch.setattr(sw, "THORDATA_PROXY_URL", None)
        monkeypatch.setattr(_budget, "_proxy_active", False)

        call_log: list[int] = []

        def fake_record_usage(bytes_used: int) -> None:
            call_log.append(bytes_used)

        monkeypatch.setattr(_budget, "record_usage", fake_record_usage)

        respx.get(url__regex=r"https?://.*").mock(
            return_value=httpx.Response(200, content=b"profile content " * 300)
        )

        await search_username("testbudgetuser")
        assert len(call_log) >= 1
        # Total bytes must be non-negative
        assert call_log[0] >= 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_19_audit_log_contains_hash_not_plaintext_username(
        self, monkeypatch, caplog
    ):
        """Audit log contains username_hash and NOT the plaintext username."""
        monkeypatch.setattr(sw, "THORDATA_PROXY_URL", None)
        monkeypatch.setattr(_budget, "_proxy_active", False)

        test_username = "superprivateuser99"
        expected_hash = hashlib.sha256(test_username.encode()).hexdigest()[:8]

        respx.get(url__regex=r"https?://.*").mock(
            return_value=httpx.Response(404, content=b"not found")
        )

        with caplog.at_level(logging.INFO, logger="nexusosint.sherlock"):
            await search_username(test_username)

        log_text = " ".join(caplog.messages)
        # Hash must be present
        assert expected_hash in log_text, (
            f"Expected username_hash={expected_hash!r} in log, got: {log_text!r}"
        )
        # Plaintext must NOT be present
        assert test_username not in log_text, (
            f"Plaintext username must not appear in logs. Found in: {log_text!r}"
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_20_per_search_byte_cap_log_when_exceeded(
        self, monkeypatch, caplog
    ):
        """When per-search bytes exceed cap, INFO log contains 'Per-search byte cap'."""
        monkeypatch.setattr(sw, "THORDATA_PROXY_URL", None)
        monkeypatch.setattr(_budget, "_proxy_active", False)
        # Set per-search cap very low (100 bytes) so any real response exceeds it
        monkeypatch.setattr(sw, "THORDATA_PER_SEARCH_CAP_BYTES", 100)

        # Each platform returns a meaningful response
        respx.get(url__regex=r"https?://.*").mock(
            return_value=httpx.Response(200, content=b"X" * 500)
        )

        with caplog.at_level(logging.INFO, logger="nexusosint.sherlock"):
            await search_username("testcapuser")

        log_text = " ".join(caplog.messages)
        assert "Per-search byte cap" in log_text, (
            f"Expected 'Per-search byte cap' in log, got: {log_text!r}"
        )
