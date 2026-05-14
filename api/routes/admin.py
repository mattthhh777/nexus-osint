"""Admin routes: stats, logs, user CRUD."""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.config import MAX_USERS, RL_ADMIN_LIMIT, RL_REGISTER_LIMIT
from api.db import DatabaseError, DatabaseManager
from api.deps import get_admin_user, get_db
from api.limiter import limiter
from api.services.auth_service import _load_users, _safe_hash, _save_users

router = APIRouter()
logger = logging.getLogger("nexusosint.admin")


@router.get("/api/admin/stats")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_stats(
    request: Request,
    _: dict = Depends(get_admin_user),
    db: DatabaseManager = Depends(get_db),
):
    """Dashboard stats for admin."""
    try:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tomorrow_start = today_start + timedelta(days=1)

        today_row = await db.fetch_one(
            "SELECT COUNT(*) as cnt FROM searches WHERE ts >= $1 AND ts < $2",
            (today_start, tomorrow_start),
        )
        today_cnt = today_row["cnt"] if today_row else 0

        total_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM searches")
        total_cnt = total_row["cnt"] if total_row else 0

        top_queries = await db.fetch_all(
            """SELECT query, COUNT(*) as cnt FROM searches
               WHERE ts >= $1 AND ts < $2 GROUP BY query ORDER BY cnt DESC LIMIT 10""",
            (today_start, tomorrow_start),
        )

        per_user = await db.fetch_all(
            """SELECT username, COUNT(*) as cnt FROM searches
               WHERE ts >= $1 AND ts < $2 GROUP BY username ORDER BY cnt DESC LIMIT 100""",
            (today_start, tomorrow_start),
        )

        quota_left = quota_used = quota_limit = None
        quota_row = await db.fetch_one(
            "SELECT used_today, left_today, daily_limit FROM quota_log ORDER BY ts DESC LIMIT 1"
        )
        if quota_row:
            quota_used  = quota_row["used_today"]
            quota_left  = quota_row["left_today"]
            quota_limit = quota_row["daily_limit"]

        users = _load_users()
        return {
            "searches_today":    today_cnt,
            "searches_total":    total_cnt,
            "active_users":      len([u for u in users.values() if u.get("active", True)]),
            "top_queries_today": top_queries,
            "searches_per_user": per_user,
            "quota_left":        quota_left,
            "quota_used":        quota_used,
            "quota_limit":       quota_limit,
        }
    except DatabaseError as exc:
        logger.error("admin_stats database error: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.get("/api/admin/logs")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_logs(
    request: Request,
    limit: int = 50,
    before_ts: Optional[str] = None,
    before_id: Optional[int] = None,
    username: Optional[str] = None,
    _: dict = Depends(get_admin_user),
    db: DatabaseManager = Depends(get_db),
):
    """Audit log list with keyset pagination. No payload in list response."""
    from datetime import datetime as _dt
    _LIST_COLS = (
        "id, ts, username, ip, query, query_type, mode,"
        " breach_count, stealer_count, social_count, elapsed_s, success"
    )
    try:
        limit = max(1, min(limit, 100))
        if username and not re.match(r'^[a-zA-Z0-9_.\-]{1,64}$', username):
            raise HTTPException(status_code=400, detail="Invalid username format")

        before_dt = None
        if before_ts:
            try:
                before_dt = _dt.fromisoformat(before_ts.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid before_ts format")

        has_cursor = before_dt is not None and before_id is not None

        if has_cursor and username:
            rows = await db.fetch_all(
                f"SELECT {_LIST_COLS} FROM searches"
                " WHERE (ts, id) < ($1, $2) AND username=$4"
                " ORDER BY ts DESC, id DESC LIMIT $3",
                (before_dt, before_id, limit, username),
            )
        elif has_cursor:
            rows = await db.fetch_all(
                f"SELECT {_LIST_COLS} FROM searches"
                " WHERE (ts, id) < ($1, $2)"
                " ORDER BY ts DESC, id DESC LIMIT $3",
                (before_dt, before_id, limit),
            )
        elif username:
            rows = await db.fetch_all(
                f"SELECT {_LIST_COLS} FROM searches"
                " WHERE username=$1"
                " ORDER BY ts DESC, id DESC LIMIT $2",
                (username, limit),
            )
        else:
            rows = await db.fetch_all(
                f"SELECT {_LIST_COLS} FROM searches"
                " ORDER BY ts DESC, id DESC LIMIT $1",
                (limit,),
            )

        next_cursor = None
        if len(rows) == limit:
            last = rows[-1]
            last_ts = last["ts"]
            next_cursor = {
                "before_ts": last_ts.isoformat() if hasattr(last_ts, "isoformat") else str(last_ts),
                "before_id": last["id"],
            }

        return {"items": rows, "next": next_cursor}
    except HTTPException:
        raise
    except DatabaseError as exc:
        logger.error("admin_logs database error: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.get("/api/admin/logs/{log_id}")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_log_detail(
    request: Request,
    log_id: int,
    _: dict = Depends(get_admin_user),
    db: DatabaseManager = Depends(get_db),
):
    """Single audit log entry with full payload column."""
    try:
        row = await db.fetch_one(
            "SELECT * FROM searches WHERE id = $1",
            (log_id,),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Log entry not found")
        return row
    except HTTPException:
        raise
    except DatabaseError as exc:
        logger.error("admin_log_detail database error: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.get("/api/admin/users")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_list_users(request: Request, _: dict = Depends(get_admin_user)):
    """List all users (without password hashes)."""
    users = _load_users()
    return {
        k: {kk: vv for kk, vv in v.items() if kk != "password_hash"}
        for k, v in users.items()
    }


@router.post("/api/admin/users")
@limiter.limit(RL_REGISTER_LIMIT)
async def admin_create_user(
    request: Request,
    body: dict,
    _: dict = Depends(get_admin_user),
):
    """Create a new user. Body: {username, password, role}"""
    uname    = body.get("username", "").strip()
    password = body.get("password", "")
    role     = body.get("role", "user")

    if not uname or not password:
        raise HTTPException(status_code=400, detail="username and password required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not re.match(r'^[a-zA-Z0-9_.\\-]{1,64}$', uname):
        raise HTTPException(status_code=400, detail="Username: only letters, numbers, _ - . (max 64)")
    if role not in ("admin", "user"):
        role = "user"

    users = _load_users()

    # D-12: Registration capacity cap — fail before writing
    if len(users) >= MAX_USERS:
        raise HTTPException(status_code=403, detail="registration capacity reached")

    if uname in users:
        raise HTTPException(status_code=409, detail="User already exists")

    users[uname] = {
        "password_hash": _safe_hash(password),
        "role":          role,
        "created_at":    datetime.now(timezone.utc).isoformat(),
        "active":        True,
    }
    _save_users(users)
    return {"ok": True, "username": uname, "role": role}


@router.delete("/api/admin/users/{username}")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_delete_user(
    request: Request,
    username: str,
    admin: dict = Depends(get_admin_user),
):
    """Deactivate a user (soft delete)."""
    if not re.match(r'^[a-zA-Z0-9_.\\-]{1,64}$', username):
        raise HTTPException(status_code=400, detail="Invalid username format")
    if username == admin["sub"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    users = _load_users()
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    users[username]["active"] = False
    _save_users(users)
    return {"ok": True}
