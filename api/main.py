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
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
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


# ── Routers (D-03 Step 4 — routes extracted to api.routes.*) ────────────────
from api.routes import root as _root_routes  # noqa: E402 — partial-init import is intentional (D-04-01)
from api.routes import auth as _auth_routes  # noqa: E402
from api.routes import admin as _admin_routes  # noqa: E402
from api.routes import search as _search_routes  # noqa: E402
app.include_router(_root_routes.router)
app.include_router(_auth_routes.router)
app.include_router(_admin_routes.router)
app.include_router(_search_routes.router)
