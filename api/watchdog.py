"""
Memory pressure watchdog for NexusOSINT.

Polls psutil.virtual_memory() every WATCHDOG_INTERVAL_S seconds and adjusts
the singleton TaskOrchestrator's concurrency ceiling based on three thresholds:

  mem_pct > 85  -> CRITICAL  (ceiling = 0, reject all new tasks)
  mem_pct > 80  -> REDUCED   (ceiling = 2)
  mem_pct < 75  -> NORMAL    (ceiling = 5)

The loop is registered as a tracked background task in api.main.lifespan and
cancelled cleanly on shutdown. It MUST NOT crash the process — only
asyncio.CancelledError is allowed to propagate.
"""

from __future__ import annotations

import asyncio
import logging

import psutil

from api.orchestrator import (
    DegradationMode,
    TaskOrchestrator,
    get_orchestrator,
)

logger = logging.getLogger("nexusosint.watchdog")

# Thresholds — match CLAUDE.md (alert > 400MB, critical > 85%) plus the
# 80% intermediate REDUCED threshold from Phase 10 requirements.
THRESHOLD_REDUCED_PCT  = 80.0
THRESHOLD_CRITICAL_PCT = 85.0
THRESHOLD_RESTORE_PCT  = 75.0
MEMORY_ALERT_MB        = 400.0  # absolute MB warning, per CLAUDE.md

WATCHDOG_INTERVAL_S = 30.0

CEILING_NORMAL   = 5
CEILING_REDUCED  = 2
CEILING_CRITICAL = 0


def _decide_mode(mem_pct: float, current: DegradationMode) -> DegradationMode:
    """
    Pure function — decides next degradation mode given current memory percent
    and current mode. Uses hysteresis: only restore to NORMAL when mem < 75%.
    """
    if mem_pct >= THRESHOLD_CRITICAL_PCT:
        return DegradationMode.CRITICAL
    if mem_pct >= THRESHOLD_REDUCED_PCT:
        return DegradationMode.REDUCED
    if mem_pct < THRESHOLD_RESTORE_PCT:
        return DegradationMode.NORMAL
    # Between 75 and 80: keep current mode (hysteresis band)
    return current


def _ceiling_for_mode(mode: DegradationMode) -> int:
    if mode == DegradationMode.CRITICAL:
        return CEILING_CRITICAL
    if mode == DegradationMode.REDUCED:
        return CEILING_REDUCED
    return CEILING_NORMAL


def _apply_degradation(
    orchestrator: TaskOrchestrator,
    mem_pct: float,
    mem_mb: float,
) -> None:
    """Apply degradation transition based on memory pressure. Logs transitions."""
    current = orchestrator.degradation_mode
    next_mode = _decide_mode(mem_pct, current)

    if mem_mb > MEMORY_ALERT_MB:
        logger.warning(
            "Memory alert %.0fMB (%.1f%%) — investigate",
            mem_mb,
            mem_pct,
        )

    if next_mode != current:
        new_ceiling = _ceiling_for_mode(next_mode)
        orchestrator.set_ceiling(new_ceiling)
        orchestrator.set_degradation_mode(next_mode)
        logger.warning(
            "Degradation transition %s -> %s (mem=%.1f%%, ceiling=%d)",
            current.value,
            next_mode.value,
            mem_pct,
            new_ceiling,
        )


async def memory_watchdog_loop(interval: float = WATCHDOG_INTERVAL_S) -> None:
    """
    Background loop. Polls memory and applies degradation transitions.

    Never raises except CancelledError. Outer try/except Exception is the
    documented background-loop guard pattern (same rationale as orchestrator
    _guarded()): a watchdog crash is worse than a transient logging hiccup.
    """
    orchestrator = get_orchestrator()
    logger.info(
        "Memory watchdog started (interval=%.0fs, thresholds=%.0f/%.0f/%.0f%%)",
        interval,
        THRESHOLD_RESTORE_PCT,
        THRESHOLD_REDUCED_PCT,
        THRESHOLD_CRITICAL_PCT,
    )
    while True:
        try:
            await asyncio.sleep(interval)
            vm = psutil.virtual_memory()
            mem_pct = vm.percent
            mem_mb = vm.used / 1024.0 / 1024.0
            _apply_degradation(orchestrator, mem_pct, mem_mb)
        except asyncio.CancelledError:
            logger.info("Memory watchdog cancelled — exiting loop")
            raise
        except Exception:  # noqa: BLE001 — documented background-loop guard
            logger.exception("Watchdog iteration failed — continuing")
