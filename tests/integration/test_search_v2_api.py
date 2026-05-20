"""Integration tests for R1-8 /api/v2/search routes + worker + SSE.

Uses an in-process httpx.AsyncClient on top of ASGITransport so the FastAPI
app, the asyncpg pool from the ``tmp_db`` fixture, and the background worker
all share the same event loop.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from unittest.mock import MagicMock
from uuid import UUID, uuid4

_TEST_SECRET = "test-secret-search-v2-r1-8-never-prod-abcdef123456"
os.environ.setdefault("JWT_SECRET", _TEST_SECRET)

import httpx
import jwt
import pytest
import pytest_asyncio
from fastapi import HTTPException, Request

import api.main as m
import api.routes.search_v2 as search_v2
from api.db import DatabaseManager
from api.deps import get_current_user, get_db, get_orchestrator_dep
from api.orchestrator import DegradationMode, TaskOrchestrator
from api.services import job_store
from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    TargetType,
)


OWNER_A_SUB = "user-alpha"
OWNER_B_SUB = "user-beta"

OWNER_A_HASH = hashlib.sha256(OWNER_A_SUB.encode("utf-8")).hexdigest()
OWNER_B_HASH = hashlib.sha256(OWNER_B_SUB.encode("utf-8")).hexdigest()


# -- Helpers ----------------------------------------------------------------

def _jwt_cookie(sub: str) -> str:
    payload = {
        "sub": sub,
        "role": "user",
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "jti": f"test-jti-{sub}-r1-8",
    }
    return jwt.encode(payload, _TEST_SECRET, algorithm="HS256")


async def _fake_current_user(request: Request) -> dict:
    """Test-only auth: trust the cookie's JWT signature, skip users.json."""
    cookie_token = request.cookies.get("nx_session")
    if not cookie_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(cookie_token, _TEST_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return payload


def _make_mock_orch() -> MagicMock:
    orch = MagicMock(spec=TaskOrchestrator)
    orch.degradation_mode = DegradationMode.NORMAL
    orch.active_count = 0
    orch.semaphore_slots_free = 5
    orch.submit = MagicMock()
    return orch


class _StubConnector:
    """In-process connector returning a pre-built ConnectorResult."""

    rate_limit_cps = 100.0
    default_timeout_s = 5

    def __init__(self, connector_id: str, target_type: TargetType, status_: ConnectorStatus, score: int = 0) -> None:
        self.name = connector_id
        self.target_types = (target_type,)
        self._status = status_
        self._score = score

    async def run(self, req: ConnectorRequest, http) -> ConnectorResult:  # noqa: ARG002
        return ConnectorResult(
            connector=self.name,
            target_type=req.target_type,
            status=self._status,
            confidence_score=self._score,
            confidence_level="medium" if self._score >= 60 else "none",
            evidence=[],
            warnings=[],
            raw_url=None,
            data={"target_hash": req.target_hash, "category": "test"},
            fetched_at=datetime.now(timezone.utc),
            cache_hit=False,
            elapsed_ms=1,
        )


def _stub_plan_username() -> list[search_v2._PlannedConnector]:
    return [
        search_v2._PlannedConnector(
            "sherlock:github",
            lambda: _StubConnector("sherlock:github", TargetType.USERNAME, ConnectorStatus.FOUND, score=90),
        ),
        search_v2._PlannedConnector(
            "sherlock:reddit",
            lambda: _StubConnector("sherlock:reddit", TargetType.USERNAME, ConnectorStatus.FOUND, score=80),
        ),
        search_v2._PlannedConnector(
            "sherlock:steam",
            lambda: _StubConnector("sherlock:steam", TargetType.USERNAME, ConnectorStatus.NOT_FOUND, score=0),
        ),
    ]


# -- Fixtures ---------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_limiter():
    m.limiter._storage.reset()
    yield
    m.limiter._storage.reset()


@pytest_asyncio.fixture
async def app_client(tmp_db: DatabaseManager, monkeypatch) -> AsyncIterator[tuple[httpx.AsyncClient, DatabaseManager]]:
    monkeypatch.setattr(m, "JWT_SECRET", _TEST_SECRET)
    monkeypatch.setattr("api.deps.JWT_SECRET", _TEST_SECRET)
    monkeypatch.setattr("api.routes.search_v2._SSE_POLL_SECONDS", 0.05)
    monkeypatch.setattr("api.routes.search_v2._SSE_MAX_DURATION_SECONDS", 10.0)
    monkeypatch.setattr(
        "api.routes.search_v2._connectors_for",
        lambda target_type: _stub_plan_username() if target_type is TargetType.USERNAME else [],
    )
    mock_orch = _make_mock_orch()
    m.app.dependency_overrides[get_db] = lambda: tmp_db
    m.app.dependency_overrides[get_orchestrator_dep] = lambda: mock_orch
    m.app.dependency_overrides[get_current_user] = _fake_current_user
    transport = httpx.ASGITransport(app=m.app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client, tmp_db
    finally:
        m.app.dependency_overrides.pop(get_db, None)
        m.app.dependency_overrides.pop(get_orchestrator_dep, None)
        m.app.dependency_overrides.pop(get_current_user, None)


async def _wait_for_job_done(db: DatabaseManager, job_id: UUID, timeout: float = 5.0) -> dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        row = await db.fetch_one(
            "SELECT status, overall_status, overall_confidence FROM search_jobs WHERE id=$1",
            (job_id,),
        )
        if row and row["status"] in ("done", "failed"):
            return row
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"job {job_id} did not finish (status={row['status'] if row else None})")
        await asyncio.sleep(0.05)


# -- POST /api/v2/search ----------------------------------------------------

@pytest.mark.asyncio
async def test_post_returns_201_with_job_id_and_sse_url(app_client):
    client, db = app_client
    resp = await client.post(
        "/api/v2/search",
        json={"target_value": "testuser", "target_type": "username"},
        cookies={"nx_session": _jwt_cookie(OWNER_A_SUB)},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    job_id = UUID(body["job_id"])
    assert body["sse_url"] == f"/api/v2/search/{job_id}/events"
    await _wait_for_job_done(db, job_id)


@pytest.mark.asyncio
async def test_post_rejects_invalid_target_value(app_client):
    client, _db = app_client
    resp = await client.post(
        "/api/v2/search",
        json={"target_value": "  "},
        cookies={"nx_session": _jwt_cookie(OWNER_A_SUB)},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_requires_auth(app_client):
    client, _db = app_client
    resp = await client.post(
        "/api/v2/search",
        json={"target_value": "x", "target_type": "username"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_rejects_unrecognized_target_value_pattern(app_client):
    client, _db = app_client
    resp = await client.post(
        "/api/v2/search",
        json={"target_value": "@!#$%not_a_username"},
        cookies={"nx_session": _jwt_cookie(OWNER_A_SUB)},
    )
    assert resp.status_code == 400


# -- Worker writes hash-only events + G3 quorum -----------------------------

@pytest.mark.asyncio
async def test_worker_persists_hash_only_events_and_marks_done(app_client):
    client, db = app_client
    resp = await client.post(
        "/api/v2/search",
        json={"target_value": "TestUser", "target_type": "username"},
        cookies={"nx_session": _jwt_cookie(OWNER_A_SUB)},
    )
    assert resp.status_code == 201
    job_id = UUID(resp.json()["job_id"])

    final = await _wait_for_job_done(db, job_id)
    assert final["status"] == "done"
    # 2 independent FOUND -> G3 quorum -> overall FOUND
    assert final["overall_status"] == ConnectorStatus.FOUND.value

    events = await db.fetch_all(
        "SELECT seq, event_type, payload FROM search_events WHERE job_id=$1 ORDER BY seq",
        (job_id,),
    )
    assert len(events) >= 6
    for ev in events:
        payload = ev["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        for key in payload.keys():
            assert key in job_store.SAFE_EVENT_KEYS, f"unsafe key {key!r} in event payload"
        if "target_hash" in payload:
            assert payload["target_hash"] == hashlib.sha256(
                "testuser".encode("utf-8")
            ).hexdigest()[:12]
        assert "testuser" not in json.dumps(payload).lower()


# -- GET /api/v2/search/{job_id} --------------------------------------------

@pytest.mark.asyncio
async def test_owner_can_read_job_snapshot(app_client):
    client, db = app_client
    cookie = _jwt_cookie(OWNER_A_SUB)
    create = await client.post(
        "/api/v2/search",
        json={"target_value": "snap_user", "target_type": "username"},
        cookies={"nx_session": cookie},
    )
    job_id = create.json()["job_id"]
    await _wait_for_job_done(db, UUID(job_id))

    resp = await client.get(f"/api/v2/search/{job_id}", cookies={"nx_session": cookie})
    assert resp.status_code == 200
    snap = resp.json()
    assert snap["job_id"] == job_id
    assert snap["status"] == "done"
    assert snap["overall_status"] == "found"
    assert snap["connectors_planned"] == ["sherlock:github", "sherlock:reddit", "sherlock:steam"]
    assert sorted(snap["connectors_run"]) == ["sherlock:github", "sherlock:reddit", "sherlock:steam"]


@pytest.mark.asyncio
async def test_cross_user_snapshot_returns_403(app_client):
    client, db = app_client
    create = await client.post(
        "/api/v2/search",
        json={"target_value": "victim_user", "target_type": "username"},
        cookies={"nx_session": _jwt_cookie(OWNER_A_SUB)},
    )
    job_id = create.json()["job_id"]
    await _wait_for_job_done(db, UUID(job_id))

    resp = await client.get(
        f"/api/v2/search/{job_id}",
        cookies={"nx_session": _jwt_cookie(OWNER_B_SUB)},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_missing_job_returns_404(app_client):
    client, _db = app_client
    resp = await client.get(
        f"/api/v2/search/{uuid4()}",
        cookies={"nx_session": _jwt_cookie(OWNER_A_SUB)},
    )
    assert resp.status_code == 404


# -- SSE replay endpoint ----------------------------------------------------

@pytest.mark.asyncio
async def test_sse_replays_persisted_events_for_owner(app_client):
    client, db = app_client
    cookie = _jwt_cookie(OWNER_A_SUB)
    create = await client.post(
        "/api/v2/search",
        json={"target_value": "sse_user", "target_type": "username"},
        cookies={"nx_session": cookie},
    )
    job_id = create.json()["job_id"]
    await _wait_for_job_done(db, UUID(job_id))

    async with client.stream(
        "GET",
        f"/api/v2/search/{job_id}/events",
        cookies={"nx_session": cookie},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = ""
        async for chunk in resp.aiter_text():
            body += chunk

    frames = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    event_types = [f["event_type"] for f in frames]
    assert event_types[0] == "job_started"
    assert "summary" in event_types
    assert "job_done" in event_types
    seqs = [f["seq"] for f in frames]
    assert seqs == sorted(seqs)


@pytest.mark.asyncio
async def test_sse_cross_user_returns_403(app_client):
    client, db = app_client
    create = await client.post(
        "/api/v2/search",
        json={"target_value": "leak_user", "target_type": "username"},
        cookies={"nx_session": _jwt_cookie(OWNER_A_SUB)},
    )
    job_id = create.json()["job_id"]
    await _wait_for_job_done(db, UUID(job_id))

    resp = await client.get(
        f"/api/v2/search/{job_id}/events",
        cookies={"nx_session": _jwt_cookie(OWNER_B_SUB)},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sse_from_seq_skips_replayed_events(app_client):
    client, db = app_client
    cookie = _jwt_cookie(OWNER_A_SUB)
    create = await client.post(
        "/api/v2/search",
        json={"target_value": "seq_user", "target_type": "username"},
        cookies={"nx_session": cookie},
    )
    job_id = create.json()["job_id"]
    await _wait_for_job_done(db, UUID(job_id))

    async with client.stream(
        "GET",
        f"/api/v2/search/{job_id}/events?from_seq=3",
        cookies={"nx_session": cookie},
    ) as resp:
        body = ""
        async for chunk in resp.aiter_text():
            body += chunk
    frames = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert all(f["seq"] > 3 for f in frames)


# -- Legacy /api/search must stay live --------------------------------------

def test_legacy_api_search_route_still_registered():
    routes = {route.path for route in m.app.router.routes if hasattr(route, "path")}
    assert "/api/search" in routes, "legacy /api/search must remain registered"
    assert "/api/v2/search" in routes
    assert "/api/v2/search/{job_id}" in routes
    assert "/api/v2/search/{job_id}/events" in routes


# -- R1-9 frontend must be opt-in -------------------------------------------

def test_r1_9_frontend_is_opt_in():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    index = (repo / "static" / "index.html").read_text(encoding="utf-8")
    v2 = (repo / "static" / "js" / "v2-search.js").read_text(encoding="utf-8")
    replay = (repo / "static" / "js" / "job-replay.js").read_text(encoding="utf-8")
    legacy = (repo / "static" / "js" / "search.js").read_text(encoding="utf-8")

    assert "/static/js/job-replay.js" in index
    assert "/static/js/v2-search.js" in index
    assert "getParam('engine') === 'v2'" in v2
    assert "apiFetch('/api/v2/search'" in v2
    assert "apiFetch('/api/search'" not in v2
    assert "apiFetch('/api/search'" in legacy
    assert "searchParams.set('from_seq'" in replay
