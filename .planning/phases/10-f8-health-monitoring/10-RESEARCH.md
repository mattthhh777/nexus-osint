# Phase 10: F8 — Health Monitoring - Research

**Researched:** 2026-04-08
**Domain:** FastAPI health endpoint + psutil memory watchdog + graceful shutdown
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| F8 | Real `/health` endpoint with RSS, CPU%, active tasks, semaphore slots, WAL size, uptime | Existing psutil + Path.stat() patterns verified in codebase |
| F8 | Memory watchdog: >80% warn, >85% reduce semaphore ceiling, <75% restore | Existing `_agents_paused` global + psutil confirmed; semaphore ceiling adjustment is new |
| F8 | Graceful shutdown: drain orchestrator → flush DB → close — completes < 35s | Existing `_db.shutdown()` in lifespan confirmed; orchestrator cancel_all() exists; docker stop_grace_period must be 35s |
| F8 | Degradation modes: NORMAL / REDUCED / CRITICAL | Global state enum needed; ties to watchdog thresholds |
</phase_requirements>

---

## Summary

Phase 10 is the final milestone phase. Nearly all infrastructure is already in place — the work is integrating and formalizing what exists into a production-quality watchdog. The existing `/health` endpoint (line 1644 of `api/main.py`) already returns `status`, `rss_mb`, `cpu_pct`, `memory_pct`, `swap_used_mb`, `agents_paused`, `cache_entries`. It is missing: `active_tasks`, `semaphore_slots_free`, `wal_size_bytes`, `uptime_s`, and a formal `degradation_mode` field.

The `TaskOrchestrator` class (`api/orchestrator.py`) exists and has `active_count`, `cancel_all()`, and the internal `_global_sem`. However it is NOT a singleton — a new instance is created per search in `_stream_search`. This means the health endpoint cannot query "current active tasks" without a global registry. The plan must create a module-level singleton orchestrator (or a lightweight global counter) so `/health` can report real active task counts. This is the only non-trivial architectural decision in this phase.

Graceful shutdown is partially implemented in the `lifespan` function: it calls `_db.shutdown()` (which drains the write queue, 10s timeout) and `oathnet_client.close()`. It does NOT call `orchestrator.cancel_all()` because the orchestrator is per-request. With a singleton orchestrator, `cancel_all()` can be added to the lifespan shutdown sequence. The 35s total budget breaks down as: 5s orchestrator drain + 10s DB flush + 2s client close + 18s margin. Docker's default `stop_grace_period` is 10s — this must be explicitly set to 35s in `docker-compose.yml`.

**Primary recommendation:** Extract a module-level singleton `TaskOrchestrator` in `api/orchestrator.py`, wire it into `_stream_search`, expose its `active_count` and `_global_sem._value` to `/health`, run `cancel_all()` in lifespan shutdown, and move the watchdog loop into a new `api/watchdog.py` background task.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psutil | 5.9.x (already installed) | RSS, CPU%, swap, process create_time | Already in requirements.txt, used in existing /health |
| asyncio | stdlib | Background watchdog task, Semaphore introspection | No dep needed |
| pathlib.Path | stdlib | WAL file size via `.stat().st_size` | No dep needed |
| time | stdlib | Uptime calculation: `time.time() - proc.create_time()` | No dep needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| loguru / logging | already active | Watchdog threshold alerts | Existing `logger` in main.py |
| aiosqlite | already installed | WAL checkpoint on graceful shutdown | For `PRAGMA wal_checkpoint(TRUNCATE)` before close |

**No new dependencies required.** This phase is pure integration of existing libraries.

---

## Architecture Patterns

### Recommended Project Structure
```
api/
├── main.py         # /health endpoint enriched; watchdog task registered in lifespan
├── watchdog.py     # NEW: MemoryWatchdog class + degradation state enum
├── orchestrator.py # MODIFIED: add module-level singleton + expose semaphore stats
└── db.py           # UNCHANGED (shutdown already correct)
```

### Pattern 1: Module-Level Singleton Orchestrator

**What:** A single `TaskOrchestrator` instance created at module level in `orchestrator.py`, imported by both `main.py` (for `/health` reads) and wherever `_stream_search` submits tasks.

**Why:** Per-search instances make global task counting impossible. The semaphore must also be shared for the watchdog to reduce concurrency under memory pressure.

**Current state:** `TaskOrchestrator` is per-search. `_stream_search` does NOT import or use it (confirmed: zero `TaskOrchestrator` imports in `main.py`). The orchestrator built in Phase 05 was explicitly marked "not wired to _stream_search — deferred".

**Plan implication:** Phase 10 Plan must wire the singleton orchestrator into `_stream_search` as part of making active_count visible. This was the deferred Phase 05b work.

```python
# api/orchestrator.py — add at module bottom
# Module-level singleton — shared by /health and _stream_search
_singleton: TaskOrchestrator | None = None

def get_orchestrator() -> TaskOrchestrator:
    global _singleton
    if _singleton is None:
        _singleton = TaskOrchestrator()
    return _singleton
```

### Pattern 2: Degradation State Enum

**What:** A formal `DegradationMode` enum with NORMAL/REDUCED/CRITICAL replaces the current bare boolean `_agents_paused`.

**When to use:** Whenever health status needs structured representation. REDUCED = semaphore ceiling lowered from 5 to 2 (not zero — system still serves requests). CRITICAL = all new tasks rejected.

```python
# api/watchdog.py
import enum

class DegradationMode(enum.Enum):
    NORMAL   = "normal"    # mem < 75%
    REDUCED  = "reduced"   # 80% < mem < 85% — semaphore ceiling reduced
    CRITICAL = "critical"  # mem > 85% — new agents paused entirely
```

**Threshold mapping (from CLAUDE.md + phase description):**
- `>80%` memory → warn + switch to REDUCED (lower semaphore to 2)
- `>85%` memory → CRITICAL (pause all new agents, semaphore to 0 effective)
- `<75%` memory → restore NORMAL (semaphore back to 5)

Note: CLAUDE.md specifies MEMORY_ALERT_MB = 400MB (absolute) AND MEMORY_CRITICAL_PCT = 85%. The phase description adds an 80% threshold for REDUCED mode. These are complementary — use percent thresholds for degradation (consistent across deployments), absolute MB threshold for log warnings.

### Pattern 3: Watchdog Background Task

**What:** An `asyncio.create_task()` loop registered in lifespan that polls memory every 30s and mutates the singleton orchestrator's semaphore ceiling.

**Why not a separate process:** VPS is 1vCPU/1GB. A thread or subprocess adds overhead. An async loop with 30s sleep adds near-zero cost.

```python
# api/watchdog.py
import asyncio
import psutil
import logging
from api.orchestrator import get_orchestrator, GLOBAL_CONCURRENCY_LIMIT

logger = logging.getLogger("nexusosint.watchdog")

THRESHOLD_REDUCED_PCT  = 80   # warn + reduce semaphore
THRESHOLD_CRITICAL_PCT = 85   # pause all new tasks
THRESHOLD_RESTORE_PCT  = 75   # restore normal

async def memory_watchdog_loop(interval: float = 30.0) -> None:
    """
    Background task: polls memory every `interval` seconds.
    Mutates orchestrator semaphore ceiling based on thresholds.
    Never raises — watchdog must not crash the process.
    """
    orchestrator = get_orchestrator()
    while True:
        try:
            await asyncio.sleep(interval)
            mem_pct = psutil.virtual_memory().percent
            mem_mb  = psutil.virtual_memory().used / 1024 / 1024
            _apply_degradation(orchestrator, mem_pct, mem_mb)
        except asyncio.CancelledError:
            logger.info("Watchdog loop cancelled — shutting down")
            raise
        except Exception:
            logger.exception("Watchdog loop error — continuing")  # never crash
```

**Registration in lifespan:**
```python
@asynccontextmanager
async def lifespan(application: FastAPI):
    _validate_jwt_secret()
    tracemalloc.start(10)
    _ensure_default_user()
    await _db.startup(db_path=AUDIT_DB)
    watchdog_task = asyncio.create_task(
        memory_watchdog_loop(), name="memory-watchdog"
    )
    logger.info("NexusOSINT started — watchdog active")
    yield
    # shutdown
    watchdog_task.cancel()
    await asyncio.gather(watchdog_task, return_exceptions=True)
    await get_orchestrator().cancel_all()
    await _db.shutdown()
    if oathnet_client:
        await oathnet_client.close()
    logger.info("NexusOSINT shutdown complete")
```

### Pattern 4: WAL File Size Inspection

**What:** Read WAL file size from filesystem. The WAL file lives at the same path as the DB with `-wal` suffix. File size is a proxy for pending uncommitted pages — useful for monitoring checkpoint lag.

```python
# In /health endpoint
wal_path = Path(str(AUDIT_DB) + "-wal")
wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0
```

**Pitfall:** WAL file may not exist if checkpointed to zero (normal). Return 0 in that case — not an error.

### Pattern 5: Graceful Shutdown Sequencing

Docker sends SIGTERM → uvicorn begins shutdown → stops accepting connections → waits for in-flight requests → calls lifespan shutdown (the `yield` block exits). The key constraint: **docker stop default grace period is 10s, then SIGKILL**. Our shutdown needs 35s — must set `stop_grace_period: 35s` in `docker-compose.yml`.

Shutdown order (< 35s total budget):
1. Cancel watchdog task (immediate)
2. `orchestrator.cancel_all()` — cancels in-flight modules, drains queue (~5s worst case: active Sherlock/SpiderFoot calls may take a few seconds to respond to cancellation)
3. `_db.shutdown()` — sends STOP_SENTINEL to write queue, waits up to 10s for writer to drain, then closes connection
4. `oathnet_client.close()` — closes httpx connection pool (~1s)

Total worst-case: ~17s. 35s limit provides ample margin.

**uvicorn flag:** Add `--timeout-graceful-shutdown 30` to the compose command so uvicorn doesn't wait indefinitely for hung requests before calling lifespan shutdown.

### Pattern 6: Semaphore Ceiling Reduction

**What:** Dynamically lower the global semaphore's `_value` to reduce concurrency under memory pressure.

**Critical pitfall:** `asyncio.Semaphore` has no public API to change the ceiling. Directly mutating `_value` is the only option. This is internal API — document the coupling explicitly.

```python
async def _set_semaphore_ceiling(orchestrator: TaskOrchestrator, new_ceiling: int) -> None:
    """
    Reduce the effective concurrency ceiling by draining sem slots.
    This is done by acquiring the semaphore until the desired ceiling is reached.
    WARNING: Mutates internal asyncio.Semaphore._value — no public API exists.
    Document this coupling explicitly and pin asyncio version.
    """
    # Safer approach: add a _ceiling attribute to TaskOrchestrator
    # and check it before _guarded() submits
```

**Recommended safer pattern:** Add an explicit `_max_concurrent: int` attribute to `TaskOrchestrator` that `_guarded()` checks via a soft gate, rather than mutating semaphore internals:

```python
class TaskOrchestrator:
    def __init__(self, max_concurrent: int = 5, ...):
        self._max_concurrent = max_concurrent  # mutable ceiling
        ...

    async def _guarded(self, name, coro, is_oathnet):
        if len(self._registry) >= self._max_concurrent:
            raise RuntimeError(f"Concurrency ceiling {self._max_concurrent} reached")
        # ... proceed with semaphore acquisition
```

The watchdog then calls `orchestrator.set_ceiling(2)` for REDUCED and `orchestrator.set_ceiling(0)` (reject all) for CRITICAL.

### Anti-Patterns to Avoid

- **Watchdog as a separate thread:** Adds context switching overhead on 1vCPU. Use asyncio task.
- **Polling interval < 10s:** WAL checkpoint and psutil calls are not free. 30s is appropriate; 5s would add measurable CPU overhead.
- **Calling `cancel_all()` without `gather(return_exceptions=True)`:** Cancellation errors will surface as unhandled exceptions. Always gather with `return_exceptions=True`.
- **Setting `stop_grace_period` without `--timeout-graceful-shutdown`:** uvicorn may wait indefinitely for hung connections before calling lifespan shutdown, consuming the grace window.
- **Using bare `_agents_paused: bool` for three-mode state:** The current implementation conflates REDUCED and CRITICAL into a single flag. The new design needs the enum.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Memory metrics | Custom /proc parsing | `psutil.virtual_memory()` | Cross-platform, already imported |
| Process RSS | Manual /proc/self/status parse | `psutil.Process().memory_info().rss` | Already used in /health today |
| WAL file size | SQLite pragma | `Path(db_path + "-wal").stat().st_size` | Simpler, no DB round-trip needed |
| Uptime | Clock arithmetic from os.stat | `time.time() - psutil.Process().create_time()` | One line, accurate |
| Semaphore introspection | Complex counter | `sem._value` or explicit `_max_concurrent` attribute | See Pattern 6 above |

**Key insight:** 90% of F8 is wiring existing components. The only new code is `watchdog.py` (~80 lines) and `/health` field additions (~10 lines). The non-trivial work is the singleton orchestrator wiring.

---

## Common Pitfalls

### Pitfall 1: Orchestrator is Per-Search, Not Singleton
**What goes wrong:** `/health` reports `active_tasks: 0` always because there's no shared orchestrator to query.
**Why it happens:** Phase 05 explicitly deferred wiring TaskOrchestrator into `_stream_search`. The orchestrator is built but not used in production search flow.
**How to avoid:** Create singleton in `orchestrator.py`, import it in both `main.py` (`/health` reads) and `_stream_search` (submits tasks). Update `_stream_search` to call `singleton.submit()` instead of running modules directly.
**Warning signs:** `active_tasks` is always 0 in `/health` during a scan.

### Pitfall 2: Docker Stop Grace Period Too Short
**What goes wrong:** `docker stop nexus-osint` sends SIGKILL after 10s, killing the process mid-shutdown. Write queue not fully drained — last search log entry lost.
**Why it happens:** Docker default `stop_grace_period` is 10s. Our shutdown sequence needs up to ~17s.
**How to avoid:** Add `stop_grace_period: 35s` to the `nexus` service in `docker-compose.yml`.
**Warning signs:** Search audit logs missing last entry after restart; `docker stop` completes instantly (SIGKILL).

### Pitfall 3: Watchdog Crashes Stop Health Endpoint
**What goes wrong:** An unhandled exception in the watchdog loop propagates up, cancelling the background task. Subsequent `/health` calls still work but memory thresholds are no longer enforced.
**Why it happens:** `asyncio.create_task()` swallows exceptions silently unless retrieved from the task.
**How to avoid:** Wrap the poll iteration in `try/except Exception: logger.exception(...)` and continue. Only `CancelledError` should propagate.
**Warning signs:** Memory climbs past 85% but degradation mode stays NORMAL.

### Pitfall 4: Semaphore Ceiling Reduction Race Condition
**What goes wrong:** Reducing the ceiling while tasks are mid-execution doesn't cancel in-flight tasks — they continue. New submissions are blocked, but semaphore `_value` reflects in-progress acquisitions.
**Why it happens:** Semaphore is a counting mechanism, not a preemptive canceller.
**How to avoid:** Use the soft-gate `_max_concurrent` pattern (Pattern 6) rather than mutating semaphore internals. Accept that in-flight tasks complete; only new submissions are throttled.
**Warning signs:** After calling `set_ceiling(2)`, the orchestrator still has 5 active tasks for 30s until they finish.

### Pitfall 5: WAL File Non-Existence Treated as Error
**What goes wrong:** If SQLite has checkpointed (WAL file deleted/zeroed), `Path.stat()` raises `FileNotFoundError`, crashing `/health`.
**Why it happens:** WAL file only exists when there are uncommitted pages. A clean checkpoint removes it.
**How to avoid:** `wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0`
**Warning signs:** `/health` returns 500 after a clean database state.

### Pitfall 6: `_agents_paused` Global Conflicts With Singleton Orchestrator
**What goes wrong:** After introducing a singleton orchestrator, both `_agents_paused` (global bool in main.py) and `orchestrator._max_concurrent` control degradation independently. They can disagree.
**Why it happens:** `_agents_paused` was the original degradation mechanism; the new orchestrator has its own ceiling.
**How to avoid:** Remove `_agents_paused` from main.py. Let `DegradationMode` on the watchdog/orchestrator be the single source of truth. The `/health` endpoint reads from the orchestrator, not a separate global.
**Warning signs:** `/health` reports `agents_paused: false` but `degradation_mode: critical`.

---

## Code Examples

### /health Endpoint — Target Shape
```python
# Source: codebase analysis + CLAUDE.md F8 requirements
@app.get("/health")
@app.head("/health")
@limiter.limit(RL_READ_LIMIT)
async def health(request: Request):
    proc   = psutil.Process()
    mem    = psutil.virtual_memory()
    swap   = psutil.swap_memory()
    cpu    = psutil.cpu_percent(interval=0.1)
    orch   = get_orchestrator()

    wal_path = Path(str(AUDIT_DB) + "-wal")
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0

    uptime_s = round(time.time() - proc.create_time(), 1)

    degradation = orch.degradation_mode  # DegradationMode enum

    return {
        "status":                degradation.value,           # "normal" / "reduced" / "critical"
        "version":               "3.0.0",
        "timestamp":             datetime.now(timezone.utc).isoformat(),
        "uptime_s":              uptime_s,
        "rss_mb":                round(proc.memory_info().rss / 1024 / 1024, 1),
        "memory_pct":            mem.percent,
        "memory_used_mb":        round(mem.used / 1024 / 1024, 1),
        "swap_used_mb":          round(swap.used / 1024 / 1024, 1),
        "cpu_pct":               cpu,
        "active_tasks":          orch.active_count,
        "semaphore_slots_free":  orch.semaphore_slots_free,   # new property
        "wal_size_bytes":        wal_size,
        "cache_entries":         len(_api_cache),
        "degradation_mode":      degradation.value,
    }
```

### Singleton Orchestrator — get_orchestrator()
```python
# api/orchestrator.py — add after class definition
import threading
_singleton_lock = threading.Lock()
_singleton: TaskOrchestrator | None = None

def get_orchestrator() -> TaskOrchestrator:
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = TaskOrchestrator()
    return _singleton
```

### Semaphore Slots Free Property
```python
# In TaskOrchestrator class
@property
def semaphore_slots_free(self) -> int:
    """Free slots in the global semaphore. Uses internal _value — no public API."""
    return self._global_sem._value  # confirmed: asyncio.Semaphore._value tracks available count
```

### docker-compose.yml — Stop Grace Period
```yaml
services:
  nexus:
    stop_grace_period: 35s          # ADD: default 10s insufficient for db flush
    command: >
      uvicorn api.main:app
        --host 0.0.0.0
        --port 8000
        --timeout-graceful-shutdown 30   # ADD: uvicorn waits max 30s before forcing
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `@asynccontextmanager lifespan` | Phase 07 | Already done — no regression |
| Per-request orchestrator | Singleton orchestrator | Phase 10 (this phase) | Enables global active_count for /health |
| Boolean `_agents_paused` | `DegradationMode` enum (NORMAL/REDUCED/CRITICAL) | Phase 10 (this phase) | Structured three-mode degradation |
| 10s docker grace period | 35s stop_grace_period | Phase 10 (this phase) | Prevents SIGKILL mid-flush |

---

## Open Questions

1. **Wiring singleton orchestrator into `_stream_search`**
   - What we know: `_stream_search` (~400 lines) runs modules directly with individual `asyncio.create_task()` calls or direct `await`s — not through the orchestrator. Confirmed: zero `TaskOrchestrator` imports in `main.py`.
   - What's unclear: The exact refactor scope needed to wire `singleton.submit()` into the 400-line function without regressions.
   - Recommendation: Plan this as a separate sub-task (Wave 1). It is the highest-complexity item in this phase. Read `_stream_search` fully before planning.

2. **Semaphore ceiling reduction — hard vs soft gate**
   - What we know: `asyncio.Semaphore._value` is accessible but internal. Direct mutation is unsafe under concurrent access.
   - What's unclear: Whether the soft-gate (`_max_concurrent` check before submission) is sufficient for the REDUCED mode use case.
   - Recommendation: Use soft-gate (`_max_concurrent` attribute on orchestrator) — safer than mutating semaphore internals. Document the semantics explicitly: ceiling change is prospective, not retroactive.

3. **`_agents_paused` removal backward compatibility**
   - What we know: `_agents_paused` is used in the existing `/health` response and in `_stream_search` (if it checks it before running modules — needs verification).
   - What's unclear: Whether any frontend JS reads `agents_paused` field specifically.
   - Recommendation: Keep `agents_paused` as a derived field in `/health` response for backward compatibility (`"agents_paused": degradation != DegradationMode.NORMAL`), but derive it from the new enum rather than the old bool.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| psutil | Watchdog + /health | Yes | 5.9.x | — |
| asyncio (stdlib) | Watchdog loop | Yes | Python 3.12 stdlib | — |
| pathlib (stdlib) | WAL size inspection | Yes | Python 3.12 stdlib | — |
| Docker stop_grace_period | Graceful shutdown | Yes (compose config only) | N/A — config change | — |

**No missing dependencies.** All required tools are available.

---

## Project Constraints (from CLAUDE.md)

All directives from CLAUDE.md that constrain this phase:

| Directive | Impact on Phase 10 |
|-----------|-------------------|
| n8n-mcp OUT OF SCOPE — use internal FastAPI + psutil only | Watchdog must be pure asyncio + psutil, no external alerting |
| `asyncio.Semaphore(max=5)` is the absolute ceiling | Watchdog reduces ceiling dynamically but never exceeds 5 |
| RAM resting < 200MB; alert > 400MB; critical > 85% | Watchdog thresholds exactly match these values |
| `except Exception` genérico proibido | Watchdog loop: only `except Exception` in the outermost `try/except Exception: logger.exception(...)` in a background loop — per CLAUDE.md this is acceptable in the background watchdog (similar rationale to `_guarded()` in orchestrator) |
| Docker memory limit: 800m | Health endpoint must account for container-level limit, not just OS-level |
| Graceful shutdown must complete < 35s | `stop_grace_period: 35s` in docker-compose.yml |
| Code completo — sem pseudo-código, placeholders, TODOs sem implementação | All code in plan must be complete and runnable |
| Sem `asyncio.create_task()` sem registry | Watchdog task must be saved to a variable and cancelled in lifespan shutdown |
| CLAUDE.md protected — no modification without approval | Not relevant to this phase |
| Brand Amber/Noir — no frontend changes without approval | This phase is backend-only; no frontend changes |
| Logs: nunca logar PII ou dados do alvo | Watchdog logs only memory/CPU percentages — no user data |

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection (`api/main.py` lines 1644-1712, `api/orchestrator.py`, `api/db.py`) — existing /health implementation, orchestrator API, DB shutdown sequence
- `api/main.py` lifespan function (lines 223-237) — current shutdown sequence confirmed
- `docker-compose.yml` — confirmed no `stop_grace_period`, confirms 10s default is in effect
- pytest.ini — confirmed `nyquist_validation: false` → Validation Architecture section skipped
- Python stdlib docs (asyncio.Semaphore, signal) — verified SIGTERM available on Windows/Linux

### Secondary (MEDIUM confidence)
- Uvicorn 0.30.6 source (`uvicorn.server.Server.shutdown`) — verified SIGTERM → lifespan shutdown flow; `--timeout-graceful-shutdown` flag confirmed
- psutil verified working in project environment — `psutil.Process().memory_info()` tested directly

### Tertiary (LOW confidence)
- `asyncio.Semaphore._value` internal attribute — verified accessible via runtime test but undocumented. Recommendation: use soft-gate pattern instead.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, versions verified
- Architecture: HIGH — based on direct codebase inspection, no speculation
- Pitfalls: HIGH — derived from actual code state (orchestrator not wired, grace period missing)
- Open questions: MEDIUM — `_stream_search` internals require full read before planning

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable stack, no fast-moving deps)
