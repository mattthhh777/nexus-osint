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
import hashlib
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional, Union

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
import bcrypt as _bcrypt_lib
from pydantic import BaseModel, field_validator
from starlette.middleware.base import BaseHTTPMiddleware
import ipaddress

import aiosqlite
from cachetools import TTLCache
from api.db import db as _db  # single-connection DatabaseManager (WAL + write queue)
from modules.oathnet_client import oathnet_client  # async singleton — one TCP/TLS pool

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
OATHNET_API_KEY = os.getenv("OATHNET_API_KEY", "")
SPIDERFOOT_URL  = os.getenv("SPIDERFOOT_URL", "http://spiderfoot:5001")
APP_PASSWORD    = os.getenv("APP_PASSWORD", "")   # legacy single-user fallback
LOG_LEVEL       = os.getenv("LOG_LEVEL", "WARNING")
_jwt_fallback   = hashlib.sha256(
    (OATHNET_API_KEY + "nexusosint_jwt_v3_" + os.urandom(8).hex()).encode()
).hexdigest()
JWT_SECRET      = os.getenv("JWT_SECRET") or _jwt_fallback
if not os.getenv("JWT_SECRET"):
    import warnings
    warnings.warn(
        "JWT_SECRET not set in .env — using ephemeral secret. "
        "Tokens will be invalidated on restart. Set JWT_SECRET for production.",
        stacklevel=1
    )
JWT_ALGORITHM   = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

DATA_DIR   = Path("/app/data")
USERS_FILE = DATA_DIR / "users.json"
AUDIT_DB   = DATA_DIR / "audit.db"

# ── User cache — avoids redundant disk reads on every admin request ────────────
_users_cache: dict | None = None
_users_cache_mtime: float = 0.0

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.WARNING))
logger = logging.getLogger("nexusosint")

# ── TTL cache for external API responses ─────────────────────────────────────
# 5-min TTL, max 200 entries — 200 * ~10KB avg = ~2MB max, acceptable for 1GB VPS
# Preserves OathNet 100 lookups/day quota: repeat queries within 5 min skip the API
_api_cache: TTLCache = TTLCache(maxsize=200, ttl=300)


def _cache_key(endpoint: str, query: str) -> str:
    """Generate normalised cache key for external API responses."""
    return f"{endpoint}:{query.lower().strip()}"


def _get_cached(endpoint: str, query: str):
    """Return cached API response or None if absent / expired."""
    return _api_cache.get(_cache_key(endpoint, query))


def _set_cached(endpoint: str, query: str, data) -> None:
    """Store a successful API response in cache. Never cache None / errors."""
    if data is not None:
        _api_cache[_cache_key(endpoint, query)] = data


# ── Models ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class SearchRequest(BaseModel):
    query: str
    mode: str = "automated"
    modules: list[str] = []
    spiderfoot_mode: str = "passive"

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        if len(v) < 2:
            raise ValueError("Query too short (min 2 chars)")
        if len(v) > 256:
            raise ValueError("Query too long (max 256 chars)")
        # Strip null bytes and control characters
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        # Strip SQL injection patterns (defense in depth — OathNet handles its own)
        v = re.sub(r"[;\x27\x22\x5c]", "", v)
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        return v if v in ("automated", "manual") else "automated"

    @field_validator("spiderfoot_mode")
    @classmethod
    def validate_sf_mode(cls, v: str) -> str:
        return v if v in ("passive", "footprint", "investigate") else "passive"



# ── In-memory rate limiter ────────────────────────────────────────────────────
# ── Persistent rate limiting via SQLite ──────────────────────────────────────
async def _save_quota(used: int, left: int, daily_limit: int) -> None:
    """Save current OathNet quota to DB for admin dashboard."""
    await _db.write(
        "INSERT INTO quota_log (ts, used_today, left_today, daily_limit) VALUES (?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), used, left, daily_limit),
    )
    # Keep only last 100 entries — fire-and-forget trim
    await _db.write(
        "DELETE FROM quota_log WHERE rowid NOT IN "
        "(SELECT rowid FROM quota_log ORDER BY ts DESC LIMIT 100)",
    )


async def _check_rate(key: str, max_calls: int, window_s: int) -> bool:
    """Persistent rate limiter via SQLite — survives container restarts."""
    now    = time.time()
    cutoff = now - window_s
    try:
        row = await _db.read_one(
            "SELECT COUNT(*) as cnt FROM rate_limits WHERE key = ? AND ts >= ?",
            (key, cutoff),
        )
        count = row["cnt"] if row else 0

        if count >= max_calls:
            # Purge expired in background — no need to wait
            await _db.write(
                "DELETE FROM rate_limits WHERE key = ? AND ts < ?", (key, cutoff)
            )
            return False

        # Purge expired + insert new entry (serialized via write queue)
        await _db.write(
            "DELETE FROM rate_limits WHERE key = ? AND ts < ?", (key, cutoff)
        )
        await _db.write(
            "INSERT INTO rate_limits (key, ts) VALUES (?, ?)", (key, now)
        )
        return True
    except aiosqlite.OperationalError as exc:
        logger.warning("Rate limit DB error (fail-closed): %s", exc)
        return False  # fail closed — prevent abuse if DB unavailable

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

app = FastAPI(title="NexusOSINT", version="3.0.0", docs_url=None, redoc_url=None, openapi_url=None)
# Allowed origins — add your domain here
_ALLOWED_ORIGINS = [
    o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", "https://nexusosint.uk,http://localhost:8000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    # Monta a pasta static inteira para que /static/css/... funcione
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    # Atalhos para o HTML encontrar /css e /js diretamente
    app.mount("/css", StaticFiles(directory=str(static_path / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(static_path / "js")), name="js")

# ── Password hashing ──────────────────────────────────────────────────────────
security = HTTPBearer(auto_error=False)



# ── Users management ──────────────────────────────────────────────────────────

def _load_users() -> dict:
    global _users_cache, _users_cache_mtime
    if not USERS_FILE.exists():
        _users_cache = {}
        _users_cache_mtime = 0.0
        return {}
    try:
        current_mtime = USERS_FILE.stat().st_mtime
        if _users_cache is not None and current_mtime == _users_cache_mtime:
            return _users_cache
        _users_cache = json.loads(USERS_FILE.read_text())
        _users_cache_mtime = current_mtime
        return _users_cache
    except (OSError, json.JSONDecodeError) as e:
        logger.error("_load_users failed: %s", e)
        return _users_cache if _users_cache is not None else {}

def _save_users(users: dict) -> None:
    global _users_cache, _users_cache_mtime
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))
    _users_cache = users
    _users_cache_mtime = USERS_FILE.stat().st_mtime

def _safe_hash(password: str) -> str:
    """Hash password safely using bcrypt directly (bypasses passlib bugs)."""
    import hashlib
    safe = hashlib.sha256(password.encode()).hexdigest().encode()
    return _bcrypt_lib.hashpw(safe, _bcrypt_lib.gensalt()).decode()

def _safe_verify(password: str, hashed: str) -> bool:
    """Verify password using bcrypt directly."""
    import hashlib
    safe = hashlib.sha256(password.encode()).hexdigest().encode()
    try:
        return _bcrypt_lib.checkpw(safe, hashed.encode() if isinstance(hashed, str) else hashed)
    except Exception as _e:
        logger.warning("_safe_verify failed: %s", _e)
        return False

def _ensure_default_user() -> None:
    """Create admin user from APP_PASSWORD if no users exist."""
    users = _load_users()
    if not users and APP_PASSWORD:
        users["admin"] = {
            "password_hash": _safe_hash(APP_PASSWORD),
            "role":          "admin",
            "created_at":    datetime.now(timezone.utc).isoformat(),
            "active":        True,
        }
        _save_users(users)
        logger.info("Created admin user from APP_PASSWORD")

def _verify_user(username: str, password: str) -> Optional[dict]:
    users = _load_users()

    # Legacy: single APP_PASSWORD with username "admin"
    if not users and APP_PASSWORD:
        if username == "admin" and password == APP_PASSWORD:
            return {"username": "admin", "role": "admin"}
        return None

    user = users.get(username)
    if not user or not user.get("active", True):
        return None
    if not _safe_verify(password, user["password_hash"]):
        return None
    return {"username": username, "role": user.get("role", "user")}


# ── JWT ───────────────────────────────────────────────────────────────────────

def _create_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub":  username,
        "role": role,
        "exp":  expire,
        "iat":  datetime.now(timezone.utc),
        "jti":  str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ── Token Blacklist (revocation) ──────────────────────────────────────────────

async def _check_blacklist(jti: Optional[str]) -> None:
    """Raises 401 if the jti is revoked. Fails open on DB error."""
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
    except Exception as exc:
        logger.warning("Blacklist check failed (fail-open): %s", exc)

async def _revoke_token(jti: Optional[str], exp: Optional[int]) -> None:
    """Add a jti to the blacklist until its expiry."""
    if not jti:
        return
    await _db.write(
        "INSERT OR IGNORE INTO token_blacklist (jti, exp) VALUES (?, ?)",
        (jti, exp or int(time.time()) + JWT_EXPIRE_HOURS * 3600),
    )

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

# ── Audit DB ──────────────────────────────────────────────────────────────────

async def _log_search(
    username: str,
    ip: str,
    query: str,
    query_type: str,
    mode: str,
    modules_run: list[str],
    breach_count: int = 0,
    stealer_count: int = 0,
    social_count: int = 0,
    elapsed_s: float = 0.0,
    success: bool = True,
) -> None:
    """Write a search audit record. Non-blocking — goes through write queue."""
    await _db.write(
        """INSERT INTO searches
           (ts, username, ip, query, query_type, mode, modules_run,
            breach_count, stealer_count, social_count, elapsed_s, success)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            username, ip, query, query_type, mode,
            ",".join(modules_run),
            breach_count, stealer_count, social_count,
            elapsed_s, int(success),
        ),
    )


# ── Startup ───────────────────────────────────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Robots-Tag"]           = "noindex, nofollow, noarchive"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cross-Origin-Opener-Policy"]  = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"]= "require-corp"
        return response

app.add_middleware(SecurityHeadersMiddleware)


@app.on_event("startup")
async def startup() -> None:
    _ensure_default_user()
    await _db.startup(db_path=AUDIT_DB)
    logger.info("NexusOSINT v3.0 started — %d allowed origins", len(_ALLOWED_ORIGINS))


@app.on_event("shutdown")
async def shutdown() -> None:
    await _db.shutdown()
    if oathnet_client:
        await oathnet_client.close()
    logger.info("NexusOSINT v3.0 shutdown complete")


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
async def admin_auth_gate(
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
async def auth_legacy(request: Request):
    """Legacy endpoint — kept for frontend compat. Returns ok:true if no password set."""
    if not APP_PASSWORD and not _load_users():
        return {"ok": True}
    # Just check if server is password-protected
    return {"ok": False, "requires_login": True}


@app.post("/api/login")
async def login(request: Request, body: LoginRequest):
    """JWT login. Define cookie HttpOnly nx_session (VULN-01).
    Rate limit duplo: por IP e por username (VULN-04).
    """
    ip = get_client_ip(request)

    # Bloqueio por IP: 5 tentativas / 60s
    if not await _check_rate(f"login_ip:{ip}", 5, 60):
        raise HTTPException(status_code=429, detail="Too many login attempts from this IP. Wait 1 minute.")

    # Bloqueio por username: 10 tentativas / 300s — defesa contra ataques distribuídos
    if not await _check_rate(f"login_user:{body.username}", 10, 300):
        raise HTTPException(status_code=429, detail="Too many attempts for this account. Wait 5 minutes.")

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
async def me(user: dict = Depends(get_current_user)):
    """Returns current user info."""
    return {"username": user["sub"], "role": user.get("role", "user")}

@app.post("/api/logout")
async def logout(request: Request, response: Response):
    """Termina sessão: revoga o JWT no blacklist e apaga o cookie nx_session (VULN-01)."""
    token = request.cookies.get("nx_session")
    if token:
        try:
            payload = _decode_token(token)
            await _revoke_token(payload.get("jti"), payload.get("exp"))
        except HTTPException:
            pass  # token já inválido — só limpa o cookie
    response.delete_cookie("nx_session", path="/")
    return {"ok": True}

# ── Query detection ───────────────────────────────────────────────────────────

def detect_type(q: str) -> str:
    q = q.strip()
    if re.match(r"^\d{14,19}$", q):      return "discord_id"
    if re.match(r"^\+\d{7,15}$", q):     return "phone"
    if re.match(r"^[\w.+\-]+@[\w\-]+\.[\w.]{2,}$", q, re.I): return "email"
    if re.match(r"^(\d{1,3}\.){3}\d{1,3}$", q):               return "ip"
    if re.match(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", q): return "domain"
    if re.match(r"^\d{7,10}$", q):        return "steam_id"
    return "username"


# ── Per-module timeouts ──────────────────────────────────────────────────────
MODULE_TIMEOUTS = {
    "breach":         45,   # OathNet breach search — can be slow with many results
    "stealer":        45,   # OathNet stealer v2
    "holehe":         20,   # Email account checker
    "sherlock":       60,   # Checks 25 platforms concurrently
    "discord":        15,   # Simple Discord API
    "discord_auto":   10,   # Auto Discord from breach
    "ip_info":        15,   # IP geolocation
    "subdomain":      30,   # Subdomain enumeration
    "steam":          20,   # Steam profile
    "xbox":           20,   # Xbox profile
    "roblox":         20,   # Roblox profile
    "ghunt":          25,   # Google account OSINT
    "minecraft":      20,   # Minecraft history
    "victims":        30,   # Victims search
    "discord_roblox": 15,   # Discord→Roblox lookup
}

async def with_timeout(coro, module: str, default=None):
    """
    Wrap a coroutine with a per-module timeout.
    Returns (result, timed_out: bool).
    On timeout: returns (default, True) instead of raising.
    """
    timeout_s = MODULE_TIMEOUTS.get(module, 30)
    try:
        result = await asyncio.wait_for(coro, timeout=timeout_s)
        return result, False
    except asyncio.TimeoutError:
        logger.warning("Module '%s' timed out after %ds", module, timeout_s)
        return default, True


def _serialize_breaches(breaches) -> list[dict]:
    return [{"dbname": b.dbname, "email": b.email, "username": b.username,
             "password": b.password, "ip": b.ip, "country": b.country,
             "date": b.date, "discord_id": b.discord_id, "phone": b.phone,
             "extra": b.extra_fields} for b in breaches]

def _serialize_stealers(stealers) -> list[dict]:
    return [{"url": s.url, "username": s.username, "password": s.password,
             "domain": s.domain, "pwned_at": s.pwned_at, "log_id": s.log_id}
            for s in stealers]


# ── Search ────────────────────────────────────────────────────────────────────

@app.post("/api/search")
async def search(
    request: Request,
    req: SearchRequest,
    user: dict = Depends(get_current_user),
):
    """Protected SSE search endpoint."""
    client_ip = get_client_ip(request)
    if not await _check_rate(f"search:{client_ip}", 10, 60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 20 searches/minute.")
    return StreamingResponse(
        _stream_search(req, user["sub"], client_ip),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_search(
    req: SearchRequest,
    username: str,
    client_ip: str,
) -> AsyncGenerator[str, None]:

    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"

    query    = req.query
    q_type   = detect_type(query)
    is_email = q_type == "email"
    is_user  = q_type == "username"
    is_ip    = q_type == "ip"
    is_disc  = q_type == "discord_id"
    is_dom   = q_type == "domain"
    is_steam = q_type == "steam_id"

    if req.mode == "automated":
        run = {
            "breach": True, "stealer": True,
            "sherlock": is_email or is_user,
            "holehe": is_email, "discord": is_disc,
            "ip_info": is_ip, "subdomain": is_dom,
            "steam": is_steam or is_user,
            "xbox":  is_user,
            "roblox": is_user,
            "ghunt": is_email, "minecraft": is_user,
            "spiderfoot": False,
        }
    else:
        mods = set(req.modules)
        run = {
            "breach":    "breach"     in mods,
            "stealer":   "stealer"    in mods,
            "sherlock":  "sherlock"   in mods and (is_email or is_user),
            "holehe":    "holehe"     in mods and is_email,
            "discord":   "discord"    in mods,
            "ip_info":   "ip_info"    in mods and is_ip,
            "subdomain": "subdomain"  in mods and is_dom,
            "steam":     "steam"      in mods,
            "xbox":      "xbox"       in mods,
            "roblox":    "roblox"     in mods,
            "ghunt":     "ghunt"      in mods and is_email,
            "minecraft": "minecraft"  in mods and is_user,
            "spiderfoot":"spiderfoot" in mods,
        }

    total    = sum(run.values())
    done_cnt = [0]
    ran: list[str] = []
    # Counters for audit log
    breach_count = stealer_count = social_count = 0

    def progress(label: str) -> str:
        done_cnt[0] += 1
        pct = int(done_cnt[0] / max(total, 1) * 100)
        return event({"type": "progress", "pct": pct, "label": label})

    yield event({
        "type": "start", "query": query,
        "query_type": q_type, "total_modules": total,
        "modules_planned": [k for k, v in run.items() if v],
        "user": username,
    })

    from modules.sherlock_wrapper import search_username

    if oathnet_client is None:
        yield event({"type": "error", "message": "OATHNET_API_KEY not configured"})
        return

    t0 = time.time()

    # ── Breach + Stealer parallel ─────────────────────────────────────────
    if run.get("breach") or run.get("stealer") or run.get("holehe"):
        yield progress("Searching breach databases & stealer logs…")
        ran += ["breach", "stealer"]
        try:
            # Check breach cache first — avoids OathNet API call within 5-min TTL
            cached_breach = _get_cached("breach", query)
            if cached_breach is not None:
                tasks = []
                breach_future = cached_breach
            else:
                tasks = [oathnet_client.search_breach(query)]
                breach_future = None

            stealer_future = None
            if run.get("stealer"):
                cached_stealer = _get_cached("stealer", query)
                if cached_stealer is not None:
                    stealer_future = cached_stealer
                else:
                    tasks.append(oathnet_client.search_stealer_v2(query))

            results_gathered = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

            # Reconstruct results: cache hits are already resolved, API results from gather
            gather_idx = 0
            if breach_future is not None:
                res = breach_future
            else:
                raw = results_gathered[gather_idx] if gather_idx < len(results_gathered) else None
                res = raw if not isinstance(raw, Exception) else None
                if res is not None:
                    _set_cached("breach", query, res)
                gather_idx += 1

            if run.get("stealer"):
                if stealer_future is not None:
                    sts_result = stealer_future
                else:
                    raw_sts = results_gathered[gather_idx] if gather_idx < len(results_gathered) else None
                    sts_result = raw_sts if not isinstance(raw_sts, Exception) else None
                    if sts_result is not None:
                        _set_cached("stealer", query, sts_result)
                    gather_idx += 1
            else:
                sts_result = None

            if res is None:
                err_detail = str(results_gathered[0]) if results_gathered else "Breach search failed"
                yield event({"type": "module_error", "module": "breach", "error": err_detail})
            else:
                if run.get("stealer") and sts_result is not None:
                    res.stealers       = sts_result.stealers
                    res.stealers_found = sts_result.stealers_found

                if run.get("holehe") and is_email:
                    ran.append("holehe")
                    cached_holehe = _get_cached("holehe", query)
                    if cached_holehe is not None:
                        res.holehe_domains = cached_holehe
                    else:
                        h, timed_out = await with_timeout(
                            oathnet_client.holehe(query), "holehe"
                        )
                        if timed_out:
                            logger.warning("Holehe timed out")
                        elif h:
                            res.holehe_domains = h.holehe_domains
                            _set_cached("holehe", query, h.holehe_domains)

                breaches_data = _serialize_breaches(res.breaches)
                breach_count  = len(breaches_data)
                stealer_count = len(res.stealers)

                discord_ids_from_breach = []
                if req.mode == "automated" and not is_disc:
                    discord_ids_from_breach = list({
                        b["discord_id"] for b in breaches_data
                        if b.get("discord_id") and re.match(r"^\d{14,19}$", str(b["discord_id"]))
                    })

                yield event({
                    "type": "oathnet", "success": res.success,
                    "breach_count": breach_count,
                    "stealer_count": stealer_count,
                    "holehe_count": len(res.holehe_domains),
                    "results_found": res.results_found,
                    "breaches": breaches_data,
                    "stealers": _serialize_stealers(res.stealers),
                    "holehe_domains": res.holehe_domains,
                    "plan": res.meta.plan,
                    "used_today": res.meta.used_today,
                    "left_today": res.meta.left_today,
                    "daily_limit": res.meta.daily_limit,
                    "error": res.error,
                    "discord_ids_found": discord_ids_from_breach,
                })

                if discord_ids_from_breach and req.mode == "automated":
                    for disc_id in discord_ids_from_breach[:3]:
                        yield progress(f"Discord lookup: {disc_id}")
                        ran.append("discord")
                        try:
                            (ok_u, user_data), td1 = await with_timeout(
                                oathnet_client.discord_userinfo(disc_id), "discord_auto"
                            )
                            (ok_h, raw_hist), td2 = await with_timeout(
                                oathnet_client.discord_username_history(disc_id), "discord_auto"
                            )
                            if td1: ok_u = False; user_data = None
                            if td2: ok_h = False; raw_hist = None
                            yield event({
                                "type": "discord", "query_id": disc_id,
                                "user": user_data if ok_u else None,
                                "history": _parse_discord_history(raw_hist) if ok_h else None,
                            })
                        except Exception as exc:
                            logger.warning("Auto Discord failed %s: %s", disc_id, exc)

        except Exception as exc:
            logger.error("OathNet failed: %s", exc)
            yield event({"type": "module_error", "module": "oathnet", "error": str(exc)})

    # ── Sherlock ──────────────────────────────────────────────────────────
    if run.get("sherlock"):
        yield progress("Scanning social platforms…")
        ran.append("sherlock")
        try:
            uname = query if is_user else query.split("@")[0]
            sherl, timed_out = await with_timeout(
                asyncio.to_thread(search_username, uname, False), "sherlock"
            )
            if timed_out:
                yield event({"type": "module_error", "module": "sherlock",
                             "error": "Sherlock timed out after 60s — partial results unavailable"})
            elif sherl:
                social_count = sherl.found_count
                yield event({
                    "type": "sherlock",
                    "found_count": sherl.found_count,
                    "total_checked": sherl.total_checked,
                    "source": sherl.source,
                    "found": [{"platform": p.platform, "url": p.url,
                               "category": p.category, "icon": p.icon}
                              for p in sherl.found],
                })
        except Exception as exc:
            logger.error("Sherlock failed: %s", exc)
            yield event({"type": "module_error", "module": "sherlock", "error": str(exc)})

    # ── Discord ───────────────────────────────────────────────────────────
    if run.get("discord"):
        yield progress("Looking up Discord profile…")
        ran.append("discord")
        if not is_disc:
            yield event({
                "type": "discord",
                "error": "Discord lookup requires a numeric Discord ID (14-19 digits).",
                "hint": "Use Automated mode — it auto-detects Discord IDs found in breach data.",
                "user": None, "history": None,
            })
        else:
            try:
                cached_disc_user = _get_cached("discord_user", query)
                cached_disc_hist = _get_cached("discord_hist", query)

                if cached_disc_user is not None and cached_disc_hist is not None:
                    yield event({
                        "type": "discord",
                        "user": cached_disc_user,
                        "history": _parse_discord_history(cached_disc_hist),
                        "timeout": False,
                    })
                else:
                    (ok_u, user_data), td1 = await with_timeout(
                        oathnet_client.discord_userinfo(query), "discord"
                    )
                    (ok_h, raw_hist), td2 = await with_timeout(
                        oathnet_client.discord_username_history(query), "discord"
                    )
                    if td1: ok_u = False; user_data = None
                    if td2: ok_h = False; raw_hist = None
                    if ok_u and user_data is not None:
                        _set_cached("discord_user", query, user_data)
                    if ok_h and raw_hist is not None:
                        _set_cached("discord_hist", query, raw_hist)
                    yield event({
                        "type": "discord",
                        "user": user_data if ok_u else None,
                        "history": _parse_discord_history(raw_hist) if ok_h else None,
                        "timeout": td1,
                    })
            except Exception as exc:
                yield event({"type": "module_error", "module": "discord", "error": str(exc)})

    # ── IP Info ───────────────────────────────────────────────────────────
    if run.get("ip_info"):
        yield progress("Fetching IP geolocation…")
        ran.append("ip_info")
        try:
            cached_ip = _get_cached("ip_info", query)
            if cached_ip is not None:
                yield event({"type": "ip_info", "ok": True, "data": cached_ip})
            else:
                (ok, data), timed_out = await with_timeout(
                    oathnet_client.ip_info(query), "ip_info"
                )
                if timed_out:
                    yield event({"type": "module_error", "module": "ip_info", "error": "IP lookup timed out"})
                else:
                    if ok and data is not None:
                        _set_cached("ip_info", query, data)
                    yield event({"type": "ip_info", "ok": ok, "data": data if ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "ip_info", "error": str(exc)})

    # ── Subdomains ────────────────────────────────────────────────────────
    if run.get("subdomain"):
        yield progress("Enumerating subdomains…")
        ran.append("subdomain")
        try:
            (ok, data), timed_out = await with_timeout(
                oathnet_client.extract_subdomains(query), "subdomain"
            )
            if timed_out:
                yield event({"type": "module_error", "module": "subdomains", "error": "Subdomain lookup timed out"})
            else:
                subs = data.get("subdomains", []) if ok else []
                yield event({"type": "subdomains", "ok": ok, "data": subs, "count": len(subs)})
        except Exception as exc:
            yield event({"type": "module_error", "module": "subdomains", "error": str(exc)})

    # ── Steam ─────────────────────────────────────────────────────────────
    if run.get("steam"):
        yield progress("Looking up Steam profile…")
        ran.append("steam")
        try:
            cached_steam = _get_cached("steam", query)
            if cached_steam is not None:
                yield event({"type": "steam", "ok": True, "data": cached_steam})
            else:
                (ok, data), timed_out = await with_timeout(
                    oathnet_client.steam_lookup(query), "steam"
                )
                if timed_out:
                    yield event({"type": "module_error", "module": "steam", "error": "Steam lookup timed out"})
                else:
                    if ok and data is not None:
                        _set_cached("steam", query, data)
                    yield event({"type": "steam", "ok": ok,
                                 "data": data if ok else None,
                                 "error": data.get("error") if not ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "steam", "error": str(exc)})

    # ── Xbox ──────────────────────────────────────────────────────────────
    if run.get("xbox"):
        yield progress("Looking up Xbox profile…")
        ran.append("xbox")
        try:
            cached_xbox = _get_cached("xbox", query)
            if cached_xbox is not None:
                yield event({"type": "xbox", "ok": True, "data": cached_xbox})
            else:
                (ok, data), timed_out = await with_timeout(
                    oathnet_client.xbox_lookup(query), "xbox"
                )
                if timed_out:
                    yield event({"type": "module_error", "module": "xbox", "error": "Xbox lookup timed out"})
                else:
                    if ok and data is not None:
                        _set_cached("xbox", query, data)
                    yield event({"type": "xbox", "ok": ok, "data": data if ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "xbox", "error": str(exc)})

    # ── Roblox ────────────────────────────────────────────────────────────
    if run.get("roblox"):
        yield progress("Looking up Roblox profile…")
        ran.append("roblox")
        try:
            cached_roblox = _get_cached("roblox", query)
            if cached_roblox is not None:
                yield event({"type": "roblox", "ok": True, "data": cached_roblox})
            else:
                (ok, data), timed_out = await with_timeout(
                    oathnet_client.roblox_lookup(username=query), "roblox"
                )
                if timed_out:
                    yield event({"type": "module_error", "module": "roblox", "error": "Roblox lookup timed out"})
                else:
                    if ok and data is not None:
                        _set_cached("roblox", query, data)
                    yield event({"type": "roblox", "ok": ok, "data": data if ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "roblox", "error": str(exc)})

    # ── GHunt ─────────────────────────────────────────────────────────────
    if run.get("ghunt"):
        yield progress("Looking up Google account (GHunt)…")
        ran.append("ghunt")
        try:
            (ok, data), timed_out = await with_timeout(
                oathnet_client.ghunt(query), "ghunt"
            )
            if timed_out:
                yield event({"type": "module_error", "module": "ghunt", "error": "GHunt timed out"})
            else:
                yield event({"type": "ghunt", "ok": ok,
                             "data": data if ok else None,
                             "error": data.get("error") if not ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "ghunt", "error": str(exc)})

    # ── Minecraft ─────────────────────────────────────────────────────────
    if run.get("minecraft"):
        yield progress("Looking up Minecraft account…")
        ran.append("minecraft")
        try:
            (ok, data), timed_out = await with_timeout(
                oathnet_client.minecraft_history(query), "minecraft"
            )
            if timed_out:
                yield event({"type": "module_error", "module": "minecraft", "error": "Minecraft lookup timed out"})
            else:
                yield event({"type": "minecraft", "ok": ok,
                             "data": data if ok else None,
                             "error": data.get("error") if not ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "minecraft", "error": str(exc)})

    # ── Victims ──────────────────────────────────────────────────────────
    if run.get("victims"):
        yield progress("Searching compromised machine logs (Victims)…")
        ran.append("victims")
        try:
            # Build filters from query type
            v_filters: dict = {}
            if is_email:     v_filters["email"]      = query
            elif is_ip:      v_filters["ip"]         = query
            elif is_disc:    v_filters["discord_id"] = query
            elif is_user:    v_filters["username"]   = query
            else:            pass  # generic query

            ok, data = await oathnet_client.victims_search(
                query if not v_filters else "",
                10, "", "", **v_filters
            )
            if ok:
                items = data.get("items", [])
                meta  = data.get("meta", {})
                yield event({
                    "type":        "victims",
                    "ok":          True,
                    "items":       items[:10],
                    "total":       meta.get("total", len(items)),
                    "has_more":    meta.get("has_more", False),
                    "next_cursor": data.get("next_cursor", ""),
                })
            else:
                yield event({"type": "victims", "ok": False,
                             "error": data.get("error", ""), "items": []})
        except Exception as exc:
            yield event({"type": "module_error", "module": "victims", "error": str(exc)})

    # ── Discord → Roblox ─────────────────────────────────────────────────
    if run.get("discord_roblox") and is_disc:
        yield progress("Looking up linked Roblox account…")
        ran.append("discord_roblox")
        try:
            ok, data = await oathnet_client.discord_to_roblox(query)
            yield event({"type": "discord_roblox", "ok": ok,
                         "data": data if ok else None,
                         "error": data.get("error") if not ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "discord_roblox", "error": str(exc)})

    # ── SpiderFoot ────────────────────────────────────────────────────────
    if run.get("spiderfoot"):
        yield progress("Starting SpiderFoot scan…")
        ran.append("spiderfoot")
        async for sf_event in _run_spiderfoot(query, req.spiderfoot_mode):
            yield sf_event

    elapsed = round(time.time() - t0, 1)

    # ── Audit log — non-blocking via db write queue (no create_task needed) ──
    await _log_search(
        username=username, ip=client_ip, query=query,
        query_type=q_type, mode=req.mode,
        modules_run=list(set(ran)),
        breach_count=breach_count,
        stealer_count=stealer_count,
        social_count=social_count,
        elapsed_s=elapsed,
    )

    yield event({
        "type": "done",
        "elapsed_s": elapsed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules_run": list(set(ran)),
    })


# ── Admin endpoints ───────────────────────────────────────────────────────────

@app.get("/api/admin/stats")
async def admin_stats(_: dict = Depends(get_admin_user)):
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
async def admin_logs(
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
async def admin_list_users(_: dict = Depends(get_admin_user)):
    """List all users (without password hashes)."""
    users = _load_users()
    return {
        k: {kk: vv for kk, vv in v.items() if kk != "password_hash"}
        for k, v in users.items()
    }


@app.post("/api/admin/users")
async def admin_create_user(
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
async def admin_delete_user(
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


# ── SpiderFoot ────────────────────────────────────────────────────────────────

async def _run_spiderfoot(target: str, scan_mode: str) -> AsyncGenerator[str, None]:
    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"
    try:
        async with httpx.AsyncClient(timeout=600) as http:
            try:
                ping = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping", timeout=5)
                if ping.status_code != 200:
                    yield event({"type": "spiderfoot", "available": False,
                                 "error": "SpiderFoot not responding"})
                    return
            except Exception:
                yield event({"type": "spiderfoot", "available": False,
                             "error": f"Cannot reach SpiderFoot at {SPIDERFOOT_URL}"})
                return

            scan_resp = await http.post(f"{SPIDERFOOT_URL}/api/v1/startscan", data={
                "scanname":   f"nexus_{target}_{int(time.time())}",
                "scantarget": target,
                "usecase":    scan_mode,
                "modulelist": "", "typelist": "",
            })
            if scan_resp.status_code != 200:
                yield event({"type": "spiderfoot", "available": True,
                             "error": f"Failed to start: {scan_resp.text[:200]}"})
                return

            scan_id = scan_resp.json().get("id", "")
            yield event({"type": "spiderfoot_started", "scan_id": scan_id})

            poll_interval = 5.0   # start at 5s
            max_interval  = 30.0  # cap at 30s
            max_elapsed   = 600.0 # 10 min total timeout (same as before: 120 * 5s)
            elapsed       = 0.0

            while elapsed < max_elapsed:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                try:
                    sr = await http.get(f"{SPIDERFOOT_URL}/api/v1/scanstatus/{scan_id}")
                    if sr.status_code != 200:
                        poll_interval = min(poll_interval * 2, max_interval)
                        continue
                    sc = sr.json().get("status", "")
                    yield event({"type": "spiderfoot_progress", "status": sc})
                    if sc in ("FINISHED", "ABORTED", "ERROR"):
                        break
                    # Backoff: double interval each successful poll, cap at 30s
                    poll_interval = min(poll_interval * 2, max_interval)
                except httpx.HTTPError:
                    poll_interval = min(poll_interval * 2, max_interval)
                    continue

            rr = await http.get(f"{SPIDERFOOT_URL}/api/v1/scaneventresults/{scan_id}")
            if rr.status_code == 200:
                RELEVANT = {"EMAILADDR","USERNAME","SOCIAL_MEDIA","ACCOUNT_EXTERNAL_OWNED",
                            "PHONE_NUMBER","IP_ADDRESS","DOMAIN_NAME","LEAKSITE_URL",
                            "PASSWORD_COMPROMISED","DATA_HAS_BEEN_PWNED","DARKNET_MENTION_URL",
                            "MALICIOUS_IPADDR","MALICIOUS_EMAILADDR","GEOINFO"}
                filtered = [{"type": r[4], "data": r[1], "source": r[3]}
                            for r in rr.json() if len(r) >= 5 and r[4] in RELEVANT]
                yield event({"type": "spiderfoot", "available": True,
                             "scan_id": scan_id, "results": filtered[:500],
                             "total": len(filtered)})
    except Exception as exc:
        yield event({"type": "spiderfoot", "available": False, "error": str(exc)})


def _parse_discord_history(raw: dict) -> dict | None:
    if not raw:
        return None
    history_raw = raw.get("history", [])
    if not history_raw:
        return None
    return {"usernames": [
        {"username": (e.get("name", [None])[0] if isinstance(e.get("name"), list) else e.get("name")),
         "timestamp": (e.get("time", [None])[0] if isinstance(e.get("time"), list) else e.get("time"))}
        for e in history_raw
    ]}


# ── SpiderFoot proxy ──────────────────────────────────────────────────────────

# ── Breach pagination endpoint ───────────────────────────────────────────────

@app.post("/api/search/more-breaches")
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


def _validate_id(val: str, max_len: int = 128) -> str:
    """Validate log_id / file_id — only safe chars, no path traversal."""
    if not val or len(val) > max_len:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    # Allow alphanumeric, dash, underscore, dot — no slashes, no null bytes
    if not re.match(r'^[a-zA-Z0-9.\\-_]+$', val):
        raise HTTPException(status_code=400, detail="Invalid ID characters")
    return val


@app.get("/api/victims/{log_id}/manifest")
async def victims_manifest_endpoint(
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
async def victims_file_endpoint(
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
async def sf_status(_: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping")
            return {"available": r.status_code == 200, "url": SPIDERFOOT_URL}
    except Exception as exc:
        return {"available": False, "error": str(exc), "url": SPIDERFOOT_URL}


@app.get("/health")
@app.head("/health")
async def health():
    return {"status": "ok", "version": "3.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat()}