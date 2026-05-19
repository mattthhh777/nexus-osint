"""Integration tests for the R1-3 job store."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from api.db import DatabaseManager
from api.services import job_store
from modules.connectors.base import ConnectorStatus, TargetType


OWNER_A = "a" * 64
OWNER_B = "b" * 64
TARGET_HASH = "abcdef012345"


async def _event_count(db: DatabaseManager, job_id) -> int:
    row = await db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM search_events WHERE job_id=$1",
        (job_id,),
    )
    assert row is not None
    return row["cnt"]


@pytest.mark.asyncio
async def test_create_job_with_owner_hash_and_null_owner(tmp_db: DatabaseManager) -> None:
    owned_job = await job_store.create_job(
        owner_key_hash=OWNER_A,
        target_type=TargetType.EMAIL,
        target_hash=TARGET_HASH,
        connectors_planned=["oathnet:breach", "sherlock:github"],
        db=tmp_db,
    )
    anonymous_job = await job_store.create_job(
        owner_key_hash=None,
        target_type=TargetType.USERNAME,
        target_hash="123abc456def",
        connectors_planned=[],
        db=tmp_db,
    )

    owned = await tmp_db.fetch_one(
        "SELECT owner_key_hash, target_hash, target_encrypted, created_at, expires_at "
        "FROM search_jobs WHERE id=$1",
        (owned_job,),
    )
    anonymous = await tmp_db.fetch_one(
        "SELECT owner_key_hash FROM search_jobs WHERE id=$1",
        (anonymous_job,),
    )

    assert owned is not None
    assert owned["owner_key_hash"] == OWNER_A
    assert owned["target_hash"] == TARGET_HASH
    assert owned["target_encrypted"] is None
    assert timedelta(days=6, hours=23) <= owned["expires_at"] - owned["created_at"] <= timedelta(days=7, hours=1)
    assert anonymous == {"owner_key_hash": None}


@pytest.mark.asyncio
async def test_append_event_accepts_safe_payload_and_streams_from_seq(
    tmp_db: DatabaseManager,
) -> None:
    job_id = await job_store.create_job(
        owner_key_hash=OWNER_A,
        target_type="email",
        target_hash=TARGET_HASH,
        connectors_planned=["mock"],
        db=tmp_db,
    )

    for seq in range(1, 51):
        await job_store.append_event(
            job_id,
            seq,
            "connector_result",
            {
                "target_hash": TARGET_HASH,
                "connector": "mock",
                "status": ConnectorStatus.LIKELY.value,
                "confidence_score": 60,
                "confidence_level": "medium",
                "metadata": {"category": "social"},
            },
            db=tmp_db,
        )

    rows = [
        row
        async for row in job_store.stream_events(
            job_id,
            from_seq=10,
            owner_key_hash=OWNER_A,
            db=tmp_db,
        )
    ]

    assert len(rows) == 40
    assert [row["seq"] for row in rows] == list(range(11, 51))
    assert rows[0]["payload"]["target_hash"] == TARGET_HASH
    assert rows[0]["payload"]["metadata"] == {"category": "social"}


@pytest.mark.asyncio
async def test_append_event_rejects_sensitive_payload_before_db(
    tmp_db: DatabaseManager,
) -> None:
    job_id = await job_store.create_job(
        owner_key_hash=OWNER_A,
        target_type=TargetType.EMAIL,
        target_hash=TARGET_HASH,
        connectors_planned=["mock"],
        db=tmp_db,
    )
    sensitive_payloads = [
        {"target_hash": TARGET_HASH, "target_value": "analyst@example.test"},
        {"target_hash": TARGET_HASH, "metadata": {"email": "analyst@example.test"}},
        {"target_hash": TARGET_HASH, "metadata": {"phone": "+55 11 99999-9999"}},
        {"target_hash": TARGET_HASH, "metadata": {"cpf": "123.456.789-10"}},
        {"target_hash": TARGET_HASH, "headers": {"authorization": "Bearer abc"}},
        {"target_hash": TARGET_HASH, "body": "raw request body"},
        {"target_hash": TARGET_HASH, "token": "secret-token"},
    ]

    for seq, payload in enumerate(sensitive_payloads, start=1):
        with pytest.raises(job_store.EventPayloadRejected):
            await job_store.append_event(
                job_id,
                seq,
                "connector_result",
                payload,
                db=tmp_db,
            )

    assert await _event_count(tmp_db, job_id) == 0


@pytest.mark.asyncio
async def test_append_event_requires_target_hash(tmp_db: DatabaseManager) -> None:
    job_id = await job_store.create_job(
        owner_key_hash=None,
        target_type=TargetType.USERNAME,
        target_hash=TARGET_HASH,
        connectors_planned=["mock"],
        db=tmp_db,
    )

    with pytest.raises(job_store.EventPayloadRejected):
        await job_store.append_event(
            job_id,
            1,
            "connector_result",
            {"connector": "mock", "status": "likely"},
            db=tmp_db,
        )

    assert await _event_count(tmp_db, job_id) == 0


@pytest.mark.asyncio
async def test_append_event_rejects_unknown_payload_keys_as_allowlist(
    tmp_db: DatabaseManager,
) -> None:
    job_id = await job_store.create_job(
        owner_key_hash=None,
        target_type=TargetType.USERNAME,
        target_hash=TARGET_HASH,
        connectors_planned=["mock"],
        db=tmp_db,
    )

    with pytest.raises(job_store.EventPayloadRejected):
        await job_store.append_event(
            job_id,
            1,
            "connector_result",
            {"target_hash": TARGET_HASH, "unreviewed_field": "safe-looking"},
            db=tmp_db,
        )

    assert await _event_count(tmp_db, job_id) == 0


@pytest.mark.asyncio
async def test_owner_key_hash_filters_job_and_event_replay(
    tmp_db: DatabaseManager,
) -> None:
    job_id = await job_store.create_job(
        owner_key_hash=OWNER_A,
        target_type=TargetType.EMAIL,
        target_hash=TARGET_HASH,
        connectors_planned=["mock"],
        db=tmp_db,
    )
    await job_store.append_event(
        job_id,
        1,
        "connector_result",
        {"target_hash": TARGET_HASH, "connector": "mock", "status": "likely"},
        db=tmp_db,
    )

    assert await job_store.get_job(job_id, owner_key_hash=OWNER_A, db=tmp_db) is not None
    assert await job_store.get_job(job_id, owner_key_hash=OWNER_B, db=tmp_db) is None
    assert await job_store.get_job(job_id, owner_key_hash=None, db=tmp_db) is None

    rows_for_owner_b = [
        row
        async for row in job_store.stream_events(
            job_id,
            owner_key_hash=OWNER_B,
            db=tmp_db,
        )
    ]
    rows_without_owner = [
        row
        async for row in job_store.stream_events(
            job_id,
            owner_key_hash=None,
            db=tmp_db,
        )
    ]

    assert rows_for_owner_b == []
    assert rows_without_owner == []


@pytest.mark.asyncio
async def test_mark_done_and_purge_expired(tmp_db: DatabaseManager) -> None:
    job_id = await job_store.create_job(
        owner_key_hash=None,
        target_type=TargetType.USERNAME,
        target_hash=TARGET_HASH,
        connectors_planned=["mock"],
        db=tmp_db,
    )

    await job_store.mark_running(job_id, db=tmp_db)
    await job_store.mark_done(
        job_id,
        overall_status=ConnectorStatus.LIKELY,
        overall_confidence=60,
        connectors_run=["mock"],
        elapsed_ms=123,
        db=tmp_db,
    )
    done = await tmp_db.fetch_one(
        "SELECT status, overall_status, overall_confidence, connectors_run, elapsed_ms "
        "FROM search_jobs WHERE id=$1",
        (job_id,),
    )
    assert done == {
        "status": "done",
        "overall_status": "likely",
        "overall_confidence": 60,
        "connectors_run": ["mock"],
        "elapsed_ms": 123,
    }

    await tmp_db.execute(
        "UPDATE search_jobs "
        "SET created_at = NOW() - INTERVAL '8 days', "
        "    expires_at = NOW() - INTERVAL '1 second' "
        "WHERE id=$1",
        (job_id,),
    )
    assert await job_store.purge_expired(db=tmp_db) == 1
    assert await tmp_db.fetch_one("SELECT id FROM search_jobs WHERE id=$1", (job_id,)) is None


def test_legacy_api_search_route_remains_active() -> None:
    route_source = Path("api/routes/search.py").read_text(encoding="utf-8")
    docs_source = Path("docs/CONNECTORS.md").read_text(encoding="utf-8")

    assert '@router.post("/api/search")' in route_source
    assert "/api/search` is not deprecated" in docs_source


def test_job_store_replay_uses_fetch_stream_not_fetch_all() -> None:
    source = Path("api/services/job_store.py").read_text(encoding="utf-8")

    assert ".fetch_stream(" in source
    assert ".fetch_all(" not in source
