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
import api.budget as _budget
from api.config import THORDATA_PROXY_URL
from modules.sherlock_wrapper import _masked_proxy_log
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


async def _thordata_startup_check() -> None:
    """Phase 16 D-07: non-blocking Thordata proxy reachability check on startup.

    Sets api.budget._proxy_active. Failure does NOT crash the app —
    Sherlock falls back to direct DO IP path. Logs masked URL only (D-H5).
    """
    if not THORDATA_PROXY_URL:
        logger.info("Thordata proxy unset — Sherlock will use direct DO IP")
        _budget._proxy_active = False
        return

    masked = _masked_proxy_log(THORDATA_PROXY_URL)
    try:
        async with httpx.AsyncClient(
            proxy=THORDATA_PROXY_URL,
            timeout=10.0,
            verify=False,
        ) as client:
            resp = await client.get("https://api.ipify.org", params={"format": "text"})
            resp.raise_for_status()
            exit_ip = resp.text.strip()[:64]
        _budget._proxy_active = True
        logger.info("Thordata proxy OK | proxy=%s exit_ip=%s", masked, exit_ip)
    except (httpx.ProxyError, httpx.TimeoutException, httpx.ConnectError,
            httpx.HTTPStatusError, httpx.HTTPError) as exc:
        _budget._proxy_active = False
        logger.warning(
            "Thordata proxy unavailable | proxy=%s reason=%s — Sherlock will use direct DO IP",
            masked, type(exc).__name__,
        )


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
    # Phase 16 D-07: probe Thordata proxy; sets _budget._proxy_active before first request
    await _thordata_startup_check()
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



# ── Routers (D-03 Step 4 — routes extracted to api.routes.*) ────────────────
from api.routes import root as _root_routes  # noqa: E402 — partial-init import is intentional (D-04-01)
from api.routes import auth as _auth_routes  # noqa: E402
from api.routes import admin as _admin_routes  # noqa: E402
from api.routes import search as _search_routes  # noqa: E402
from api.routes import victims as _victims_routes  # noqa: E402
from api.routes import spiderfoot as _spiderfoot_routes  # noqa: E402
from api.routes import health as _health_routes  # noqa: E402
app.include_router(_root_routes.router)
app.include_router(_auth_routes.router)
app.include_router(_admin_routes.router)
app.include_router(_search_routes.router)
app.include_router(_victims_routes.router)
app.include_router(_spiderfoot_routes.router)
app.include_router(_health_routes.router)
