"""Outbound rate limiting for username checks."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta


class OutboundRateLimiter:
    """Token bucket rate limiter â€” 1 semaphore + min-interval per domain."""

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


# Module-level singleton â€” shared across all concurrent searches (Open Q #5)
_outbound_limiter = OutboundRateLimiter(calls_per_second=1.0)  # D-04

