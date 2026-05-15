"""Username search public API."""
from __future__ import annotations

from modules.username_check.runner import (
    HEADERS,
    PLATFORMS,
    CONNECT_TIMEOUT,
    OutboundRateLimiter,
    PlatformResult,
    SherlockResult,
    THORDATA_PER_SEARCH_CAP_BYTES,
    THORDATA_PROXY_URL,
    _SHERLOCK_BODY_CAP,
    _build_client_kwargs,
    _build_rotate_url,
    _build_sticky_url,
    _check_platform,
    _check_platform_with_retry,
    _compute_confidence,
    _fetch_with_cap,
    _masked_proxy_log,
    search_username,
)
from modules.username_check.fetcher import FetchResult

__all__ = [
    "HEADERS",
    "PLATFORMS",
    "CONNECT_TIMEOUT",
    "OutboundRateLimiter",
    "PlatformResult",
    "SherlockResult",
    "THORDATA_PER_SEARCH_CAP_BYTES",
    "THORDATA_PROXY_URL",
    "_SHERLOCK_BODY_CAP",
    "_build_client_kwargs",
    "_build_rotate_url",
    "_build_sticky_url",
    "_check_platform",
    "_check_platform_with_retry",
    "_compute_confidence",
    "_fetch_with_cap",
    "_masked_proxy_log",
    "search_username",
    "FetchResult",
]
