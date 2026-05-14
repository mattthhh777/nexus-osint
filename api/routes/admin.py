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
    offset: int = 0,
    username: Optional[str] = None,
    _: dict = Depends(get_admin_user),
    db: DatabaseManager = Depends(get_db),
):
    """Recent audit logs with optional user filter."""
    try:
        limit = max(1, min(limit, 100))
        offset = max(0, min(offset, 10_000))
        if username and not re.match(r'^[a-zA-Z0-9_.\\-]{1,64}$', username):
            raise HTTPException(status_code=400, detail="Invalid username format")
        if username:
            rows = [
                row async for row in db.fetch_stream(
                    "SELECT * FROM searches WHERE username=$1 ORDER BY ts DESC LIMIT $2 OFFSET $3",
                    (username, limit, offset),
                )
            ]
        else:
            rows = [
                row async for row in db.fetch_stream(
                    "SELECT * FROM searches ORDER BY ts DESC LIMIT $1 OFFSET $2",
                    (limit, offset),
                )
            ]
        return {"logs": rows, "limit": limit, "offset": offset}
    except HTTPException:
        raise
    except DatabaseError as exc:
        logger.error("admin_logs database error: %s", type(exc).__name__)
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
