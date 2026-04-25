"""Authentication service: users CRUD, password hashing, JWT lifecycle, startup guards."""
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt_lib
import jwt

from api.config import (
    APP_PASSWORD,
    DATA_DIR,
    JWT_ALGORITHM,
    JWT_EXPIRE_HOURS,
    JWT_SECRET,
    USERS_FILE,
    _WEAK_JWT_SECRETS,
)
from api.db import db as _db

logger = logging.getLogger("nexusosint.auth_service")

_users_cache: dict | None = None
_users_cache_mtime: float = 0.0


def _validate_jwt_secret() -> None:
    """Fail-hard guard — called as FIRST step in lifespan startup.

    Reads JWT_SECRET from env. Exits the process with code 1 if:
      - the variable is missing or empty
      - the value (stripped, lowercased) matches a known weak default

    Returns None on success; the caller should then read os.environ["JWT_SECRET"]
    to configure the JWT engine.
    """
    secret = os.environ.get("JWT_SECRET", "")
    if not secret or secret.strip().lower() in _WEAK_JWT_SECRETS:
        # Use print as a last resort — logging may not be configured yet
        import logging as _log
        _log.critical(
            "JWT_SECRET missing, empty, or matches a known weak default — refusing to start"
        )
        sys.exit(1)


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
    except (ValueError, TypeError, UnicodeDecodeError) as _e:
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


async def _revoke_token(jti: Optional[str], exp: Optional[int]) -> None:
    """Add a jti to the blacklist until its expiry."""
    if not jti:
        return
    await _db.write(
        "INSERT OR IGNORE INTO token_blacklist (jti, exp) VALUES (?, ?)",
        (jti, exp or int(time.time()) + JWT_EXPIRE_HOURS * 3600),
    )
