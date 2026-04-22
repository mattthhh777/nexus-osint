"""Pydantic I/O schemas for the FastAPI app. Leaf module — imports nothing from api/* or modules/*."""
import re
from pydantic import BaseModel, field_validator


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
