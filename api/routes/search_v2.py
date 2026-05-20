"""R1-8 - /api/v2/search HTTP surface, worker, and SSE replay.

Implements:

- ``POST /api/v2/search`` - validate input, detect ``target_type``, create a
  hash-only job via ``job_store.create_job``, enqueue a background worker, and
  return ``201 {job_id, sse_url}``.
- ``GET /api/v2/search/{job_id}`` - owner-scoped job snapshot. Cross-user
  access is rejected with ``403`` before any payload is returned.
- ``GET /api/v2/search/{job_id}/events?from_seq=N`` - SSE replay + live tail.
  Replays from ``from_seq`` then polls the job store until the job reaches a
  terminal state. All event payloads are routed through ``job_store.append_event``,
  which enforces the hash-only sanitizer in ``api/services/job_store.py``.

Scope guards (R1-8 only):

- ``/api/search`` (the legacy SSE route) is **not** touched.
- No UI/frontend wiring (R1-9 deferred).
- No new connectors. No Gravatar (R1-10 skipped per G2).
- The closed connector registry from ``job_store.ALLOWED_CONNECTOR_IDS``
  governs which connectors may appear in a job plan.
- Aggregation is delegated to ``search_orchestrator.aggregate_results`` so the
  G3 quorum rule remains the single source of truth for overall status.
- ``likely`` is never promoted to ``found`` outside G3. ``blocked`` never
  collapses to ``not_found`` or ``error``.
- No raw ``target_value`` lands in DB events, logs, or client-visible job
  payloads. The sanitizer is enforced by ``job_store``; the worker also
  builds hash-only payloads at the source.
"""
import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from api.config import RL_SEARCH_LIMIT
from api.db import DatabaseError, DatabaseManager
from api.deps import get_current_user, get_db
from api.limiter import limiter
from api.schemas import SearchV2Request
from api.services import job_store
from api.services.search_orchestrator import (
    AggregateSummary,
    OrchestratorError,
    aggregate_results,
)
from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    TargetType,
)
from modules.connectors.oathnet_adapter import OathNetAdapter
from modules.connectors.phone.carrier_lookup import CarrierLookup
from modules.connectors.runner import run_connector
from modules.connectors.username.sherlock_adapter import SherlockAdapter


logger = logging.getLogger("nexusosint.routes.search_v2")
router = APIRouter()


# -- Constants ---------------------------------------------------------------

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_EMAIL_RE = re.compile(r"^[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+$", re.IGNORECASE)
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

_SSE_HEARTBEAT_SECONDS = 15.0
_SSE_POLL_SECONDS = 0.5
_SSE_MAX_DURATION_SECONDS = 180.0
_WORKER_CONNECTOR_TIMEOUT_S = 30

# Job workers are tracked here so shutdown can cancel them if needed. The
# registry is module-level because each worker outlives the request that
# spawned it.
_job_workers: dict[UUID, asyncio.Task[None]] = {}


@dataclass(frozen=True)
class _PlannedConnector:
    """A connector slot resolved at job-plan time."""

    connector_id: str
    factory: Callable[[], Any]


def _connectors_for(target_type: TargetType) -> list[_PlannedConnector]:
    """Return the connector plan for ``target_type``.

    Every ``connector_id`` here MUST also appear in
    ``job_store.ALLOWED_CONNECTOR_IDS`` and in the orchestrator's closed
    registry. Adding new connectors to this map requires extending the
    closed registry in lockstep.
    """
    if target_type is TargetType.USERNAME:
        return [
            _PlannedConnector("sherlock:github", lambda: SherlockAdapter("github")),
            _PlannedConnector("sherlock:reddit", lambda: SherlockAdapter("reddit")),
            _PlannedConnector("sherlock:steam", lambda: SherlockAdapter("steam")),
        ]
    if target_type is TargetType.EMAIL:
        return [
            _PlannedConnector("oathnet:breach", lambda: OathNetAdapter("breach")),
            _PlannedConnector("oathnet:stealer", lambda: OathNetAdapter("stealer")),
            _PlannedConnector("oathnet:victims", lambda: OathNetAdapter("victims")),
        ]
    if target_type is TargetType.PHONE:
        return [
            _PlannedConnector("oathnet:breach", lambda: OathNetAdapter("breach")),
            _PlannedConnector("oathnet:stealer", lambda: OathNetAdapter("stealer")),
            _PlannedConnector("carrier_lookup", lambda: CarrierLookup()),
        ]
    raise ValueError("unsupported_target_type")


# -- Input handling ---------------------------------------------------------

def _detect_target_type(target_value: str) -> TargetType:
    candidate = target_value.strip()
    if _EMAIL_RE.match(candidate):
        return TargetType.EMAIL
    if _E164_RE.match(candidate):
        return TargetType.PHONE
    if _USERNAME_RE.match(candidate):
        return TargetType.USERNAME
    raise HTTPException(
        status_code=400,
        detail="target_value does not match a supported target_type pattern",
    )


def _target_value_matches_type(target_value: str, target_type: TargetType) -> bool:
    candidate = target_value.strip()
    if target_type is TargetType.EMAIL:
        return bool(_EMAIL_RE.fullmatch(candidate))
    if target_type is TargetType.PHONE:
        return bool(_E164_RE.fullmatch(candidate))
    if target_type is TargetType.USERNAME:
        return bool(_USERNAME_RE.fullmatch(candidate))
    return False


def _coerce_target_type(payload: SearchV2Request) -> TargetType:
    if payload.target_type is None:
        return _detect_target_type(payload.target_value)
    try:
        target_type = TargetType(payload.target_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid target_type") from exc
    if not _target_value_matches_type(payload.target_value, target_type):
        raise HTTPException(
            status_code=400,
            detail="target_value does not match target_type",
        )
    return target_type


def _derive_owner_key_hash(user: dict) -> str:
    subject = str(user.get("sub") or "").strip()
    if not subject:
        raise HTTPException(status_code=401, detail="missing user identity")
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()


def _derive_target_hash(target_value: str) -> str:
    normalized = target_value.strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


# -- Job lookup helpers (404 vs 403 distinction) ----------------------------

async def _lookup_job_for_request(
    db: DatabaseManager,
    job_id: UUID,
    owner_key_hash: str,
) -> dict[str, Any]:
    """Owner-scoped lookup. ``404`` for missing, ``403`` for cross-owner."""
    try:
        row = await db.fetch_one(
            """
            SELECT id, owner_key_hash, target_type, target_hash, status,
                   connectors_planned, connectors_run, overall_status,
                   overall_confidence, created_at, started_at, finished_at,
                   elapsed_ms, expires_at
            FROM search_jobs
            WHERE id=$1 AND expires_at >= NOW()
            """,
            (job_id,),
        )
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    if row["owner_key_hash"] != owner_key_hash:
        raise HTTPException(status_code=403, detail="forbidden")
    return row


def _serialize_job(row: dict[str, Any]) -> dict[str, Any]:
    """Build a hash-safe job snapshot for HTTP responses."""
    return {
        "job_id": str(row["id"]),
        "status": row["status"],
        "target_type": row["target_type"],
        "target_hash": row["target_hash"],
        "connectors_planned": list(row.get("connectors_planned") or []),
        "connectors_run": list(row.get("connectors_run") or []),
        "overall_status": row.get("overall_status"),
        "overall_confidence": row.get("overall_confidence"),
        "elapsed_ms": row.get("elapsed_ms"),
        "created_at": _isoformat(row.get("created_at")),
        "started_at": _isoformat(row.get("started_at")),
        "finished_at": _isoformat(row.get("finished_at")),
        "expires_at": _isoformat(row.get("expires_at")),
    }


def _isoformat(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return None


# -- Worker -----------------------------------------------------------------

async def _emit_event(
    db: DatabaseManager,
    job_id: UUID,
    owner_key_hash: str | None,
    seq: int,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Persist one event via ``job_store.append_event`` (sanitizer enforced)."""
    await job_store.append_event(
        job_id,
        seq,
        event_type,
        payload,
        owner_key_hash=owner_key_hash,
        db=db,
    )


async def _run_connector_safe(
    planned: _PlannedConnector,
    req: ConnectorRequest,
    http: httpx.AsyncClient,
) -> ConnectorResult:
    """Run one planned connector, returning an ERROR result on instantiation
    failures so the worker can keep going through the plan."""
    try:
        connector = planned.factory()
    except (ValueError, RuntimeError, TypeError) as exc:
        logger.warning(
            "search_v2 connector factory failed | connector=%s type=%s",
            planned.connector_id,
            type(exc).__name__,
        )
        return ConnectorResult(
            connector=planned.connector_id,
            target_type=req.target_type,
            status=ConnectorStatus.ERROR,
            confidence_score=0,
            confidence_level="none",
            evidence=[],
            warnings=["connector_unavailable"],
            raw_url=None,
            data={"target_hash": req.target_hash},
            fetched_at=datetime.now(timezone.utc),
            cache_hit=False,
            elapsed_ms=0,
        )
    return await run_connector(connector, req, http)


def _connector_result_payload(result: ConnectorResult) -> dict[str, Any]:
    """Hash-only payload for ``connector_result`` events. No PII, no URLs."""
    return {
        "connector": result.connector,
        "status": result.status.value,
        "confidence_score": int(result.confidence_score),
        "confidence_level": result.confidence_level,
        "cache_hit": bool(result.cache_hit),
        "elapsed_ms": int(result.elapsed_ms),
        "fetched_at": result.fetched_at,
        "reason_code": "connector_result",
    }


def _summary_payload(summary: AggregateSummary) -> dict[str, Any]:
    return {
        "overall_status": summary.overall_status.value,
        "confidence_score": int(summary.overall_confidence),
        "confidence_level": summary.overall_confidence_level,
        "reason_code": "job_done",
    }


async def _execute_job(
    job_id: UUID,
    target_value: str,
    owner_key_hash: str,
    connector_plan: list[_PlannedConnector],
    db: DatabaseManager,
) -> None:
    """Run the connector plan and emit hash-only events along the way."""
    started_at = time.monotonic()
    seq = 0
    job = await job_store.get_job(job_id, owner_key_hash=owner_key_hash, db=db)
    if job is None:
        raise job_store.JobStoreError("job_not_found")
    target_type = TargetType(job["target_type"])
    target_hash = str(job["target_hash"])

    await job_store.mark_running(job_id, db=db)

    seq += 1
    await _emit_event(
        db,
        job_id,
        owner_key_hash,
        seq,
        "job_started",
        {"reason_code": "job_started"},
    )

    results: list[ConnectorResult] = []
    async with httpx.AsyncClient(timeout=30.0) as http:
        for planned in connector_plan:
            seq += 1
            await _emit_event(
                db,
                job_id,
                owner_key_hash,
                seq,
                "connector_started",
                {
                    "connector": planned.connector_id,
                    "reason_code": "connector_started",
                },
            )
            req = ConnectorRequest(
                target_type=target_type,
                target_value=target_value,
                target_hash=target_hash,
                timeout_s=_WORKER_CONNECTOR_TIMEOUT_S,
                job_id=job_id,
            )
            try:
                result = await _run_connector_safe(planned, req, http)
            except asyncio.CancelledError:
                raise
            except (
                ValidationError,
                DatabaseError,
                httpx.HTTPError,
                RuntimeError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
            ) as exc:
                logger.warning(
                    "search_v2 connector unexpected failure | job=%s connector=%s type=%s",
                    job_id,
                    planned.connector_id,
                    type(exc).__name__,
                )
                result = ConnectorResult(
                    connector=planned.connector_id,
                    target_type=target_type,
                    status=ConnectorStatus.ERROR,
                    confidence_score=0,
                    confidence_level="none",
                    evidence=[],
                    warnings=["worker_error"],
                    raw_url=None,
                    data={"target_hash": target_hash},
                    fetched_at=datetime.now(timezone.utc),
                    cache_hit=False,
                    elapsed_ms=0,
                )
            results.append(result)

            seq += 1
            await _emit_event(
                db,
                job_id,
                owner_key_hash,
                seq,
                "connector_result",
                _connector_result_payload(result),
            )

    summary = aggregate_results(results)

    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    seq += 1
    await _emit_event(
        db,
        job_id,
        owner_key_hash,
        seq,
        "summary",
        _summary_payload(summary),
    )

    await job_store.mark_done(
        job_id,
        overall_status=summary.overall_status,
        overall_confidence=summary.overall_confidence,
        connectors_run=list(summary.connectors_run),
        elapsed_ms=elapsed_ms,
        db=db,
    )

    seq += 1
    await _emit_event(
        db,
        job_id,
        owner_key_hash,
        seq,
        "job_done",
        {
            "overall_status": summary.overall_status.value,
            "confidence_score": int(summary.overall_confidence),
            "confidence_level": summary.overall_confidence_level,
            "elapsed_ms": elapsed_ms,
            "reason_code": "job_done",
        },
    )


async def _worker(
    job_id: UUID,
    target_value: str,
    owner_key_hash: str,
    connector_plan: list[_PlannedConnector],
    db: DatabaseManager,
) -> None:
    try:
        await _execute_job(
            job_id,
            target_value,
            owner_key_hash,
            connector_plan,
            db,
        )
    except asyncio.CancelledError:
        logger.info("search_v2 worker cancelled | job=%s", job_id)
        try:
            await job_store.mark_failed(job_id, db=db)
        except (job_store.JobStoreError, DatabaseError, RuntimeError) as exc:
            logger.warning(
                "search_v2 mark_failed after cancel failed | job=%s type=%s",
                job_id,
                type(exc).__name__,
            )
        raise
    except (
        job_store.JobStoreError,
        OrchestratorError,
        DatabaseError,
        httpx.HTTPError,
        ValidationError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        logger.warning(
            "search_v2 worker failed | job=%s type=%s",
            job_id,
            type(exc).__name__,
        )
        try:
            await job_store.mark_failed(job_id, db=db)
        except (job_store.JobStoreError, DatabaseError, RuntimeError) as mark_exc:
            logger.warning(
                "search_v2 mark_failed failed | job=%s type=%s",
                job_id,
                type(mark_exc).__name__,
            )


def _spawn_worker(
    job_id: UUID,
    coro: Awaitable[None],
) -> None:
    task = asyncio.create_task(coro, name=f"search_v2-job-{job_id}")
    _job_workers[job_id] = task

    def _on_done(t: asyncio.Task[None]) -> None:
        _job_workers.pop(job_id, None)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.warning(
                "search_v2 worker exited with exception | job=%s type=%s",
                job_id,
                type(exc).__name__,
            )

    task.add_done_callback(_on_done)


# -- Routes -----------------------------------------------------------------

@router.post("/api/v2/search", status_code=status.HTTP_201_CREATED)
@limiter.limit(RL_SEARCH_LIMIT)
async def create_search_v2(
    request: Request,
    body: SearchV2Request,
    user: dict = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> dict[str, Any]:
    """Create a v2 search job, enqueue the worker, return ``{job_id, sse_url}``."""
    target_type = _coerce_target_type(body)
    target_value = body.target_value
    target_hash = _derive_target_hash(target_value)
    owner_key_hash = _derive_owner_key_hash(user)

    try:
        connector_plan = _connectors_for(target_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    planned_ids = [item.connector_id for item in connector_plan]

    try:
        job_id = await job_store.create_job(
            owner_key_hash=owner_key_hash,
            target_type=target_type,
            target_hash=target_hash,
            connectors_planned=planned_ids,
            db=db,
        )
    except job_store.JobStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    _spawn_worker(
        job_id,
        _worker(
            job_id,
            target_value,
            owner_key_hash,
            connector_plan,
            db,
        ),
    )

    logger.info(
        "search_v2 job created | job=%s target_type=%s target_hash=%s",
        job_id,
        target_type.value,
        target_hash,
    )

    return {
        "job_id": str(job_id),
        "sse_url": f"/api/v2/search/{job_id}/events",
    }


@router.get("/api/v2/search/{job_id}")
async def get_search_v2(
    job_id: UUID,
    user: dict = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> dict[str, Any]:
    owner_key_hash = _derive_owner_key_hash(user)
    row = await _lookup_job_for_request(db, job_id, owner_key_hash)
    return _serialize_job(row)


@router.get("/api/v2/search/{job_id}/events")
async def stream_search_v2_events(
    job_id: UUID,
    from_seq: int = Query(0, ge=0, le=2_000_000_000),
    user: dict = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
) -> StreamingResponse:
    owner_key_hash = _derive_owner_key_hash(user)
    await _lookup_job_for_request(db, job_id, owner_key_hash)

    return StreamingResponse(
        _sse_generator(job_id, owner_key_hash, from_seq, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -- SSE generator ----------------------------------------------------------

async def _sse_generator(
    job_id: UUID,
    owner_key_hash: str,
    from_seq: int,
    db: DatabaseManager,
):
    """Yield SSE frames: replay from ``from_seq`` then poll until terminal."""
    last_seq = from_seq
    start = time.monotonic()
    last_heartbeat = start
    try:
        while True:
            async for event in job_store.stream_events(
                job_id,
                from_seq=last_seq,
                owner_key_hash=owner_key_hash,
                db=db,
            ):
                last_seq = int(event["seq"])
                yield _format_sse_frame(event)

            row = await db.fetch_one(
                "SELECT status FROM search_jobs WHERE id=$1 AND expires_at >= NOW()",
                (job_id,),
            )
            if row is None or row["status"] in ("done", "failed"):
                async for event in job_store.stream_events(
                    job_id,
                    from_seq=last_seq,
                    owner_key_hash=owner_key_hash,
                    db=db,
                ):
                    last_seq = int(event["seq"])
                    yield _format_sse_frame(event)
                break

            now = time.monotonic()
            if now - last_heartbeat >= _SSE_HEARTBEAT_SECONDS:
                yield ": heartbeat\n\n"
                last_heartbeat = now
            if now - start >= _SSE_MAX_DURATION_SECONDS:
                yield ": stream-timeout\n\n"
                break
            await asyncio.sleep(_SSE_POLL_SECONDS)
    except asyncio.CancelledError:
        return


def _format_sse_frame(event: dict[str, Any]) -> str:
    body = {
        "seq": int(event["seq"]),
        "event_type": event["event_type"],
        "payload": event.get("payload") or {},
        "emitted_at": _isoformat(event.get("emitted_at")),
    }
    return (
        f"event: {event['event_type']}\n"
        f"data: {json.dumps(body, separators=(',', ':'))}\n\n"
    )


__all__ = ["router"]
