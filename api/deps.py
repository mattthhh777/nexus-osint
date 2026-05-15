"""
FastAPI dependency providers for NexusOSINT.

Scope: Only Depends()-compatible callables live here.
  - security  — HTTPBearer instance (credentials extractor)
  - get_client_ip — real IP extraction through Cloudflare/Nginx
  - _decode_token  — JWT decode + 401 on failure
  - _check_blacklist — blacklist look-up + fail-closed on DB error
  - get_current_user — primary auth dependency (cookie → Bearer fallback)
  - get_admin_user   — role-guard on top of get_current_user
  - get_db            — request.app.state.db (DatabaseManager singleton)
  - get_orchestrator_dep — request.app.state.orchestrator (TaskOrchestrator singleton)

Import contract (D-05):
  - stdlib: time, typing, ipaddress
  - 3rd party: fastapi, fastapi.security, jwt (PyJWT)
  - internal: api.db — allowed (db is below deps in the import graph)
  - PROHIBITED: api.main — would create a circular import
"""
import ipaddress
import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt
try:
    from jwt.exceptions import InvalidTokenError as JWTError
except ImportError:
    from jwt import InvalidTokenError as JWTError

from api.config import JWT_ALGORITHM, JWT_SECRET
from api.db import DatabaseError, db as _db, DatabaseManager
from api.orchestrator import TaskOrchestrator, get_orchestrator
from api.services.auth_service import _load_users

logger = logging.getLogger("nexusosint.deps")

# ── Credentials extractor ─────────────────────────────────────────────────────
security = HTTPBearer(auto_error=False)

# ── Blacklist rate-limit state ────────────────────────────────────────────────
# Rate-limit duplicate blacklist-failure log messages to once per minute.
_last_blacklist_warn: list[float] = [0.0]


# ── Client IP extraction ──────────────────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    """Extrai IP real com cadeia de confiança: Cloudflare → Nginx → direto.
    Valida formato antes de retornar — nunca retorna um header forjável bruto.
    """
    for header in ("X-Real-IP",):
        val = request.headers.get(header, "").strip()
        if val:
            try:
                ipaddress.ip_address(val)
                return val
            except ValueError:
                continue  # header presente mas inválido — ignora, não confia
    # Fallback: conexão direta (Nginx em prod, uvicorn em dev)
    host = request.client.host if request.client else "unknown"
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return "unknown"


# ── JWT decode ────────────────────────────────────────────────────────────────

def _decode_token(token: str) -> dict:
    """Decode and verify a JWT.  Raises HTTP 401 on any failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _enforce_user_session_state(payload: dict) -> dict:
    """Reject stale JWTs after password rotation or user deactivation."""
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    users = _load_users()
    if not users:
        return payload

    user = users.get(username)
    if not user or not user.get("active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    changed_at = user.get("password_changed_at")
    if changed_at:
        try:
            changed_ts = datetime.fromisoformat(changed_at).timestamp()
            issued_at = payload.get("iat", 0)
            issued_ts = (
                issued_at.timestamp()
                if isinstance(issued_at, datetime)
                else float(issued_at)
            )
        except (TypeError, ValueError, OSError) as exc:
            logger.warning(
                "session state timestamp invalid | user=%s err=%s",
                username,
                type(exc).__name__,
            )
            raise HTTPException(status_code=503, detail="security policy unavailable")
        if issued_ts < changed_ts:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    current_payload = dict(payload)
    current_payload["role"] = user.get("role", "user")
    return current_payload


# ── Token blacklist check ─────────────────────────────────────────────────────

async def _check_blacklist(jti: Optional[str], db: DatabaseManager | None = None) -> None:
    """Raises 401 if the jti is revoked.

    D-10 (FIND-06): Fail-CLOSED on DB error — any read failure returns HTTP 503
    to prevent a storage outage from allowing revoked tokens through.
    """
    if not jti:
        return
    active_db = db or _db
    try:
        row = await active_db.fetch_one(
            "SELECT 1 as found FROM token_blacklist WHERE jti = $1", (jti,)
        )
        if row is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except (DatabaseError, OSError, ValueError, RuntimeError) as exc:
        # D-10: fail-closed — deny access when blacklist is unreadable.
        # RuntimeError covers the "DB not started" case (e.g. in tests or early startup).
        now = time.monotonic()
        if now - _last_blacklist_warn[0] > 60:
            logger.warning(
                "blacklist read failure — fail-closed | err=%s", type(exc).__name__
            )
            _last_blacklist_warn[0] = now
        raise HTTPException(
            status_code=503,
            detail="security policy unavailable",
        )


# ── Auth dependencies ─────────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Dependency: valida JWT — lê cookie nx_session primeiro, Bearer como fallback."""
    # VULN-01: cookie HttpOnly tem prioridade
    cookie_token = request.cookies.get("nx_session")
    if cookie_token:
        payload = _decode_token(cookie_token)
        payload = _enforce_user_session_state(payload)
        await _check_blacklist(payload.get("jti"), db=get_db(request))
        return payload

    # Fallback de retrocompatibilidade: Authorization: Bearer <token>
    if credentials and credentials.credentials:
        payload = _decode_token(credentials.credentials)
        payload = _enforce_user_session_state(payload)
        await _check_blacklist(payload.get("jti"), db=get_db(request))
        return payload

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: requires admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


async def get_optional_admin_user(request: Request) -> dict | None:
    """Return admin user dict if authenticated as admin, else None. Never raises HTTPException.

    Phase 16 D-H14: used by /health to gate Thordata bandwidth metrics — non-admin
    callers receive the standard /health response without the thordata sub-object.

    Calls get_current_user and role-checks inline (cannot call get_admin_user directly
    since Depends() injection is not available outside FastAPI's request lifecycle).
    """
    try:
        user = await get_current_user(request, credentials=None)
        if user.get("role") != "admin":
            return None
        return user
    except HTTPException:
        return None


# ── Application-state providers (D-05 canonical pattern) ─────────────────────

def get_db(request: Request) -> DatabaseManager:
    """Provide the singleton DatabaseManager via app.state.

    The lifespan startup binds `application.state.db = _db` before any
    request is served. Routes that need DB access declare:
        db: DatabaseManager = Depends(get_db)
    and pass `db` explicitly to service-layer functions (D-05).
    """
    override = request.app.dependency_overrides.get(_db)
    if override is not None:
        return override()
    return getattr(request.app.state, "db", _db)


def get_orchestrator_dep(request: Request) -> TaskOrchestrator:
    """Provide the singleton TaskOrchestrator via app.state.

    Named `_dep` to avoid shadowing `api.orchestrator.get_orchestrator`,
    which is the module-level singleton accessor still used by lifespan
    and by callers that don't have a Request in scope.
    """
    return getattr(request.app.state, "orchestrator", get_orchestrator())
