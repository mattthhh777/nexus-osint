---
phase: 10-f8-health-monitoring
plan: 02
status: complete
completed_at: "2026-04-08"
---

# Plan 10-02 Summary — Watchdog + Lifespan + /health + _agents_paused elimination

## Deliverables

- `api/watchdog.py` — novo módulo criado
- `api/main.py` — lifespan, /health, /health/memory, search gate, _stream_search modificados

## Implementation Notes

### Lifespan function (lines ~225-248)

Watchdog task criado em startup:
```python
watchdog_task = asyncio.create_task(memory_watchdog_loop(), name="memory-watchdog")
```
Shutdown: cancel watchdog → cancel_all orchestrator → _db.shutdown() → oathnet close.

### AUDIT_DB constant

Confirmado: `AUDIT_DB = DATA_DIR / "audit.db"` (line 114). WAL path: `Path(str(AUDIT_DB) + "-wal")`.

### _agents_paused fully removed

`grep -c "_agents_paused" api/main.py` → **0**. Completamente removido:
- Declaração global removida (linha ~124)
- Bloco de mutação no /health removido
- Search gate substituído por `get_orchestrator().degradation_mode == DegradationMode.CRITICAL`
- /health/memory atualizado para usar `get_orchestrator().degradation_mode != DegradationMode.NORMAL`

### Search gate replacement

**Old (line ~779):** `if _agents_paused:`
**New:** `if get_orchestrator().degradation_mode == DegradationMode.CRITICAL:`

Only CRITICAL mode blocks new scans. REDUCED mode (ceiling=2) permits scans but with lower concurrency ceiling (soft-gate in orchestrator.submit).

### _stream_search refactor

Pattern chosen: **sentinel coroutine**. Reasons:
- _stream_search is sequential (~500 lines), no central "module loop"
- Full orchestrator.submit() per-module would require refactoring all OathNet calls
- Sentinel tracks the SEARCH (not individual modules) in the registry

Sentinel lifecycle:
1. Start: `asyncio.Event` created, `_search_sentinel()` submitted to `get_orchestrator().submit()`
2. Sentinel awaits the event → stays in registry → `active_count` shows non-zero
3. End: `_sentinel_done.set()` → sentinel returns → removed from registry

If ceiling reached (REDUCED mode at capacity): RuntimeError caught, search continues untracked. Warning logged.

### Sample /health response

```json
{
  "status": "healthy",
  "uptime_s": 2.1,
  "active_tasks": 0,
  "semaphore_slots_free": 5,
  "wal_size_bytes": 0,
  "degradation_mode": "normal"
}
```

## Verification

```
python -c "import api.main, api.watchdog, api.orchestrator"
→ imports OK

grep -c "_agents_paused" api/main.py
→ 0

pytest tests/ -x -q
→ 62 passed

TestClient /health → all 5 new fields present
```
