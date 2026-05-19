"""R1-2 schema tests for real-time OSINT job/event persistence."""
from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from api.db import DatabaseError, DatabaseManager


MIGRATION = Path("migrations/versions/0004_real_time_osint_jobs.py")
OWNER_KEY_HASH_COMMENT = (
    "owner_key_hash is a privacy-preserving owner identifier aligned with "
    "current JSON auth. It is intentionally not a FK until DB-backed users exist."
)
SAFE_OWNER_HASH = "a" * 64
SAFE_TARGET_HASH = "abcdef012345"


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


async def _columns(db: DatabaseManager, table_name: str) -> dict[str, dict]:
    rows = await db.fetch_all(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return {row["column_name"]: row for row in rows}


async def _insert_job(db: DatabaseManager) -> str:
    row = await db.fetch_one(
        """
        INSERT INTO search_jobs (owner_key_hash, target_type, target_hash, status)
        VALUES ($1, 'email', $2, 'queued')
        RETURNING id::text AS id
        """,
        (SAFE_OWNER_HASH, SAFE_TARGET_HASH),
    )
    assert row is not None
    return row["id"]


def test_migration_uses_owner_key_hash_without_users_fk() -> None:
    text = _migration_text()

    assert "owner_key_hash" in text
    assert "privacy-preserving owner identifier" in text
    assert "intentionally not a FK until DB-backed users exist" in text
    assert "users.id" not in text
    assert "REFERENCES users" not in text
    assert "user_id" not in text
    assert '"connector_metrics"' not in text
    assert not re.search(r"sa\.Column\(\s*[\"']target_value[\"']", text)
    assert not re.search(r"sa\.Column\(\s*[\"']email[\"']", text)
    assert not re.search(r"sa\.Column\(\s*[\"']phone[\"']", text)
    assert not re.search(r"sa\.Column\(\s*[\"']cpf[\"']", text)


def test_migration_documents_g1_hash_only_ttl_and_pii_gates() -> None:
    text = _migration_text()

    assert "INTERVAL '7 days'" in text
    assert "target_encrypted IS NULL" in text
    assert "ck_search_jobs_owner_key_hash_hmac_sha256_hex" in text
    assert "ck_search_events_payload_no_sensitive_keys" in text
    assert "ck_search_events_payload_no_raw_pii" in text
    assert "ck_search_events_payload_target_hash" in text


@pytest.mark.asyncio
async def test_search_job_tables_exist_with_privacy_columns(
    tmp_db: DatabaseManager,
) -> None:
    jobs = await _columns(tmp_db, "search_jobs")
    events = await _columns(tmp_db, "search_events")

    assert "owner_key_hash" in jobs
    assert "user_id" not in jobs
    assert "target_hash" in jobs
    assert "target_value" not in jobs
    assert "email" not in jobs
    assert "phone" not in jobs
    assert "job_id" in events
    assert "payload" in events
    assert "target_value" not in events

    comment = await tmp_db.fetch_one(
        """
        SELECT col_description('search_jobs'::regclass, ordinal_position) AS comment
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'search_jobs'
          AND column_name = 'owner_key_hash'
        """
    )
    assert comment == {"comment": OWNER_KEY_HASH_COMMENT}


@pytest.mark.asyncio
async def test_search_jobs_defaults_to_hash_only_ttl_7d(
    tmp_db: DatabaseManager,
) -> None:
    row = await tmp_db.fetch_one(
        """
        INSERT INTO search_jobs (owner_key_hash, target_type, target_hash, status)
        VALUES ($1, 'email', $2, 'queued')
        RETURNING owner_key_hash, target_encrypted, created_at, expires_at
        """,
        (SAFE_OWNER_HASH, SAFE_TARGET_HASH),
    )

    assert row is not None
    assert row["owner_key_hash"] == SAFE_OWNER_HASH
    assert row["target_encrypted"] is None
    ttl = row["expires_at"] - row["created_at"]
    assert timedelta(days=6, hours=23) <= ttl <= timedelta(days=7, hours=1)


@pytest.mark.asyncio
async def test_search_jobs_rejects_raw_owner_key_and_bad_target_hash(
    tmp_db: DatabaseManager,
) -> None:
    with pytest.raises(DatabaseError):
        await tmp_db.execute(
            """
            INSERT INTO search_jobs (owner_key_hash, target_type, target_hash, status)
            VALUES ($1, 'email', $2, 'queued')
            """,
            ("analyst@example.test", SAFE_TARGET_HASH),
        )

    with pytest.raises(DatabaseError):
        await tmp_db.execute(
            """
            INSERT INTO search_jobs (owner_key_hash, target_type, target_hash, status)
            VALUES ($1, 'email', $2, 'queued')
            """,
            (SAFE_OWNER_HASH, "analyst@example.test"),
        )


@pytest.mark.asyncio
async def test_search_events_accept_hash_only_payload(
    tmp_db: DatabaseManager,
) -> None:
    job_id = await _insert_job(tmp_db)
    payload = {
        "target_hash": SAFE_TARGET_HASH,
        "connector": "mock",
        "status": "likely",
        "confidence": 60,
        "metadata": {"category": "social"},
    }

    await tmp_db.execute(
        """
        INSERT INTO search_events (job_id, seq, event_type, payload)
        VALUES ($1::uuid, 1, 'connector_result', $2::jsonb)
        """,
        (job_id, json.dumps(payload)),
    )

    row = await tmp_db.fetch_one(
        "SELECT payload FROM search_events WHERE job_id = $1::uuid AND seq = 1",
        (job_id,),
    )
    assert row is not None
    assert json.loads(row["payload"]) == payload


@pytest.mark.asyncio
async def test_search_events_reject_raw_pii_payloads(
    tmp_db: DatabaseManager,
) -> None:
    job_id = await _insert_job(tmp_db)
    bad_payloads = [
        {"target_hash": SAFE_TARGET_HASH, "target_value": "analyst@example.test"},
        {"target_hash": SAFE_TARGET_HASH, "metadata": {"email": "analyst@example.test"}},
        {"target_hash": SAFE_TARGET_HASH, "metadata": {"cpf": "123.456.789-10"}},
        {"target_hash": SAFE_TARGET_HASH, "detail": "+55 11 99999-9999"},
        {
            "target_hash": SAFE_TARGET_HASH,
            "raw_url": "https://example.test/u/analyst@example.test",
        },
    ]

    for seq, payload in enumerate(bad_payloads, start=1):
        with pytest.raises(DatabaseError):
            await tmp_db.execute(
                """
                INSERT INTO search_events (job_id, seq, event_type, payload)
                VALUES ($1::uuid, $2, 'connector_result', $3::jsonb)
                """,
                (job_id, seq, json.dumps(payload)),
            )


@pytest.mark.asyncio
async def test_search_events_reject_missing_or_invalid_target_hash(
    tmp_db: DatabaseManager,
) -> None:
    job_id = await _insert_job(tmp_db)

    for seq, payload in enumerate(
        [
            {"connector": "mock", "status": "likely"},
            {"target_hash": "analyst@example.test", "connector": "mock"},
        ],
        start=1,
    ):
        with pytest.raises(DatabaseError):
            await tmp_db.execute(
                """
                INSERT INTO search_events (job_id, seq, event_type, payload)
                VALUES ($1::uuid, $2, 'connector_result', $3::jsonb)
                """,
                (job_id, seq, json.dumps(payload)),
            )


@pytest.mark.asyncio
async def test_search_events_cascade_when_job_is_deleted(
    tmp_db: DatabaseManager,
) -> None:
    job_id = await _insert_job(tmp_db)

    await tmp_db.execute(
        """
        INSERT INTO search_events (job_id, seq, event_type, payload)
        VALUES ($1::uuid, 1, 'connector_result', $2::jsonb)
        """,
        (job_id, json.dumps({"target_hash": SAFE_TARGET_HASH, "connector": "mock"})),
    )
    await tmp_db.execute("DELETE FROM search_jobs WHERE id = $1::uuid", (job_id,))

    row = await tmp_db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM search_events WHERE job_id = $1::uuid",
        (job_id,),
    )
    assert row == {"cnt": 0}
