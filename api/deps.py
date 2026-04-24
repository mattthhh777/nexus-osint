"""
FastAPI dependency providers for NexusOSINT.

Scope: Only Depends()-compatible callables live here.
  - security  — HTTPBearer instance (credentials extractor)
  - get_client_ip — real IP extraction through Cloudflare/Nginx
  - _decode_token  — JWT decode + 401 on failure
  - _check_blacklist — blacklist look-up + fail-closed on DB error
  - get_current_user — primary auth dependency (cookie → Bearer fallback)
  - get_admin_user   — role-guard on top of get_current_user

Import contract (D-05):
  - stdlib: time, typing, ipaddress
  - 3rd party: aiosqlite, fastapi, fastapi.security, jwt (PyJWT)
  - internal: api.db — allowed (db is below deps in the import graph)
  - PROHIBITED: api.main — would create a circular import
"""
import ipaddress
import logging
import time
from typing import Optional

import aiosqlite
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt
try:
    from jwt.exceptions import InvalidTokenError as JWTError
except ImportError:
    from jwt import InvalidTokenError as JWTError

import os

from api.db import db as _db

logger = logging.getLogger("nexusosint.deps")

# ── Config (read from env; keep in sync with main.py) ────────────────────────
JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM: str = "HS256"

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
    for header in ("CF-Connecting-IP", "X-Real-IP"):
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
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Token blacklist check ─────────────────────────────────────────────────────

async def _check_blacklist(jti: Optional[str]) -> None:
    """Raises 401 if the jti is revoked.

    D-10 (FIND-06): Fail-CLOSED on DB error — any read failure returns HTTP 503
    to prevent a storage outage from allowing revoked tokens through.
    """
    if not jti:
        return
    try:
        # Purge expired entries — fire-and-forget
        await _db.write(
            "DELETE FROM token_blacklist WHERE exp < ?",
            (int(time.time()),),
        )
        row = await _db.read_one(
            "SELECT 1 as found FROM token_blacklist WHERE jti = ?", (jti,)
        )
        if row is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except (aiosqlite.Error, OSError, ValueError, RuntimeError) as exc:
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
        await _check_blacklist(payload.get("jti"))
        return payload

    # Fallback de retrocompatibilidade: Authorization: Bearer <token>
    if credentials and credentials.credentials:
        payload = _decode_token(credentials.credentials)
        await _check_blacklist(payload.get("jti"))
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
