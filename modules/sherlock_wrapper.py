"""
NexusOSINT — Sherlock Wrapper
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
import sys
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import httpx

from api.config import (
    SHERLOCK_CONFIRMED_THRESHOLD,
    SHERLOCK_LIKELY_THRESHOLD,
    THORDATA_PER_SEARCH_CAP_BYTES,
    THORDATA_PROXY_URL,
)
import api.budget as _budget

logger = logging.getLogger("nexusosint.sherlock")

# ── Scoring constants ─────────────────────────────────────────────────────────
_SCORE_STATUS = 40
_SCORE_TEXT = 40
_SCORE_SIZE = 20
_MIN_BODY_BYTES = 3_072       # 3KB sanity threshold (D-08)
_SHERLOCK_BODY_CAP = 262_144  # 256KB per response (D-15)

# ── Sticky session ────────────────────────────────────────────────────────────
# NOTE: Thordata sesstime unit is MINUTES (Thordata docs, confirmed 2026-04-29).
# CONTEXT.md D-03 specifies "sesstime-60" intending 60 SECONDS. Implementing as
# sesstime-2 (2 minutes = 120 seconds) to match D-03's stated intent of covering
# full Sherlock search (~30s) plus 1x retry margin. See 16-RESEARCH.md Pitfall 2.
_STICKY_SESSTIME_MINUTES = 2


# ── OutboundRateLimiter (token bucket per domain) ─────────────────────────────
# Per CLAUDE.md "Rate limiting out" + D-04 (1 req/s per domain)

class OutboundRateLimiter:
    """Token bucket rate limiter — 1 semaphore + min-interval per domain."""

    def __init__(self, calls_per_second: float = 1.0):
        self._semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(1)
        )
        self._last_call: dict[str, datetime] = {}
        self._min_interval = timedelta(seconds=1.0 / calls_per_second)

    async def acquire(self, domain: str) -> None:
        async with self._semaphores[domain]:
            if domain in self._last_call:
                elapsed = datetime.now() - self._last_call[domain]
                if elapsed < self._min_interval:
                    await asyncio.sleep(
                        (self._min_interval - elapsed).total_seconds()
                    )
            self._last_call[domain] = datetime.now()


# Module-level singleton — shared across all concurrent searches (Open Q #5)
_outbound_limiter = OutboundRateLimiter(calls_per_second=1.0)  # D-04


# ── Platform definitions ──────────────────────────────────────────────────────
# Each entry: name, url_template, claim_type, claim_value, category, icon,
#             negative_markers (Phase 16 — empty list = backward compat)
# claim_type: "status_code" | "text_present" | "text_absent"

PLATFORMS: list[dict] = [
    {
        "name": "GitHub",
        "url": "https://github.com/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🐙",
        "negative_markers": ["Not Found", "Page not found"],
    },
    {
        "name": "GitLab",
        "url": "https://gitlab.com/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🦊",
        "negative_markers": ["not found", "404 Page Not Found"],
    },
    {
        "name": "Twitter / X",
        "url": "https://x.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "This account doesn't exist",
        "category": "Social",
        "icon": "🐦",
        # Audit 2026-05-01: X returns a full React SPA (HTTP 200, ~256KB).
        # The marker "this account doesn't exist" is injected client-side by
        # React and is NOT present in the SSR HTML received by httpx.
        # Cleared negative_markers: no SSR-detectable text distinguishes
        # missing vs existing accounts from the raw HTTP response body.
        "negative_markers": [],
    },
    {
        "name": "Instagram",
        "url": "https://www.instagram.com/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Sorry, this page",
        "category": "Social",
        "icon": "📸",
        # Audit 2026-05-01: Instagram returns HTTP 200 + full React SPA (~800KB)
        # regardless of account existence. "Sorry, this page isn't available"
        # is rendered client-side only. SSR HTML contains no detectable
        # text difference. Negative markers cleared; platform reliability
        # is LOW without browser execution or residential proxy.
        "negative_markers": [],
    },
    {
        "name": "TikTok",
        "url": "https://www.tiktok.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "Couldn't find this account",
        "category": "Social",
        "icon": "🎵",
        "negative_markers": ["couldn't find this account", '"statusCode":10221'],
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, nobody on Reddit",
        "category": "Social",
        "icon": "🤖",
        # Audit 2026-05-01: Reddit returns HTTP 200 with a bot-verification
        # challenge page ("Please wait for verification") for automated
        # requests. The marker "sorry, nobody on reddit goes by that name"
        # is NOT present in the challenge page body. Negative markers cleared
        # since the challenge page never contains them; the claim_value
        # "Sorry, nobody on Reddit" also won't be found in the challenge body,
        # so the text_absent claim will score positively even for nonexistent
        # accounts — known limitation requiring proxy or API access.
        "negative_markers": [],
    },
    {
        "name": "LinkedIn",
        "url": "https://www.linkedin.com/in/{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Professional",
        "icon": "💼",
        # Audit 2026-05-01: LinkedIn returns HTTP 999 (proprietary login-wall
        # status code) for all unauthenticated requests. Negative markers are
        # unreachable — the response body is a JS redirect to the login page.
        # text_absent claim will not match (body does not contain "Page not
        # found") → score boost applies even for nonexistent accounts.
        # No SSR-detectable markers; platform requires authenticated session.
        "negative_markers": [],
    },
    {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Sorry! We couldn't find that page",
        "category": "Social",
        "icon": "📌",
        "negative_markers": ["sorry! we couldn't find that page"],
    },
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "This page isn't available",
        "category": "Video",
        "icon": "▶️",
        "negative_markers": ["this page isn't available", "404 not found"],
    },
    {
        "name": "Twitch",
        "url": "https://www.twitch.tv/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry. Unless you've got a time machine",
        "category": "Video",
        "icon": "🎮",
        "negative_markers": ["sorry. unless you've got a time machine"],
    },
    {
        "name": "Steam",
        "url": "https://steamcommunity.com/id/{username}",
        "claim_type": "text_absent",
        "claim_value": "The specified profile could not be found",
        "category": "Gaming",
        "icon": "🎮",
        "negative_markers": ["the specified profile could not be found"],
    },
    {
        "name": "Keybase",
        "url": "https://keybase.io/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🔑",
        "negative_markers": ["not found", "user not found"],
    },
    {
        "name": "HackerNews",
        "url": "https://news.ycombinator.com/user?id={username}",
        "claim_type": "text_present",
        "claim_value": "user?id=",
        "category": "Dev / Tech",
        "icon": "🟠",
        "negative_markers": ["no such user", "sorry"],
    },
    {
        "name": "Dev.to",
        "url": "https://dev.to/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "👩‍💻",
        "negative_markers": ["page not found", "404 not found"],
    },
    {
        "name": "Medium",
        "url": "https://medium.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Blogging",
        "icon": "✍️",
        "negative_markers": ["page not found"],
    },
    {
        "name": "Mastodon (social.linux.pizza)",
        "url": "https://social.linux.pizza/@{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Social",
        "icon": "🐘",
        "negative_markers": ["not found", "this resource was not found"],
    },
    {
        "name": "Flickr",
        "url": "https://www.flickr.com/people/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Page Not Found",
        "category": "Photo",
        "icon": "📷",
        "negative_markers": ["page not found"],
    },
    {
        "name": "Vimeo",
        "url": "https://vimeo.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, we couldn't find that page",
        "category": "Video",
        "icon": "🎬",
        "negative_markers": ["sorry, we couldn't find that page"],
    },
    {
        "name": "SoundCloud",
        "url": "https://soundcloud.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "We can't find that user",
        "category": "Music",
        "icon": "🎵",
        "negative_markers": ["we can't find that user"],
    },
    {
        "name": "Spotify",
        "url": "https://open.spotify.com/user/{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Music",
        "icon": "🎧",
        "negative_markers": ["page not found", "user not found"],
    },
    {
        "name": "DockerHub",
        "url": "https://hub.docker.com/u/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🐳",
        "negative_markers": ["not found", "page not found"],
    },
    {
        "name": "NPM",
        "url": "https://www.npmjs.com/~{username}",
        "claim_type": "text_absent",
        "claim_value": "We're sorry, you've reached a 404",
        "category": "Dev / Tech",
        "icon": "📦",
        "negative_markers": ["we're sorry, you've reached a 404"],
    },
    {
        "name": "PyPI",
        "url": "https://pypi.org/user/{username}/",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🐍",
        "negative_markers": ["not found", "404: page not found"],
    },
    {
        "name": "Telegram",
        "url": "https://t.me/{username}",
        "claim_type": "text_present",
        "claim_value": "tgme_page_title",
        "category": "Messaging",
        "icon": "✈️",
        "negative_markers": [],
    },
    {
        "name": "Snapchat",
        "url": "https://www.snapchat.com/add/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, we couldn't find",
        "category": "Social",
        "icon": "👻",
        "negative_markers": ["sorry, we couldn't find"],
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

CONNECT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


# ── Result models ─────────────────────────────────────────────────────────────

@dataclass
class PlatformResult:
    platform: str = ""
    url: str = ""
    found: bool = False           # True iff state != "not_found" (backward compat)
    category: str = ""
    icon: str = ""
    confidence: int = 0           # 0-100 score (Phase 16)
    state: str = "not_found"      # "confirmed" | "likely" | "not_found" (Phase 16)
    error: Optional[str] = None   # "timeout" | "connection_error" | "http_NNN"
                                  # | "proxy_unavailable" | "cf_challenge"


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


# ── Proxy URL helpers (D-H5, D-03, Pitfall 2) ────────────────────────────────

def _masked_proxy_log(proxy_url: str | None) -> str:
    """Return 'host:port' only — never user:pass in logs (D-H5)."""
    if not proxy_url:
        return "unset"
    parsed = urllib.parse.urlparse(proxy_url)
    return f"{parsed.hostname}:{parsed.port}"


def _build_sticky_url(base_proxy_url: str, sessid: str) -> str:
    """
    Inject sticky session sessid + sesstime into Thordata proxy username.

    Input:  http://td-customer-USER:PASS@t.pr.thordata.net:9999
    Output: http://td-customer-USER-sessid-abc123ef-sesstime-2:PASS@host:9999

    sesstime=2 = 2 minutes (Thordata unit is MINUTES, minimum 1 minute).
    sessid stripped to alphanumeric-only for URL safety.
    """
    parsed = urllib.parse.urlparse(base_proxy_url)
    safe_sessid = re.sub(r"[^A-Za-z0-9]", "", sessid)[:16]
    new_username = f"{parsed.username}-sessid-{safe_sessid}-sesstime-{_STICKY_SESSTIME_MINUTES}"
    new_netloc = f"{new_username}:{parsed.password}@{parsed.hostname}:{parsed.port}"
    return urllib.parse.urlunparse(parsed._replace(netloc=new_netloc))


def _build_rotate_url(base_proxy_url: str, sessid: str) -> str:
    """Forced IP rotation — different sessid = different IP pool assignment (D-06)."""
    return _build_sticky_url(base_proxy_url, sessid + "r")


# ── Confidence scoring (D-08..D-12) ──────────────────────────────────────────

def _compute_confidence(
    resp_status: int,
    resp_body: str,
    resp_body_bytes: int,
    platform: dict,
) -> tuple[int, str]:
    """
    Returns (confidence_score 0-100, state 'confirmed'|'likely'|'not_found').
    Negative markers short-circuit to (0, 'not_found').
    Backend-only — never expose raw signal scores to frontend (D-H2).
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


# ── Body cap streaming fetch (Pitfall 4 fix) ──────────────────────────────────

async def _fetch_with_cap(
    client: httpx.AsyncClient,
    url: str,
    cap_bytes: int = _SHERLOCK_BODY_CAP,
) -> tuple[int, dict, bytes, int]:
    """
    Fetch URL, stopping body read at cap_bytes.
    Returns (status_code, response_headers, body_bytes, actual_bytes_read).
    Headers captured BEFORE body iteration (Cloudflare cf-mitigated detection — Pitfall 5).
    Real cap, not resp.text slice (Pitfall 4 fix).
    """
    async with client.stream("GET", url) as resp:
        headers = dict(resp.headers)
        chunks: list[bytes] = []
        total = 0
        async for chunk in resp.aiter_bytes(chunk_size=8192):
            chunks.append(chunk)
            total += len(chunk)
            if total >= cap_bytes:
                break
        body = b"".join(chunks)
        return resp.status_code, headers, body, total


# ── Per-platform async check ──────────────────────────────────────────────────

async def _check_platform(
    client: httpx.AsyncClient,
    username: str,
    platform: dict,
    per_search_counter: dict,
) -> PlatformResult:
    """
    Check one platform. Re-raises httpx.ProxyError so caller can retry.
    Named exceptions only — no bare except Exception (CLAUDE.md).
    """
    url = platform["url"].format(username=username)
    result = PlatformResult(
        platform=platform["name"],
        url=url,
        category=platform.get("category", ""),
        icon=platform.get("icon", ""),
    )

    # Per-domain outbound rate limit (CLAUDE.md mandate + D-04)
    domain = urllib.parse.urlparse(url).hostname or ""
    await _outbound_limiter.acquire(domain)

    try:
        status, headers, body_bytes, bytes_read = await _fetch_with_cap(client, url)
    except httpx.ProxyError:
        # MUST come first — re-raise so caller can retry with rotated sessid (D-06)
        raise
    except httpx.TimeoutException:
        # Pitfall 1 fix: existing code incorrectly caught asyncio.TimeoutError (dead code)
        result.error = "timeout"
        return result
    except httpx.ConnectError:
        result.error = "connection_error"
        return result
    except httpx.HTTPStatusError as exc:
        result.error = f"http_{exc.response.status_code}"
        return result
    except httpx.HTTPError as exc:
        result.error = str(exc)[:80]
        return result
    # NO bare except Exception (CLAUDE.md prohibition)

    # Account bytes consumed (shared counter — Pitfall 7)
    per_search_counter["bytes"] = per_search_counter.get("bytes", 0) + bytes_read

    # Cloudflare challenge detection (Pitfall 5)
    if headers.get("cf-mitigated") == "challenge":
        result.error = "cf_challenge"
        result.confidence = 0
        result.state = "not_found"
        result.found = False
        return result

    body_text = body_bytes.decode("utf-8", errors="replace")
    confidence, state = _compute_confidence(status, body_text, bytes_read, platform)
    result.confidence = confidence
    result.state = state
    result.found = state != "not_found"
    return result


# ── Proxy retry wrapper (D-06) ────────────────────────────────────────────────

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
            return PlatformResult(
                platform=platform["name"],
                url=platform["url"].format(username=username),
                category=platform.get("category", ""),
                icon=platform.get("icon", ""),
                error="proxy_unavailable",
                state="not_found",
                confidence=0,
                found=False,
            )


# ── Sherlock CLI integration ──────────────────────────────────────────────────

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
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None


# ── httpx client builder ──────────────────────────────────────────────────────

def _build_client_kwargs(proxy_url: str | None) -> dict:
    """Build httpx.AsyncClient kwargs with optional Thordata sticky-session proxy."""
    base: dict = {
        "headers": HEADERS,
        "timeout": CONNECT_TIMEOUT,
        "follow_redirects": True,
        "verify": False,
    }
    if proxy_url:
        base["proxy"] = proxy_url  # singular 'proxy=' (httpx 0.27.x; 'proxies=' deprecated)
        base["limits"] = httpx.Limits(max_connections=8, max_keepalive_connections=5)
    else:
        base["limits"] = httpx.Limits(max_connections=15, max_keepalive_connections=10)
    return base


# ── Public API ────────────────────────────────────────────────────────────────

async def search_username(
    username: str,
    prefer_cli: bool = False,
    timeout_per: int = 10,
) -> SherlockResult:
    """
    Main entry point (async). Public signature unchanged (timeout_per added, default safe).
    - If prefer_cli=True: tries Sherlock CLI first (via to_thread — subprocess is blocking).
      Falls back to internal async engine if CLI is not found OR returns 0 results.
    - Always runs internal async engine if CLI is unavailable/finds nothing.
    - Routes outbound traffic through Thordata when THORDATA_PROXY_URL is set
      and _budget._proxy_active is True (set by lifespan health check D-07).

    Caller is responsible for username validation (D-H8/D-H9 — Plan 03 routes layer).
    Pre-validated username accepted; never echoed in error messages.
    """
    username = username.strip().lstrip("@")

    if prefer_cli:
        # _try_sherlock_cli uses subprocess.run(timeout=120) — must run in thread
        cli_result = await asyncio.to_thread(_try_sherlock_cli, username)
        if cli_result and cli_result.found_count > 0:
            return cli_result

    # Generate per-search sticky session ID (D-02, D-03)
    search_id = secrets.token_hex(8)  # 16-char hex, alphanumeric-safe

    # Determine if proxy is active for this search
    use_proxy = bool(THORDATA_PROXY_URL and _budget._proxy_active)

    per_search_counter: dict = {"bytes": 0}

    if use_proxy:
        primary_url = _build_sticky_url(THORDATA_PROXY_URL, search_id)
        rotate_url = _build_rotate_url(THORDATA_PROXY_URL, search_id)
        primary_kwargs = _build_client_kwargs(primary_url)
        rotate_kwargs = _build_client_kwargs(rotate_url)

        async with httpx.AsyncClient(**primary_kwargs) as primary_client, \
                   httpx.AsyncClient(**rotate_kwargs) as rotate_client:
            tasks = [
                _check_platform_with_retry(
                    primary_client, rotate_client, username, p, per_search_counter
                )
                for p in PLATFORMS
            ]
            platform_results = await asyncio.gather(*tasks)
    else:
        direct_kwargs = _build_client_kwargs(None)
        async with httpx.AsyncClient(**direct_kwargs) as client:
            tasks = [
                _check_platform(client, username, p, per_search_counter)
                for p in PLATFORMS
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

    # D-H13 audit log — SHA256 hash only, plaintext username NEVER logged
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
