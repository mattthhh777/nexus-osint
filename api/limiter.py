"""Rate limiter singleton - extracted to break api.main circular import."""
import ipaddress

import jwt
from fastapi import Request
from slowapi import Limiter

from api.config import JWT_ALGORITHM, JWT_SECRET


def _request_ip(request: Request) -> str:
    """Use only proxy-normalized X-Real-IP; never trust client-supplied XFF."""
    val = request.headers.get("X-Real-IP", "").strip()
    if val:
        try:
            ipaddress.ip_address(val)
            return val
        except ValueError:
            pass
    host = request.client.host if request.client else "unknown"
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return "unknown"


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
    return f"ip:{_request_ip(request)}"


limiter = Limiter(key_func=_rate_key, storage_uri="memory://")
