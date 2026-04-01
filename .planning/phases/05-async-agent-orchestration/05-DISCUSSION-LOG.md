# Phase 05: Async Agent Orchestration (F3) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 05-async-agent-orchestration
**Areas discussed:** SSE streaming model, Progress reporting, Module grouping strategy

---

## SSE Streaming Model

| Option | Description | Selected |
|--------|-------------|----------|
| Collect-then-yield | All modules run concurrently, results collected in dict, yielded in order after all finish. Simpler code, no race conditions. | |
| Queue bridge (incremental) | Each module puts results into asyncio.Queue as it finishes. SSE generator consumes queue, yielding events live. More complex but frontend renders results one-by-one. | ✓ |
| You decide | Claude picks based on codebase constraints. | |

**User's choice:** Queue bridge (incremental)
**Notes:** User prioritizes UX — wants results to appear as modules complete, not all at once.

### Follow-up: TaskGroup Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Background TaskGroup + queue consumer | TaskGroup runs in background task, modules put results in queue. SSE generator consumes queue. TaskGroup guarantees cleanup. | |
| Semaphore only (no TaskGroup wrapper) | Semaphore(5) + tracked create_task + queue. Skip TaskGroup since queue consumer handles completion. Orchestrator cancel_all() provides cleanup. | ✓ |

**User's choice:** Semaphore only (no TaskGroup wrapper)
**Notes:** Chosen because yield inside TaskGroup context manager is not possible. Deviation from CLAUDE.md "TaskGroup + registry" mandate accepted — technical incompatibility is the justification. Tracked create_task + registry + cancel_all() provides equivalent lifecycle management.

---

## Progress Reporting

| Option | Description | Selected |
|--------|-------------|----------|
| N/M modules complete | Each queue consumption emits progress with done/total count. No race condition (single-threaded consumer). Frontend sees "3/12 modules complete". | ✓ |
| Single progress event | One "Running N modules concurrently..." at start, nothing until done. Simplest but progress bar jumps 0% to 100%. | |
| You decide | Claude picks based on frontend progress bar implementation. | |

**User's choice:** N/M modules complete
**Notes:** Clean pattern that naturally fits the queue bridge model. Progress event emitted before each module result event.

---

## Module Grouping Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| One slot per module | Each asyncio.to_thread() gets own semaphore slot. Max 5 OathNet calls in flight. Maximizes parallelism. | |
| OathNet grouped (1 slot for all) | All OathNet calls share one semaphore slot and run sequentially within it. Safest for API but slower. | |
| Hybrid: OathNet 2 slots max | OathNet limited to 2 concurrent slots. Remaining 3 for other modules. | |
| **Dual semaphore** | Global Semaphore(5) hard ceiling + OathNet-scoped Semaphore(3). Each OathNet call acquires both. Non-OathNet only acquires global. Prevents OathNet from starving faster modules. | ✓ |

**User's choice:** Dual semaphore (user-proposed — none of the presented options fit)
**Notes:** User rejected all three options and proposed a superior dual semaphore design. Global Sem(5) ensures hard ceiling. OathNet Sem(3) ensures at least 2 slots remain available for Sherlock, DNS, and other fast modules. discord_auto stays sequential (depends on breach results).

---

## Claude's Discretion

- SpiderFoot polling guard — user did not select for discussion
- Internal orchestrator API design details
- SSE event ordering within queue (first-finished-first-yielded)

## Deferred Ideas

None — discussion stayed within phase scope
