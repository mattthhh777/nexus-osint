from __future__ import annotations

import httpx
import pytest
import respx

import modules.sherlock_wrapper as sw
from modules.sherlock_wrapper import _check_platform
from modules.username_check.baseline import (
    BaselineResult,
    clear_baseline_cache,
    get_baseline,
    make_fake_username,
)
from modules.username_check.fetcher import FetchResult
from modules.username_check.validators.base import ValidationContext
from modules.username_check.validators.baseline_compare import (
    BaselineCompareValidator,
    BaselineValidationContext,
    normalize_body,
)


def _platform() -> dict:
    return {
        "name": "Example",
        "url": "https://example.com/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Test",
        "icon": "",
        "negative_markers": [],
    }


def _fetch(body: str, *, status_code: int = 200) -> FetchResult:
    return FetchResult(
        status_code=status_code,
        headers={},
        body=body.encode(),
        bytes_read=len(body),
        final_url="https://example.com/alice",
        redirect_chain=[],
    )


def _validation_ctx(body: str, *, status_code: int = 200) -> ValidationContext:
    return ValidationContext(
        username="alice",
        platform=_platform(),
        fetch_result=_fetch(body, status_code=status_code),
        body_text=body,
        original_url="https://example.com/alice",
    )


def _baseline(body: str, *, status_code: int = 200, cache_hit: bool = False) -> BaselineResult:
    return BaselineResult(
        fetch_result=_fetch(body, status_code=status_code),
        fake_username="nexus_absent_test",
        cache_hit=cache_hit,
    )


def test_normalize_body_removes_volatile_tokens():
    left = 'csrf_token=abc timestamp=1711111111 data-id="123" /static/abcdef123456.js'
    right = 'csrf_token=xyz timestamp=1711112222 data-id="456" /static/99999999.js'
    assert normalize_body(left) == normalize_body(right)


def test_baseline_indistinguishable_is_hard_negative():
    outcome = BaselineCompareValidator().validate(
        BaselineValidationContext(
            validation=_validation_ctx("same profile shell"),
            baseline=_baseline("same profile shell"),
        )
    )
    signal = next(s for s in outcome.signals if s.name == "baseline_indistinguishable")
    assert signal.hard_negative is True


def test_baseline_different_is_positive_signal():
    outcome = BaselineCompareValidator().validate(
        BaselineValidationContext(
            validation=_validation_ctx("alice unique biography and repositories"),
            baseline=_baseline("generic not found shell"),
        )
    )
    signal = next(s for s in outcome.signals if s.name == "baseline_different")
    assert signal.weight == 20


def test_baseline_unavailable_is_warning():
    outcome = BaselineCompareValidator().validate(
        BaselineValidationContext(
            validation=_validation_ctx("alice"),
            baseline=BaselineResult(None, "fake", error="timeout"),
        )
    )
    assert outcome.warnings == ["baseline_unavailable:timeout"]


def test_baseline_cache_hit_warning():
    outcome = BaselineCompareValidator().validate(
        BaselineValidationContext(
            validation=_validation_ctx("same"),
            baseline=_baseline("same", cache_hit=True),
        )
    )
    assert "baseline_cache_hit" in outcome.warnings


@pytest.mark.asyncio
@respx.mock
async def test_get_baseline_cache_hit_second_lookup_within_hour():
    clear_baseline_cache()
    platform = _platform()
    fake = make_fake_username(platform)
    route = respx.get(f"https://example.com/{fake}").mock(
        return_value=httpx.Response(200, content=b"baseline")
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        first = await get_baseline(client, platform, cap_bytes=262_144)
        second = await get_baseline(client, platform, cap_bytes=262_144)

    assert first.ok is True
    assert first.cache_hit is False
    assert second.ok is True
    assert second.cache_hit is True
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_200_for_every_user_baseline_is_hard_negative():
    clear_baseline_cache()
    platform = _platform()
    fake = make_fake_username(platform)
    respx.get("https://example.com/alice").mock(
        return_value=httpx.Response(200, content=b"<title>Profile</title>" * 50)
    )
    respx.get(f"https://example.com/{fake}").mock(
        return_value=httpx.Response(200, content=b"<title>Profile</title>" * 50)
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        candidate = await _check_platform(client, "alice", platform, {"bytes": 0})
        baseline = await get_baseline(client, platform, cap_bytes=262_144)

    validation = next(out for out in candidate._outcomes if out.validator == "generic_content")
    assert validation.validator == "generic_content"
    outcome = BaselineCompareValidator().validate(
        BaselineValidationContext(
            validation=ValidationContext(
                username="alice",
                platform=platform,
                fetch_result=_fetch("<title>Profile</title>" * 50),
                body_text="<title>Profile</title>" * 50,
                original_url="https://example.com/alice",
            ),
            baseline=baseline,
        )
    )
    assert any(signal.hard_negative for signal in outcome.signals)


@pytest.mark.asyncio
@respx.mock
async def test_runner_baseline_fail_adds_warning_and_continues(monkeypatch):
    clear_baseline_cache()
    monkeypatch.setattr(sw, "USERNAME_CHECK_BASELINE_ENABLED", True)
    platform = _platform()
    fake = make_fake_username(platform)
    respx.get("https://example.com/alice").mock(
        return_value=httpx.Response(200, content=b"alice profile " * 400)
    )
    respx.get(f"https://example.com/{fake}").mock(
        side_effect=httpx.TimeoutException("baseline timeout")
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        result = await _check_platform(client, "alice", platform, {"bytes": 0})

    assert result.state == "likely"
    baseline_outcome = next(out for out in result._outcomes if out.validator == "baseline_compare")
    assert baseline_outcome.warnings == ["baseline_unavailable:timeout"]
