"""Health routes: /health, /health/memory."""
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import psutil
from fastapi import APIRouter, Depends, Request

from api.config import AUDIT_DB, RL_ADMIN_LIMIT, RL_READ_LIMIT
from api.deps import get_admin_user, get_orchestrator_dep
from api.main import limiter
from api.orchestrator import DegradationMode, TaskOrchestrator
from api.services.search_service import _api_cache

router = APIRouter()


@router.get("/health")
@router.head("/health")
@limiter.limit(RL_READ_LIMIT)
async def health(
    request: Request,
    orch: TaskOrchestrator = Depends(get_orchestrator_dep),
):
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    mem_mb = mem.used / 1024 / 1024
    proc = psutil.Process()

    uptime_s = round(time.time() - proc.create_time(), 1)
    wal_path = Path(str(AUDIT_DB) + "-wal")
    wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0
    degradation = orch.degradation_mode

    return {
        "status": "degraded" if degradation != DegradationMode.NORMAL else "healthy",
        "version": "3.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "memory_used_mb": round(mem_mb, 1),
        "memory_pct": mem.percent,
        "rss_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
        "cpu_pct": cpu,
        "swap_used_mb": round(swap.used / 1024 / 1024, 1),
        "agents_paused": degradation != DegradationMode.NORMAL,
        "cache_entries": len(_api_cache),
        "uptime_s":             uptime_s,
        "active_tasks":         orch.active_count,
        "semaphore_slots_free": orch.semaphore_slots_free,
        "wal_size_bytes":       wal_size_bytes,
        "degradation_mode":     degradation.value,
    }


@router.get("/health/memory")
@limiter.limit(RL_ADMIN_LIMIT)
async def health_memory(
    request: Request,
    _: dict = Depends(get_admin_user),
    orch: TaskOrchestrator = Depends(get_orchestrator_dep),
):
    """Detailed memory profiling snapshot — admin only.
    Exposes RSS, VMS, tracemalloc current/peak, top allocations, and cache stats.
    Use for diagnosing memory leaks on the 1GB VPS.
    """
    proc = psutil.Process()
    mem_info = proc.memory_info()
    mem = psutil.virtual_memory()
    traced_current, traced_peak = tracemalloc.get_traced_memory()

    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")[:15]

    return {
        "rss_mb": round(mem_info.rss / 1024 / 1024, 1),
        "vms_mb": round(mem_info.vms / 1024 / 1024, 1),
        "system_memory_pct": mem.percent,
        "tracemalloc_current_mb": round(traced_current / 1024 / 1024, 2),
        "tracemalloc_peak_mb": round(traced_peak / 1024 / 1024, 2),
        "top_allocations": [
            {
                "file": str(stat.traceback),
                "size_kb": round(stat.size / 1024, 1),
                "count": stat.count,
            }
            for stat in top_stats
        ],
        "cache_size": len(_api_cache),
        "cache_maxsize": _api_cache.maxsize,
        "agents_paused": orch.degradation_mode != DegradationMode.NORMAL,
    }
