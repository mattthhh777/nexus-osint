// Opt-in frontend bridge for /api/v2/search jobs.

(function (global) {
  'use strict';

  var SUPPORTED_TARGET_TYPES = Object.freeze({
    email: true,
    phone: true,
    username: true
  });

  var legacyStartSearch = global.startSearch;

  function getParam(name) {
    var match = new RegExp('[?&]' + name + '=([^&]+)').exec(global.location.search);
    return match ? decodeURIComponent(match[1]) : null;
  }

  function isEngineV2() {
    return getParam('engine') === 'v2';
  }

  function isSignalUiActive() {
    return global.NX_SIGNAL_UI === true || getParam('ui') === 'signal';
  }

  function detectSupportedTargetType(query) {
    var detected = typeof detectType === 'function' ? detectType(query) : 'username';
    if (SUPPORTED_TARGET_TYPES[detected]) return detected;
    return null;
  }

  function safeMessage(err) {
    if (!err || !err.message) return 'Search failed';
    if (err.message.indexOf('target_value') >= 0) return 'Unsupported target for v2 search';
    return err.message;
  }

  function resetScanUi(query, targetType) {
    document.getElementById('results').classList.remove('visible');
    document.getElementById('scanStatus').classList.add('visible');
    document.getElementById('scanModules').innerHTML = '';
    document.getElementById('searchBtn').disabled = true;
    var liveResults = document.getElementById('v2ConnectorLive');
    if (liveResults) liveResults.remove();
    if (typeof moduleRows !== 'undefined') moduleRows = {};
    if (typeof modulesRan !== 'undefined') modulesRan = new Set();
    setScanProgress(0, 'Creating job...');

    currentResult = {
      query: query,
      oathnet: emptyOathNet(),
      sherlock: emptySherlock(),
      extras: {},
      connectorResultsByName: {},
      connectorResults: [],
      v2: {
        engine: 'v2',
        target_type: targetType,
        last_seq: 0,
        connectors_started: [],
        events_seen: []
      }
    };
    renderSignalUi();
  }

  function emptyOathNet() {
    return {
      breach_count: 0,
      stealer_count: 0,
      holehe_count: 0,
      breaches: [],
      stealers: []
    };
  }

  function emptySherlock() {
    return {
      found_count: 0,
      likely_count: 0,
      total_checked: 0,
      found: [],
      likely: [],
      platforms: []
    };
  }

  async function parseJsonResponse(resp) {
    var body = await resp.json().catch(function () { return {}; });
    if (!resp.ok) {
      throw new Error(body.detail || body.error || 'Search request failed');
    }
    return body;
  }

  async function createJob(query, targetType) {
    var resp = await apiFetch('/api/v2/search', {
      method: 'POST',
      body: JSON.stringify({
        target_value: query,
        target_type: targetType
      })
    });
    return parseJsonResponse(resp);
  }

  async function loadSnapshot(jobId) {
    var resp = await apiFetch('/api/v2/search/' + encodeURIComponent(jobId), {
      method: 'GET'
    });
    return parseJsonResponse(resp);
  }

  function applySnapshot(snapshot) {
    currentResult.v2.job_id = snapshot.job_id;
    currentResult.v2.status = snapshot.status;
    currentResult.v2.target_type = snapshot.target_type;
    currentResult.v2.target_hash = snapshot.target_hash;
    currentResult.v2.connectors_planned = snapshot.connectors_planned || [];
    currentResult.v2.connectors_run = snapshot.connectors_run || [];
    currentResult.v2.connectors_started = currentResult.v2.connectors_started || [];
    currentResult.v2.overall_status = snapshot.overall_status || null;
    currentResult.v2.overall_confidence = snapshot.overall_confidence || 0;
    currentResult.searchId = snapshot.job_id;
    renderSignalUi();
  }

  function connectorToModule(connector) {
    if (!connector) return 'v2';
    if (connector.indexOf('sherlock:') === 0) return 'sherlock';
    if (connector.indexOf('oathnet:breach') === 0) return 'breach';
    if (connector.indexOf('oathnet:stealer') === 0) return 'stealer';
    if (connector.indexOf('oathnet:victims') === 0) return 'victims';
    if (connector.indexOf('carrier_lookup') === 0) return 'carrier_lookup';
    return connector.split(':')[0];
  }

  function connectorLabel(connector) {
    return String(connector || 'connector').replace(/[:_]/g, ' ');
  }

  function escapeRegExp(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function redactRawTarget(value) {
    var text = String(value == null ? '' : value);
    var raw = currentResult && currentResult.query ? String(currentResult.query) : '';
    if (raw.length > 2) {
      text = text.replace(new RegExp(escapeRegExp(raw), 'gi'), '[target redacted]');
    }
    return text;
  }

  function sanitizeStringList(items) {
    if (!Array.isArray(items)) return [];
    return items.map(redactRawTarget).filter(Boolean);
  }

  function safeEvidenceBody(item) {
    if (!item || typeof item !== 'object') return redactRawTarget(item);
    var preferred = item.summary || item.snippet || item.description || item.value || item.message;
    if (preferred) return redactRawTarget(preferred);

    var safe = {};
    Object.keys(item).forEach(function (key) {
      if (/^(raw_url|url|target|target_value|query)$/i.test(key)) return;
      var value = item[key];
      if (value == null || typeof value === 'object') return;
      safe[key] = redactRawTarget(value);
    });
    return Object.keys(safe).length ? JSON.stringify(safe) : '';
  }

  function sanitizeEvidenceList(items) {
    if (!Array.isArray(items)) return [];
    return items.map(function (item) {
      if (!item || typeof item !== 'object') {
        return {
          title: 'Evidence',
          source: '',
          type: '',
          body: redactRawTarget(item)
        };
      }
      return {
        title: redactRawTarget(item.title || item.label || item.type || 'Evidence'),
        source: redactRawTarget(item.source || item.connector || ''),
        type: redactRawTarget(item.type || ''),
        body: safeEvidenceBody(item)
      };
    }).filter(function (item) {
      return item.body || item.title || item.source || item.type;
    });
  }

  function connectorResultFromPayload(payload) {
    return {
      connector: payload.connector,
      target_type: currentResult.v2.target_type,
      status: payload.status,
      confidence_score: Number(payload.confidence_score || 0),
      confidence_level: payload.confidence_level || 'none',
      evidence: sanitizeEvidenceList(payload.evidence),
      warnings: sanitizeStringList(payload.warnings),
      raw_url: null,
      data: {
        target_hash: currentResult.v2.target_hash || ''
      },
      fetched_at: payload.fetched_at || null,
      cache_hit: Boolean(payload.cache_hit),
      elapsed_ms: Number(payload.elapsed_ms || 0)
    };
  }

  function storeConnectorResult(result) {
    if (!result.connector) return;
    currentResult.connectorResultsByName[result.connector] = result;
    currentResult.connectorResults = Object.values(currentResult.connectorResultsByName);
    rebuildLegacyAggregates();
    renderV2LiveConnectorResults();
    renderSignalUi();
  }

  function rebuildLegacyAggregates() {
    var results = currentResult.connectorResults || [];
    var oathnet = emptyOathNet();
    var sherlock = emptySherlock();

    results.forEach(function (result) {
      var status = result.status;
      if (result.connector.indexOf('oathnet:breach') === 0 && status === 'found') {
        oathnet.breach_count += 1;
      }
      if (result.connector.indexOf('oathnet:stealer') === 0 && status === 'found') {
        oathnet.stealer_count += 1;
      }
      if (result.connector.indexOf('sherlock:') === 0) {
        sherlock.total_checked += 1;
        if (status === 'found') sherlock.found_count += 1;
        if (status === 'likely') sherlock.likely_count += 1;
      }
    });

    currentResult.oathnet = oathnet;
    currentResult.sherlock = sherlock;
  }

  function updateProgress() {
    var planned = currentResult.v2.connectors_planned || [];
    var completed = currentResult.connectorResults.length;
    if (!planned.length) {
      setScanProgress(15, 'Running connectors...');
      return;
    }
    var pct = Math.min(95, 10 + Math.round((completed / planned.length) * 85));
    setScanProgress(pct, 'Running connectors...');
  }

  function rememberEvent(event) {
    currentResult.v2.last_seq = Math.max(currentResult.v2.last_seq || 0, Number(event.seq || 0));
    currentResult.v2.events_seen.push({
      seq: event.seq,
      event_type: event.event_type
    });
  }

  function statusClass(status) {
    if (status === 'not_found') return 'not-found';
    return String(status || 'idle').replace(/[^a-z0-9_-]/gi, '-');
  }

  function normalizeStatus(status) {
    var value = String(status || 'pending');
    var allowed = {
      pending: true,
      running: true,
      found: true,
      likely: true,
      not_found: true,
      uncertain: true,
      blocked: true,
      error: true
    };
    return allowed[value] ? value : 'uncertain';
  }

  function shortValue(value, fallback) {
    var text = String(value || '');
    if (!text) return fallback;
    if (text.length <= 12) return text;
    return text.slice(0, 6) + '...' + text.slice(-6);
  }

  function createSignalPill(label, status) {
    var pill = document.createElement('span');
    var normalized = normalizeStatus(status || 'idle');
    pill.className = 'signal-pill signal-pill--' + statusClass(normalized);
    pill.textContent = label;
    return pill;
  }

  function getSignalResults() {
    return currentResult && currentResult.connectorResults ? currentResult.connectorResults : [];
  }

  function getConnectorNames() {
    var seen = {};
    var names = [];

    function push(name) {
      if (!name || seen[name]) return;
      seen[name] = true;
      names.push(name);
    }

    ((currentResult.v2 && currentResult.v2.connectors_planned) || []).forEach(push);
    ((currentResult.v2 && currentResult.v2.connectors_started) || []).forEach(push);
    getSignalResults().forEach(function (result) { push(result.connector); });
    return names;
  }

  function getConnectorResult(name) {
    var byName = currentResult && currentResult.connectorResultsByName;
    return byName ? byName[name] : null;
  }

  function getConnectorStatus(name) {
    var result = getConnectorResult(name);
    if (result) return normalizeStatus(result.status);
    var started = (currentResult.v2 && currentResult.v2.connectors_started) || [];
    return started.indexOf(name) >= 0 ? 'running' : 'pending';
  }

  function renderSignalDossier() {
    var title = document.getElementById('signalDossierTitle');
    var meta = document.getElementById('signalDossierMeta');
    var badges = document.getElementById('signalDossierBadges');
    if (!title || !meta || !badges) return;

    var v2 = currentResult && currentResult.v2 ? currentResult.v2 : {};
    if (!v2.job_id && !v2.target_hash) {
      title.textContent = 'No investigation active';
      meta.textContent = isEngineV2()
        ? 'Run a v2 investigation to populate hash-only target context.'
        : 'Signal layout is active. V2 engine remains off until ?engine=v2 is present.';
      badges.replaceChildren(
        createSignalPill('status idle', 'pending'),
        createSignalPill('risk unavailable', 'uncertain'),
        createSignalPill('confidence pending', 'pending')
      );
      return;
    }

    title.textContent = String(v2.target_type || 'target') + ' investigation';
    meta.textContent = 'Hash-only target context. Raw target is not rendered in Signal UI.';
    badges.replaceChildren(
      createSignalPill('type ' + String(v2.target_type || 'unknown'), 'running'),
      createSignalPill('hash ' + shortValue(v2.target_hash, 'pending'), 'uncertain'),
      createSignalPill('job ' + shortValue(v2.job_id, 'pending'), 'running'),
      createSignalPill('status ' + String(v2.status || v2.overall_status || 'running'), v2.overall_status || v2.status || 'running'),
      createSignalPill('confidence ' + String(Number(v2.overall_confidence || 0)), v2.overall_status || 'uncertain'),
      createSignalPill('risk unavailable', 'uncertain')
    );
  }

  function renderSignalLayers() {
    var grid = document.getElementById('signalLayerGrid');
    var count = document.getElementById('signalLayerCount');
    if (!grid || !count) return;

    var names = getConnectorNames();
    var results = getSignalResults();
    count.textContent = String(results.length) + ' / ' + String(names.length || 0);

    if (!names.length) {
      var empty = document.createElement('div');
      empty.className = 'signal-layer signal-layer--empty';
      var dot = document.createElement('span');
      dot.className = 'signal-layer__dot';
      var body = document.createElement('div');
      body.className = 'signal-layer__body';
      var strong = document.createElement('strong');
      strong.textContent = 'No connector results yet';
      var p = document.createElement('p');
      p.textContent = 'Signal waits for real v2 connector events. No simulated findings.';
      body.append(strong, p);
      empty.append(dot, body);
      grid.replaceChildren(empty);
      return;
    }

    grid.replaceChildren();
    names.forEach(function (name) {
      var result = getConnectorResult(name);
      var status = getConnectorStatus(name);
      var row = document.createElement('div');
      row.className = 'signal-layer signal-layer--' + status;

      var dot = document.createElement('span');
      dot.className = 'signal-layer__dot';
      var body = document.createElement('div');
      body.className = 'signal-layer__body';
      var top = document.createElement('div');
      top.className = 'signal-layer__top';
      var strong = document.createElement('strong');
      strong.className = 'signal-layer__name';
      strong.textContent = connectorLabel(name);
      top.append(strong, createSignalPill(status, status));

      var meta = document.createElement('div');
      meta.className = 'signal-layer__meta';
      if (result) {
        meta.append(
          createSignalPill('confidence ' + String(result.confidence_score), status),
          createSignalPill(result.cache_hit ? 'cache hit' : 'live', 'uncertain'),
          createSignalPill(String(result.elapsed_ms || 0) + 'ms', 'uncertain')
        );
      } else {
        meta.append(createSignalPill(status === 'running' ? 'event received' : 'waiting', status));
      }

      body.append(top, meta);
      row.append(dot, body);
      grid.appendChild(row);
    });
  }

  function renderSignalOutput() {
    var title = document.getElementById('signalOutputTitle');
    var list = document.getElementById('signalOutputList');
    if (!title || !list) return;

    var results = getSignalResults();
    if (!results.length) {
      title.textContent = 'Awaiting live module data';
      list.replaceChildren(
        createSignalPill('pending 0', 'pending'),
        createSignalPill('found 0', 'found'),
        createSignalPill('likely 0', 'likely'),
        createSignalPill('blocked 0', 'blocked')
      );
      return;
    }

    var counts = {
      found: 0,
      likely: 0,
      not_found: 0,
      blocked: 0,
      error: 0,
      uncertain: 0
    };
    results.forEach(function (result) {
      var status = normalizeStatus(result.status);
      if (Object.prototype.hasOwnProperty.call(counts, status)) counts[status] += 1;
    });

    var statusRow = document.createElement('div');
    statusRow.className = 'signal-output-list';
    Object.keys(counts).forEach(function (status) {
      statusRow.appendChild(createSignalPill(status + ' ' + String(counts[status]), status));
    });

    var cards = document.createElement('div');
    cards.className = 'signal-module-list';
    results.forEach(function (result) {
      var status = normalizeStatus(result.status);
      var card = document.createElement('div');
      card.className = 'signal-module-card signal-module-card--' + status;
      var header = document.createElement('div');
      header.className = 'signal-module-title';
      var name = document.createElement('span');
      name.textContent = connectorLabel(result.connector);
      header.append(name, createSignalPill(status, status));
      var meta = document.createElement('div');
      meta.className = 'signal-module-meta';
      meta.append(
        createSignalPill('confidence ' + String(result.confidence_score), status),
        createSignalPill(result.confidence_level || 'none', status),
        createSignalPill(String(result.elapsed_ms || 0) + 'ms', 'uncertain')
      );
      card.append(header, meta);
      cards.appendChild(card);
    });

    title.textContent = 'Live connector output';
    list.replaceChildren(statusRow, cards);
  }

  function renderSignalEvidence() {
    var title = document.getElementById('signalEvidenceTitle');
    var body = document.getElementById('signalEvidenceBody');
    if (!title || !body) return;

    var evidence = [];
    getSignalResults().forEach(function (result) {
      (result.evidence || []).forEach(function (item) {
        evidence.push({
          connector: result.connector,
          item: item
        });
      });
    });

    if (!evidence.length) {
      title.textContent = getSignalResults().length ? 'Evidence unavailable' : 'Nothing queued';
      var strong = document.createElement('strong');
      strong.textContent = 'No client-visible evidence';
      var p = document.createElement('p');
      p.textContent = getSignalResults().length
        ? 'Connector results arrived without evidence fields. Signal UI will not invent evidence.'
        : 'Evidence rows will render only when backend events provide evidence fields. No simulated findings.';
      body.className = 'signal-empty';
      body.replaceChildren(strong, p);
      return;
    }

    title.textContent = 'Evidence received';
    var rows = document.createElement('div');
    rows.className = 'signal-evidence-list';
    evidence.forEach(function (entry) {
      var item = entry.item;
      var row = document.createElement('div');
      row.className = 'signal-evidence-row';
      var top = document.createElement('div');
      top.className = 'signal-evidence-row__top';
      var name = document.createElement('strong');
      name.className = 'signal-evidence-row__title';
      name.textContent = item.title || connectorLabel(entry.connector);
      top.append(name, createSignalPill(item.type || 'evidence', 'found'));
      var p = document.createElement('p');
      p.textContent = item.body || 'Evidence field received without client-visible detail.';
      var meta = document.createElement('div');
      meta.className = 'signal-evidence-row__meta';
      meta.append(createSignalPill(connectorLabel(entry.connector), 'running'));
      if (item.source) meta.append(createSignalPill('source ' + item.source, 'uncertain'));
      row.append(top, p, meta);
      rows.appendChild(row);
    });
    body.className = '';
    body.replaceChildren(rows);
  }

  function renderSignalUi() {
    if (!isSignalUiActive() || !currentResult || !currentResult.v2) return;
    renderSignalDossier();
    renderSignalLayers();
    renderSignalOutput();
    renderSignalEvidence();
  }

  function handleV2Event(event) {
    var payload = event.payload || {};
    rememberEvent(event);

    if (event.event_type === 'job_started') {
      setScanProgress(10, 'Job started');
      addModuleRow('v2 job', 'active');
      renderSignalUi();
      return;
    }

    if (event.event_type === 'connector_started') {
      currentResult.v2.connectors_started = currentResult.v2.connectors_started || [];
      if (payload.connector && currentResult.v2.connectors_started.indexOf(payload.connector) < 0) {
        currentResult.v2.connectors_started.push(payload.connector);
      }
      addModuleRow(connectorLabel(payload.connector), 'active');
      renderSignalUi();
      return;
    }

    if (event.event_type === 'connector_result') {
      var result = connectorResultFromPayload(payload);
      storeConnectorResult(result);
      markModuleDone(connectorLabel(payload.connector));
      if (typeof modulesRan !== 'undefined') modulesRan.add(connectorToModule(payload.connector));
      updateProgress();
      return;
    }

    if (event.event_type === 'summary') {
      currentResult.v2.summary = payload;
      currentResult.v2.overall_status = payload.overall_status;
      currentResult.v2.overall_confidence = Number(payload.confidence_score || 0);
      setScanProgress(98, 'Finalizing...');
      renderSignalUi();
      return;
    }

    if (event.event_type === 'job_done') {
      currentResult.v2.status = 'done';
      currentResult.elapsed = Math.round(Number(payload.elapsed_ms || 0) / 1000);
      currentResult.timestamp = new Date().toISOString();
      setScanProgress(100, 'Complete');
      renderSignalUi();
      return;
    }

    if (event.event_type === 'job_failed') {
      currentResult.v2.status = 'failed';
      renderSignalUi();
      throw new Error('Search job failed');
    }
  }

  function renderV2LiveConnectorResults() {
    if (!global.NX_V2 || typeof createConnectorCard !== 'function') return;
    var scanStatus = document.getElementById('scanStatus');
    if (!scanStatus) return;

    var box = document.getElementById('v2ConnectorLive');
    if (!box) {
      box = document.createElement('div');
      box.id = 'v2ConnectorLive';
      box.className = 'nx-connector-grid';
      scanStatus.appendChild(box);
    }

    box.replaceChildren();
    currentResult.connectorResults.forEach(function (result) {
      box.appendChild(createConnectorCard({ result: result }));
    });
  }

  function renderV2ConnectorSummary() {
    var body = document.getElementById('extrasBody');
    var badge = document.getElementById('extrasBadge');
    var panel = document.getElementById('panelExtras');
    var results = currentResult.connectorResults || [];
    if (!body || !results.length) return;

    if (panel) {
      panel.style.display = '';
      panel.classList.remove('not-run');
      panel.classList.add('open');
    }
    if (badge) badge.textContent = String(results.length);

    if (global.NX_V2 && typeof renderConnectorCardList === 'function') {
      renderConnectorCardList(body, results, 'No connector results available.');
      return;
    }

    body.innerHTML = results.map(function (result) {
      return '<div class="scan-module done"><div class="scan-module-dot"></div><span>'
        + esc(connectorLabel(result.connector)) + ' - ' + esc(result.status)
        + '</span></div>';
    }).join('');
  }

  function waitForEvents(sseUrl) {
    return new Promise(function (resolve, reject) {
      var replay;
      replay = global.NXJobReplay.connect({
        url: sseUrl,
        fromSeq: currentResult.v2.last_seq || 0,
        onEvent: function (event) {
          try {
            handleV2Event(event);
          } catch (err) {
            if (replay) replay.close();
            reject(err);
            return;
          }
          if (event.event_type === 'job_done') resolve(event);
        },
        onError: function (err) {
          if (currentResult.v2.status === 'failed') reject(err);
        },
        onState: function (state) {
          if (state.type === 'reconnecting') {
            addModuleRow('event replay', 'active');
          }
        }
      });
      currentResult.v2.replay = replay;
    });
  }

  function finalizeSearch() {
    setTimeout(function () {
      document.getElementById('scanStatus').classList.remove('visible');
      renderResults();
      renderV2ConnectorSummary();
      // V2 job history remains hash-only server-side; do not persist raw targets.
    }, 600);
  }

  async function startV2Search() {
    var query = document.getElementById('searchInput').value.trim();
    if (!query) return;

    var targetType = detectSupportedTargetType(query);
    if (!targetType) {
      showToast('V2 search supports username, email, and phone targets.');
      return;
    }

    resetScanUi(query, targetType);

    try {
      var created = await createJob(query, targetType);
      currentResult.v2.job_id = created.job_id;
      currentResult.v2.sse_url = created.sse_url;
      renderSignalUi();
      addModuleRow('job queued', 'active');
      setScanProgress(5, 'Loading job snapshot...');

      var snapshot = await loadSnapshot(created.job_id);
      applySnapshot(snapshot);
      setScanProgress(8, 'Connecting event stream...');
      await waitForEvents(created.sse_url);
      finalizeSearch();
    } catch (err) {
      showToast('Search failed: ' + safeMessage(err));
      document.getElementById('scanStatus').classList.remove('visible');
    } finally {
      document.getElementById('searchBtn').disabled = false;
    }
  }

  global.NXV2Search = {
    isEngineV2: isEngineV2,
    start: startV2Search,
    detectSupportedTargetType: detectSupportedTargetType
  };

  if (isEngineV2()) {
    global.__nxLegacyStartSearch = legacyStartSearch;
    global.startSearch = startV2Search;
  }
})(window);
