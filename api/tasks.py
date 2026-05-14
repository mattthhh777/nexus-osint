"""Background tasks for NexusOSINT.

Centralised here so orchestrator._registry tracks them and cancel_all()
cleans them up cleanly. Each loop must be registered via orchestrator.submit()
in the lifespan startup block.
"""
import asyncio
import logging
import time

from api.db import DatabaseManager

logger = logging.getLogger("nexusosint.tasks")

_GRACE_SECONDS = 300  # keep entries 5 min past exp for clock-skew safety


async def blacklist_purge_loop(db: DatabaseManager, interval: int = 60) -> None:
    """Purge expired token_blacklist rows every `interval` seconds.

    Runs indefinitely; cancellation is handled by TaskOrchestrator.cancel_all()
    during shutdown. A 5-minute grace window (exp < now - 300) prevents
    clock-skew false positives.
    """
    while True:
        await asyncio.sleep(interval)
        cutoff = int(time.time()) - _GRACE_SECONDS
        try:
            await db.execute_nowait(
                "DELETE FROM token_blacklist WHERE exp < $1",
                (cutoff,),
            )
        except Exception:
            logger.warning("blacklist_purge_loop: DB error — will retry next cycle", exc_info=True)
