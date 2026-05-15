"""Negative baseline fetch/cache for username validation."""
from __future__ import annotations

import hashlib
import time
import urllib.parse
from collections import OrderedDict
from dataclasses import dataclass, replace

import httpx

from modules.username_check.fetcher import FetchResult, _fetch_with_cap
from modules.username_check.rate_limit import _outbound_limiter

_CACHE_TTL_SECONDS = 3600
_MAX_CACHE_ENTRIES = 128


@dataclass(frozen=True)
class BaselineResult:
    fetch_result: FetchResult | None
    fake_username: str
    cache_hit: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.fetch_result is not None and self.error is None


_baseline_cache: OrderedDict[tuple[str, int], tuple[float, BaselineResult]] = OrderedDict()


def _hour_bucket(now: float | None = None) -> int:
    timestamp = time.time() if now is None else now
    return int(timestamp // _CACHE_TTL_SECONDS)


def make_fake_username(platform: dict, hour_bucket: int | None = None) -> str:
    bucket = _hour_bucket() if hour_bucket is None else hour_bucket
    platform_name = str(platform.get("name", "unknown")).lower()
    digest = hashlib.sha256(f"{platform_name}:{bucket}".encode()).hexdigest()[:10]
    return f"nexus_absent_{digest}"


def _cache_key(platform: dict, hour_bucket: int | None = None) -> tuple[str, int]:
    bucket = _hour_bucket() if hour_bucket is None else hour_bucket
    return str(platform.get("name", "unknown")), bucket


def clear_baseline_cache() -> None:
    _baseline_cache.clear()


def _remember(key: tuple[str, int], result: BaselineResult) -> BaselineResult:
    expires_at = time.time() + _CACHE_TTL_SECONDS
    _baseline_cache[key] = (expires_at, result)
    _baseline_cache.move_to_end(key)
    while len(_baseline_cache) > _MAX_CACHE_ENTRIES:
        _baseline_cache.popitem(last=False)
    return result


async def get_baseline(
    client: httpx.AsyncClient,
    platform: dict,
    *,
    cap_bytes: int,
) -> BaselineResult:
    key = _cache_key(platform)
    cached = _baseline_cache.get(key)
    if cached is not None:
        expires_at, cached_result = cached
        if expires_at > time.time():
            _baseline_cache.move_to_end(key)
            return replace(cached_result, cache_hit=True)
        _baseline_cache.pop(key, None)

    fake_username = make_fake_username(platform, key[1])
    url = str(platform["url"]).format(username=fake_username)
    domain = urllib.parse.urlparse(url).hostname or ""
    await _outbound_limiter.acquire(domain)

    try:
        fetch_result = await _fetch_with_cap(client, url, cap_bytes=cap_bytes)
    except httpx.TimeoutException:
        return BaselineResult(None, fake_username, error="timeout")
    except httpx.ProxyError:
        return BaselineResult(None, fake_username, error="proxy_error")
    except httpx.ConnectError:
        return BaselineResult(None, fake_username, error="connection_error")
    except httpx.HTTPError as exc:
        return BaselineResult(None, fake_username, error=type(exc).__name__)

    return _remember(
        key,
        BaselineResult(
            fetch_result=fetch_result,
            fake_username=fake_username,
        ),
    )
