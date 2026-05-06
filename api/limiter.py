"""Rate limiter singleton — extracted to break api.main circular import."""
import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.config import JWT_ALGORITHM, JWT_SECRET


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
