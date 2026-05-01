"""
Phase 16: Thordata residential-proxy daily bandwidth budget tracker.

Module-level state — resets at UTC midnight (lazy check, no background task).
State is in-memory only (D-16 trade-off: container restart resets counters).

Leaf import rule: this module imports only stdlib + api.config.
Both modules/sherlock_wrapper.py (writer) and api/routes/health.py (reader)
import from here — avoids the api/ → modules/ cross-layer dependency that
would arise if budget state lived inline in sherlock_wrapper.py
(Phase 16 RESEARCH Pitfall 8).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import logging

from api.config import THORDATA_DAILY_BUDGET_BYTES

logger = logging.getLogger("nexusosint.budget")

# ── Module-level state ──────────────────────────────────────────────────────
_bytes_today: int = 0
_requests_today: int = 0
_current_day: date = datetime.now(timezone.utc).date()

# Set to True by api/main.py lifespan after Thordata HEAD https://api.ipify.org
# health check passes (D-07). Read by /health/thordata (D-19).
_proxy_active: bool = False


def _maybe_reset() -> None:
    """Lazy UTC day-rollover check. Fires on every counter operation."""
    global _bytes_today, _requests_today, _current_day
    today = datetime.now(timezone.utc).date()
    if today != _current_day:
        logger.info(
            "Thordata budget reset: new UTC day. prev_bytes=%d prev_reqs=%d",
            _bytes_today, _requests_today,
        )
        _bytes_today = 0
        _requests_today = 0
        _current_day = today


def record_usage(bytes_used: int) -> None:
    """
    Record outbound bytes consumed via Thordata proxy.

    Triggers SOFT-threshold WARNING log at 50% of daily budget (D-16: 500MB).
    Caller is responsible for checking is_hard_limit_exceeded() BEFORE issuing
    the request — this function only accounts.
    """
    global _bytes_today, _requests_today
    _maybe_reset()
    _bytes_today += bytes_used
    _requests_today += 1
    soft_bytes = THORDATA_DAILY_BUDGET_BYTES // 2  # D-16 SOFT = 500MB (50% of 1GB)
    if _bytes_today > soft_bytes:
        logger.warning(
            "Thordata SOFT budget exceeded: %.1fMB used (limit %.0fMB)",
            _bytes_today / 1_048_576,
            THORDATA_DAILY_BUDGET_BYTES / 1_048_576,
        )


def is_hard_limit_exceeded() -> bool:
    """
    D-16 HARD threshold check. Caller raises HTTPException(503, Retry-After=86400)
    when this returns True (D-H12 -- never silently drop).
    """
    _maybe_reset()
    return _bytes_today >= THORDATA_DAILY_BUDGET_BYTES


def get_metrics() -> dict:
    """
    D-19 health metrics payload. Admin-gated by caller (D-H14).
    Only 4 keys exposed -- no raw signal scores, no proxy URL (D-H2, D-H5).
    """
    _maybe_reset()
    budget_mb = THORDATA_DAILY_BUDGET_BYTES / 1_048_576
    used_mb = _bytes_today / 1_048_576
    remaining_pct = max(0.0, (1.0 - used_mb / budget_mb) * 100) if budget_mb > 0 else 0.0
    return {
        "bytes_today_mb": round(used_mb, 2),
        "requests_today": _requests_today,
        "budget_remaining_pct": round(remaining_pct, 1),
        "proxy_active": _proxy_active,
    }
