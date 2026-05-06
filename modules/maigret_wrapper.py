"""
NexusOSINT — Maigret Wrapper
Checks username presence across 500 social platforms via Maigret's async API.
Returns PlatformResult/SherlockResult — same interface as sherlock_wrapper —
so search_service.py requires minimal changes.

Maigret status mapping:
  CLAIMED   -> state="confirmed", confidence=90
  AVAILABLE -> state="not_found", confidence=0
  UNKNOWN   -> error (check failed), state="not_found"
  ILLEGAL   -> username format invalid for site, treated as skip

Budget: aiohttp internals not hookable via Thordata byte counter.
Bytes estimated: CLAIMED=50KB, AVAILABLE/UNKNOWN=5KB per site.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets

import api.budget as _budget
from api.config import THORDATA_PROXY_URL
from modules.sherlock_wrapper import (
    PlatformResult,
    SherlockResult,
    _build_sticky_url,
    _masked_proxy_log,
)

logger = logging.getLogger("nexusosint.maigret")

# Maigret site tags that indicate unreliable SSR detection
_LOW_RELIABILITY_TAGS: frozenset[str] = frozenset({
    "SPA", "login_required", "auth_required",
})

_TOP_SITES = 500           # Top N by Alexa rank
_BYTES_CLAIMED = 50_000    # ~50KB budget estimate per confirmed profile
_BYTES_OTHER   = 5_000     # ~5KB per available/error response
_MAX_CONNECTIONS = 10      # Conservative for 1vCPU/1GB VPS


# ── Database singleton ────────────────────────────────────────────────────────

def _load_sites() -> dict | None:
    """Load Maigret site database once at module import."""
    try:
        from maigret.sites import MaigretDatabase
        import maigret as _mpkg
        data_path = os.path.join(
            os.path.dirname(_mpkg.__file__), "resources", "data.json"
        )
        db = MaigretDatabase().load_from_path(data_path)
        sites = db.ranked_sites_dict(top=_TOP_SITES)
        logger.info("Maigret DB loaded: %d sites (top=%d)", len(sites), _TOP_SITES)
        return sites
    except Exception as exc:
        logger.error("Maigret DB load failed: %s", exc)
        return None


_MAIGRET_SITES: dict | None = _load_sites()


# ── Result mapping ────────────────────────────────────────────────────────────

def _site_reliability(site) -> str:
    tags = set(getattr(site, "tags", []) or [])
    return "low" if tags & _LOW_RELIABILITY_TAGS else "normal"


def _site_category(site) -> str:
    tags = list(getattr(site, "tags", []) or [])
    return tags[0].capitalize() if tags else ""


def _map_result(site_name: str, r: dict) -> PlatformResult:
    """Map one Maigret QueryResultWrapper to PlatformResult."""
    site   = r.get("site")
    status = r.get("status")

    url         = r.get("url_user", "")
    category    = _site_category(site) if site else ""
    reliability = _site_reliability(site) if site else "normal"

    is_claimed = callable(getattr(status, "is_found", None)) and status.is_found()

    if is_claimed:
        return PlatformResult(
            platform=site_name,
            url=url,
            found=True,
            category=category,
            icon="",
            confidence=90,
            state="confirmed",
            reliability=reliability,
        )

    # UNKNOWN = check error; AVAILABLE/ILLEGAL = clean miss
    status_val = str(getattr(getattr(status, "status", None), "value", "")).lower()
    is_error = status_val == "unknown" or status_val == ""

    if is_error:
        error_obj = getattr(status, "error", None)
        error_str = (
            str(getattr(error_obj, "type", "unknown"))[:80]
            if error_obj else "unknown"
        )
        return PlatformResult(
            platform=site_name,
            url=url,
            found=False,
            category=category,
            icon="",
            confidence=0,
            state="not_found",
            error=error_str,
            reliability=reliability,
        )

    return PlatformResult(
        platform=site_name,
        url=url,
        found=False,
        category=category,
        icon="",
        confidence=0,
        state="not_found",
        reliability=reliability,
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def search_username(
    username: str,
    prefer_cli: bool = False,   # ignored — kept for API compat
    timeout_per: int = 10,
) -> SherlockResult:
    """
    Async entry point. Returns SherlockResult using same interface as
    sherlock_wrapper.search_username. Username must already be validated
    by caller (D-H8/D-H9 enforced in search_service).
    """
    username = username.strip().lstrip("@")

    if _MAIGRET_SITES is None:
        return SherlockResult(
            username=username,
            success=False,
            error="Maigret database failed to load at startup",
            source="maigret",
        )

    from maigret import search as _maigret_search

    use_proxy = bool(THORDATA_PROXY_URL and _budget._proxy_active)
    proxy_url: str | None = None
    if use_proxy:
        proxy_url = _build_sticky_url(THORDATA_PROXY_URL, secrets.token_hex(8))
        logger.debug("Maigret using proxy: %s", _masked_proxy_log(THORDATA_PROXY_URL))

    try:
        raw: dict = await _maigret_search(
            username=username,
            site_dict=_MAIGRET_SITES,
            logger=logger,
            proxy=proxy_url,
            timeout=timeout_per,
            is_parsing_enabled=False,
            no_progressbar=True,
            max_connections=_MAX_CONNECTIONS,
            retries=1,
        )
    except Exception as exc:
        logger.error("Maigret search error: %s", type(exc).__name__)
        return SherlockResult(
            username=username,
            success=False,
            error=str(exc)[:200],
            source="maigret",
            proxy_used=use_proxy,
        )

    result = SherlockResult(
        username=username,
        success=True,
        source="maigret",
        proxy_used=use_proxy,
    )

    claimed_count = 0
    for site_name, r in raw.items():
        pr = _map_result(site_name, r)
        if pr.error and pr.error != "illegal_username":
            result.errors.append(pr)
        elif pr.state == "confirmed":
            result.found.append(pr)
            claimed_count += 1
        else:
            result.not_found.append(pr)

    estimated_bytes = (
        claimed_count * _BYTES_CLAIMED
        + (len(raw) - claimed_count) * _BYTES_OTHER
    )
    _budget.record_usage(estimated_bytes)

    username_hash = hashlib.sha256(username.encode()).hexdigest()[:8]
    logger.info(
        "Maigret search complete | username_hash=%s proxy_used=%s "
        "confirmed=%d not_found=%d errors=%d sites_checked=%d estimated_bytes=%d",
        username_hash,
        use_proxy,
        len(result.found),
        len(result.not_found),
        len(result.errors),
        len(raw),
        estimated_bytes,
    )

    return result
