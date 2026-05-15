from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

import api.budget as budget
import api.services.search_service as search_service
from api.db import DatabaseManager
from api.orchestrator import DegradationMode, TaskOrchestrator
from api.schemas import SearchRequest
from modules.sherlock_wrapper import PlatformResult, SherlockResult
from modules.username_check.fetcher import FetchResult
from modules.username_check.scoring import combine_outcomes
from modules.username_check.validators.base import Signal, ValidationOutcome


def _parse_sse(content: bytes) -> list[dict]:
    events = []
    for line in content.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[6:]))
    return events


def _make_mock_db() -> MagicMock:
    db = MagicMock(spec=DatabaseManager)
    db.write = AsyncMock()
    db.read_one = AsyncMock(return_value=None)
    return db


def _make_mock_orch() -> MagicMock:
    orch = MagicMock(spec=TaskOrchestrator)
    orch.degradation_mode = DegradationMode.NORMAL
    orch.active_count = 0
    orch.semaphore_slots_free = 5
    orch.submit = MagicMock()
    return orch


async def _collect_sse(req: SearchRequest) -> list[dict]:
    chunks = []
    async for chunk in search_service._stream_search(
        req, "alice", "127.0.0.1", db=_make_mock_db(), orch=_make_mock_orch()
    ):
        chunks.append(chunk)
    raw = b"".join(chunk.encode() if isinstance(chunk, str) else chunk for chunk in chunks)
    return _parse_sse(raw)


def _make_v2_stub() -> SherlockResult:
    platform = PlatformResult(
        platform="Example",
        url="https://example.com/alice",
        category="Test",
        icon="T",
        state="confirmed",
        confidence=90,
        found=True,
    )
    platform._fetch_result = FetchResult(
        status_code=200,
        headers={},
        body=b"profile",
        bytes_read=7,
        final_url="https://example.com/alice",
        redirect_chain=[],
    )
    platform._v2_score = combine_outcomes(
        [
            ValidationOutcome(
                "test",
                [
                    Signal("title_contains_username", 30),
                    Signal("canonical_contains_username", 30),
                    Signal("og_url_contains_username", 30),
                ],
            )
        ]
    )
    return SherlockResult(
        username="alice",
        success=True,
        found=[platform],
        source="internal",
        proxy_used=False,
    )


@pytest.fixture(autouse=True)
def _reset_budget(monkeypatch):
    monkeypatch.setattr(budget, "_bytes_today", 0)
    monkeypatch.setattr(budget, "_requests_today", 0)
    monkeypatch.setattr(budget, "_proxy_active", False)


def test_sherlock_v2_dual_emission_when_flag_enabled(monkeypatch):
    import modules.sherlock_wrapper as mw

    monkeypatch.setattr(search_service, "SHERLOCK_VALIDATION_V2", True)
    monkeypatch.setattr(mw, "search_username", AsyncMock(return_value=_make_v2_stub()))

    req = SearchRequest(query="alice", mode="manual", modules=["sherlock"])
    events = asyncio.get_event_loop().run_until_complete(_collect_sse(req))

    assert any(event.get("type") == "sherlock" for event in events)
    v2_event = next(event for event in events if event.get("type") == "sherlock_v2")
    assert v2_event["found_count"] == 1
    assert v2_event["platforms"][0]["validation_status"] == "confirmed"
    assert v2_event["platforms"][0]["evidence"]


def test_sherlock_v2_not_emitted_when_flag_disabled(monkeypatch):
    import modules.sherlock_wrapper as mw

    monkeypatch.setattr(search_service, "SHERLOCK_VALIDATION_V2", False)
    monkeypatch.setattr(mw, "search_username", AsyncMock(return_value=_make_v2_stub()))

    req = SearchRequest(query="alice", mode="manual", modules=["sherlock"])
    events = asyncio.get_event_loop().run_until_complete(_collect_sse(req))

    assert any(event.get("type") == "sherlock" for event in events)
    assert not any(event.get("type") == "sherlock_v2" for event in events)
