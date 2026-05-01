"""Module-level configuration for NexusOSINT. Leaf module — imports no api/*, no modules/*."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
OATHNET_API_KEY = os.getenv("OATHNET_API_KEY", "")
SPIDERFOOT_URL  = os.getenv("SPIDERFOOT_URL", "http://spiderfoot:5001")
APP_PASSWORD    = os.getenv("APP_PASSWORD", "")   # legacy single-user fallback
LOG_LEVEL       = os.getenv("LOG_LEVEL", "WARNING")
JWT_ALGORITHM   = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# ── JWT security constants ────────────────────────────────────────────────────
# Known weak defaults that must never be used in production.
# Compared case-insensitively in _validate_jwt_secret().
_WEAK_JWT_SECRETS: frozenset[str] = frozenset(
    {"changeme", "secret", "dev", "test", "password"}
)

# Operational cap: POST /api/admin/users returns 403 once count >= MAX_USERS.
MAX_USERS: int = int(os.environ.get("MAX_USERS", "50"))

# ── Rate limit ceilings — tunable per deployment via env vars ────────────────
RL_LOGIN_LIMIT      = os.environ.get("RL_LOGIN_LIMIT",      "5/minute")
RL_REGISTER_LIMIT   = os.environ.get("RL_REGISTER_LIMIT",   "3/hour")
RL_SEARCH_LIMIT     = os.environ.get("RL_SEARCH_LIMIT",     "10/minute")
RL_SPIDERFOOT_LIMIT = os.environ.get("RL_SPIDERFOOT_LIMIT", "3/hour")
RL_ADMIN_LIMIT      = os.environ.get("RL_ADMIN_LIMIT",      "30/minute")
RL_READ_LIMIT       = os.environ.get("RL_READ_LIMIT",       "60/minute")

# JWT_SECRET module-level var — read from env at import time.
# _validate_jwt_secret() is called as FIRST step in lifespan startup and
# calls sys.exit(1) if absent or weak, preventing any request from being served.
JWT_SECRET: str = os.environ.get("JWT_SECRET", "")

DATA_DIR   = Path("/app/data")
USERS_FILE = DATA_DIR / "users.json"
AUDIT_DB   = DATA_DIR / "audit.db"

# ── Memory watchdog thresholds ───────────────────────────────────────────────
MEMORY_ALERT_MB: int = 400       # log warning, investigate (watchdog uses this)
MEMORY_CRITICAL_PCT: int = 85    # Phase 10: watchdog CRITICAL threshold (85%)

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

    "victims":        30,   # Victims search
    "discord_roblox": 15,   # Discord→Roblox lookup
}

# Memory guard: serialize at most MAX_BREACH_SERIALIZE breaches in the SSE payload.
# Frontend paginates at BREACH_PAGE_SIZE=25; cursor API (/api/search/more-breaches)
# fetches the rest on demand. 200 breaches ≈ 200KB JSON — acceptable for 1GB VPS.
MAX_BREACH_SERIALIZE = 200

# ── Phase 16: Thordata residential proxy + Sherlock confidence thresholds ────
# Per CONTEXT.md D-11 / D-15 / D-18 / D-H5. Backend-only enforcement (D-H1, D-H4).
# THORDATA_PROXY_URL = None means proxy disabled — Sherlock falls back to direct DO IP
# (may be blocked by LinkedIn / Instagram / TikTok). User-supplied via .env.
THORDATA_PROXY_URL: str | None = os.getenv("THORDATA_PROXY_URL")

# Daily budget — D-16: SOFT 500MB warning, HARD 1024MB circuit breaker.
# Stored as bytes for direct comparison against running counter.
_THORDATA_DAILY_BUDGET_MB: int = int(os.getenv("THORDATA_DAILY_BUDGET_MB", "1024"))
THORDATA_DAILY_BUDGET_BYTES: int = _THORDATA_DAILY_BUDGET_MB * 1_048_576

# Per-search cap — D-17: 1MB total across 25 platforms (~40KB avg per platform).
_THORDATA_PER_SEARCH_CAP_MB: int = int(os.getenv("THORDATA_PER_SEARCH_CAP_MB", "1"))
THORDATA_PER_SEARCH_CAP_BYTES: int = _THORDATA_PER_SEARCH_CAP_MB * 1_048_576

# Confidence scoring — D-10/D-11: tunable without redeploy.
# >= CONFIRMED → state="confirmed"; >= LIKELY → state="likely"; below → state="not_found".
SHERLOCK_CONFIRMED_THRESHOLD: int = int(os.getenv("SHERLOCK_CONFIRMED_THRESHOLD", "70"))
SHERLOCK_LIKELY_THRESHOLD: int = int(os.getenv("SHERLOCK_LIKELY_THRESHOLD", "40"))

# Allowed origins — add your domain here
_ALLOWED_ORIGINS = [
    o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", "https://nexusosint.uk,http://localhost:8000").split(",")
    if o.strip()
]
