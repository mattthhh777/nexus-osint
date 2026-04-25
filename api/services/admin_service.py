"""Admin service: input guards and helpers. Route-handler business logic migrates here in Plan 04."""
import re

from fastapi import HTTPException


def _validate_id(val: str, max_len: int = 128) -> str:
    """Validate log_id / file_id — only safe chars, no path traversal."""
    if not val or len(val) > max_len:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    # Allow alphanumeric, dash, underscore, dot — no slashes, no null bytes
    if not re.match(r'^[a-zA-Z0-9.\\-_]+$', val):
        raise HTTPException(status_code=400, detail="Invalid ID characters")
    return val
