"""Pydantic I/O schemas for the FastAPI app. Leaf module — imports nothing from api/* or modules/*."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class VictimsSearchRequest(BaseModel):
    q: str = ""
    page_size: int = 10
    cursor: str = ""
    search_id: str = ""
    email: str = ""
    ip: str = ""
    discord_id: str = ""
    username: str = ""

    @field_validator("q", "cursor", "search_id", "email", "ip", "discord_id", "username")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) > 256:
            raise ValueError("Input too long")
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)

    @field_validator("page_size")
    @classmethod
    def cap_page_size(cls, v: int) -> int:
        if v < 1:
            return 1
        return min(v, 50)


class SearchMoreBreachesRequest(BaseModel):
    query: str
    cursor: str
    search_id: str = ""

    @field_validator("query", "cursor", "search_id")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) > 256:
            raise ValueError("Input too long")
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)


class SearchV2Request(BaseModel):
    """R1-8 input schema for POST /api/v2/search.

    Sanitizes raw `target_value` at the edge. Detection of `target_type` is
    optional - clients may pass it explicitly; otherwise the route detects.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    target_value: str = Field(min_length=1, max_length=256)
    target_type: Literal["username", "email", "phone"] | None = None

    @field_validator("target_value")
    @classmethod
    def sanitize_target_value(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_value cannot be empty")
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        if not v:
            raise ValueError("target_value cannot be empty")
        if len(v) > 256:
            raise ValueError("target_value too long (max 256 chars)")
        return v


class SherlockUsernameRequest(BaseModel):
    """Phase 16 D-H8/D-H9: pre-validate username before invoking sherlock_wrapper.

    Strict regex: alphanumerics + underscore + dot + hyphen only, 1-64 chars.
    Rejects /, :, ?, #, &, =, whitespace, null byte, control chars.
    Validation error message is generic — never echoes input (CLAUDE.md regra 3).
    hide_input_in_errors=True prevents Pydantic v2 from embedding input_value in
    the ValidationError repr, satisfying D-H9.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.fullmatch(r"^[A-Za-z0-9_.-]{1,64}$", v):
            raise ValueError("Invalid username")
        return v


class SherlockEvidence(BaseModel):
    signal: str
    weight: int
    detail: str = ""


class SherlockPlatformResponse(BaseModel):
    source: Literal["sherlock", "maigret"] = "sherlock"
    username: str
    platform: str
    category: str
    icon: str
    url_original: str
    url_final: str
    redirect_chain: list[str] = Field(default_factory=list)
    http_status: int | None = None
    fetch_status: Literal[
        "ok",
        "timeout",
        "connection_error",
        "proxy_unavailable",
        "cf_challenge",
        "http_error",
        "invalid",
    ]
    validation_status: Literal[
        "confirmed",
        "likely",
        "uncertain",
        "likely_false_positive",
        "not_found",
        "invalid",
    ]
    confidence_score: int
    confidence_level: str
    evidence: list[SherlockEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    checked_at: datetime
    reliability: Literal["normal", "low"] = "normal"
    baseline_used: bool = False


class SherlockUsernameResponse(BaseModel):
    username: str
    found_count: int
    likely_count: int
    total_checked: int
    source: str
    proxy_used: bool
    platforms: list[SherlockPlatformResponse] = Field(default_factory=list)
