"""Background tasks for NexusOSINT.

Centralised here so orchestrator._registry tracks them and cancel_all()
cleans them up cleanly. Each loop must be registered via orchestrator.submit()
in the lifespan startup block.
"""
import asyncio
import logging
import time

from api.db import DatabaseError, DatabaseManager
from api.services import job_store

logger = logging.getLogger("nexusosint.tasks")

_GRACE_SECONDS = 300  # keep entries 5 min past exp for clock-skew safety
_JOB_CLEANUP_INTERVAL_SECONDS = 3600


async def _purge_expired_jobs(db: DatabaseManager) -> None:
    try:
        deleted = await job_store.purge_expired(db=db)
    except (DatabaseError, RuntimeError, OSError) as exc:
        logger.warning(
            "job_cleanup_loop: DB error - will retry next cycle: %s",
            type(exc).__name__,
            exc_info=True,
        )
        return

    if deleted:
        logger.info("job_cleanup_loop: purged expired jobs count=%d", deleted)


async def job_cleanup_loop(
    db: DatabaseManager,
    interval: int = _JOB_CLEANUP_INTERVAL_SECONDS,
) -> None:
    """Purge expired search_jobs every hour.

    Events cascade through FK constraints. Logs only aggregate counts.
    """
    while True:
        await asyncio.sleep(interval)
        await _purge_expired_jobs(db)


async def blacklist_purge_loop(
    db: DatabaseManager,
    interval: int = 60,
    job_cleanup_interval: int = _JOB_CLEANUP_INTERVAL_SECONDS,
) -> None:
    """Purge expired token_blacklist rows every `interval` seconds.

    Runs indefinitely; cancellation is handled by TaskOrchestrator.cancel_all()
    during shutdown. A 5-minute grace window (exp < now - 300) prevents
    clock-skew false positives.
    """
    last_job_cleanup = time.monotonic()
    while True:
        await asyncio.sleep(interval)
        cutoff = int(time.time()) - _GRACE_SECONDS
        try:
            await db.execute_nowait(
                "DELETE FROM token_blacklist WHERE exp < $1",
                (cutoff,),
            )
        except (DatabaseError, RuntimeError, OSError) as exc:
            logger.warning(
                "blacklist_purge_loop: DB error - will retry next cycle: %s",
                type(exc).__name__,
                exc_info=True,
            )

        now = time.monotonic()
        if now - last_job_cleanup >= job_cleanup_interval:
            await _purge_expired_jobs(db)
            last_job_cleanup = now
