"""
NexusOSINT v3.0 — FastAPI Backend
Security upgrade over v2.3:
  - JWT authentication (python-jose) with 24h expiring tokens
  - Multi-user support via users.json (bcrypt passwords)
  - All API routes protected by Bearer token
  - slowapi rate limiting per IP + per user
  - SQLite audit log (aiosqlite) — every search logged
  - Admin endpoints: /api/admin/logs, /api/admin/users, /api/admin/stats
  - Legacy APP_PASSWORD still works as single-user fallback
"""
import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
import jwt
try:
    from jwt.exceptions import InvalidTokenError as JWTError
except ImportError:
    # Fallback para versões ou ambientes específicos
    from jwt import InvalidTokenError as JWTError
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

import tracemalloc

import aiosqlite
import psutil
from api.db import db as _db  # single-connection DatabaseManager (WAL + write queue)
from api.schemas import LoginRequest, SearchRequest  # I/O models — defined in leaf module
from api.deps import (  # auth dependency providers — extracted in Phase 15 Plan 02
    security,
    get_client_ip,
    _decode_token,
    _check_blacklist,
    get_current_user,
    get_admin_user,
)
from api.orchestrator import get_orchestrator, DegradationMode  # Phase 10: singleton + degradation
from api.watchdog import memory_watchdog_loop  # Phase 10: memory pressure watchdog
from api.config import (
    _ALLOWED_ORIGINS,
    _WEAK_JWT_SECRETS,
    APP_PASSWORD,
    AUDIT_DB,
    DATA_DIR,
    JWT_ALGORITHM,
    JWT_EXPIRE_HOURS,
    JWT_SECRET,
    LOG_LEVEL,
    MAX_BREACH_SERIALIZE,
    MAX_USERS,
    MEMORY_ALERT_MB,
    MEMORY_CRITICAL_PCT,
    MODULE_TIMEOUTS,
    OATHNET_API_KEY,
    RL_ADMIN_LIMIT,
    RL_LOGIN_LIMIT,
    RL_READ_LIMIT,
    RL_REGISTER_LIMIT,
    RL_SEARCH_LIMIT,
    RL_SPIDERFOOT_LIMIT,
    SPIDERFOOT_URL,
    USERS_FILE,
)
from api.services.auth_service import (
    _create_token,
    _ensure_default_user,
    _load_users,
    _revoke_token,
    _safe_hash,
    _save_users,
    _validate_jwt_secret,
    _verify_user,
)
from api.services.search_service import (
    _api_cache,
    _seen_breach_extra_keys,
    _serialize_breaches,
    _stream_search,
)
from api.services.admin_service import _validate_id
from modules.oathnet_client import oathnet_client  # async singleton — one TCP/TLS pool

load_dotenv()

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.WARNING))
logger = logging.getLogger("nexusosint")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan — replaces deprecated @app.on_event handlers."""
    # startup — D-09: fail hard if JWT_SECRET is missing or weak
    _validate_jwt_secret()
    tracemalloc.start(10)  # 10 frames — memory profiling for /health/memory
    _ensure_default_user()
    await _db.startup(db_path=AUDIT_DB)
    # D-05: expose singletons via app.state for Depends(get_db) / Depends(get_orchestrator_dep)
    application.state.db = _db
    application.state.orchestrator = get_orchestrator()
    # Phase 10: start memory watchdog as tracked background task
    watchdog_task = asyncio.create_task(
        memory_watchdog_loop(), name="memory-watchdog"
    )
    logger.info("NexusOSINT v3.0 started — %d allowed origins, tracemalloc active, memory watchdog active", len(_ALLOWED_ORIGINS))
    yield
    # shutdown — Phase 10: cancel watchdog + drain orchestrator before DB shutdown
    watchdog_task.cancel()
    await asyncio.gather(watchdog_task, return_exceptions=True)
    try:
        await get_orchestrator().cancel_all()
    except asyncio.CancelledError:
        raise
    except (RuntimeError, OSError) as exc:
        logger.warning("orchestrator.cancel_all() error during shutdown: %s", type(exc).__name__)
    await _db.shutdown()
    if oathnet_client:
        await oathnet_client.close()
    logger.info("NexusOSINT v3.0 shutdown complete")


app = FastAPI(title="NexusOSINT", version="3.0.0", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# ── Rate limiter — key function + registration ────────────────────────────────

def _rate_key(request: Request) -> str:
    """Prefer JWT sub for authenticated users, fall back to client IP."""
    token = request.cookies.get("nx_session")
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            sub = payload.get("sub")
            if sub:
                return f"u:{sub}"
        except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_key, storage_uri="memory://")
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom 429 handler — returns normalised JSON body with Retry-After header.

    Retry-After is estimated from the limit window when available, with a 60s
    fallback. This avoids the slowapi _inject_headers path which requires the
    return value to be a starlette Response (breaks endpoints that return dicts).
    """
    # exc.limit is a Limit object; its string form is e.g. "5 per 1 minute"
    limit = getattr(exc, "limit", None)
    try:
        # limits.Limit exposes .get_expiry_length() in some versions; fall back to 60
        retry_after = int(limit.get_expiry_length()) if limit and hasattr(limit, "get_expiry_length") else 60
    except Exception:
        retry_after = 60
    return JSONResponse(
        {"detail": "rate limit exceeded", "retry_after": retry_after},
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    # Monta a pasta static inteira para que /static/css/... funcione
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    # Atalhos para o HTML encontrar /css e /js diretamente
    app.mount("/css", StaticFiles(directory=str(static_path / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(static_path / "js")), name="js")


# ── Startup ───────────────────────────────────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Robots-Tag"]           = "noindex, nofollow, noarchive"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cross-Origin-Opener-Policy"]  = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"]= "unsafe-none"
        return response

app.add_middleware(SecurityHeadersMiddleware)


# Startup and shutdown are handled by the lifespan context manager above.


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def root():
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>NexusOSINT v3</h1>")


# ── Admin gate: troca Bearer token por HttpOnly cookie (bridge VULN-01) ──
@app.post("/api/admin/auth-gate")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_auth_gate(
    request: Request,
    response: Response,
    user: dict = Depends(get_admin_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """
    Recebe um Bearer token admin válido e define o cookie nx_session (HttpOnly).
    Bridge de transição entre localStorage e cookies (VULN-01/Fase 2).
    """
    response.set_cookie(
        key="nx_session",
        value=credentials.credentials,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=JWT_EXPIRE_HOURS * 3600,
        path="/",
    )
    return {"ok": True}


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Admin panel — auth server-side via cookie nx_session (VULN-03)."""
    token = request.cookies.get("nx_session")

    if token:
        try:
            payload = _decode_token(token)
            if payload.get("role") == "admin":
                admin_file = Path(__file__).parent.parent / "static" / "admin.html"
                if admin_file.exists():
                    return HTMLResponse(admin_file.read_text(encoding="utf-8"))
                return HTMLResponse("<h1>Admin panel not found</h1>", status_code=404)
        except HTTPException:
            pass  # token inválido/expirado → cai no fallback abaixo

    # Sem cookie válido: bridge page que lê localStorage e chama auth-gate
    # Após VULN-01 completo, esta página raramente será exibida
    return HTMLResponse("""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>NexusOSINT Admin</title>
<style>
  body{background:#0a0a0f;display:flex;align-items:center;
       justify-content:center;height:100vh;margin:0;
       font-family:monospace;color:#666;font-size:.85rem}
</style>
</head>
<body><span>Authenticating…</span>
<script>
(async () => {
  const t = localStorage.getItem('nx_token');
  if (!t) { location.replace('/'); return; }
  try {
    const r = await fetch('/api/admin/auth-gate', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + t }
    });
    // Se ok: cookie nx_session foi setado → recarrega para entrar pelo check de cookie
    if (r.ok) { location.replace('/admin'); }
    else       { location.replace('/'); }
  } catch { location.replace('/'); }
})();
</script>
</body></html>""")


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth")
@limiter.limit(RL_LOGIN_LIMIT)
async def auth_legacy(request: Request):
    """Legacy endpoint — kept for frontend compat. Returns ok:true if no password set."""
    if not APP_PASSWORD and not _load_users():
        return {"ok": True}
    # Just check if server is password-protected
    return {"ok": False, "requires_login": True}


@app.post("/api/login")
@limiter.limit(RL_LOGIN_LIMIT)
async def login(request: Request, body: LoginRequest):
    """JWT login. Define cookie HttpOnly nx_session (VULN-01).
    Rate limited by slowapi (RL_LOGIN_LIMIT, keyed by IP — supersedes _check_rate, FIND-04).
    """
    user = _verify_user(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token     = _create_token(user["username"], user["role"])
    max_age_s = JWT_EXPIRE_HOURS * 3600
    is_prod   = os.getenv("ENV", "dev").lower() == "prod"

    response = JSONResponse(content={
        "ok":         True,
        "token_type": "cookie",
        "expires_in": max_age_s,
        "username":   user["username"],
        "role":       user["role"],
    })
    response.set_cookie(
        key="nx_session",
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="strict",
        max_age=max_age_s,
        path="/",
    )
    return response


@app.get("/api/me")
@limiter.limit(RL_READ_LIMIT)
async def me(request: Request, user: dict = Depends(get_current_user)):
    """Returns current user info."""
    return {"username": user["sub"], "role": user.get("role", "user")}

@app.post("/api/logout")
@limiter.limit(RL_READ_LIMIT)
async def logout(request: Request, response: Response):
    """Termina sessão: revoga o JWT no blacklist e apaga o cookie nx_session (VULN-01)."""
    token = request.cookies.get("nx_session")
    if token:
        try:
            payload = _decode_token(token)
            await _revoke_token(payload.get("jti"), payload.get("exp"), db=_db)
        except HTTPException:
            pass  # token já inválido — só limpa o cookie
    response.delete_cookie("nx_session", path="/")
    return {"ok": True}

# ── Search ────────────────────────────────────────────────────────────────────

@app.post("/api/search")
@limiter.limit(RL_SEARCH_LIMIT)
async def search(
    request: Request,
    req: SearchRequest,
    user: dict = Depends(get_current_user),
):
    """Protected SSE search endpoint. Rate limited by slowapi (RL_SEARCH_LIMIT, per user)."""
    # Phase 10: gate on CRITICAL only — REDUCED still permits scans at lower ceiling
    if get_orchestrator().degradation_mode == DegradationMode.CRITICAL:
        raise HTTPException(
            status_code=503,
            detail="System under memory pressure — new scans temporarily rejected",
            headers={"Retry-After": "120"},
        )
    client_ip = get_client_ip(request)
    return StreamingResponse(
        _stream_search(req, user["sub"], client_ip, db=_db, orch=get_orchestrator()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Admin endpoints ───────────────────────────────────────────────────────────

@app.get("/api/admin/stats")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_stats(request: Request, _: dict = Depends(get_admin_user)):
    """Dashboard stats for admin."""
    try:
        today = datetime.now(timezone.utc).date().isoformat()

        today_row  = await _db.read_one(
            "SELECT COUNT(*) as cnt FROM searches WHERE ts LIKE ?", (f"{today}%",)
        )
        today_cnt = today_row["cnt"] if today_row else 0

        total_row  = await _db.read_one("SELECT COUNT(*) as cnt FROM searches")
        total_cnt = total_row["cnt"] if total_row else 0

        top_queries = await _db.read_all(
            """SELECT query, COUNT(*) as cnt FROM searches
               WHERE ts LIKE ? GROUP BY query ORDER BY cnt DESC LIMIT 10""",
            (f"{today}%",),
        )

        per_user = await _db.read_all(
            """SELECT username, COUNT(*) as cnt FROM searches
               WHERE ts LIKE ? GROUP BY username ORDER BY cnt DESC""",
            (f"{today}%",),
        )

        quota_left = quota_used = quota_limit = None
        quota_row = await _db.read_one(
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
    except aiosqlite.OperationalError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/admin/logs")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_logs(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    username: Optional[str] = None,
    _: dict = Depends(get_admin_user),
):
    """Recent audit logs with optional user filter."""
    try:
        if username:
            rows = [
                row async for row in _db.read_stream(
                    "SELECT * FROM searches WHERE username=? ORDER BY ts DESC LIMIT ? OFFSET ?",
                    (username, limit, offset),
                )
            ]
        else:
            rows = [
                row async for row in _db.read_stream(
                    "SELECT * FROM searches ORDER BY ts DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ]
        return {"logs": rows, "limit": limit, "offset": offset}
    except aiosqlite.OperationalError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/admin/users")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_list_users(request: Request, _: dict = Depends(get_admin_user)):
    """List all users (without password hashes)."""
    users = _load_users()
    return {
        k: {kk: vv for kk, vv in v.items() if kk != "password_hash"}
        for k, v in users.items()
    }


@app.post("/api/admin/users")
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


@app.delete("/api/admin/users/{username}")
@limiter.limit(RL_ADMIN_LIMIT)
async def admin_delete_user(
    request: Request,
    username: str,
    admin: dict = Depends(get_admin_user),
):
    """Deactivate a user (soft delete)."""
    # Validate username — no special chars
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


# ── Breach pagination endpoint ───────────────────────────────────────────────

@app.post("/api/search/more-breaches")
@limiter.limit(RL_SEARCH_LIMIT)
async def more_breaches(
    request: Request,
    body: dict,
    user: dict = Depends(get_current_user),
):
    """Fetch next page of breach results using OathNet cursor."""
    query  = body.get("query", "").strip()
    cursor = body.get("cursor", "")
    if not query or not cursor:
        raise HTTPException(status_code=400, detail="query and cursor required")
    if len(query) > 256:
        raise HTTPException(status_code=400, detail="Query too long")
    if oathnet_client is None:
        raise HTTPException(status_code=503, detail="OATHNET_API_KEY not configured")
    try:
        result = await oathnet_client.search_breach(query, cursor)
        if not result.success:
            raise HTTPException(status_code=502, detail=result.error or "Breach search failed")
        breaches_data = _serialize_breaches(result.breaches)
        return {
            "breaches":      breaches_data,
            "breach_count":  len(breaches_data),
            "results_found": result.results_found,
            "next_cursor":   result.next_cursor,
            "has_more":      bool(result.next_cursor),
        }
    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="OathNet API unreachable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OathNet API timed out")


# ── Victims API endpoints ────────────────────────────────────────────────────

@app.get("/api/victims/search")
@limiter.limit(RL_READ_LIMIT)
async def victims_search_endpoint(
    request: Request,
    q: str = "",
    page_size: int = 10,
    cursor: str = "",
    email: str = "",
    ip: str = "",
    discord_id: str = "",
    username: str = "",
    user: dict = Depends(get_current_user),
):
    """Search victim profiles (compromised machines)."""
    if oathnet_client is None:
        raise HTTPException(status_code=503, detail="OATHNET_API_KEY not configured")
    filters = {}
    if email:      filters["email"]      = email
    if ip:         filters["ip"]         = ip
    if discord_id: filters["discord_id"] = discord_id
    if username:   filters["username"]   = username
    ok, data = await oathnet_client.victims_search(q, page_size, cursor, "", **filters)
    if not ok:
        raise HTTPException(status_code=400, detail=data.get("error", "Search failed"))
    return data


@app.get("/api/victims/{log_id}/manifest")
@limiter.limit(RL_READ_LIMIT)
async def victims_manifest_endpoint(
    request: Request,
    log_id: str,
    user: dict = Depends(get_current_user),
):
    """Get file tree for a victim log."""
    _validate_id(log_id)
    if oathnet_client is None:
        raise HTTPException(status_code=503, detail="OATHNET_API_KEY not configured")
    ok, data = await oathnet_client.victims_manifest(log_id)
    if not ok:
        raise HTTPException(status_code=404, detail=data.get("error", "Not found"))
    return data


@app.get("/api/victims/{log_id}/files/{file_id}")
@limiter.limit(RL_READ_LIMIT)
async def victims_file_endpoint(
    request: Request,
    log_id: str,
    file_id: str,
    user: dict = Depends(get_current_user),
):
    """Get raw file content from a victim log."""
    _validate_id(log_id)
    _validate_id(file_id)
    if oathnet_client is None:
        raise HTTPException(status_code=503, detail="OATHNET_API_KEY not configured")
    ok, content_text = await oathnet_client.victims_file(log_id, file_id)
    if not ok:
        raise HTTPException(status_code=404, detail=content_text)
    return PlainTextResponse(content_text)


@app.get("/api/spiderfoot/status")
@limiter.limit(RL_READ_LIMIT)
async def sf_status(request: Request, _: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping")
            return {"available": r.status_code == 200, "url": SPIDERFOOT_URL}
    except httpx.HTTPError as exc:
        return {"available": False, "error": str(exc), "url": SPIDERFOOT_URL}


@app.get("/health")
@app.head("/health")
@limiter.limit(RL_READ_LIMIT)
async def health(request: Request):
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    mem_mb = mem.used / 1024 / 1024
    proc = psutil.Process()

    # Phase 10: single source of truth — orchestrator degradation_mode
    orch = get_orchestrator()
    uptime_s = round(time.time() - proc.create_time(), 1)
    wal_path = Path(str(AUDIT_DB) + "-wal")
    wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0
    degradation = orch.degradation_mode

    return {
        "status": "degraded" if degradation != DegradationMode.NORMAL else "healthy",
        "version": "3.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "memory_used_mb": round(mem_mb, 1),
        "memory_pct": mem.percent,
        "rss_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
        "cpu_pct": cpu,
        "swap_used_mb": round(swap.used / 1024 / 1024, 1),
        "agents_paused": degradation != DegradationMode.NORMAL,
        "cache_entries": len(_api_cache),
        # Phase 10 new fields
        "uptime_s":             uptime_s,
        "active_tasks":         orch.active_count,
        "semaphore_slots_free": orch.semaphore_slots_free,
        "wal_size_bytes":       wal_size_bytes,
        "degradation_mode":     degradation.value,
    }


@app.get("/health/memory")
@limiter.limit(RL_ADMIN_LIMIT)
async def health_memory(request: Request, _: dict = Depends(get_admin_user)):
    """Detailed memory profiling snapshot — admin only.
    Exposes RSS, VMS, tracemalloc current/peak, top allocations, and cache stats.
    Use for diagnosing memory leaks on the 1GB VPS.
    """
    proc = psutil.Process()
    mem_info = proc.memory_info()
    mem = psutil.virtual_memory()
    traced_current, traced_peak = tracemalloc.get_traced_memory()

    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")[:15]

    return {
        "rss_mb": round(mem_info.rss / 1024 / 1024, 1),
        "vms_mb": round(mem_info.vms / 1024 / 1024, 1),
        "system_memory_pct": mem.percent,
        "tracemalloc_current_mb": round(traced_current / 1024 / 1024, 2),
        "tracemalloc_peak_mb": round(traced_peak / 1024 / 1024, 2),
        "top_allocations": [
            {
                "file": str(stat.traceback),
                "size_kb": round(stat.size / 1024, 1),
                "count": stat.count,
            }
            for stat in top_stats
        ],
        "cache_size": len(_api_cache),
        "cache_maxsize": _api_cache.maxsize,
        "agents_paused": get_orchestrator().degradation_mode != DegradationMode.NORMAL,
    }


@app.get("/api/admin/breach-extra-keys")
@limiter.limit(RL_ADMIN_LIMIT)
async def breach_extra_keys(request: Request, _: dict = Depends(get_admin_user)):
    """Phase 13 diagnostic: return key names seen in breach extra_fields since process start.

    Accumulates across all real OathNet scans run while the container is up.
    Only key names are exposed — never field values (no PII leak risk).
    Resets on container restart. Run a few real queries before calling this.

    Use the result to build the Phase 14 breach card whitelist in render.js.
    """
    return {
        "keys": sorted(_seen_breach_extra_keys),
        "count": len(_seen_breach_extra_keys),
        "note": (
            "In-memory accumulator — resets on container restart. "
            "Run at least one real breach query before checking."
        ),
    }
