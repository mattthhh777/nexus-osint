---
phase: 10-f8-health-monitoring
plan: 01
status: complete
completed_at: "2026-04-08"
---

# Plan 10-01 Summary — Singleton + DegradationMode + soft-gate

## Deliverables

- `api/orchestrator.py` updated with all Phase 10 additions, preserving 100% of existing API.

## Implementation Notes

### Entry method where soft-gate was added

`submit()` — the public method that creates the task. Soft-gate check is inserted before `asyncio.create_task(...)`.

**Key design decision:** soft-gate fires only when `_max_concurrent < _initial_ceiling` (watchdog has explicitly reduced the ceiling). When in NORMAL mode (`_max_concurrent == _initial_ceiling`), the Semaphore queues tasks as before — preserving compatibility with the per-search pattern (submit 10 modules, max 5 run concurrently via semaphore).

### active_count property

Already existed as `@property def active_count(self) -> int: return len(self._registry)`. No addition needed.

### _global_sem preserved

Confirmed: `asyncio.Semaphore(max_concurrent)` unchanged. Soft-gate is purely additive.

### Singleton pattern

Module-level `_singleton` + `threading.Lock` (double-checked locking). `reset_orchestrator_for_tests()` clears singleton for test isolation.

## Verification

```
python -c "from api.orchestrator import TaskOrchestrator, DegradationMode, get_orchestrator, reset_orchestrator_for_tests; ..."
→ OK — all assertions passed

pytest tests/ -k orchestrator -x -q
→ 6 passed, 56 deselected
```

## Files modified

- `api/orchestrator.py` — imports (enum, threading), DegradationMode enum, `__init__` additions, new properties/methods, singleton at bottom
