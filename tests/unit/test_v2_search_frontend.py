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
    assert "likely: 0" in v2
    assert "blocked: 0" in v2
    assert "blocked: true" in v2


def test_v2_does_not_persist_raw_target_history() -> None:
    v2 = read("static/js/v2-search.js")

    assert "saveHistory()" not in v2
    assert "localStorage.setItem" not in v2
    assert "history.pushState" not in v2
    assert "history.replaceState" not in v2


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


def test_signal_ui_has_stable_empty_state_containers() -> None:
    html = read("static/index.html")

    assert 'id="signalDossierMeta"' in html
    assert 'id="signalDossierBadges"' in html
    assert 'id="signalLayerCount"' in html
    assert 'id="signalLayerGrid"' in html
    assert 'id="signalEvidenceBody"' in html
    assert 'id="signalOutputList"' in html
    assert 'id="signalCasesBody"' in html
    assert "No simulated findings" in html


def test_signal_ui_renders_real_v2_state_without_changing_engine_flag() -> None:
    v2 = read("static/js/v2-search.js")

    assert "function isSignalUiActive()" in v2
    assert "getParam('ui') === 'signal'" in v2
    assert "function renderSignalUi()" in v2
    assert "renderSignalDossier();" in v2
    assert "renderSignalLayers();" in v2
    assert "renderSignalOutput();" in v2
    assert "renderSignalEvidence();" in v2
    assert "global.startSearch = startV2Search" in v2
    assert "getParam('engine') === 'v2'" in v2


def test_signal_ui_connector_results_and_evidence_are_real_only() -> None:
    v2 = read("static/js/v2-search.js")

    assert "sanitizeEvidenceList(payload.evidence)" in v2
    assert "Evidence unavailable until connector results provide evidence payloads" in v2
    assert "Signal UI will not invent evidence" in v2
    assert "Evidence rows will render only when backend events provide evidence fields" in read("static/index.html")
    assert "davibrito" not in v2
    assert "OathNet 84 left" not in v2
    assert "risk 100" not in v2


def test_signal_ui_does_not_render_raw_query_or_persist_target() -> None:
    v2 = read("static/js/v2-search.js")

    assert "redactRawTarget" in v2
    assert "Hash-only target context" in v2
    assert "title.textContent = currentResult.query" not in v2
    assert "meta.textContent = currentResult.query" not in v2
    assert "history.pushState" not in v2
    assert "history.replaceState" not in v2
    assert "localStorage.setItem" not in v2


def test_signal_evidence_detail_is_keyboard_selectable_and_grouped() -> None:
    v2 = read("static/js/v2-search.js")
    css = read("static/css/signal.css")

    assert "selectedSignalEvidenceKey" in v2
    assert "getSignalEvidenceGroups" in v2
    assert "renderSignalEvidenceDetail" in v2
    assert "row.type = 'button'" in v2
    assert "aria-pressed" in v2
    assert "No evidence payload provided" in v2
    assert ".signal-evidence-detail" in css
    assert ".signal-evidence-row--selected" in css


def test_signal_evidence_sanitizes_sensitive_fields() -> None:
    v2 = read("static/js/v2-search.js")

    assert "function isSensitiveEvidenceKey" in v2
    assert "headers?|body|cookies?|tokens?|secrets?" in v2
    assert "authorization|password|api_?key" in v2
    assert "detail unavailable" in v2
    assert "safeEvidenceValue(item, ['detail', 'summary', 'snippet', 'description', 'value', 'message'])" in v2
    assert "item.headers" not in v2
    assert "item.body" not in v2
    assert "item.token" not in v2
    assert "item.cookie" not in v2
    assert "item.secret" not in v2


def test_signal_cases_only_render_safe_hash_metadata() -> None:
    v2 = read("static/js/v2-search.js")
    css = read("static/css/signal.css")

    assert "renderSignalCases" in v2
    assert "readSignalStorageList('nx_cases')" in v2
    assert "readSignalStorageList('nx_history')" in v2
    assert "target_hash ' + shortValue" in v2
    assert "Legacy entries with raw targets stay hidden" in v2
    assert "localStorage.setItem" not in v2
    assert ".signal-case-card" in css


def test_signal_cases_do_not_render_stored_raw_targets() -> None:
    v2 = read("static/js/v2-search.js")

    assert "item.name" not in v2
    assert "item.query" not in v2
    assert "history-target" not in v2
    assert "target_hash" in v2
    assert "No safe case metadata available" in v2
