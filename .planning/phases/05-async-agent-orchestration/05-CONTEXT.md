# Phase 05: Async Agent Orchestration (F3) - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace serial OSINT module execution in `_stream_search` with concurrent orchestration via a `TaskOrchestrator` class. Create `api/orchestrator.py` with Semaphore-based concurrency control and task registry. Harden SpiderFoot subprocess cleanup (FIND-08). Verify Phase 04 FIND-02 fix is intact.

</domain>

<decisions>
## Implementation Decisions

### SSE Streaming Model
- **D-01:** Use **queue bridge pattern** (incremental streaming) — NOT collect-then-yield. Each module puts its result into an `asyncio.Queue` as it finishes. The SSE generator in `_stream_search` consumes the queue and yields events live, so the frontend renders results one-by-one as modules complete.
- **D-02:** Use **Semaphore(5) + tracked `create_task` + registry + `cancel_all()`** instead of wrapping in `asyncio.TaskGroup`. Rationale: `yield` inside `async with TaskGroup()` is not possible (Python limitation — generators cannot suspend inside a non-suspendable context manager exit). The tracked create_task + registry pattern provides equivalent lifecycle management. The `_guarded()` wrapper catches per-module errors internally.
- **D-03:** Deviation from CLAUDE.md "TaskGroup + registry" mandate is accepted for this specific case. Justification is technical incompatibility between TaskGroup and async generators.

### Progress Reporting
- **D-04:** Use **N/M modules complete** progress model. Each time a module result comes through the queue, emit a progress event with `done/total` count and percentage. No race condition since the queue consumer is single-threaded. Frontend sees "3/12 modules complete" style progress.
- **D-05:** Emit progress event BEFORE the module result event for each completion. Pattern: `yield progress → yield module_result` per queue item.

### Module Grouping Strategy
- **D-06:** **Dual semaphore** architecture:
  - Global `asyncio.Semaphore(5)` — hard ceiling for ALL concurrent tasks
  - OathNet-scoped `asyncio.Semaphore(3)` — limits OathNet modules to max 3 of the 5 slots
  - Each OathNet module call acquires BOTH semaphores (global + OathNet)
  - Non-OathNet modules (Sherlock, DNS, etc.) only acquire the global semaphore
  - This prevents OathNet from monopolizing all 5 slots and starving faster modules
- **D-07:** `discord_auto` stays sequential — runs AFTER breach results to extract Discord IDs. Not included in the parallel module group.

### Claude's Discretion
- SpiderFoot polling guard (`_run_spiderfoot` HTTP API path timeout) — user did not select for discussion, Claude may add if low-effort
- Internal orchestrator API design details (method signatures, error propagation)
- Exact SSE event type ordering within the queue (first-finished-first-yielded is fine)
- Whether to read `search.js` to confirm frontend handles out-of-order events (recommended)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Architecture
- `CLAUDE.md` — Project rules, exception handling patterns, rate limiting, F3 Definition of Done
- `.planning/ROADMAP.md` §Phase 05 — Phase scope, verification criteria, findings addressed
- `.planning/phases/05-async-agent-orchestration/05-RESEARCH.md` — Full technical research with code patterns, pitfalls, and environment warnings

### Source Files (read before modifying)
- `api/main.py` — `_stream_search` (~400 lines), `with_timeout()`, `_run_spiderfoot()`, module dispatch logic
- `api/db.py` — DatabaseManager singleton (Phase 04) — do NOT modify, use `db.write()` for audit log
- `modules/oathnet_client.py` — Synchronous OathNet client, called via `asyncio.to_thread()`
- `modules/spiderfoot_wrapper.py` — Subprocess-based SpiderFoot CLI wrapper (FIND-08 target)
- `modules/sherlock_wrapper.py` — Sherlock wrapper with internal aiohttp event loop

### Frontend (verify event handling)
- `static/js/search.js` — SSE event consumer, `handleEvent()` dispatcher
- `static/js/state.js` — `currentResult` accumulator

### Prior Phase Artifacts
- `.planning/phases/04-sqlite-hardening/04-VERIFICATION.md` — Phase 04 verification (FIND-02 fix confirmed)
- `.planning/phases/03-codebase-audit/AUDIT-REPORT.md` — FIND-02, FIND-08 original descriptions

### Codebase Maps
- `.planning/codebase/ARCHITECTURE.md` — System layers, data flow, SSE event types
- `.planning/codebase/CONVENTIONS.md` — Naming, error handling, import patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `with_timeout(coro, module, default)` in `api/main.py` — per-module async timeout wrapper. Can be reused inside `_guarded()` or replaced by the orchestrator's own timeout logic.
- `event()` helper in `api/main.py` — SSE string formatter. Reuse for all yielded events.
- `MODULE_TIMEOUTS` dict in `api/main.py` — per-module timeout values. Pass to orchestrator.
- `api/db.py` `db.write()` — non-blocking audit log write via queue. Already integrated.

### Established Patterns
- All OSINT modules are synchronous — called via `asyncio.to_thread()` from the async context
- `OathnetClient` is instantiated once per search at the top of `_stream_search` — must be passed to all module coroutines (thread-safe for session reuse)
- Module errors yield `{"type": "module_error"}` SSE events — non-fatal, search continues
- `"start"` event always first, `"done"` event always last — invariant

### Integration Points
- New `api/orchestrator.py` — imported by `api/main.py`, used inside `_stream_search`
- `_stream_search` signature and return type (`AsyncGenerator[str, None]`) must NOT change
- Startup/shutdown hooks in `api/main.py` — no new hooks needed (orchestrator is per-search, not singleton)

</code_context>

<specifics>
## Specific Ideas

- User explicitly wants incremental result streaming — results should appear in the UI as each module completes, not all at once after a long wait
- Dual semaphore is the user's design — do not simplify to a single semaphore
- The queue bridge pattern was chosen despite higher complexity because UX matters more than code simplicity for this feature

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-async-agent-orchestration*
*Context gathered: 2026-04-01*
