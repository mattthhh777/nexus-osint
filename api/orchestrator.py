"""
NexusOSINT — Task Orchestrator (api/orchestrator.py)
Concurrent OSINT module execution with dual semaphore control and queue bridge.

Design (per Phase 05 decisions D-01 through D-06):
  - Global asyncio.Semaphore(5): hard ceiling for ALL concurrent module tasks
  - OathNet asyncio.Semaphore(3): limits OathNet modules to max 3 of the 5 global slots
  - asyncio.Queue bridge: each module result pushed as (name, result_or_exception) tuple
  - Tracked create_task + registry (NOT TaskGroup — D-02/D-03: yield inside TaskGroup is impossible)
  - _guarded() wrapper: catches per-module exceptions, pushes error to queue, never crashes orchestrator

Usage:
    orchestrator = TaskOrchestrator()
    orchestrator.submit("breach", coro, is_oathnet=True)
    orchestrator.submit("sherlock", coro, is_oathnet=False)
    async for name, result in orchestrator.results():
        if isinstance(result, Exception):
            handle_error(name, result)
        else:
            handle_result(name, result)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Coroutine

# ── Constants ────────────────────────────────────────────────────────────────

GLOBAL_CONCURRENCY_LIMIT = 5   # hard ceiling — ALL concurrent module tasks
OATHNET_CONCURRENCY_LIMIT = 3  # OathNet scoped limit — prevents slot starvation

logger = logging.getLogger("nexusosint.orchestrator")


# ── TaskOrchestrator ─────────────────────────────────────────────────────────

class TaskOrchestrator:
    """
    Manages concurrent OSINT module execution with dual semaphore control.

    Enforces a global Semaphore(5) ceiling across all modules and an additional
    Semaphore(3) ceiling for OathNet modules, preventing them from monopolizing
    all concurrent slots and starving faster non-OathNet modules.

    Results are delivered incrementally via an asyncio.Queue as each module
    completes. The SSE generator in _stream_search consumes via results().

    Designed for single-use per search: create one instance, submit all modules,
    consume results(), discard. Not a long-lived singleton.

    Semaphore acquisition order for OathNet modules:
        _oathnet_sem FIRST, then _global_sem — ALWAYS this order to prevent deadlock.
    """

    def __init__(
        self,
        max_concurrent: int = GLOBAL_CONCURRENCY_LIMIT,
        max_oathnet: int = OATHNET_CONCURRENCY_LIMIT,
    ) -> None:
        self._global_sem: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)
        self._oathnet_sem: asyncio.Semaphore = asyncio.Semaphore(max_oathnet)
        self._registry: dict[str, asyncio.Task[None]] = {}
        self._result_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._expected: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def submit(
        self,
        name: str,
        coro: Coroutine[Any, Any, Any],
        *,
        is_oathnet: bool = False,
    ) -> None:
        """
        Submit a module coroutine for concurrent execution.

        The task is tracked in the registry and results are pushed to the
        internal queue when the module completes (or fails).

        Args:
            name:       Unique module identifier (e.g. "breach", "sherlock").
            coro:       Awaitable coroutine for the module.
            is_oathnet: True if this module uses the OathNet API and should
                        consume an OathNet semaphore slot in addition to the
                        global slot.
        """
        task = asyncio.create_task(
            self._guarded(name, coro, is_oathnet),
            name=f"module-{name}",
        )
        self._registry[name] = task
        self._expected += 1

    async def results(self) -> AsyncGenerator[tuple[str, Any], None]:
        """
        Async generator that yields (module_name, result_or_exception) tuples
        as each submitted module completes.

        Yields exactly self._expected items — one per submit() call.
        The caller (SSE generator) knows the stream is exhausted when this
        generator returns.

        Usage:
            async for name, result in orchestrator.results():
                ...
        """
        for _ in range(self._expected):
            name, result = await self._result_queue.get()
            yield name, result

    @property
    def active_count(self) -> int:
        """Number of tasks currently executing (in registry)."""
        return len(self._registry)

    async def cancel_all(self) -> None:
        """
        Cancel all active tasks and clear the registry.

        Drains any remaining items from the result queue after cancellation
        to leave the orchestrator in a clean state.
        """
        tasks_to_cancel = [
            task for task in self._registry.values()
            if not task.done()
        ]
        for task in tasks_to_cancel:
            task.cancel()

        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        self._registry.clear()

        # Drain any buffered results to avoid queue leakage
        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _guarded(
        self,
        name: str,
        coro: Coroutine[Any, Any, Any],
        is_oathnet: bool,
    ) -> None:
        """
        Execute a module coroutine under the appropriate semaphore(s).

        OathNet modules acquire _oathnet_sem FIRST, then _global_sem.
        This consistent ordering prevents deadlock between the two semaphores.

        All exceptions are caught here and pushed to the result queue as the
        exception object itself — the orchestrator never crashes on module
        failures.
        """
        if is_oathnet:
            async with self._oathnet_sem:
                async with self._global_sem:
                    await self._run_module(name, coro)
        else:
            async with self._global_sem:
                await self._run_module(name, coro)

    async def _run_module(
        self,
        name: str,
        coro: Coroutine[Any, Any, Any],
    ) -> None:
        """
        Execute the coroutine and push the result (or exception) to the queue.
        Always deregisters from the task registry in the finally block.
        """
        try:
            result = await coro
            await self._result_queue.put((name, result))
        except asyncio.CancelledError:
            # Task was cancelled via cancel_all() — do not push to queue,
            # let the cancellation propagate so gather() can collect it.
            logger.info("Module '%s' was cancelled", name)
            raise
        except Exception as exc:  # noqa: BLE001
            # Per-module failure — deliver to caller as exception tuple.
            # CLAUDE.md: no generic except outside _guarded. This IS _guarded.
            logger.warning("Module '%s' failed: %s", name, type(exc).__name__)
            await self._result_queue.put((name, exc))
        finally:
            self._registry.pop(name, None)
