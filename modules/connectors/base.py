"""Connector contract shared by all OSINT sources.

This module defines the canonical schemas. Status enum is 8-state.
`likely` and `blocked` are first-class and MUST NOT collapse into other states
at any layer (backend, adapter, frontend). See .planning/R0_R1_REVISION.md.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TargetType(str, Enum):
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"


class ConnectorStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    FOUND = "found"
    LIKELY = "likely"
    NOT_FOUND = "not_found"
    UNCERTAIN = "uncertain"
    BLOCKED = "blocked"
    ERROR = "error"


ConfidenceLevel = Literal["high", "medium", "low", "none"]


def derive_confidence_level(score: int) -> ConfidenceLevel:
    if score >= 85:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 30:
        return "low"
    return "none"


class Evidence(BaseModel):
    signal: str
    weight: int = Field(ge=-100, le=100)
    detail: str = ""


class ConnectorRequest(BaseModel):
    target_type: TargetType
    target_value: str
    target_hash: str
    timeout_s: int = 15
    job_id: UUID


class ConnectorResult(BaseModel):
    connector: str
    target_type: TargetType
    status: ConnectorStatus
    confidence_score: int = Field(ge=0, le=100)
    confidence_level: ConfidenceLevel
    evidence: list[Evidence] = []
    warnings: list[str] = []
    raw_url: str | None = None
    data: dict = {}
    fetched_at: datetime
    cache_hit: bool = False
    elapsed_ms: int = Field(ge=0)
