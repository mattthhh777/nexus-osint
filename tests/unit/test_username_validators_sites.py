"""Tests for site-specific validators (Fase G)."""
from __future__ import annotations

from modules.username_check.fetcher import FetchResult
from modules.username_check.validators.base import ValidationContext
from modules.username_check.validators.registry import _resolve_site_validator, for_platform
from modules.username_check.validators.sites.github import GitHubValidator
from modules.username_check.validators.sites.instagram import InstagramValidator
from modules.username_check.validators.sites.linkedin import LinkedInValidator
from modules.username_check.validators.sites.medium import MediumValidator
from modules.username_check.validators.sites.reddit import RedditValidator
from modules.username_check.validators.sites.tiktok import TikTokValidator
from modules.username_check.validators.sites.x import XValidator
from modules.username_check.validators.sites.youtube import YouTubeValidator


def _ctx(
    username: str = "alice",
    body: str = "",
    status: int = 200,
    final_url: str = "",
    original_url: str = "https://example.com/alice",
    redirect_chain: list[str] | None = None,
    platform: dict | None = None,
) -> ValidationContext:
    fetch = FetchResult(
        status_code=status,
        headers={},
        body=body.encode(),
        bytes_read=len(body.encode()),
        final_url=final_url or original_url,
        redirect_chain=redirect_chain or [],
    )
    return ValidationContext(
        username=username,
        platform=platform or {},
        fetch_result=fetch,
        body_text=body,
        original_url=original_url,
    )


# ── Registry ──────────────────────────────────────────────────────────────────

def test_for_platform_returns_default_plus_site_specific():
    validators = for_platform("GitHub")
    names = [v.name for v in validators]
    assert "generic_content" in names
    assert "github_site" in names


def test_for_platform_maigret_prefix_stripped():
    validators = for_platform("Maigret: GitHub")
    names = [v.name for v in validators]
    assert "github_site" in names


def test_for_platform_unknown_returns_only_defaults():
    validators = for_platform("SomeObscureSite")
    assert len(validators) == 3
    assert all(v.name in {"generic_content", "url_final", "negative_markers"} for v in validators)


def test_resolve_site_validator_twitter_slash_x():
    v = _resolve_site_validator("Twitter / X")
    assert v is not None
    assert v.name == "x_site"


def test_resolve_site_validator_maigret_linkedin():
    v = _resolve_site_validator("Maigret: LinkedIn")
    assert v is not None
    assert v.name == "linkedin_site"


# ── GitHub ────────────────────────────────────────────────────────────────────

def test_github_real_profile_itemprop():
    body = (
        '<span itemprop="additionalName">alice</span>'
        '<img src="https://avatars.githubusercontent.com/u/12345?v=4">'
    )
    outcome = GitHubValidator().validate(_ctx("alice", body))
    names = [s.name for s in outcome.signals]
    assert "github_username_itemprop" in names
    assert any(s.hard_positive for s in outcome.signals)


def test_github_itemprop_requires_exact_username():
    body = '<span itemprop="additionalName">malice</span>'
    outcome = GitHubValidator().validate(_ctx("alice", body))
    assert outcome.signals == []


def test_github_avatar_without_itemprop():
    body = '<img src="https://avatars.githubusercontent.com/u/99999?v=4">'
    outcome = GitHubValidator().validate(_ctx("alice", body))
    names = [s.name for s in outcome.signals]
    assert "github_avatar_url" in names
    assert not any(s.hard_positive for s in outcome.signals)


def test_github_not_found_title():
    body = "<title>Not Found \xb7 GitHub</title>"
    outcome = GitHubValidator().validate(_ctx("alice", body))
    assert any(s.hard_negative for s in outcome.signals)
    assert any(s.name == "github_not_found_title" for s in outcome.signals)


def test_github_empty_body_no_signals():
    outcome = GitHubValidator().validate(_ctx("alice", ""))
    assert outcome.signals == []


# ── Instagram ─────────────────────────────────────────────────────────────────

def test_instagram_login_redirect_hard_negative():
    outcome = InstagramValidator().validate(
        _ctx(
            "alice",
            final_url="https://www.instagram.com/accounts/login/?next=%2Falice%2F",
        )
    )
    assert any(s.name == "instagram_login_wall" for s in outcome.signals)
    assert not any(s.hard_negative for s in outcome.signals)
    assert "login_required" in outcome.warnings


def test_instagram_og_profile_type_hard_positive():
    body = '<meta property="og:type" content="profile">'
    outcome = InstagramValidator().validate(_ctx("alice", body))
    assert any(s.name == "instagram_og_profile_type" for s in outcome.signals)
    assert any(s.hard_positive for s in outcome.signals)


def test_instagram_require_login_json():
    body = '{"requiresLogin": true, "data": {}}'
    outcome = InstagramValidator().validate(_ctx("alice", body))
    assert any(s.name == "instagram_require_login_json" for s in outcome.signals)
    assert "login_required" in outcome.warnings


def test_instagram_normal_body_no_signals():
    outcome = InstagramValidator().validate(_ctx("alice", "<html>normal page</html>"))
    assert outcome.signals == []


# ── X (Twitter) ───────────────────────────────────────────────────────────────

def test_x_not_exist_ssr():
    body = "<p>This account doesn’t exist</p>"
    outcome = XValidator().validate(_ctx("ghost", body))
    assert any(s.name == "x_not_found_ssr" for s in outcome.signals)
    assert any(s.hard_negative for s in outcome.signals)


def test_x_og_title_contains_username():
    body = '<meta property="og:title" content="alice (@alice) / X">'
    outcome = XValidator().validate(_ctx("alice", body))
    assert any(s.name == "x_og_title_username" for s in outcome.signals)


def test_x_og_title_does_not_match_substring_username():
    body = '<meta property="og:title" content="Malice (@malice) / X">'
    outcome = XValidator().validate(_ctx("alice", body))
    assert outcome.signals == []


def test_x_not_found_title_pattern():
    body = "<title>Page not found | X</title>"
    outcome = XValidator().validate(_ctx("ghost", body))
    assert any(s.hard_negative for s in outcome.signals)


def test_x_empty_spa_body_no_signals():
    body = "<html><body><div id='root'></div></body></html>"
    outcome = XValidator().validate(_ctx("alice", body))
    assert outcome.signals == []


# ── LinkedIn ──────────────────────────────────────────────────────────────────

def test_linkedin_status_999_hard_negative():
    outcome = LinkedInValidator().validate(_ctx("alice", status=999))
    assert any(s.name == "linkedin_auth_wall_999" for s in outcome.signals)
    assert any(s.hard_negative for s in outcome.signals)
    assert "login_required" in outcome.warnings


def test_linkedin_authwall_redirect():
    outcome = LinkedInValidator().validate(
        _ctx("alice", final_url="https://www.linkedin.com/authwall?trk=abc")
    )
    assert any(s.name == "linkedin_authwall_redirect" for s in outcome.signals)
    assert "login_required" in outcome.warnings


def test_linkedin_normal_200_no_signals():
    outcome = LinkedInValidator().validate(_ctx("alice", status=200))
    assert outcome.signals == []


# ── Reddit ────────────────────────────────────────────────────────────────────

def test_reddit_bot_challenge():
    body = "<title>Robot or human?</title><p>Please wait for verification</p>"
    outcome = RedditValidator().validate(_ctx("alice", body))
    assert any(s.name == "reddit_bot_challenge" for s in outcome.signals)
    assert any(s.hard_negative for s in outcome.signals)
    assert "bot_check" in outcome.warnings


def test_reddit_no_user_ssr():
    body = "<p>Sorry, nobody on Reddit goes by that name.</p>"
    outcome = RedditValidator().validate(_ctx("ghost", body))
    assert any(s.name == "reddit_no_user" for s in outcome.signals)
    assert any(s.hard_negative for s in outcome.signals)


def test_reddit_suspended_warning():
    body = "<p>account has been suspended for violating rules</p>"
    outcome = RedditValidator().validate(_ctx("alice", body))
    assert "account_suspended" in outcome.warnings
    assert not any(s.hard_negative for s in outcome.signals)


def test_reddit_normal_profile_no_signals():
    outcome = RedditValidator().validate(_ctx("alice", "<html>normal user page</html>"))
    assert outcome.signals == []


# ── TikTok ────────────────────────────────────────────────────────────────────

def test_tiktok_not_found_ssr():
    body = "<p>Couldn’t find this account</p>"
    outcome = TikTokValidator().validate(_ctx("ghost", body))
    assert any(s.name == "tiktok_not_found" for s in outcome.signals)
    assert any(s.hard_negative for s in outcome.signals)


def test_tiktok_status_code_json():
    body = '{"statusCode": 10221, "message": "user not found"}'
    outcome = TikTokValidator().validate(_ctx("ghost", body))
    assert any(s.hard_negative for s in outcome.signals)


def test_tiktok_og_url_username():
    body = '<meta property="og:url" content="https://www.tiktok.com/@alice">'
    outcome = TikTokValidator().validate(_ctx("alice", body))
    assert any(s.name == "tiktok_og_url_username" for s in outcome.signals)


def test_tiktok_og_url_does_not_match_substring_username():
    body = '<meta property="og:url" content="https://www.tiktok.com/@malice">'
    outcome = TikTokValidator().validate(_ctx("alice", body))
    assert outcome.signals == []


# ── YouTube ───────────────────────────────────────────────────────────────────

def test_youtube_not_found():
    body = "<title>404 Not Found</title>"
    outcome = YouTubeValidator().validate(_ctx("ghost", body))
    assert any(s.name == "youtube_not_found" for s in outcome.signals)
    assert any(s.hard_negative for s in outcome.signals)


def test_youtube_og_title_username():
    body = '<meta property="og:title" content="Alice - YouTube">'
    outcome = YouTubeValidator().validate(_ctx("alice", body))
    assert any(s.name == "youtube_og_title_username" for s in outcome.signals)


def test_youtube_og_url_username():
    body = '<meta property="og:url" content="https://www.youtube.com/@alice">'
    outcome = YouTubeValidator().validate(_ctx("alice", body))
    assert any(s.name == "youtube_og_url_username" for s in outcome.signals)


def test_youtube_og_url_does_not_match_substring_username():
    body = '<meta property="og:url" content="https://www.youtube.com/@malice">'
    outcome = YouTubeValidator().validate(_ctx("alice", body))
    assert outcome.signals == []


# ── Medium ────────────────────────────────────────────────────────────────────

def test_medium_not_found():
    body = "<title>Profile not found – Medium</title>"
    outcome = MediumValidator().validate(_ctx("ghost", body))
    assert any(s.name == "medium_not_found" for s in outcome.signals)
    assert any(s.hard_negative for s in outcome.signals)


def test_medium_page_not_found():
    body = "<title>Page not found – Medium</title>"
    outcome = MediumValidator().validate(_ctx("ghost", body))
    assert any(s.hard_negative for s in outcome.signals)


def test_medium_og_title_username():
    body = '<meta property="og:title" content="alice – Medium">'
    outcome = MediumValidator().validate(_ctx("alice", body))
    assert any(s.name == "medium_og_title_username" for s in outcome.signals)


def test_medium_og_title_does_not_match_substring_username():
    body = '<meta property="og:title" content="malice – Medium">'
    outcome = MediumValidator().validate(_ctx("alice", body))
    assert outcome.signals == []
