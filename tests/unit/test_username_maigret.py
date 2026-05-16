from __future__ import annotations

import inspect

import httpx
import pytest
import respx

import api.budget as _budget
from modules.username_check import runner
from modules.username_check.fetcher import FetchResult
from modules.username_check.normalize import normalize_platform
from modules.username_check.scoring import combine_outcomes
from modules.username_check.sources import maigret_db
from modules.username_check.validators.base import Signal, ValidationOutcome


def _sample_maigret_data() -> dict:
    return {
        "sites": {
            "ProfileExample": {
                "url": "https://profiles.example/{username}",
                "urlMain": "https://profiles.example",
                "alexaRank": 1,
                "type": "username",
                "requestMethod": "GET",
                "tags": ["social"],
                "presenseStrs": ["profile-card"],
                "absenceStrs": ["not found"],
            },
            "DevExample": {
                "url": "https://dev.example/u/{username}",
                "urlMain": "https://dev.example",
                "alexaRank": 2,
                "type": "username",
                "requestMethod": "GET",
                "tags": ["coding"],
                "absenceStrs": ["missing user"],
            },
        }
    }


@pytest.fixture(autouse=True)
def fake_maigret_data(monkeypatch):
    maigret_db._load_all_sites.cache_clear()
    monkeypatch.setattr(maigret_db, "_load_raw_json", _sample_maigret_data)
    yield
    maigret_db._load_all_sites.cache_clear()


def test_maigret_adapter_loads_static_sites_without_fetcher_imports():
    source = inspect.getsource(maigret_db)

    assert "maigret.search" not in source
    assert "maigret.report" not in source
    assert "maigret.checking" not in source

    sites = maigret_db.load_top_n_sites(10)
    assert sites
    assert all(site["source"] == "maigret" for site in sites)
    assert all("{username}" in site["url"] for site in sites)
    assert all(site["claim_type"] in {"status_code", "text_present", "text_absent"} for site in sites)


def test_candidate_platforms_keep_curated_platforms_and_add_maigret(monkeypatch):
    monkeypatch.setattr(runner, "MAIGRET_ENABLED", True)
    monkeypatch.setattr(runner, "MAIGRET_TOP_N", 20)

    candidates = runner._candidate_platforms()
    domains = [runner._canonical_domain(item["url"]) for item in candidates]

    assert len(runner.PLATFORMS) == 25
    assert len(candidates) > len(runner.PLATFORMS)
    assert len(domains) == len(set(domains))
    assert any(item.get("source") == "maigret" for item in candidates)


def test_normalize_preserves_maigret_source():
    platform = runner.PlatformResult(
        platform="Maigret: Example",
        source="maigret",
        url="https://example.com/alice",
        category="Social",
    )
    platform._fetch_result = FetchResult(
        status_code=200,
        headers={},
        body=b"profile",
        bytes_read=7,
        final_url="https://example.com/alice",
        redirect_chain=[],
    )
    scored = combine_outcomes(
        [
            ValidationOutcome(
                validator="test",
                signals=[Signal("site_specific_profile", 90, hard_positive=True)],
            )
        ]
    )

    payload = normalize_platform("alice", platform, scored)

    assert payload["source"] == "maigret"
    assert payload["validation_status"] == "confirmed"


@pytest.mark.asyncio
@respx.mock
async def test_search_username_runs_maigret_candidate_through_internal_fetcher(monkeypatch):
    monkeypatch.setattr(runner, "MAIGRET_ENABLED", True)
    monkeypatch.setattr(runner, "MAIGRET_TOP_N", 1)
    monkeypatch.setattr(runner, "THORDATA_PROXY_URL", None)
    monkeypatch.setattr(_budget, "_proxy_active", False)
    monkeypatch.setattr(
        runner,
        "PLATFORMS",
        [
            {
                "name": "CuratedExample",
                "url": "https://curated.example/{username}",
                "claim_type": "status_code",
                "claim_value": 200,
                "category": "Test",
                "icon": "",
                "negative_markers": [],
            }
        ],
    )
    monkeypatch.setattr(
        runner,
        "load_top_n_sites",
        lambda n: [
            {
                "name": "Maigret: ProfileExample",
                "url": "https://profiles.example/{username}",
                "claim_type": "text_present",
                "claim_value": "alice",
                "category": "Social",
                "icon": "",
                "negative_markers": [],
                "source": "maigret",
            }
        ],
    )

    respx.get("https://curated.example/alice").mock(
        return_value=httpx.Response(404, content=b"not found")
    )
    respx.get("https://profiles.example/alice").mock(
        return_value=httpx.Response(200, content=b"<title>alice</title>" + b"x" * 4000)
    )

    result = await runner.search_username("alice")
    all_results = result.found + result.likely + result.not_found + result.errors
    maigret_result = next(item for item in all_results if item.source == "maigret")

    assert maigret_result.error is None
    assert maigret_result._fetch_result is not None
    assert maigret_result._fetch_result.bytes_read > 0
    assert maigret_result.state == "confirmed"
