from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v2_scripts_are_loaded_after_legacy_search_before_bootstrap() -> None:
    html = read("static/index.html")

    search_pos = html.index("/static/js/search.js")
    replay_pos = html.index("/static/js/job-replay.js")
    v2_pos = html.index("/static/js/v2-search.js")
    bootstrap_pos = html.index("/static/js/bootstrap.js")

    assert search_pos < replay_pos < v2_pos < bootstrap_pos


def test_engine_off_keeps_legacy_start_search() -> None:
    v2 = read("static/js/v2-search.js")
    legacy = read("static/js/search.js")

    assert "getParam('engine') === 'v2'" in v2
    assert "global.__nxLegacyStartSearch = legacyStartSearch" in v2
    assert "global.startSearch = startV2Search" in v2
    assert "apiFetch('/api/search'" in legacy


def test_engine_v2_posts_to_job_api_only() -> None:
    v2 = read("static/js/v2-search.js")

    assert "apiFetch('/api/v2/search'" in v2
    assert "target_value: query" in v2
    assert "target_type: targetType" in v2
    assert "apiFetch('/api/search'" not in v2


def test_sse_replay_uses_from_seq() -> None:
    replay = read("static/js/job-replay.js")

    assert "searchParams.set('from_seq'" in replay
    assert "state.lastSeq" in replay
    assert "seq <= state.lastSeq" in replay


def test_v2_scope_has_no_ip_gravatar_or_fake_cancel() -> None:
    combined = "\n".join(
        [
            read("static/js/v2-search.js"),
            read("static/js/job-replay.js"),
        ]
    ).lower()

    assert "gravatar" not in combined
    assert "targettype.ip" not in combined
    assert "target_type: 'ip'" not in combined
    assert "target_type: \"ip\"" not in combined
    assert "fake cancel" not in combined


def test_v2_preserves_likely_and_blocked_statuses() -> None:
    v2 = read("static/js/v2-search.js")

    assert "status: payload.status" in v2
    assert "status === 'likely'" in v2
    assert "status === 'blocked'" not in v2
    assert "blocked" not in v2


def test_v2_does_not_persist_raw_target_history() -> None:
    v2 = read("static/js/v2-search.js")

    assert "saveHistory()" not in v2
    assert "localStorage" not in v2


def test_signal_ui_foundation_is_query_flagged_and_frontend_only() -> None:
    html = read("static/index.html")
    bootstrap = read("static/js/bootstrap.js")
    signal_css = read("static/css/signal.css")

    assert "/static/css/signal.css" in html
    assert 'id="signalShell"' in html
    assert "No investigation active" in html
    assert "params.get('ui') === 'signal'" in bootstrap
    assert "window.NX_SIGNAL_UI = active" in bootstrap
    assert "classList.toggle('nx-signal', active)" in bootstrap
    assert "localStorage" not in bootstrap
    assert "document.cookie" not in bootstrap
    assert "/api/search" not in signal_css
    assert "/api/v2/search" not in signal_css
