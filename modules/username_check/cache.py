"""Redis-backed cache and metrics for username validation v2."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Any

from api.cache import cache_backend
from api.config import CACHE_TTL_SECONDS

VALIDATOR_VERSION = "username-validation-v2-fase-h-1"
USERNAME_CACHE_ENDPOINT = "username_check"


@dataclass(frozen=True)
class UsernameValidationMetrics:
    username_searches_total: int
    username_cache_hits: int
    username_cache_misses: int
    baseline_cache_hits: int
    validation_v2_total: int
    validation_v2_pct: float
    maigret_sites_loaded: int
    confirmed_per_search_avg: float


_lock = Lock()
_username_searches_total = 0
_username_cache_hits = 0
_username_cache_misses = 0
_baseline_cache_hits = 0
_validation_v2_total = 0
_confirmed_total = 0


def username_cache_key(username: str) -> str:
    normalized = username.strip().lstrip("@").casefold()
    return sha256(f"{normalized}|{VALIDATOR_VERSION}".encode("utf-8")).hexdigest()


async def get_cached_username_result(username: str) -> dict[str, Any] | None:
    payload = await cache_backend.get(USERNAME_CACHE_ENDPOINT, username_cache_key(username))
    with _lock:
        global _username_cache_hits, _username_cache_misses
        if payload is None:
            _username_cache_misses += 1
        else:
            _username_cache_hits += 1
    return payload if isinstance(payload, dict) else None


async def set_cached_username_result(username: str, payload: dict[str, Any]) -> None:
    await cache_backend.set(
        USERNAME_CACHE_ENDPOINT,
        username_cache_key(username),
        payload,
        ttl=CACHE_TTL_SECONDS,
    )


def record_username_validation(payload: dict[str, Any], *, cache_hit: bool) -> None:
    platforms = payload.get("platforms", [])
    if not isinstance(platforms, list):
        platforms = []
    baseline_hits = sum(
        1
        for item in platforms
        if isinstance(item, dict) and "baseline_cache_hit" in (item.get("warnings") or [])
    )
    confirmed = int(payload.get("found_count") or 0)
    with _lock:
        global _username_searches_total, _baseline_cache_hits, _validation_v2_total, _confirmed_total
        _username_searches_total += 1
        _validation_v2_total += 1
        _baseline_cache_hits += baseline_hits
        _confirmed_total += confirmed


def username_validation_metrics(*, maigret_sites_loaded: int = 0) -> UsernameValidationMetrics:
    with _lock:
        total = _username_searches_total
        v2_total = _validation_v2_total
        confirmed_total = _confirmed_total
        cache_hits = _username_cache_hits
        cache_misses = _username_cache_misses
        baseline_hits = _baseline_cache_hits
    return UsernameValidationMetrics(
        username_searches_total=total,
        username_cache_hits=cache_hits,
        username_cache_misses=cache_misses,
        baseline_cache_hits=baseline_hits,
        validation_v2_total=v2_total,
        validation_v2_pct=round((v2_total / total * 100.0), 1) if total else 0.0,
        maigret_sites_loaded=maigret_sites_loaded,
        confirmed_per_search_avg=round((confirmed_total / total), 2) if total else 0.0,
    )
