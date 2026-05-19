"""Persistent real-time OSINT job store.

R1-3 scope only: create/update jobs, append sanitized events, stream replay, and
purge expired jobs. API routes and orchestration arrive in later R1 steps.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from api.db import DatabaseManager, db as _db
from modules.connectors.base import ConnectorStatus, TargetType


JOB_TTL = timedelta(days=7)
TARGET_HASH_RE = re.compile(r"^[a-f0-9]{12}$")
OWNER_KEY_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
CONNECTOR_NAME_RE = re.compile(r"^[A-Za-z0-9:_\-.]{1,80}$")
EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
PHONE_RE = re.compile(r"(\+?\d{1,3}[ .-]?)?\(?\d{2,3}\)?[ .-]?\d{4,5}[ .-]\d{4}")
URL_RE = re.compile(r"https?://", re.IGNORECASE)


class JobStoreError(ValueError):
    """Base class for job store validation errors."""


class EventPayloadRejected(JobStoreError):
    """Raised when an event payload is unsafe to persist."""


SENSITIVE_EVENT_KEYS = frozenset(
    {
        "target",
        "target_value",
        "raw_target",
        "query",
        "raw",
        "raw_url",
        "url",
        "profile_url",
        "request_url",
        "raw_response",
        "headers",
        "body",
        "request_headers",
        "response_headers",
        "request_body",
        "response_body",
        "cookies",
        "cookie",
        "authorization",
        "auth",
        "bearer",
        "token",
        "secret",
        "api_key",
        "password",
        "credential",
        "credentials",
        "session",
        "set_cookie",
        "email",
        "account_email",
        "phone",
        "phone_number",
        "cpf",
        "document",
        "sensitive",
        "username",
        "account_username",
        "handle",
        "display_name",
    }
)

SAFE_EVENT_KEYS = frozenset(
    {
        "target_hash",
        "target_type",
        "job_id",
        "connector",
        "connectors_planned",
        "connectors_run",
        "event_type",
        "seq",
        "status",
        "overall_status",
        "confidence",
        "confidence_score",
        "confidence_level",
        "category",
        "labels",
        "tags",
        "cache_hit",
        "elapsed_ms",
        "fetched_at",
        "emitted_at",
        "metadata",
        "data",
        "evidence",
        "summary",
        "counts",
        "blocked_reason",
        "error_code",
        "source",
        "signal",
        "weight",
        "detail",
    }
)


def _database(db: DatabaseManager | None) -> DatabaseManager:
    return db if db is not None else _db


def _target_type_value(target_type: TargetType | str) -> str:
    if isinstance(target_type, TargetType):
        return target_type.value
    try:
        return TargetType(target_type).value
    except ValueError as exc:
        raise JobStoreError("invalid_target_type") from exc


def _status_value(status: ConnectorStatus | str) -> str:
    if isinstance(status, ConnectorStatus):
        return status.value
    try:
        return ConnectorStatus(status).value
    except ValueError as exc:
        raise JobStoreError("invalid_connector_status") from exc


def _validate_target_hash(target_hash: str) -> str:
    candidate = str(target_hash).strip().lower()
    if not TARGET_HASH_RE.fullmatch(candidate):
        raise JobStoreError("invalid_target_hash")
    return candidate


def _validate_owner_key_hash(owner_key_hash: str | None) -> str | None:
    if owner_key_hash is None:
        return None
    candidate = str(owner_key_hash).strip().lower()
    if not OWNER_KEY_HASH_RE.fullmatch(candidate):
        raise JobStoreError("invalid_owner_key_hash")
    return candidate


def _validate_connector_names(names: Sequence[str] | None) -> list[str]:
    if not names:
        return []
    clean: list[str] = []
    for name in names:
        candidate = str(name).strip()
        if not CONNECTOR_NAME_RE.fullmatch(candidate):
            raise JobStoreError("invalid_connector_name")
        clean.append(candidate)
    return clean


def _reject_sensitive_string(value: str, *, key: str) -> str:
    if key == "target_hash":
        return _validate_target_hash(value)
    if len(value) > 256:
        raise EventPayloadRejected("payload_string_too_long")
    if EMAIL_RE.search(value) or CPF_RE.search(value) or PHONE_RE.search(value) or URL_RE.search(value):
        raise EventPayloadRejected("payload_contains_sensitive_value")
    return value


def _sanitize_payload_value(value: Any, *, key: str) -> Any:
    normalized_key = key.lower()
    if normalized_key in SENSITIVE_EVENT_KEYS:
        raise EventPayloadRejected("payload_contains_sensitive_key")
    if normalized_key not in SAFE_EVENT_KEYS:
        raise EventPayloadRejected("payload_contains_unknown_key")

    if isinstance(value, Mapping):
        return _sanitize_payload_dict(value)
    if isinstance(value, list):
        return [_sanitize_payload_value(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload_value(item, key=key) for item in value]
    if isinstance(value, str):
        return _reject_sensitive_string(value, key=normalized_key)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            raise EventPayloadRejected("payload_contains_invalid_number")
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise EventPayloadRejected("payload_contains_unsupported_value")


def _sanitize_payload_dict(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key).strip()
        if not key_text:
            raise EventPayloadRejected("payload_contains_empty_key")
        sanitized[key_text] = _sanitize_payload_value(value, key=key_text)
    return sanitized


def sanitize_event_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe hash-only payload or raise before DB write."""
    if not isinstance(payload, Mapping):
        raise EventPayloadRejected("payload_must_be_object")
    sanitized = _sanitize_payload_dict(payload)
    target_hash = sanitized.get("target_hash")
    if not isinstance(target_hash, str):
        raise EventPayloadRejected("payload_missing_target_hash")
    sanitized["target_hash"] = _validate_target_hash(target_hash)
    return sanitized


def _decode_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise JobStoreError("invalid_event_payload_json") from exc
        if isinstance(decoded, dict):
            return decoded
        raise JobStoreError("event_payload_not_object")
    if isinstance(payload, dict):
        return payload
    raise JobStoreError("event_payload_not_object")


async def create_job(
    *,
    owner_key_hash: str | None,
    target_type: TargetType | str,
    target_hash: str,
    connectors_planned: Sequence[str] | None,
    db: DatabaseManager | None = None,
) -> UUID:
    """Insert a queued job and return its UUID.

    `owner_key_hash=None` is explicit for unauthenticated/dev/admin contexts.
    Raw usernames, emails, phones, and target values are never accepted here.
    """
    job_id = uuid4()
    now = datetime.now(timezone.utc)
    expires_at = now + JOB_TTL
    await _database(db).execute(
        """
        INSERT INTO search_jobs
            (id, owner_key_hash, target_type, target_hash, status,
             connectors_planned, created_at, expires_at)
        VALUES ($1, $2, $3, $4, 'queued', $5, $6, $7)
        """,
        (
            job_id,
            _validate_owner_key_hash(owner_key_hash),
            _target_type_value(target_type),
            _validate_target_hash(target_hash),
            _validate_connector_names(connectors_planned),
            now,
            expires_at,
        ),
    )
    return job_id


async def mark_running(job_id: UUID, *, db: DatabaseManager | None = None) -> None:
    await _database(db).execute(
        "UPDATE search_jobs SET status='running', started_at=NOW() WHERE id=$1",
        (job_id,),
    )


async def mark_done(
    job_id: UUID,
    *,
    overall_status: ConnectorStatus | str,
    overall_confidence: int,
    connectors_run: Sequence[str] | None,
    elapsed_ms: int,
    db: DatabaseManager | None = None,
) -> None:
    if not 0 <= overall_confidence <= 100:
        raise JobStoreError("invalid_overall_confidence")
    if elapsed_ms < 0:
        raise JobStoreError("invalid_elapsed_ms")
    await _database(db).execute(
        """
        UPDATE search_jobs
        SET status='done',
            overall_status=$1,
            overall_confidence=$2,
            connectors_run=$3,
            finished_at=NOW(),
            elapsed_ms=$4
        WHERE id=$5
        """,
        (
            _status_value(overall_status),
            overall_confidence,
            _validate_connector_names(connectors_run),
            elapsed_ms,
            job_id,
        ),
    )


async def mark_failed(job_id: UUID, *, db: DatabaseManager | None = None) -> None:
    await _database(db).execute(
        "UPDATE search_jobs SET status='failed', finished_at=NOW() WHERE id=$1",
        (job_id,),
    )


async def get_job(
    job_id: UUID,
    *,
    owner_key_hash: str | None,
    db: DatabaseManager | None = None,
) -> dict[str, Any] | None:
    owner_hash = _validate_owner_key_hash(owner_key_hash)
    if owner_hash is None:
        return await _database(db).fetch_one(
            "SELECT * FROM search_jobs WHERE id=$1 AND owner_key_hash IS NULL",
            (job_id,),
        )
    return await _database(db).fetch_one(
        "SELECT * FROM search_jobs WHERE id=$1 AND owner_key_hash=$2",
        (job_id, owner_hash),
    )


async def append_event(
    job_id: UUID,
    seq: int,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    db: DatabaseManager | None = None,
) -> None:
    """Insert one sanitized event. Caller computes monotonic `seq` per job."""
    if seq < 1:
        raise JobStoreError("invalid_event_seq")
    event = str(event_type).strip()
    if not EVENT_TYPE_RE.fullmatch(event):
        raise JobStoreError("invalid_event_type")
    sanitized_payload = sanitize_event_payload(payload)
    await _database(db).execute(
        """
        INSERT INTO search_events (job_id, seq, event_type, payload)
        VALUES ($1, $2, $3, $4::jsonb)
        """,
        (
            job_id,
            seq,
            event,
            json.dumps(sanitized_payload, sort_keys=True, separators=(",", ":")),
        ),
    )


async def stream_events(
    job_id: UUID,
    *,
    from_seq: int = 0,
    owner_key_hash: str | None,
    db: DatabaseManager | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Replay events for SSE using a server-side cursor, never fetch_all."""
    if from_seq < 0:
        raise JobStoreError("invalid_from_seq")
    owner_hash = _validate_owner_key_hash(owner_key_hash)
    if owner_hash is None:
        query = (
            "SELECT e.seq, e.event_type, e.payload, e.emitted_at "
            "FROM search_events e "
            "JOIN search_jobs j ON j.id = e.job_id "
            "WHERE e.job_id = $1 AND e.seq > $2 AND j.owner_key_hash IS NULL "
            "ORDER BY e.seq ASC"
        )
        params: tuple[Any, ...] = (job_id, from_seq)
    else:
        query = (
            "SELECT e.seq, e.event_type, e.payload, e.emitted_at "
            "FROM search_events e "
            "JOIN search_jobs j ON j.id = e.job_id "
            "WHERE e.job_id = $1 AND e.seq > $2 AND j.owner_key_hash = $3 "
            "ORDER BY e.seq ASC"
        )
        params = (job_id, from_seq, owner_hash)

    async for row in _database(db).fetch_stream(query, params):
        yield {
            "seq": row["seq"],
            "event_type": row["event_type"],
            "payload": _decode_payload(row["payload"]),
            "emitted_at": row["emitted_at"],
        }


async def purge_expired(*, db: DatabaseManager | None = None) -> int:
    """Delete expired jobs; events cascade via FK ON DELETE CASCADE."""
    row = await _database(db).fetch_one(
        """
        WITH deleted AS (
            DELETE FROM search_jobs
            WHERE expires_at < $1
            RETURNING 1
        )
        SELECT COUNT(*)::int AS deleted FROM deleted
        """,
        (datetime.now(timezone.utc),),
    )
    return int(row["deleted"]) if row is not None else 0
