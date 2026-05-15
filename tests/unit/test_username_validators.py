from __future__ import annotations

import httpx
import pytest
import respx

from modules.sherlock_wrapper import _check_platform
from modules.username_check.fetcher import FetchResult
from modules.username_check.validators.base import (
    Signal,
    ValidationContext,
    ValidationOutcome,
    ValidatorError,
)
from modules.username_check.validators.generic_content import GenericContentValidator
from modules.username_check.validators.negative_markers import NegativeMarkersValidator
from modules.username_check.validators.registry import validate_all
from modules.username_check.validators.url_final import UrlFinalValidator


def _fetch(
    body: bytes = b"",
    *,
    status_code: int = 200,
    final_url: str = "https://example.com/alice",
    redirect_chain: list[str] | None = None,
) -> FetchResult:
    return FetchResult(
        status_code=status_code,
        headers={},
        body=body,
        bytes_read=len(body),
        final_url=final_url,
        redirect_chain=redirect_chain or [],
    )


def _ctx(
    body: str,
    *,
    username: str = "alice",
    final_url: str = "https://example.com/alice",
    original_url: str = "https://example.com/alice",
    redirect_chain: list[str] | None = None,
    platform: dict | None = None,
) -> ValidationContext:
    fetch = _fetch(
        body.encode(),
        final_url=final_url,
        redirect_chain=redirect_chain,
    )
    return ValidationContext(
        username=username,
        platform=platform or {"name": "Example", "negative_markers": []},
        fetch_result=fetch,
        body_text=body,
        original_url=original_url,
    )


def _signals(outcome: ValidationOutcome) -> set[str]:
    return {signal.name for signal in outcome.signals}


class TestGenericContentValidator:
    validator = GenericContentValidator()

    def test_title_contains_username(self):
        outcome = self.validator.validate(_ctx("<title>Alice profile</title>"))
        assert "title_contains_username" in _signals(outcome)

    def test_script_content_is_ignored(self):
        body = "<script><title>Alice profile</title></script><title>Home</title>"
        outcome = self.validator.validate(_ctx(body))
        assert "title_contains_username" not in _signals(outcome)

    def test_canonical_contains_username(self):
        body = '<link href="https://example.com/alice" rel="canonical">'
        outcome = self.validator.validate(_ctx(body))
        assert "canonical_contains_username" in _signals(outcome)

    def test_og_url_contains_username(self):
        body = '<meta content="https://example.com/alice" property="og:url">'
        outcome = self.validator.validate(_ctx(body))
        assert "og_url_contains_username" in _signals(outcome)

    def test_jsonld_id_contains_username(self):
        body = '<script type="application/ld+json">{"@id":"https://example.com/alice"}</script>'
        outcome = self.validator.validate(_ctx(body))
        assert "jsonld_contains_username" in _signals(outcome)

    def test_title_negative_marker_is_hard_negative(self):
        outcome = self.validator.validate(_ctx("<title>404 not found</title>"))
        signal = next(s for s in outcome.signals if s.name == "title_negative_marker")
        assert signal.hard_negative is True

    def test_invalid_jsonld_does_not_crash(self):
        body = '<script type="application/ld+json">{broken</script>'
        outcome = self.validator.validate(_ctx(body))
        assert outcome.validator == "generic_content"


class TestUrlFinalValidator:
    validator = UrlFinalValidator()

    def test_final_url_contains_username(self):
        outcome = self.validator.validate(_ctx("", final_url="https://example.com/u/alice"))
        assert "final_url_contains_username" in _signals(outcome)

    def test_final_url_matches_expected(self):
        outcome = self.validator.validate(_ctx("", final_url="https://example.com/alice"))
        assert "final_url_matches_expected" in _signals(outcome)

    def test_redirect_homepage_is_hard_negative(self):
        outcome = self.validator.validate(
            _ctx(
                "",
                final_url="https://example.com/",
                redirect_chain=["https://example.com/alice", "https://example.com/"],
            )
        )
        signal = next(s for s in outcome.signals if s.name == "redirect_to_homepage")
        assert signal.hard_negative is True

    def test_redirect_login_is_warning(self):
        outcome = self.validator.validate(
            _ctx(
                "",
                final_url="https://example.com/login",
                redirect_chain=["https://example.com/alice", "https://example.com/login"],
            )
        )
        assert "redirect_to_login" in outcome.warnings

    def test_redirect_search_is_negative_signal(self):
        outcome = self.validator.validate(
            _ctx(
                "",
                final_url="https://example.com/search?q=alice",
                redirect_chain=["https://example.com/alice", "https://example.com/search?q=alice"],
            )
        )
        signal = next(s for s in outcome.signals if s.name == "redirect_to_search")
        assert signal.weight == -30

    def test_redirect_other_profile_is_hard_negative(self):
        outcome = self.validator.validate(
            _ctx(
                "",
                final_url="https://example.com/bob",
                redirect_chain=["https://example.com/alice", "https://example.com/bob"],
            )
        )
        signal = next(s for s in outcome.signals if s.name == "redirect_to_other_profile")
        assert signal.hard_negative is True


class TestNegativeMarkersValidator:
    validator = NegativeMarkersValidator()

    def test_platform_marker_is_hard_negative(self):
        ctx = _ctx("Sorry, no Alice here", platform={"name": "Example", "negative_markers": ["no alice"]})
        outcome = self.validator.validate(ctx)
        signal = next(s for s in outcome.signals if s.name == "negative_marker_platform")
        assert signal.hard_negative is True

    def test_common_user_not_found_marker(self):
        outcome = self.validator.validate(_ctx("This user does not exist"))
        assert "negative_marker_common" in _signals(outcome)

    def test_common_404_marker(self):
        outcome = self.validator.validate(_ctx("404"))
        assert "negative_marker_common" in _signals(outcome)

    def test_portuguese_marker(self):
        outcome = self.validator.validate(_ctx("usuario nao encontrado"))
        assert "negative_marker_common" in _signals(outcome)

    def test_spanish_marker(self):
        outcome = self.validator.validate(_ctx("cuenta no encontrada"))
        assert "negative_marker_common" in _signals(outcome)

    def test_positive_body_has_no_negative_signal(self):
        outcome = self.validator.validate(_ctx("Alice profile page"))
        assert outcome.signals == []


class FailingValidator:
    name = "failing"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        raise ValidatorError("expected validator failure")


def test_registry_isolates_expected_validator_error():
    outcome = validate_all(_ctx("Alice profile page"), validators=[FailingValidator()])[0]
    assert outcome.validator == "failing"
    assert outcome.warnings == ["validator_error:failing"]


@pytest.mark.asyncio
@respx.mock
async def test_runner_attaches_internal_validation_outcomes():
    platform = {
        "name": "Example",
        "url": "https://example.com/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Test",
        "icon": "",
        "negative_markers": [],
    }
    respx.get("https://example.com/alice").mock(
        return_value=httpx.Response(
            200,
            content=b"<title>Alice profile</title>" + (b"x" * 3_100),
        )
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        result = await _check_platform(client, "alice", platform, {"bytes": 0})

    assert result._outcomes
    assert "title_contains_username" in {
        signal.name for outcome in result._outcomes for signal in outcome.signals
    }
