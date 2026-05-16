"""Structured audit logging for username validation decisions."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger("nexusosint.username_validation")


def _hash_username(username: str) -> str:
    return hashlib.sha256(username.strip().casefold().encode("utf-8")).hexdigest()[:12]


def log_decision(username: str, payload: dict[str, Any], *, cache_hit: bool) -> None:
    platforms = payload.get("platforms", [])
    if not isinstance(platforms, list):
        platforms = []
    status_counts: dict[str, int] = {}
    warning_count = 0
    for item in platforms:
        if not isinstance(item, dict):
            continue
        status = str(item.get("validation_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        warning_count += len(item.get("warnings") or [])
    logger.info(
        "username_validation_decision username_hash=%s cache_hit=%s total_checked=%s "
        "confirmed=%s likely=%s warnings=%s status_counts=%s",
        _hash_username(username),
        cache_hit,
        payload.get("total_checked", 0),
        payload.get("found_count", 0),
        payload.get("likely_count", 0),
        warning_count,
        status_counts,
    )
