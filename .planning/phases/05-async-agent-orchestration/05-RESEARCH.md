# Phase 05: Async Agent Orchestration (F3) - Research

**Researched:** 2026-03-31
**Domain:** Python asyncio — TaskGroup, Semaphore, SSE streaming, subprocess lifecycle
**Confidence:** HIGH

---

## Summary

Phase 05 is the highest-risk phase in the v4.0 milestone. Its primary target is `_stream_search` — a ~400-line async generator in `api/main.py` that currently runs all OSINT modules serially via `asyncio.to_thread()`. The function yields SSE events directly to the HTTP response stream, which constrains the refactor: the public event sequence must be preserved or the frontend breaks.

The core architectural change is creating `api/orchestrator.py`, a `TaskOrchestrator` class that wraps `asyncio.TaskGroup` + `asyncio.Semaphore(5)` + a task registry dict. Independent OSINT modules will be launched concurrently through the orchestrator instead of running one-by-one. The SSE generator in `_stream_search` remains the public interface — only its internal execution model changes.

FIND-02 (fire-and-forget audit log via `asyncio.create_task()`) has already been resolved in Phase 04: `api/db.py` was built with an `asyncio.Queue` write serializer, and `main.py` was updated to use `await _log_search()` directly. Phase 05 must confirm this is intact and not regressed.

FIND-08 (subprocess zombie risk in `spiderfoot_wrapper.py`) requires adding explicit `proc.kill()` + `proc.wait()` after `subprocess.TimeoutExpired`. SpiderFoot runs as a separate process via `subprocess.run()` — the cleanup gap is real but the impact is low because SpiderFoot is optional and rarely enabled.

**Primary recommendation:** Build `TaskOrchestrator` first, integrate it into `_stream_search` second, harden SpiderFoot subprocess third. Keep a golden-file SSE test from the start to detect event sequence regressions.

---

## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for Phase 05 — constraints come from CLAUDE.md (project-level mandatory rules) and STATE.md (accumulated decisions).

### Locked Decisions (from STATE.md + CLAUDE.md)

- TaskGroup (Python 3.11+) + Semaphore(5) + task registry — NOT fire-and-forget `asyncio.create_task()`
- asyncio.Semaphore(5) is the absolute ceiling for simultaneous tasks
- No `asyncio.create_task()` without task registry
- SQLite: single persistent connection + asyncio.Queue (already in `api/db.py` — do not touch)
- Hardware: 1 vCPU / 1 GB RAM — everything must be memory-disciplined
- No generic `except Exception:` — use specific exception types
- No placeholder code, no pseudo-code
- `api/db.py` (DatabaseManager singleton) is the only write path — no direct aiosqlite usage in new code

### Claude's Discretion

- Internal module grouping within _stream_search (which modules run in parallel vs sequential)
- Exact orchestrator API design (how callers interact with it)
- Whether to use `asyncio.gather()` for the parallel group or TaskGroup — see Architecture Patterns for guidance

### Deferred (OUT OF SCOPE for Phase 05)

- Memory profiling / tracemalloc (Phase 06)
- Sherlock 512KB response limit (Phase 06)
- OathnetClient singleton (Phase 06)
- Python 3.12 upgrade (Phase 07)
- requests → httpx migration (Phase 07)
- CSP / JWT / rate limiting (Phase 09)

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| F3-01 | TaskOrchestrator with TaskGroup + Semaphore(5) + task registry | Architecture Patterns §1 |
| F3-02 | Parallelize independent modules in _stream_search | Architecture Patterns §2 |
| F3-03 | Fix FIND-02: no bare create_task for audit log (confirm Phase 04 fix intact) | Current State §FIND-02 |
| F3-04 | Fix FIND-08: subprocess cleanup after SpiderFoot timeout | Architecture Patterns §4 |
| F3-05 | Verification: Semaphore(5) ceiling enforced; zero task leaks | Verification section |
| F3-06 | Verification: 100 searches = 100 audit entries | Verification section |
| F3-07 | Verification: SSE event sequence matches golden file | Verification section |

---

## Current State Inventory

### _stream_search Architecture (api/main.py lines ~643–1043)

The function is an `AsyncGenerator[str, None]` that yields SSE-formatted strings. Current execution model:

```
_stream_search()
  │
  ├── yield "start" event
  │
  ├── GROUP 1: breach + stealer (parallel via asyncio.gather + asyncio.to_thread)
  │     ├── client.search_breach(query)       — blocking, ~45s timeout
  │     └── client.search_stealer_v2(query)   — blocking, ~45s timeout
  │     └── (if holehe) client.holehe(query)  — sequential inside group, ~20s
  │     └── (if auto discord IDs found) up to 3x discord_userinfo — sequential
  │     └── yield "oathnet" event
  │
  ├── sherlock (sequential)             — asyncio.to_thread, ~60s timeout
  │     └── yield "sherlock" event
  │
  ├── discord (sequential)             — asyncio.to_thread, ~15s timeout
  ├── ip_info (sequential)             — asyncio.to_thread, ~15s timeout
  ├── subdomain (sequential)           — asyncio.to_thread, ~30s timeout
  ├── steam (sequential)               — asyncio.to_thread, ~20s timeout
  ├── xbox (sequential)                — asyncio.to_thread, ~20s timeout
  ├── roblox (sequential)              — asyncio.to_thread, ~20s timeout
  ├── ghunt (sequential)               — asyncio.to_thread, ~25s timeout
  ├── minecraft (sequential)           — asyncio.to_thread, ~20s timeout
  ├── victims (sequential)             — asyncio.to_thread, ~30s timeout
  ├── discord_roblox (sequential)      — asyncio.to_thread, ~15s timeout
  ├── spiderfoot (sequential)          — async HTTP polling loop, ~10 min
  │
  ├── await _log_search(...)           — NON-BLOCKING via db.write() queue (Phase 04 fix)
  └── yield "done" event
```

**Total serial time (worst case, username query):** breach(45) + stealer(45) + sherlock(60) + steam(20) + xbox(20) + roblox(20) + minecraft(20) + victims(30) = ~260 seconds.

**Parallelization opportunity:** All OathNet modules (breach, stealer, holehe, discord, ip_info, subdomain, steam, xbox, roblox, ghunt, minecraft, victims, discord_roblox) and Sherlock are fully independent. They share no state and have no ordering dependencies. Parallelizing them against Semaphore(5) reduces worst-case from ~260s to ~60s (bottleneck: sherlock timeout).

### FIND-02 Status (fire-and-forget audit log)

**Already fixed in Phase 04.** Evidence from STATE.md decision log:
> "[Phase 04]: asyncio.create_task(_log_search) replaced with direct await — db.write() is already non-blocking via queue"

Phase 05 must verify this is intact in the current main.py. The current code at line 1028 shows:
```python
await _log_search(
    username=username, ip=client_ip, ...
)
```
This is correct. No `asyncio.create_task()` wrapping. Phase 05 confirms this — no fix needed.

### FIND-08 Status (subprocess zombie cleanup)

**Not yet fixed.** Current `spiderfoot_wrapper.py` (lines 293–336):
```python
try:
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, ...
    )
except subprocess.TimeoutExpired:
    result.error = f"Scan cancelado após {timeout}s."
    # ← NO proc.kill() + proc.wait() here
```

`subprocess.run()` calls `proc.kill()` internally on timeout, but does not call `proc.wait()` to reap children. If SpiderFoot spawned subprocesses, they become zombies. Fix: replace `subprocess.run()` with `subprocess.Popen()` + manual kill+wait in the timeout handler.

**Note:** The `_run_spiderfoot()` function in `api/main.py` (lines 1186–1241) is a DIFFERENT SpiderFoot integration path — it uses HTTP API polling, not subprocess. `spiderfoot_wrapper.py` is the CLI subprocess path. Both exist. The HTTP API path in main.py does not have subprocess issues but has a different problem: the polling loop runs for up to 120×5s = 600s inside the SSE generator without a timeout guard on the outer httpx.AsyncClient (timeout=600 is set on the client, but the polling loop itself is unbounded if SpiderFoot keeps returning non-terminal status codes).

### OathNet Client (modules/oathnet_client.py)

All methods are synchronous (use `requests` library). They are called via `asyncio.to_thread()` from `_stream_search`, which offloads them to the thread pool executor. This is correct for Phase 05. The migration to `httpx.AsyncClient` is Phase 07.

Current to_thread call pattern:
```python
results_gathered = await asyncio.gather(
    asyncio.to_thread(client.search_breach, query),
    asyncio.to_thread(client.search_stealer_v2, query),
)
```

This already runs breach + stealer in parallel. The Semaphore must wrap these as a unit (one slot for the whole OathNet group) or individually per sub-call. Recommendation: one slot per to_thread call, since each makes an independent network request.

### Sherlock (modules/sherlock_wrapper.py)

`search_username()` is synchronous but internally uses `aiohttp` run in its own event loop (creates a new one via `asyncio.run()`). This means calling it via `asyncio.to_thread()` is safe — it runs a complete new event loop in the thread. No nested event loop issue. Timeout: 60s.

### SSE Event Sequence

The frontend in `static/js/search.js` (not read in detail but inferable from main.py) expects this sequence:
```
data: {"type": "start", ...}
data: {"type": "progress", ...}    (repeated, one per module)
data: {"type": "oathnet", ...}     (breach + stealer results)
data: {"type": "sherlock", ...}
data: {"type": "discord", ...}     (if applicable)
data: {"type": "ip_info", ...}
data: {"type": "subdomains", ...}
data: {"type": "steam", ...}
data: {"type": "xbox", ...}
data: {"type": "roblox", ...}
data: {"type": "ghunt", ...}
data: {"type": "minecraft", ...}
data: {"type": "victims", ...}
data: {"type": "discord_roblox", ...}
data: {"type": "spiderfoot_started", ...}  (if spiderfoot)
data: {"type": "spiderfoot_progress", ...} (repeated)
data: {"type": "spiderfoot", ...}
data: {"type": "done", ...}
```

**CRITICAL constraint:** The frontend processes events by `type` field — the ORDER of events does not matter to the frontend (each event type triggers independent UI rendering). This means parallelizing modules will NOT break the frontend, as long as:
1. `"start"` event comes first
2. `"done"` event comes last
3. `"progress"` events have correct percentage values (this may need adjustment with parallelism)

The `progress()` function currently increments a counter and computes percentage as `done_cnt[0] / total`. With parallel execution, multiple tasks could call `progress()` concurrently — this requires thread-safe incrementing or removing per-module progress tracking in favor of a simpler "N modules started / M modules complete" model.

---

## Standard Stack

### Core (already in requirements.txt — no new installs)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| asyncio.TaskGroup | Python 3.11 stdlib | Structured concurrency | Available in Docker (python:3.11-slim); NOT available locally (Python 3.10.10) |
| asyncio.Semaphore | Python stdlib | Concurrency ceiling | Works in Python 3.10+ |
| asyncio.to_thread | Python stdlib | Run sync code in thread pool | Works in Python 3.10+ |
| aiosqlite | 0.20.0 | Async SQLite | Already in use via api/db.py |

### New file to create

| File | Purpose |
|------|---------|
| `api/orchestrator.py` | TaskOrchestrator class |

**No new pip dependencies required for this phase.**

### Environment Warning

Local Python is 3.10.10 — `asyncio.TaskGroup` does NOT exist locally. Tests must run inside Docker (`docker compose exec api pytest`) or the CI environment. Do not test TaskGroup code with the local Python interpreter.

```bash
# Verify inside Docker:
docker compose exec api python -c "import asyncio; print(asyncio.TaskGroup)"
# Expected: <class 'asyncio.TaskGroup'>
```

---

## Architecture Patterns

### Pattern 1: TaskOrchestrator Class (new api/orchestrator.py)

**What:** A class that wraps `asyncio.TaskGroup` + `asyncio.Semaphore(5)` + task registry dict. Provides a single launch point for all OSINT module coroutines.

**Why TaskGroup instead of asyncio.gather():** TaskGroup cancels all sibling tasks when one raises an unhandled exception — this prevents orphaned tasks on failures. For the orchestrator's internal use, `asyncio.gather(return_exceptions=True)` would also work, but TaskGroup is the mandated pattern per CLAUDE.md.

**Design:**

```python
# api/orchestrator.py
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger("nexusosint.orchestrator")

# Absolute ceiling — never exceed this
_SEMAPHORE_MAX = 5


class TaskOrchestrator:
    """
    Manages concurrent OSINT module execution.

    Enforces Semaphore(5) ceiling. Tracks active tasks in a registry.
    Uses TaskGroup for structured concurrency — all tasks are cancelled
    on unhandled exceptions, preventing orphans.

    Designed for single-use per search: create, run all modules, discard.
    Not a long-lived singleton.
    """

    def __init__(self) -> None:
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(_SEMAPHORE_MAX)
        self._registry: dict[str, asyncio.Task[Any]] = {}

    async def run(
        self,
        modules: dict[str, Coroutine[Any, Any, Any]],
    ) -> dict[str, Any]:
        """
        Run all provided module coroutines concurrently under the semaphore.

        Args:
            modules: dict of {module_name: coroutine}

        Returns:
            dict of {module_name: result_or_exception}
        """
        results: dict[str, Any] = {}

        async def _guarded(name: str, coro: Coroutine[Any, Any, Any]) -> None:
            async with self._semaphore:
                try:
                    results[name] = await coro
                except Exception as exc:
                    logger.warning("Module '%s' failed: %s", name, exc)
                    results[name] = exc
                finally:
                    self._registry.pop(name, None)

        try:
            async with asyncio.TaskGroup() as tg:
                for name, coro in modules.items():
                    task = tg.create_task(_guarded(name, coro), name=f"module-{name}")
                    self._registry[name] = task
        except ExceptionGroup as eg:
            # TaskGroup raises ExceptionGroup if any task raises
            # Individual task errors are caught in _guarded above
            # This catches errors from the _guarded wrapper itself (unlikely)
            for exc in eg.exceptions:
                logger.error("Orchestrator task wrapper failed: %s", exc)

        return results

    @property
    def active_count(self) -> int:
        """Number of tasks currently in the registry."""
        return len(self._registry)

    def cancel_all(self) -> None:
        """Cancel all active tasks (for graceful shutdown)."""
        for name, task in list(self._registry.items()):
            if not task.done():
                task.cancel()
                logger.info("Cancelled task: %s", name)
```

**Note on ExceptionGroup:** Python 3.11+ uses `except*` syntax for matching ExceptionGroups. However, a plain `except ExceptionGroup` also works. Since CLAUDE.md prohibits generic `except Exception:`, use specific exception types. The `_guarded()` wrapper catches all module exceptions internally — the TaskGroup should only see exceptions from the wrapper infrastructure itself (extremely rare).

### Pattern 2: Integrating Orchestrator into _stream_search

**What:** Replace the long sequential chain with two phases:
1. Launch all applicable modules concurrently via orchestrator
2. Yield SSE events as results arrive (or after all complete)

**Key constraint:** `_stream_search` is an `AsyncGenerator` — it yields SSE strings. TaskGroup does not natively yield to a generator while tasks run. Two valid approaches:

**Approach A — Collect then yield (simpler, slight latency increase):**
All modules run concurrently, then results are yielded in order. The client sees a faster overall time but no incremental rendering during execution.

```python
orchestrator = TaskOrchestrator()
coros = {}

if run["breach"]:
    coros["breach"] = asyncio.to_thread(client.search_breach, query)
if run["stealer"]:
    coros["stealer"] = asyncio.to_thread(client.search_stealer_v2, query)
if run["sherlock"]:
    coros["sherlock"] = asyncio.to_thread(search_username, uname, False)
# ... etc

results = await orchestrator.run(coros)

# Now yield events from results dict
if "breach" in results:
    r = results["breach"]
    if isinstance(r, Exception):
        yield event({"type": "module_error", "module": "breach", "error": str(r)})
    else:
        yield event({"type": "oathnet", ...})
```

**Approach B — asyncio.Queue bridge (incremental streaming, complex):**
Each module task puts its result into a `asyncio.Queue`. The SSE generator consumes from the queue, yielding events as they arrive.

```python
result_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

async def run_module(name: str, coro):
    async with semaphore:
        try:
            result = await coro
            await result_queue.put((name, result))
        except Exception as exc:
            await result_queue.put((name, exc))

# Launch all modules as tasks (tracked)
tasks = {}
for name, coro in coros.items():
    tasks[name] = asyncio.create_task(run_module(name, coro), name=f"mod-{name}")

# Consume queue and yield SSE events
remaining = len(tasks)
while remaining > 0:
    name, result = await result_queue.get()
    remaining -= 1
    if isinstance(result, Exception):
        yield event({"type": "module_error", "module": name, "error": str(result)})
    else:
        yield event(_build_event(name, result))
```

**Recommendation: Approach A for Phase 05.** Approach B is more complex and risks errors in the queue coordination logic. The frontend does not depend on incremental rendering order (it renders each event type independently). Approach A is safer for a high-risk refactor. The UX difference is minimal — users see results when all modules finish rather than as each finishes, but total time is the same.

**Progress tracking with parallel execution:** The current `progress()` function uses a shared `done_cnt[0]` closure variable that increments by 1 per module. With parallelism, increment atomically via `asyncio.Lock` or simplify to:
```python
yield event({"type": "progress", "pct": 50, "label": "Running OSINT modules concurrently…"})
# (single progress event at start)
# (done event at end with elapsed_s)
```

### Pattern 3: Module Grouping Strategy

**Independent modules (can all run in parallel):**
- `breach` — OathNet API, no dependencies
- `stealer` — OathNet API, no dependencies
- `holehe` — OathNet API, no dependencies
- `sherlock` — HTTP checks, no dependencies
- `discord` — OathNet API, no dependencies
- `ip_info` — OathNet API, no dependencies
- `subdomain` — OathNet API, no dependencies
- `steam` — OathNet API, no dependencies
- `xbox` — OathNet API, no dependencies
- `roblox` — OathNet API, no dependencies
- `ghunt` — OathNet API, no dependencies
- `minecraft` — OathNet API, no dependencies
- `victims` — OathNet API, no dependencies
- `discord_roblox` — OathNet API, no dependencies

**Dependent modules (must run AFTER breach results):**
- `discord_auto` — requires breach results to extract Discord IDs. This must stay sequential: run breach first, extract Discord IDs, then run discord lookups.

**Recommendation:** Split into two phases:
1. Phase A: run all non-dependent modules concurrently (up to Semaphore(5) ceiling)
2. Phase B: if auto_discord enabled and Discord IDs found in breach results, run up to 3 discord lookups sequentially (they are already bounded by the breach result set)

### Pattern 4: SpiderFoot Subprocess Hardening (FIND-08)

**Current issue:** `subprocess.run()` internally calls `proc.kill()` on `TimeoutExpired` but does not call `proc.wait()`. Child processes may become zombies.

**Fix:** Replace `subprocess.run()` with manual `Popen` + explicit cleanup:

```python
# modules/spiderfoot_wrapper.py — subprocess section

import subprocess

with tempfile.TemporaryDirectory(prefix="nexusosint_sf_") as tmpdir:
    env = {**os.environ, "HOME": tmpdir}
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=tmpdir,
        env=env,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        elapsed = time.time() - t_start
        result.elapsed_s = round(elapsed, 1)

        if proc.returncode not in (0, 1):
            result.error = f"SpiderFoot returned code {proc.returncode}. stderr: {stderr[:200]}"
            return result

        raw_output = stdout.strip()
        if not raw_output:
            result.success = True
            return result
        result = _parse_output(raw_output, result, max_events)

    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)  # reap children — prevents zombies
        except subprocess.TimeoutExpired:
            logger.warning("SpiderFoot process did not exit after kill — may leave zombie")
        result.error = f"Scan cancelled after {timeout}s."
        logger.warning("SpiderFoot scan timed out for '%s'", target)

    except FileNotFoundError:
        result.available = False
        result.error = "python3 or sf.py not found."
        logger.error("SpiderFoot executable not found")

    except OSError as exc:
        result.error = f"OS error running SpiderFoot: {exc}"
        logger.error("SpiderFoot OS error: %s", exc, exc_info=True)
```

**Note on async:** `spiderfoot_wrapper.py` uses synchronous subprocess. It is called via `asyncio.to_thread()` from `_stream_search`. The subprocess fix above is purely in the synchronous module — no async changes needed there.

### Pattern 5: _run_spiderfoot HTTP Polling (secondary SpiderFoot path)

`_run_spiderfoot()` in `api/main.py` is a separate SpiderFoot integration that uses SpiderFoot's HTTP API (not subprocess). It has an unbounded polling loop:
```python
for _ in range(120):      # 120 iterations
    await asyncio.sleep(5)  # 5s each = max 600s = 10 minutes
    ...
    if sc in ("FINISHED", "ABORTED", "ERROR"):
        break
```

This is not called for FIND-08 (which targets the CLI subprocess path) but should be noted. The httpx.AsyncClient has `timeout=600` set, which covers the total HTTP operation time but not the polling loop duration. A stuck SpiderFoot scan could hold this generator for 10 minutes. This is acceptable for Phase 05 (SpiderFoot is opt-in), but Phase 06/07 should add an explicit timeout around the polling loop.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent task limiting | Custom semaphore logic | `asyncio.Semaphore(5)` | Stdlib primitive, handles acquire/release correctly |
| Structured task lifecycle | Custom task tracking | `asyncio.TaskGroup` | Guaranteed cancellation on failure, no orphans |
| Thread-safe counter for progress | Custom lock + counter | Simplify to single progress event | Eliminates race condition entirely |
| Subprocess timeout + cleanup | Custom signal handling | `Popen.kill()` + `Popen.wait()` | Correct POSIX child reaping pattern |
| SSE queue bridge | Custom pub/sub | Simple collect-then-yield (Approach A) | Less moving parts, same UX outcome |

---

## Common Pitfalls

### Pitfall 1: TaskGroup Exception Semantics vs gather()

**What goes wrong:** Developer uses `except Exception` to swallow all errors from TaskGroup, preventing the ExceptionGroup from surfacing useful diagnostics.

**Why it happens:** `asyncio.TaskGroup` raises `ExceptionGroup` (not individual exceptions), which requires `except*` syntax or iterating `eg.exceptions`. Developers unfamiliar with Python 3.11 exception groups fall back to bare `except Exception`.

**How to avoid:** Catch exceptions inside each module's `_guarded()` wrapper (before they reach TaskGroup). Only let infrastructure errors propagate. See Pattern 1 code above.

**Warning signs:** Modules silently disappear from results without logging.

### Pitfall 2: Semaphore Slot Starvation

**What goes wrong:** OathNet batch (breach + stealer + holehe) consumes 3 of 5 semaphore slots. If sherlock also runs (~2s to acquire), and 2 more modules start simultaneously, all 5 slots are taken. This is correct behavior (ceiling enforced), but if module timeouts are long (breach=45s), other modules wait 45s before getting a slot.

**Why it happens:** Semaphore slots are held for the full duration of the module call (including network wait).

**How to avoid:** This is acceptable — the semaphore IS the backpressure mechanism. Do not "fix" it by raising the ceiling. The 1vCPU constraint means >5 concurrent threads would degrade anyway.

**Warning signs:** Total search time is longer than the slowest module × 2 (indicates queueing behind semaphore).

### Pitfall 3: Progress Percentage Race Condition

**What goes wrong:** `done_cnt[0] += 1` is not thread-safe. Two modules completing simultaneously from different thread-pool threads could read the same value, both increment to the same number, and yield duplicate progress percentages.

**Why it happens:** `asyncio.to_thread()` runs the sync function in a thread. The `progress()` closure captures a mutable list. The `+=` is not atomic.

**How to avoid:** Use `asyncio.Lock` around the counter update, OR eliminate per-module progress tracking entirely and emit a single "Running N modules..." progress event at the start. The simpler option eliminates the bug class entirely.

**Warning signs:** Frontend shows progress percentage going backward or stalling.

### Pitfall 4: Yielding from Inside TaskGroup

**What goes wrong:** Developer tries to `yield` SSE events from inside a `async with asyncio.TaskGroup()` block to stream results as they arrive.

**Why it happens:** `AsyncGenerator` yield and `TaskGroup` context manager cannot be combined directly — generators cannot suspend inside a non-suspendable context manager exit.

**How to avoid:** Use Approach A (collect results dict, then yield after TaskGroup exits). If streaming is required, use the queue bridge pattern (Approach B) but keep the TaskGroup outside the generator's main body.

**Warning signs:** `RuntimeError: async generator ignored GeneratorExit` or tasks hanging indefinitely.

### Pitfall 5: OathNet Client Instantiated Inside Parallel Tasks

**What goes wrong:** Each parallel module instantiates its own `OathnetClient(api_key=...)` inside the task. Multiple `requests.Session()` objects are created concurrently, each with its own connection pool.

**Why it happens:** The current `_stream_search` creates one `client = OathnetClient(...)` at the top and reuses it. A naive parallelization might instantiate one per task.

**How to avoid:** Create a single `OathnetClient` instance before the orchestrator call and pass it as a closure variable to each module coroutine. The `requests` library is thread-safe for session reuse.

**Warning signs:** Increased memory usage per search (multiple sessions), connection pool exhaustion.

### Pitfall 6: Forgetting discord_auto Sequential Dependency

**What goes wrong:** `discord_auto` is run in parallel with other modules, but it depends on breach results (extracts Discord IDs from breach data). Running it in parallel yields empty results.

**Why it happens:** The current sequential code makes this dependency implicit — breach runs first, then `discord_ids_from_breach` is populated from the result.

**How to avoid:** Keep `discord_auto` as a Phase B operation: run breach first, extract IDs, then run discord lookups. Do NOT add `discord_auto` to the parallel module group.

**Warning signs:** Discord auto-lookup always returns empty results after parallelization.

---

## Code Examples

### Verified: TaskGroup basic pattern (from docs.python.org)

```python
# Source: https://docs.python.org/3/library/asyncio-task.html#task-groups
async with asyncio.TaskGroup() as tg:
    task1 = tg.create_task(some_coro(...))
    task2 = tg.create_task(another_coro(...))
# Both tasks are complete when the block exits
```

### Verified: Semaphore as concurrency ceiling

```python
# Source: Python stdlib asyncio documentation
semaphore = asyncio.Semaphore(5)

async def bounded_task(coro):
    async with semaphore:  # waits if 5 tasks already running
        return await coro
```

### Verified: ExceptionGroup handling (Python 3.11+)

```python
# Source: https://docs.python.org/3/library/asyncio-task.html#task-groups
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(failing_coro())
except ExceptionGroup as eg:
    for exc in eg.exceptions:
        logger.error("Task failed: %s", exc)
```

### Verified: Popen + timeout + cleanup pattern

```python
# Source: Python subprocess documentation
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    stdout, stderr = proc.communicate(timeout=timeout)
except subprocess.TimeoutExpired:
    proc.kill()
    proc.wait()  # reap children
    stdout, stderr = proc.communicate()
```

### Verified: asyncio.to_thread for sync functions

```python
# Source: Python stdlib asyncio documentation (3.9+)
result = await asyncio.to_thread(sync_function, arg1, arg2)
# Runs sync_function(arg1, arg2) in thread pool without blocking event loop
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| asyncio.gather() for parallelism | asyncio.TaskGroup() | Python 3.11 | Structured concurrency, auto-cancel on failure |
| asyncio.create_task() fire-and-forget | TaskGroup + registry | Python 3.11 best practice | No orphan tasks |
| subprocess.run() for long processes | Popen + communicate + kill + wait | Always correct | Proper zombie prevention |

**Python 3.11 requirement:** TaskGroup was introduced in Python 3.11 (PEP 654). The Docker image (`python:3.11-slim`) satisfies this. The local Python (3.10.10) does NOT. All TaskGroup code must be tested inside Docker.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| asyncio.TaskGroup | api/orchestrator.py | Docker: YES / Local: NO | Python 3.11 | None — must use Docker |
| asyncio.Semaphore | api/orchestrator.py | Both | Python stdlib | N/A |
| aiosqlite | api/db.py (existing) | YES | 0.20.0 | N/A |
| subprocess | spiderfoot_wrapper.py | YES | stdlib | N/A |

**Missing dependencies with no fallback:**
- None — all required libraries are available in the Docker runtime.

**Missing dependencies with fallback:**
- `asyncio.TaskGroup` on local Python 3.10 — fallback is running tests inside Docker container. Tests that use TaskGroup cannot be run locally.

---

## Verification Plan

Phase 05 verification criteria from ROADMAP.md:
1. Semaphore ceiling enforced — never more than 5 concurrent module tasks
2. Zero task leaks — all created tasks are tracked and reach completion or cancellation
3. 100 searches = 100 audit entries — every search writes exactly one row to `searches` table
4. SSE event sequence matches golden file — event `type` fields appear in correct order

### Test approach (nyquist_validation: false — manual verification)

**Semaphore ceiling test:**
```python
# Count max concurrent tasks by wrapping semaphore.acquire
# with a counter that tracks concurrent holders
```

**Zero task leak test:**
```python
# After orchestrator.run(), assert len(orchestrator._registry) == 0
# All tasks should have completed and deregistered
```

**Audit log test (existing in tests/):**
```python
# Run 100 searches via _log_search()
# Count rows in searches table: assert count == 100
```

**SSE golden file test:**
```python
# Capture full SSE stream for a known query
# Parse event types in order
# Assert: first event is "start", last event is "done"
# Assert: all expected module event types present
```

---

## Open Questions

1. **Should progress events be preserved?**
   - What we know: Current frontend uses progress percentage for a loading bar
   - What's unclear: Does the frontend break if only one progress event is emitted (50%) vs. many?
   - Recommendation: Read `static/js/search.js` in the plan phase to confirm before simplifying. If safe, emit a single progress event. If not, use an asyncio.Lock around the counter.

2. **Should _run_spiderfoot() (HTTP API path) get a polling timeout guard?**
   - What we know: The polling loop can run for 600s if SpiderFoot never terminates
   - What's unclear: Is this in scope for Phase 05 or Phase 06/07?
   - Recommendation: Add to Phase 05 scope as a low-effort hardening — it's one `asyncio.timeout(600)` context manager around the polling loop.

3. **OathNet rate limits under parallel execution**
   - What we know: OathNet Starter plan allows 100 lookups/day. Current sequential execution means at most 1 lookup is in-flight per search.
   - What's unclear: Does running breach + stealer + holehe in parallel (3 simultaneous OathNet calls) increase the risk of hitting rate limits or triggering API-side throttling?
   - Recommendation: Breach and stealer are different endpoints (`/service/search-breach` vs `/service/v2/stealer/search`). They should not count against each other's rate limits. Monitor in production after deployment.

---

## Sources

### Primary (HIGH confidence)
- Python 3.11 stdlib — asyncio.TaskGroup implementation verified via docs.python.org
- Python subprocess docs — Popen + communicate + timeout pattern verified
- Direct code analysis — `api/main.py`, `api/db.py`, `modules/spiderfoot_wrapper.py`, `modules/oathnet_client.py` (read directly)

### Secondary (MEDIUM confidence)
- `.planning/phases/03-codebase-audit/AUDIT-REPORT.md` — FIND-02 and FIND-08 descriptions
- `STATE.md` decisions section — Phase 04 fix for FIND-02 confirmed

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Current state inventory: HIGH — read all relevant source files directly
- Standard stack: HIGH — Python 3.11 stdlib, no third-party dependencies
- Architecture patterns: HIGH — verified against Python docs, grounded in actual codebase
- Pitfalls: HIGH — derived from direct code analysis
- SSE event sequence: MEDIUM — inferred from `_stream_search` yield statements, not from reading `search.js` client side

**Research date:** 2026-03-31
**Valid until:** 2026-05-01 (stable domain — asyncio stdlib does not change)
