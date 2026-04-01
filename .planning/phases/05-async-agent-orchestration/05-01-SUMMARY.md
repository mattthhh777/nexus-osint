---
phase: 05-async-agent-orchestration
plan: "01"
subsystem: api/orchestrator
tags: [async, concurrency, semaphore, queue-bridge, task-registry, osint]
dependency_graph:
  requires: []
  provides: [TaskOrchestrator]
  affects: [api/main.py (_stream_search — future plan)]
tech_stack:
  added: []
  patterns: [dual-semaphore, asyncio-queue-bridge, tracked-create_task, guarded-wrapper]
key_files:
  created:
    - api/orchestrator.py
    - tests/test_orchestrator.py
  modified: []
decisions:
  - "D-02/D-03 enforced: tracked create_task + registry instead of TaskGroup — yield inside TaskGroup is impossible for SSE async generators"
  - "Semaphore acquisition order: _oathnet_sem first, then _global_sem — consistent ordering prevents deadlock"
  - "_guarded split into _guarded + _run_module for clarity: _guarded handles semaphore acquisition, _run_module handles execution and error delivery"
  - "CancelledError re-raised in _run_module — not swallowed — so cancel_all() gather() can collect it correctly"
metrics:
  duration_minutes: 2
  completed_date: "2026-04-01"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
requirements_met: [F3-01, F3-05]
---

# Phase 05 Plan 01: TaskOrchestrator Foundation Summary

**One-liner:** TaskOrchestrator with dual Semaphore(5/3), asyncio.Queue bridge, tracked create_task registry, and _guarded wrapper for per-module error isolation.

## What Was Built

`api/orchestrator.py` — a `TaskOrchestrator` class that provides the concurrency foundation for Phase 05. The class manages concurrent OSINT module execution with:

- **Global `asyncio.Semaphore(5)`** — hard ceiling across ALL module tasks
- **OathNet `asyncio.Semaphore(3)`** — scoped limit preventing OathNet modules from monopolizing all 5 global slots (prevents slot starvation for faster non-OathNet modules like Sherlock)
- **`asyncio.Queue` bridge** — each module pushes `(name, result_or_exception)` to the queue as it completes; the SSE generator in `_stream_search` will consume via `results()` to yield events incrementally
- **Task registry** (`self._registry: dict[str, asyncio.Task]`) — all launched tasks are tracked; deregistered in `finally` block on completion or failure
- **`cancel_all()`** — cancels active tasks, awaits gather for cleanup, drains residual queue items

`tests/test_orchestrator.py` — 6 unit tests proving all behavioral guarantees:

| Test | Behavior Proven |
|------|-----------------|
| `test_global_semaphore_ceiling` | Peak concurrent never exceeds 5 (10 modules submitted) |
| `test_oathnet_semaphore_scoped_limit` | Peak OathNet concurrent never exceeds 3 (5 OathNet modules) |
| `test_queue_delivery` | All 3 results arrive as correct `(name, value)` tuples |
| `test_module_error_delivered_to_queue` | ValueError delivered to queue — orchestrator survives |
| `test_registry_empty_after_completion` | `active_count == 0` after all tasks complete |
| `test_cancel_all_clears_registry` | 3 slow (10s) tasks cancelled in < 1s; registry empty |

## Decisions Made

### D-02/D-03: No asyncio.TaskGroup (locked)

Per CONTEXT.md decisions D-02 and D-03: `asyncio.TaskGroup` cannot be used because the `_stream_search` SSE generator must `yield` events as modules complete. Python generators cannot `yield` from inside a non-suspendable context manager exit (`TaskGroup.__aexit__`). The tracked `create_task` + registry pattern provides equivalent lifecycle management: all tasks are tracked, errors are isolated in `_guarded`, and `cancel_all()` provides structured cleanup.

### Semaphore acquisition order

OathNet modules acquire `_oathnet_sem` FIRST, then `_global_sem`. This consistent ordering is mandatory to prevent deadlock. If the order were reversed, a scenario where 5 global slots are held while 3 OathNet tasks wait for `_oathnet_sem` could deadlock against tasks holding `_oathnet_sem` waiting for `_global_sem`.

### _guarded split into two methods

The plan specified a single `_guarded()` method. Implementation split it into `_guarded()` (semaphore acquisition) and `_run_module()` (execution + queue push). This keeps each method focused and makes the CancelledError handling explicit: `_run_module` re-raises `CancelledError` so `cancel_all()`'s `gather()` can collect it cleanly, while catching all other exceptions and pushing them to the queue.

### CancelledError re-raised

`asyncio.CancelledError` is explicitly re-raised in `_run_module` rather than being swallowed as a generic exception. This is required for correct asyncio cancellation semantics — `cancel_all()` calls `gather()` which expects cancelled tasks to raise `CancelledError` (via `return_exceptions=True`).

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as designed.

### Implementation Detail: _guarded split

The plan described `_guarded()` as doing both semaphore acquisition and module execution. Implementation split this into `_guarded()` + `_run_module()` for clarity. This is a structural improvement, not a functional deviation. The behavior is identical.

## Integration Points (for next plan)

The `TaskOrchestrator` is designed for single-use per search:

```python
# In _stream_search (future plan):
orchestrator = TaskOrchestrator()
orchestrator.submit("breach", asyncio.to_thread(client.search_breach, query), is_oathnet=True)
orchestrator.submit("sherlock", asyncio.to_thread(search_username, query, False), is_oathnet=False)
# ... more submit() calls ...

async for name, result in orchestrator.results():
    if isinstance(result, Exception):
        yield event({"type": "module_error", "module": name, "error": str(result)})
    else:
        yield event(_build_event_for(name, result))
```

`discord_auto` must remain sequential (runs after breach results — D-07). It should NOT be submitted to the orchestrator.

## Test Results

```
6 passed in 0.38s (Python 3.10.10, local)
```

All tests pass on local Python 3.10 because the implementation uses only `asyncio.Semaphore`, `asyncio.Queue`, and `asyncio.create_task` — no `asyncio.TaskGroup` (Python 3.11 only).

## Known Stubs

None — all methods are fully implemented with no placeholders.

## Self-Check: PASSED

- [x] `api/orchestrator.py` exists
- [x] `tests/test_orchestrator.py` exists
- [x] Commit `ac2b81c` exists
- [x] `class TaskOrchestrator` present
- [x] `asyncio.Semaphore(5)` present (as `GLOBAL_CONCURRENCY_LIMIT = 5` + `asyncio.Semaphore(max_concurrent)`)
- [x] `asyncio.Semaphore(3)` present (as `OATHNET_CONCURRENCY_LIMIT = 3` + `asyncio.Semaphore(max_oathnet)`)
- [x] `asyncio.Queue` present
- [x] `asyncio.TaskGroup` NOT used (only in docstring comment)
- [x] Logger `nexusosint.orchestrator` used
- [x] 6 tests pass
