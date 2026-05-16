"""
NexusOSINT â€” Sherlock Wrapper
Checks username presence across 25 social platforms.
Strategy: async HTTP GET checks with per-site claim detection + multi-signal
confidence scoring. Falls back to subprocess Sherlock if installed.

Phase 16 changes:
- Thordata residential proxy with sticky session + 1x rotate retry (D-01..D-07)
- Multi-signal confidence scoring 0-100, 3-state classifier (D-08..D-12)
- Real 256KB body cap via httpx streaming (Pitfall 4 fix)
- asyncio.TimeoutError -> httpx.TimeoutException bug fix (Pitfall 1)
- Cloudflare cf-mitigated:challenge detection (Pitfall 5)
- Per-search budget accounting + SHA256-truncated audit log (D-H13)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import secrets
import subprocess
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

import random

import httpx

from api.config import (
    MAIGRET_ENABLED,
    MAIGRET_TOP_N,
    SHERLOCK_CONFIRMED_THRESHOLD,
    SHERLOCK_LIKELY_THRESHOLD,
    THORDATA_PER_SEARCH_CAP_BYTES,
    THORDATA_PROXY_URL,
    USERNAME_CHECK_BASELINE_ENABLED,
)
import modules.username_check.budget as _budget
from modules.username_check.baseline import get_baseline
from modules.username_check.fetcher import FetchResult
from modules.username_check.scoring import ScoredResult, combine_outcomes
from modules.username_check.sources.maigret_db import load_top_n_sites

logger = logging.getLogger("nexusosint.sherlock")

# â”€â”€ Scoring constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_SCORE_STATUS = 40
_SCORE_TEXT = 40
_SCORE_SIZE = 20
_MIN_BODY_BYTES = 3_072       # 3KB sanity threshold (D-08)

from modules.username_check.fetcher import _SHERLOCK_BODY_CAP, _fetch_with_cap
from modules.username_check.proxy import (
    _build_rotate_url,
    _build_sticky_url,
    _masked_proxy_log,
)
from modules.username_check.rate_limit import OutboundRateLimiter, _outbound_limiter
from modules.username_check.validators import (
    BaselineCompareValidator,
    BaselineValidationContext,
    ValidationContext,
    ValidationOutcome,
    validate_all,
)

# â”€â”€ Platform definitions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Each entry: name, url_template, claim_type, claim_value, category, icon,
#             negative_markers (Phase 16 â€” empty list = backward compat)
# claim_type: "status_code" | "text_present" | "text_absent"

from modules.username_check.sources.sherlock_curated import PLATFORMS

_MAX_PLATFORM_CONCURRENCY = 10

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _get_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(_UA_POOL),
        "Accept-Language": "en-US,en;q=0.9",
    }


# Backward-compat alias used by tests and callers that expect a module-level dict.
HEADERS = _get_headers()

CONNECT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _canonical_domain(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or ""
    return host.removeprefix("www.").lower()


def _candidate_platforms() -> list[dict]:
    candidates = list(PLATFORMS)
    if not MAIGRET_ENABLED:
        return candidates

    seen_domains = {
        _canonical_domain(str(platform.get("url", "")))
        for platform in candidates
    }
    for platform in load_top_n_sites(MAIGRET_TOP_N):
        domain = _canonical_domain(str(platform.get("url", "")))
        if not domain or domain in seen_domains:
            continue
        candidates.append(platform)
        seen_domains.add(domain)
    return candidates


# â”€â”€ Result models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class PlatformResult:
    platform: str = ""
    url: str = ""
    source: str = "sherlock"
    found: bool = False           # True iff state != "not_found" (backward compat)
    category: str = ""
    icon: str = ""
    confidence: int = 0           # 0-100 score (Phase 16)
    state: str = "not_found"      # "confirmed" | "likely" | "not_found" (Phase 16)
    error: Optional[str] = None   # "timeout" | "connection_error" | "http_NNN"
                                  # | "proxy_unavailable" | "cf_challenge"
    reliability: str = "normal"   # "normal" | "low" â€” low = SPA/bot-wall, results unreliable
    _outcomes: list[ValidationOutcome] = field(default_factory=list, repr=False)
    _fetch_result: FetchResult | None = field(default=None, repr=False)
    _v2_score: ScoredResult | None = field(default=None, repr=False)


@dataclass
class SherlockResult:
    username: str = ""
    success: bool = False
    found: list[PlatformResult] = field(default_factory=list)       # confirmed only
    likely: list[PlatformResult] = field(default_factory=list)      # likely state (Phase 16)
    not_found: list[PlatformResult] = field(default_factory=list)
    errors: list[PlatformResult] = field(default_factory=list)
    error: str = ""
    source: str = "internal"    # "internal" | "sherlock_cli"
    proxy_used: bool = False    # for D-H13 audit log (Phase 16)

    @property
    def found_count(self) -> int:
        return len(self.found)

    @property
    def total_checked(self) -> int:
        return len(self.found) + len(self.likely) + len(self.not_found) + len(self.errors)

    @property
    def risk_score(self) -> int:
        """Simple risk contribution from social presence."""
        return min(self.found_count * 4, 60)


# â”€â”€ Proxy URL helpers (D-H5, D-03, Pitfall 2) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# â”€â”€ Confidence scoring (D-08..D-12) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _compute_confidence(
    resp_status: int,
    resp_body: str,
    resp_body_bytes: int,
    platform: dict,
) -> tuple[int, str]:
    """
    Returns (confidence_score 0-100, state 'confirmed'|'likely'|'not_found').
    Negative markers short-circuit to (0, 'not_found').
    Backend-only â€” never expose raw signal scores to frontend (D-H2).
    """
    body_lower = resp_body.lower()

    # Short-circuit: negative marker present -> not_found regardless of claim
    for marker in platform.get("negative_markers", []):
        if marker.lower() in body_lower:
            return 0, "not_found"

    score = 0
    claim_type = platform["claim_type"]
    claim_value = platform["claim_value"]

    # Signal 1: status_code match (+40)
    if claim_type == "status_code":
        if resp_status == int(claim_value):
            score += _SCORE_STATUS
    else:
        if resp_status == 200:
            score += _SCORE_STATUS

    # Signal 2: text marker match (+40)
    if claim_type == "text_present":
        if str(claim_value).lower() in body_lower:
            score += _SCORE_TEXT
    elif claim_type == "text_absent":
        if str(claim_value).lower() not in body_lower:
            score += _SCORE_TEXT

    # Signal 3: size sanity (+20)
    if resp_body_bytes >= _MIN_BODY_BYTES:
        score += _SCORE_SIZE

    score = min(score, 100)

    if score >= SHERLOCK_CONFIRMED_THRESHOLD:
        state = "confirmed"
    elif score >= SHERLOCK_LIKELY_THRESHOLD:
        state = "likely"
    else:
        state = "not_found"

    return score, state


# â”€â”€ Per-platform async check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _check_platform(
    client: httpx.AsyncClient,
    username: str,
    platform: dict,
    per_search_counter: dict,
) -> PlatformResult:
    """
    Check one platform. Re-raises httpx.ProxyError so caller can retry.
    Named exceptions only; generic catches are prohibited by CLAUDE.md.
    """
    url = platform["url"].format(username=username)
    result = PlatformResult(
        platform=platform["name"],
        url=url,
        source=platform.get("source", "sherlock"),
        category=platform.get("category", ""),
        icon=platform.get("icon", ""),
        reliability=platform.get("reliability", "normal"),
    )

    # Per-domain outbound rate limit (CLAUDE.md mandate + D-04)
    domain = urllib.parse.urlparse(url).hostname or ""
    await _outbound_limiter.acquire(domain)

    try:
        fetch_result = await _fetch_with_cap(client, url)
    except httpx.ProxyError:
        # MUST come first â€” re-raise so caller can retry with rotated sessid (D-06)
        raise
    except httpx.TimeoutException:
        # Pitfall 1 fix: existing code incorrectly caught asyncio.TimeoutError (dead code)
        result.error = "timeout"
        result._v2_score = combine_outcomes([], fetch_error="timeout")
        return result
    except httpx.ConnectError:
        result.error = "connection_error"
        result._v2_score = combine_outcomes([], fetch_error="connection_error")
        return result
    except httpx.HTTPStatusError as exc:
        result.error = f"http_{exc.response.status_code}"
        result._v2_score = combine_outcomes([], fetch_error=result.error)
        return result
    except httpx.HTTPError as exc:
        result.error = str(exc)[:80]
        result._v2_score = combine_outcomes([], fetch_error=type(exc).__name__)
        return result
    # No generic catch here; named httpx failures only (CLAUDE.md).

    # Account bytes consumed (shared counter â€” Pitfall 7)
    per_search_counter["bytes"] = per_search_counter.get("bytes", 0) + fetch_result.bytes_read
    result._fetch_result = fetch_result

    # Cloudflare challenge detection (Pitfall 5)
    if fetch_result.headers.get("cf-mitigated") == "challenge":
        result.error = "cf_challenge"
        result.confidence = 0
        result.state = "not_found"
        result.found = False
        result._v2_score = combine_outcomes([], fetch_error="cf_challenge")
        return result

    body_text = fetch_result.body.decode("utf-8", errors="replace")
    validation_ctx = ValidationContext(
        username=username,
        platform=platform,
        fetch_result=fetch_result,
        body_text=body_text,
        original_url=url,
    )
    result._outcomes = validate_all(validation_ctx)
    if USERNAME_CHECK_BASELINE_ENABLED:
        baseline = await get_baseline(
            client,
            platform,
            cap_bytes=_SHERLOCK_BODY_CAP,
        )
        result._outcomes.append(
            BaselineCompareValidator().validate(
                BaselineValidationContext(
                    validation=validation_ctx,
                    baseline=baseline,
                )
            )
        )
    result._v2_score = combine_outcomes(
        result._outcomes,
        reliability=result.reliability,
    )
    confidence, state = _compute_confidence(
        fetch_result.status_code,
        body_text,
        fetch_result.bytes_read,
        platform,
    )
    result.confidence = confidence
    result.state = state
    result.found = state != "not_found"
    return result


# â”€â”€ Proxy retry wrapper (D-06) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _check_platform_with_retry(
    primary_client: httpx.AsyncClient,
    rotate_client: httpx.AsyncClient,
    username: str,
    platform: dict,
    per_search_counter: dict,
) -> PlatformResult:
    """
    D-06: try primary sticky-session client; on ProxyError retry once with
    rotate_client (different sessid = forced IP rotation). On second ProxyError
    -> proxy_unavailable error result.
    """
    try:
        return await _check_platform(primary_client, username, platform, per_search_counter)
    except httpx.ProxyError:
        logger.warning(
            "Proxy error on platform=%s, retrying with IP rotation",
            platform["name"],
        )
        try:
            return await _check_platform(rotate_client, username, platform, per_search_counter)
        except httpx.ProxyError:
            failed = PlatformResult(
                platform=platform["name"],
                url=platform["url"].format(username=username),
                source=platform.get("source", "sherlock"),
                category=platform.get("category", ""),
                icon=platform.get("icon", ""),
                error="proxy_unavailable",
                state="not_found",
                confidence=0,
                found=False,
            )
            failed._v2_score = combine_outcomes([], fetch_error="proxy_unavailable")
            return failed


# â”€â”€ Sherlock CLI integration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _try_sherlock_cli(username: str) -> Optional[SherlockResult]:
    """Attempt to run the official Sherlock CLI if it's on PATH."""
    try:
        proc = subprocess.run(
            ["sherlock", username, "--print-found", "--no-color", "--timeout", "10"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode not in (0, 1):
            return None

        found: list[PlatformResult] = []
        url_pattern = re.compile(r"\[+\] (https?://\S+)")
        for line in proc.stdout.splitlines():
            m = url_pattern.search(line)
            if m:
                url = m.group(1)
                name = url.split("/")[2].replace("www.", "").split(".")[0].capitalize()
                found.append(
                    PlatformResult(
                        platform=name,
                        url=url,
                        found=True,
                        state="confirmed",
                        confidence=70,
                        category="Social",
                    )
                )

        result = SherlockResult(
            username=username,
            success=True,
            found=found,
            source="sherlock_cli",
        )
        return result
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
        return None


# â”€â”€ httpx client builder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _build_client_kwargs(proxy_url: str | None) -> dict:
    """Build httpx.AsyncClient kwargs with optional Thordata sticky-session proxy."""
    base: dict = {
        "headers": _get_headers(),
        "timeout": CONNECT_TIMEOUT,
        "follow_redirects": True,
    }
    if proxy_url:
        base["proxy"] = proxy_url  # singular 'proxy=' (httpx 0.27.x; 'proxies=' deprecated)
        base["limits"] = httpx.Limits(max_connections=8, max_keepalive_connections=5)
    else:
        base["limits"] = httpx.Limits(max_connections=15, max_keepalive_connections=10)
    return base


# â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def search_username(
    username: str,
    prefer_cli: bool = False,
    timeout_per: int = 10,
) -> SherlockResult:
    """
    Main entry point (async). Public signature unchanged (timeout_per added, default safe).
    - If prefer_cli=True: tries Sherlock CLI first (via to_thread â€” subprocess is blocking).
      Falls back to internal async engine if CLI is not found OR returns 0 results.
    - Always runs internal async engine if CLI is unavailable/finds nothing.
    - Routes outbound traffic through Thordata when THORDATA_PROXY_URL is set
      and _budget._proxy_active is True (set by lifespan health check D-07).

    Caller is responsible for username validation (D-H8/D-H9 â€” Plan 03 routes layer).
    Pre-validated username accepted; never echoed in error messages.
    """
    username = username.strip().lstrip("@")

    if prefer_cli:
        # _try_sherlock_cli uses subprocess.run(timeout=120) â€” must run in thread
        cli_result = await asyncio.to_thread(_try_sherlock_cli, username)
        if cli_result and cli_result.found_count > 0:
            return cli_result

    # Generate per-search sticky session ID (D-02, D-03)
    search_id = secrets.token_hex(8)  # 16-char hex, alphanumeric-safe

    # Determine if proxy is active for this search
    use_proxy = bool(THORDATA_PROXY_URL and _budget._proxy_active)

    per_search_counter: dict = {"bytes": 0}
    candidates = _candidate_platforms()
    semaphore = asyncio.Semaphore(_MAX_PLATFORM_CONCURRENCY)

    if use_proxy:
        primary_url = _build_sticky_url(THORDATA_PROXY_URL, search_id)
        rotate_url = _build_rotate_url(THORDATA_PROXY_URL, search_id)
        primary_kwargs = _build_client_kwargs(primary_url)
        rotate_kwargs = _build_client_kwargs(rotate_url)

        async with httpx.AsyncClient(**primary_kwargs) as primary_client, \
                   httpx.AsyncClient(**rotate_kwargs) as rotate_client:

            async def run_with_limit(platform: dict) -> PlatformResult:
                async with semaphore:
                    return await _check_platform_with_retry(
                        primary_client,
                        rotate_client,
                        username,
                        platform,
                        per_search_counter,
                    )

            tasks = [
                run_with_limit(p)
                for p in candidates
            ]
            platform_results = await asyncio.gather(*tasks)
    else:
        direct_kwargs = _build_client_kwargs(None)
        async with httpx.AsyncClient(**direct_kwargs) as client:

            async def run_with_limit(platform: dict) -> PlatformResult:
                async with semaphore:
                    return await _check_platform(client, username, platform, per_search_counter)

            tasks = [
                run_with_limit(p)
                for p in candidates
            ]
            platform_results = await asyncio.gather(*tasks)

    # Post-gather: check per-search byte cap (D-17, Pitfall 7)
    if per_search_counter["bytes"] > THORDATA_PER_SEARCH_CAP_BYTES:
        logger.info(
            "Per-search byte cap reached: bytes_consumed=%d; partial result",
            per_search_counter["bytes"],
        )

    # Account bytes to daily budget (D-16)
    _budget.record_usage(per_search_counter["bytes"])

    # Route results into 3-state buckets
    result = SherlockResult(
        username=username,
        success=True,
        source="internal",
        proxy_used=use_proxy,
    )
    for pr in platform_results:
        if pr.error:
            result.errors.append(pr)
        elif pr.state == "confirmed":
            result.found.append(pr)
        elif pr.state == "likely":
            result.likely.append(pr)
        else:
            result.not_found.append(pr)

    # D-H13 audit log â€” SHA256 hash only, plaintext username NEVER logged
    username_hash = hashlib.sha256(username.encode()).hexdigest()[:8]
    logger.info(
        "Sherlock search complete | username_hash=%s bytes_consumed=%d proxy_used=%s "
        "confirmed=%d likely=%d not_found=%d errors=%d",
        username_hash,
        per_search_counter["bytes"],
        result.proxy_used,
        len(result.found),
        len(result.likely),
        len(result.not_found),
        len(result.errors),
    )

    return result




