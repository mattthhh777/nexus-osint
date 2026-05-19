"""Persistent real-time OSINT job store.

R1-3 scope only: create/update jobs, append sanitized events, stream replay, and
purge expired jobs. API routes and orchestration arrive in later R1 steps.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from api.db import DatabaseManager, db as _db
from modules.connectors.base import ConnectorStatus, TargetType


JOB_TTL = timedelta(days=7)
TARGET_HASH_RE = re.compile(r"^[a-f0-9]{12}$")
OWNER_KEY_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
CONNECTOR_NAME_RE = re.compile(r"^[A-Za-z0-9:_\-.]{1,80}$")
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
        "detail",
        "metadata",
        "data",
        "labels",
        "tags",
        "source",
        "category",
    }
)

SAFE_EVENT_KEYS = frozenset(
    {
        "target_hash",
        "target_type",
        "job_id",
        "connector",
        "event_type",
        "seq",
        "status",
        "overall_status",
        "confidence_score",
        "confidence_level",
        "cache_hit",
        "elapsed_ms",
        "fetched_at",
        "emitted_at",
        "reason_code",
    }
)

CONFIDENCE_LEVELS = frozenset({"high", "medium", "low", "none"})
ALLOWED_REASON_CODES = frozenset(
    {
        "job_started",
        "job_running",
        "job_done",
        "job_failed",
        "connector_started",
        "connector_result",
        "connector_done",
        "connector_blocked",
        "connector_error",
        "cache_hit",
        "cache_miss",
        "rate_limited",
    }
)
ALLOWED_EVENT_TYPES = frozenset(
    {
        "job_started",
        "job_running",
        "job_done",
        "job_failed",
        "connector_started",
        "connector_result",
        "connector_done",
        "connector_blocked",
        "connector_error",
        "summary",
        "heartbeat",
    }
)
ALLOWED_CONNECTOR_NAMES = frozenset({"mock", "carrier_lookup"})
ALLOWED_CONNECTOR_PREFIXES = ("sherlock:", "oathnet:", "thordata:")


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
        if not _is_controlled_connector(candidate):
            raise JobStoreError("invalid_connector_name")
        clean.append(candidate)
    return clean


def _is_controlled_connector(candidate: str) -> bool:
    if not CONNECTOR_NAME_RE.fullmatch(candidate):
        return False
    return candidate in ALLOWED_CONNECTOR_NAMES or candidate.startswith(ALLOWED_CONNECTOR_PREFIXES)


def _event_type_value(event_type: str) -> str:
    event = str(event_type).strip()
    if event not in ALLOWED_EVENT_TYPES:
        raise JobStoreError("invalid_event_type")
    return event


def _reject_sensitive_string(value: str) -> None:
    if len(value) > 256:
        raise EventPayloadRejected("payload_string_too_long")
    if EMAIL_RE.search(value) or CPF_RE.search(value) or PHONE_RE.search(value) or URL_RE.search(value):
        raise EventPayloadRejected("payload_contains_sensitive_value")


def _validate_job_id(value: Any, *, canonical_job_id: UUID) -> str:
    try:
        candidate = value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise EventPayloadRejected("payload_invalid_job_id") from exc
    if candidate != canonical_job_id:
        raise EventPayloadRejected("payload_job_id_mismatch")
    return str(canonical_job_id)


def _validate_seq(value: Any, *, canonical_seq: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EventPayloadRejected("payload_invalid_seq")
    if value != canonical_seq:
        raise EventPayloadRejected("payload_seq_mismatch")
    return canonical_seq


def _validate_event_type(value: Any, *, canonical_event_type: str) -> str:
    if not isinstance(value, str):
        raise EventPayloadRejected("payload_invalid_event_type")
    try:
        candidate = _event_type_value(value)
    except JobStoreError as exc:
        raise EventPayloadRejected("payload_invalid_event_type") from exc
    if candidate != canonical_event_type:
        raise EventPayloadRejected("payload_event_type_mismatch")
    return canonical_event_type


def _validate_controlled_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise EventPayloadRejected(f"payload_invalid_{field}")
    candidate = value.strip()
    _reject_sensitive_string(candidate)
    return candidate


def _validate_timestamp(value: Any, *, field: str) -> str:
    if not isinstance(value, datetime):
        raise EventPayloadRejected(f"payload_invalid_{field}")
    return value.astimezone(timezone.utc).isoformat()


def _sanitize_payload_field(
    *,
    key: str,
    value: Any,
    canonical_job_id: UUID,
    canonical_seq: int,
    canonical_event_type: str,
    canonical_target_hash: str,
    canonical_target_type: str,
    planned_connectors: set[str],
) -> Any:
    if isinstance(value, Mapping) or isinstance(value, (list, tuple)):
        raise EventPayloadRejected("payload_nested_values_forbidden")
    if isinstance(value, str):
        _reject_sensitive_string(value)

    if key == "target_hash":
        candidate = _validate_target_hash(str(value))
        if candidate != canonical_target_hash:
            raise EventPayloadRejected("payload_target_hash_mismatch")
        return canonical_target_hash
    if key == "target_type":
        candidate = _target_type_value(str(value))
        if candidate != canonical_target_type:
            raise EventPayloadRejected("payload_target_type_mismatch")
        return canonical_target_type
    if key == "job_id":
        return _validate_job_id(value, canonical_job_id=canonical_job_id)
    if key == "event_type":
        return _validate_event_type(value, canonical_event_type=canonical_event_type)
    if key == "seq":
        return _validate_seq(value, canonical_seq=canonical_seq)
    if key == "connector":
        candidate = _validate_controlled_string(value, field=key)
        if not _is_controlled_connector(candidate):
            raise EventPayloadRejected("payload_invalid_connector")
        if candidate not in planned_connectors:
            raise EventPayloadRejected("payload_connector_not_planned")
        return candidate
    if key in {"status", "overall_status"}:
        return _status_value(str(value))
    if key == "confidence_score":
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise EventPayloadRejected("payload_invalid_confidence_score")
        return value
    if key == "confidence_level":
        candidate = _validate_controlled_string(value, field=key)
        if candidate not in CONFIDENCE_LEVELS:
            raise EventPayloadRejected("payload_invalid_confidence_level")
        return candidate
    if key == "cache_hit":
        if not isinstance(value, bool):
            raise EventPayloadRejected("payload_invalid_cache_hit")
        return value
    if key == "elapsed_ms":
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise EventPayloadRejected("payload_invalid_elapsed_ms")
        return value
    if key in {"fetched_at", "emitted_at"}:
        return _validate_timestamp(value, field=key)
    if key == "reason_code":
        candidate = _validate_controlled_string(value, field=key)
        if candidate not in ALLOWED_REASON_CODES:
            raise EventPayloadRejected("payload_invalid_reason_code")
        return candidate
    raise EventPayloadRejected("payload_contains_unknown_key")


def sanitize_event_payload(
    payload: Mapping[str, Any],
    *,
    canonical_job_id: UUID,
    canonical_seq: int,
    canonical_event_type: str,
    canonical_target_hash: str,
    canonical_target_type: str,
    planned_connectors: set[str],
) -> dict[str, Any]:
    """Return a JSON-safe hash-only payload or raise before DB write."""
    if not isinstance(payload, Mapping):
        raise EventPayloadRejected("payload_must_be_object")

    sanitized: dict[str, Any] = {
        "target_hash": canonical_target_hash,
        "event_type": canonical_event_type,
        "seq": canonical_seq,
    }
    for key, value in payload.items():
        normalized_key = str(key).strip().lower()
        if not normalized_key:
            raise EventPayloadRejected("payload_contains_empty_key")
        if normalized_key in SENSITIVE_EVENT_KEYS:
            raise EventPayloadRejected("payload_contains_sensitive_key")
        if normalized_key not in SAFE_EVENT_KEYS:
            raise EventPayloadRejected("payload_contains_unknown_key")
        sanitized[normalized_key] = _sanitize_payload_field(
            key=normalized_key,
            value=value,
            canonical_job_id=canonical_job_id,
            canonical_seq=canonical_seq,
            canonical_event_type=canonical_event_type,
            canonical_target_hash=canonical_target_hash,
            canonical_target_type=canonical_target_type,
            planned_connectors=planned_connectors,
        )
    sanitized["target_hash"] = canonical_target_hash
    sanitized["event_type"] = canonical_event_type
    sanitized["seq"] = canonical_seq
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
    row = await _database(db).fetch_one(
        """
        UPDATE search_jobs
        SET status='running', started_at=NOW()
        WHERE id=$1 AND status='queued' AND expires_at >= NOW()
        RETURNING id
        """,
        (job_id,),
    )
    if row is None:
        raise JobStoreError("invalid_job_transition")


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
    row = await _database(db).fetch_one(
        """
        UPDATE search_jobs
        SET status='done',
            overall_status=$1,
            overall_confidence=$2,
            connectors_run=$3,
            finished_at=NOW(),
            elapsed_ms=$4
        WHERE id=$5 AND status IN ('queued', 'running') AND expires_at >= NOW()
        RETURNING id
        """,
        (
            _status_value(overall_status),
            overall_confidence,
            _validate_connector_names(connectors_run),
            elapsed_ms,
            job_id,
        ),
    )
    if row is None:
        raise JobStoreError("invalid_job_transition")


async def mark_failed(job_id: UUID, *, db: DatabaseManager | None = None) -> None:
    row = await _database(db).fetch_one(
        """
        UPDATE search_jobs
        SET status='failed', finished_at=NOW()
        WHERE id=$1 AND status IN ('queued', 'running') AND expires_at >= NOW()
        RETURNING id
        """,
        (job_id,),
    )
    if row is None:
        raise JobStoreError("invalid_job_transition")


async def get_job(
    job_id: UUID,
    *,
    owner_key_hash: str | None,
    db: DatabaseManager | None = None,
) -> dict[str, Any] | None:
    owner_hash = _validate_owner_key_hash(owner_key_hash)
    if owner_hash is None:
        return await _database(db).fetch_one(
            "SELECT * FROM search_jobs WHERE id=$1 AND owner_key_hash IS NULL AND expires_at >= NOW()",
            (job_id,),
        )
    return await _database(db).fetch_one(
        "SELECT * FROM search_jobs WHERE id=$1 AND owner_key_hash=$2 AND expires_at >= NOW()",
        (job_id, owner_hash),
    )


async def _get_active_job_for_owner(
    job_id: UUID,
    *,
    owner_key_hash: str | None,
    db: DatabaseManager,
) -> dict[str, Any]:
    owner_hash = _validate_owner_key_hash(owner_key_hash)
    if owner_hash is None:
        row = await db.fetch_one(
            """
            SELECT id, target_type, target_hash, connectors_planned
            FROM search_jobs
            WHERE id=$1 AND owner_key_hash IS NULL AND expires_at >= NOW()
            """,
            (job_id,),
        )
    else:
        row = await db.fetch_one(
            """
            SELECT id, target_type, target_hash, connectors_planned
            FROM search_jobs
            WHERE id=$1 AND owner_key_hash=$2 AND expires_at >= NOW()
            """,
            (job_id, owner_hash),
        )
    if row is None:
        raise JobStoreError("job_not_found")
    return row


async def append_event(
    job_id: UUID,
    seq: int,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    owner_key_hash: str | None,
    db: DatabaseManager | None = None,
) -> None:
    """Insert one sanitized event. Caller computes monotonic `seq` per job."""
    if seq < 1:
        raise JobStoreError("invalid_event_seq")
    event = _event_type_value(event_type)
    database = _database(db)
    job = await _get_active_job_for_owner(job_id, owner_key_hash=owner_key_hash, db=database)
    planned_connectors = set(job["connectors_planned"] or [])
    sanitized_payload = sanitize_event_payload(
        payload,
        canonical_job_id=job_id,
        canonical_seq=seq,
        canonical_event_type=event,
        canonical_target_hash=job["target_hash"],
        canonical_target_type=job["target_type"],
        planned_connectors=planned_connectors,
    )
    await database.execute(
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
            "AND j.expires_at >= NOW() "
            "ORDER BY e.seq ASC"
        )
        params: tuple[Any, ...] = (job_id, from_seq)
    else:
        query = (
            "SELECT e.seq, e.event_type, e.payload, e.emitted_at "
            "FROM search_events e "
            "JOIN search_jobs j ON j.id = e.job_id "
            "WHERE e.job_id = $1 AND e.seq > $2 AND j.owner_key_hash = $3 "
            "AND j.expires_at >= NOW() "
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
