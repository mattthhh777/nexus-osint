from __future__ import annotations

from modules.sherlock_wrapper import PlatformResult, SherlockResult
from modules.username_check.fetcher import FetchResult
from modules.username_check.normalize import normalize_result
from modules.username_check.scoring import combine_outcomes
from modules.username_check.validators.base import Signal, ValidationOutcome


def _outcome(*signals: Signal, warnings: list[str] | None = None) -> ValidationOutcome:
    return ValidationOutcome(
        validator="test",
        signals=list(signals),
        warnings=warnings or [],
    )


def test_confirmed_requires_hard_positive_or_three_positive_signals():
    two_signals = combine_outcomes(
        [
            _outcome(
                Signal("a", 40),
                Signal("b", 45),
            )
        ]
    )
    three_signals = combine_outcomes(
        [
            _outcome(
                Signal("a", 30),
                Signal("b", 30),
                Signal("c", 30),
            )
        ]
    )

    assert two_signals.validation_status == "likely"
    assert three_signals.validation_status == "confirmed"


def test_hard_positive_can_confirm_with_high_score():
    scored = combine_outcomes(
        [_outcome(Signal("site_specific_profile", 90, hard_positive=True))]
    )
    assert scored.validation_status == "confirmed"


def test_low_reliability_never_confirmed_without_hard_positive():
    scored = combine_outcomes(
        [
            _outcome(
                Signal("a", 35),
                Signal("b", 35),
                Signal("c", 35),
            )
        ],
        reliability="low",
    )
    assert scored.confidence_score == 84
    assert scored.validation_status == "likely"


def test_baseline_indistinguishable_becomes_likely_false_positive():
    scored = combine_outcomes(
        [
            _outcome(
                Signal("final_url_contains_username", 25),
                Signal("baseline_indistinguishable", -60, hard_negative=True),
            )
        ]
    )
    assert scored.validation_status == "likely_false_positive"


def test_fetch_error_is_invalid_with_evidence():
    scored = combine_outcomes([], fetch_error="timeout")
    assert scored.validation_status == "invalid"
    assert scored.evidence[0].signal == "fetch_error"


def test_login_required_without_hard_negative_is_uncertain():
    scored = combine_outcomes(
        [
            _outcome(
                Signal("instagram_login_wall", 0, "login_redirect"),
                warnings=["login_required"],
            )
        ]
    )
    assert scored.validation_status == "uncertain"
    assert scored.confidence_score == 30


def test_auth_wall_and_bot_check_are_invalid():
    linkedin = combine_outcomes(
        [
            _outcome(
                Signal(
                    "linkedin_auth_wall_999",
                    -100,
                    "status_999",
                    hard_negative=True,
                ),
                warnings=["login_required"],
            )
        ]
    )
    reddit = combine_outcomes(
        [
            _outcome(
                Signal("reddit_bot_challenge", -100, "bot_challenge", hard_negative=True),
                warnings=["bot_check"],
            )
        ]
    )
    assert linkedin.validation_status == "invalid"
    assert reddit.validation_status == "invalid"


def test_normalize_result_includes_v2_evidence_or_error():
    fetch_result = FetchResult(
        status_code=200,
        headers={},
        body=b"profile",
        bytes_read=7,
        final_url="https://example.com/alice",
        redirect_chain=[],
    )
    platform = PlatformResult(
        platform="Example",
        url="https://example.com/alice",
        category="Test",
        icon="T",
        state="confirmed",
        confidence=90,
        found=True,
    )
    platform._fetch_result = fetch_result
    platform._v2_score = combine_outcomes(
        [
            _outcome(
                Signal("a", 30),
                Signal("b", 30),
                Signal("c", 30),
            )
        ]
    )
    result = SherlockResult(username="alice", success=True, found=[platform])
    payload = normalize_result("alice", result)

    item = payload["platforms"][0]
    assert item["validation_status"] == "confirmed"
    assert item["url_final"] == "https://example.com/alice"
    assert item["evidence"]
