"""
tests/test_orchestrator.py — Unit tests for TaskOrchestrator.

Tests verify:
1. Global semaphore ceiling (max 5 concurrent)
2. OathNet scoped semaphore (max 3 of the 5 slots)
3. Queue delivery — all results arrive as (name, result) tuples
4. Error handling — module exceptions delivered to queue, orchestrator survives
5. Registry cleanup — empty after all tasks complete
6. cancel_all() — cancels tasks within timeout, registry empty afterward
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
import pytest_asyncio  # noqa: F401 — registers async fixtures

from api.orchestrator import TaskOrchestrator


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fast_module(name: str, value: Any = None, *, delay: float = 0.0) -> Any:
    """Simulate a module that completes quickly after an optional sleep."""
    if delay:
        await asyncio.sleep(delay)
    return value if value is not None else f"result_{name}"


async def _failing_module(exc: Exception) -> None:
    """Simulate a module that raises an exception."""
    raise exc


async def _slow_module(duration: float = 10.0) -> str:
    """Simulate a long-running module (for cancellation tests)."""
    await asyncio.sleep(duration)
    return "slow_done"


# ── Test 1: Global semaphore ceiling ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_global_semaphore_ceiling():
    """
    Launch 10 modules simultaneously.
    At most 5 should be executing at any point.
    """
    max_concurrent = 5
    orchestrator = TaskOrchestrator(max_concurrent=max_concurrent, max_oathnet=3)

    peak_concurrent = [0]
    current_concurrent = [0]

    async def tracked_module(name: str) -> str:
        current_concurrent[0] += 1
        if current_concurrent[0] > peak_concurrent[0]:
            peak_concurrent[0] = current_concurrent[0]
        await asyncio.sleep(0.05)  # hold slot briefly so contention is measurable
        current_concurrent[0] -= 1
        return f"done_{name}"

    for i in range(10):
        orchestrator.submit(f"mod_{i}", tracked_module(f"mod_{i}"), is_oathnet=False)

    results = {}
    async for name, result in orchestrator.results():
        results[name] = result

    assert len(results) == 10, "All 10 modules must deliver results"
    assert peak_concurrent[0] <= max_concurrent, (
        f"Peak concurrent was {peak_concurrent[0]}, expected <= {max_concurrent}"
    )


# ── Test 2: OathNet semaphore scoped limit ────────────────────────────────────

@pytest.mark.asyncio
async def test_oathnet_semaphore_scoped_limit():
    """
    Launch 5 OathNet-flagged modules.
    At most 3 should be executing at any point (OathNet ceiling),
    AND at most 5 total (global ceiling).
    """
    oathnet_limit = 3
    orchestrator = TaskOrchestrator(max_concurrent=5, max_oathnet=oathnet_limit)

    peak_oathnet = [0]
    current_oathnet = [0]

    async def tracked_oathnet_module(name: str) -> str:
        current_oathnet[0] += 1
        if current_oathnet[0] > peak_oathnet[0]:
            peak_oathnet[0] = current_oathnet[0]
        await asyncio.sleep(0.05)
        current_oathnet[0] -= 1
        return f"oathnet_{name}"

    for i in range(5):
        orchestrator.submit(
            f"oath_{i}", tracked_oathnet_module(f"oath_{i}"), is_oathnet=True
        )

    results = {}
    async for name, result in orchestrator.results():
        results[name] = result

    assert len(results) == 5, "All 5 OathNet modules must deliver results"
    assert peak_oathnet[0] <= oathnet_limit, (
        f"Peak OathNet concurrent was {peak_oathnet[0]}, expected <= {oathnet_limit}"
    )


# ── Test 3: Queue delivery ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_queue_delivery():
    """
    Launch 3 modules.
    All 3 results appear in the result_queue as (name, result) tuples.
    """
    orchestrator = TaskOrchestrator()

    orchestrator.submit("alpha", _fast_module("alpha", value={"hits": 3}))
    orchestrator.submit("beta",  _fast_module("beta",  value=["a", "b"]))
    orchestrator.submit("gamma", _fast_module("gamma", value=42))

    collected: dict[str, Any] = {}
    async for name, result in orchestrator.results():
        collected[name] = result

    assert "alpha" in collected
    assert "beta" in collected
    assert "gamma" in collected
    assert collected["alpha"] == {"hits": 3}
    assert collected["beta"] == ["a", "b"]
    assert collected["gamma"] == 42


# ── Test 4: Error handling — exceptions delivered to queue ────────────────────

@pytest.mark.asyncio
async def test_module_error_delivered_to_queue():
    """
    A module that raises ValueError should deliver (name, ValueError_instance)
    to the queue — NOT crash the orchestrator.
    """
    orchestrator = TaskOrchestrator()
    expected_exc = ValueError("API returned 403")

    orchestrator.submit("failing_mod", _failing_module(expected_exc))
    orchestrator.submit("ok_mod",      _fast_module("ok_mod", value="success"))

    collected: dict[str, Any] = {}
    async for name, result in orchestrator.results():
        collected[name] = result

    assert "failing_mod" in collected
    assert isinstance(collected["failing_mod"], ValueError)
    assert str(collected["failing_mod"]) == "API returned 403"

    assert "ok_mod" in collected
    assert collected["ok_mod"] == "success"


# ── Test 5: Registry cleanup after completion ─────────────────────────────────

@pytest.mark.asyncio
async def test_registry_empty_after_completion():
    """
    After all modules complete, orchestrator._registry should be empty (len == 0).
    """
    orchestrator = TaskOrchestrator()

    for i in range(4):
        orchestrator.submit(f"mod_{i}", _fast_module(f"mod_{i}"))

    # Consume all results to allow tasks to finish
    async for _name, _result in orchestrator.results():
        pass

    # Give event loop one cycle to finalize any cleanup
    await asyncio.sleep(0)

    assert orchestrator.active_count == 0, (
        f"Registry should be empty, has {orchestrator.active_count} entries: "
        f"{list(orchestrator._registry.keys())}"
    )


# ── Test 6: cancel_all() cancels active tasks ─────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_all_clears_registry():
    """
    Launch 3 slow modules (sleep 10s each).
    Call cancel_all(). All tasks should be cancelled within 1 second.
    Registry should be empty afterward.
    """
    orchestrator = TaskOrchestrator()

    # Submit 3 slow modules — they would take 10s each if not cancelled
    for i in range(3):
        orchestrator.submit(f"slow_{i}", _slow_module(10.0), is_oathnet=False)

    # Give tasks a moment to start and acquire their semaphore slots
    await asyncio.sleep(0.05)

    t_start = time.monotonic()
    await orchestrator.cancel_all()
    elapsed = time.monotonic() - t_start

    assert elapsed < 1.0, f"cancel_all() took {elapsed:.2f}s — should complete in < 1s"
    assert orchestrator.active_count == 0, (
        f"Registry not empty after cancel_all: {list(orchestrator._registry.keys())}"
    )
