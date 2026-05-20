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
        events_seen: []
      }
    };
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
    currentResult.v2.overall_status = snapshot.overall_status || null;
    currentResult.v2.overall_confidence = snapshot.overall_confidence || 0;
    currentResult.searchId = snapshot.job_id;
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

  function connectorResultFromPayload(payload) {
    return {
      connector: payload.connector,
      target_type: currentResult.v2.target_type,
      status: payload.status,
      confidence_score: Number(payload.confidence_score || 0),
      confidence_level: payload.confidence_level || 'none',
      evidence: [],
      warnings: [],
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

  function handleV2Event(event) {
    var payload = event.payload || {};
    rememberEvent(event);

    if (event.event_type === 'job_started') {
      setScanProgress(10, 'Job started');
      addModuleRow('v2 job', 'active');
      return;
    }

    if (event.event_type === 'connector_started') {
      addModuleRow(connectorLabel(payload.connector), 'active');
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
      return;
    }

    if (event.event_type === 'job_done') {
      currentResult.v2.status = 'done';
      currentResult.elapsed = Math.round(Number(payload.elapsed_ms || 0) / 1000);
      currentResult.timestamp = new Date().toISOString();
      setScanProgress(100, 'Complete');
      return;
    }

    if (event.event_type === 'job_failed') {
      currentResult.v2.status = 'failed';
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
