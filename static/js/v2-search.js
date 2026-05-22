// Opt-in frontend bridge for /api/v2/search jobs.

(function (global) {
  'use strict';

  var SUPPORTED_TARGET_TYPES = Object.freeze({
    email: true,
    phone: true,
    username: true
  });

  var legacyStartSearch = global.startSearch;
  var selectedSignalEvidenceKey = null;

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

  function neutralizeSignalLegacyResults() {
    if (!isSignalUiActive()) return;
    var results = document.getElementById('results');
    var target = document.getElementById('resTarget');
    if (results) results.classList.remove('visible');
    if (target) target.replaceChildren();
  }

  function clearSignalSearchInput() {
    if (!isSignalUiActive()) return;
    var input = document.getElementById('searchInput');
    if (input) input.value = '';
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

  var CONNECTOR_LABELS = Object.freeze({
    'oathnet:breach': 'Breach intel',
    'oathnet:stealer': 'Stealer logs',
    'oathnet:victims': 'Victim drops',
    carrier_lookup: 'Carrier lookup',
    'sherlock:github': 'GitHub presence',
    'sherlock:reddit': 'Reddit presence',
    'sherlock:steam': 'Steam presence'
  });

  function connectorLabel(connector) {
    var name = String(connector || 'connector');
    if (CONNECTOR_LABELS[name]) return CONNECTOR_LABELS[name];

    var parts = name.split(':');
    var leaf = parts[parts.length - 1].replace(/_/g, ' ');
    return leaf.replace(/\b\w/g, function (letter) { return letter.toUpperCase(); });
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

  function isSensitiveEvidenceKey(key) {
    return /^(raw_url|url|target|target_value|query|headers?|body|cookies?|tokens?|secrets?|authorization|password|api_?key)$/i.test(String(key || ''));
  }

  function safeEvidenceValue(item, keys) {
    if (!item || typeof item !== 'object') return '';
    for (var i = 0; i < keys.length; i += 1) {
      var key = keys[i];
      if (isSensitiveEvidenceKey(key)) continue;
      var value = item[key];
      if (value == null || typeof value === 'object') continue;
      return redactRawTarget(value);
    }
    return '';
  }

  function safeEvidenceBody(item) {
    if (!item || typeof item !== 'object') return redactRawTarget(item);
    var preferred = safeEvidenceValue(item, ['detail', 'summary', 'snippet', 'description', 'value', 'message']);
    if (preferred) return redactRawTarget(preferred);

    var safe = {};
    Object.keys(item).forEach(function (key) {
      if (isSensitiveEvidenceKey(key)) return;
      var value = item[key];
      if (value == null || typeof value === 'object') return;
      safe[key] = redactRawTarget(value);
    });
    return Object.keys(safe).length ? JSON.stringify(safe) : 'detail unavailable';
  }

  function sanitizeEvidenceList(items) {
    if (!Array.isArray(items)) return [];
    return items.map(function (item) {
      if (!item || typeof item !== 'object') {
        return {
          title: 'Evidência',
          source: '',
          type: '',
          signal: '',
          weight: '',
          detail: redactRawTarget(item)
        };
      }
      return {
        title: safeEvidenceValue(item, ['title', 'label', 'type']) || 'Evidência',
        source: safeEvidenceValue(item, ['source', 'connector']),
        type: safeEvidenceValue(item, ['type', 'signal']),
        signal: safeEvidenceValue(item, ['signal', 'type']),
        weight: safeEvidenceValue(item, ['weight', 'confidence', 'score']),
        detail: safeEvidenceBody(item)
      };
    }).filter(function (item) {
      return item.detail || item.title || item.source || item.type || item.signal || item.weight;
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

  function signalStatusLabel(status) {
    return String(status || 'unknown')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, function (letter) { return letter.toUpperCase(); });
  }

  function shortValue(value, fallback) {
    var text = String(value || '');
    if (!text) return fallback;
    if (text.length <= 12) return text;
    return text.slice(0, 6) + '...' + text.slice(-6);
  }

  function formatSignalTime(value) {
    var date = new Date(value || '');
    if (Number.isNaN(date.getTime())) return 'horário indisponível';
    return date.toISOString().slice(0, 16).replace('T', ' ');
  }

  function createSignalPill(label, status) {
    var pill = document.createElement('span');
    var normalized = normalizeStatus(status || 'idle');
    pill.className = 'signal-pill signal-pill--' + statusClass(normalized);
    pill.textContent = label;
    return pill;
  }

  function createSignalDatum(label, value) {
    var datum = document.createElement('span');
    datum.className = 'signal-dossier__datum';
    var name = document.createElement('span');
    name.className = 'signal-dossier__datum-label';
    name.textContent = label;
    var content = document.createElement('strong');
    content.className = 'signal-dossier__datum-value';
    content.textContent = String(value);
    datum.append(name, content);
    return datum;
  }

  function createSignalSummaryStat(status, count) {
    var item = document.createElement('span');
    item.className = 'signal-summary-stat signal-summary-stat--' + status;
    item.textContent = signalStatusLabel(status) + ' ' + String(count);
    return item;
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
      title.textContent = 'Nenhuma investigação em curso';
      meta.textContent = isEngineV2()
        ? 'Inicie uma investigação v2 para carregar contexto hash-only do alvo.'
        : 'Signal ativo. Motor v2 segue desligado até ?engine=v2 estar presente.';
      badges.replaceChildren();
      return;
    }

    var status = String(v2.status || v2.overall_status || 'running');
    var datums = [
      createSignalDatum('target_hash', shortValue(v2.target_hash, 'pending')),
      createSignalDatum('target_type', String(v2.target_type || 'unknown')),
      createSignalDatum('job_id', shortValue(v2.job_id, 'pending')),
      createSignalDatum('status', signalStatusLabel(status))
    ];
    if (v2.overall_confidence != null) {
      datums.push(createSignalDatum('confidence', Number(v2.overall_confidence || 0)));
    }

    title.textContent = 'Investigação ' + String(v2.target_type || 'target');
    meta.textContent = 'Contexto hash-only. Alvo bruto não aparece no Signal.';
    badges.replaceChildren.apply(badges, datums);
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
      strong.textContent = 'Nenhum resultado de conector';
      var p = document.createElement('p');
      p.textContent = 'Signal aguarda eventos reais do motor v2. Sem achados simulados.';
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
        meta.append(createSignalPill('confidence ' + String(result.confidence_score), status));
        var runtime = document.createElement('span');
        runtime.className = 'signal-layer__runtime';
        runtime.textContent = (result.cache_hit ? 'cache hit' : 'live') + ' / ' + String(result.elapsed_ms || 0) + 'ms';
        meta.appendChild(runtime);
      } else {
        var waiting = document.createElement('span');
        waiting.className = 'signal-layer__runtime';
        waiting.textContent = status === 'running' ? 'evento recebido' : 'aguardando evento';
        meta.appendChild(waiting);
      }

      body.append(top, meta);
      row.append(dot, body);
      grid.appendChild(row);
    });
  }

  function renderSignalOutput() {
    var list = document.getElementById('signalOutputList');
    if (!list) return;

    var names = getConnectorNames();
    if (!names.length) {
      list.replaceChildren(makeSignalEmptyMessage('Resumo aparece quando conectores reais responderem.'));
      return;
    }

    var counts = {
      pending: 0,
      running: 0,
      found: 0,
      likely: 0,
      not_found: 0,
      blocked: 0,
      error: 0,
      uncertain: 0
    };
    names.forEach(function (name) {
      var status = getConnectorStatus(name);
      if (Object.prototype.hasOwnProperty.call(counts, status)) counts[status] += 1;
    });

    list.replaceChildren();
    Object.keys(counts).forEach(function (status) {
      if (counts[status]) {
        list.appendChild(createSignalSummaryStat(status, counts[status]));
      }
    });

  }

  function makeSignalEvidenceKey(connector, index) {
    return String(connector || 'connector') + '::' + String(index);
  }

  function makeSignalEmptyMessage(text) {
    var note = document.createElement('p');
    note.className = 'signal-evidence-empty-note';
    note.textContent = text;
    return note;
  }

  function getSignalEvidenceGroups() {
    return getSignalResults().map(function (result) {
      return {
        connector: result.connector,
        status: normalizeStatus(result.status),
        confidence_score: result.confidence_score,
        evidence: result.evidence || []
      };
    });
  }

  function flattenSignalEvidence(groups) {
    var items = [];
    groups.forEach(function (group) {
      group.evidence.forEach(function (item, index) {
        items.push({
          key: makeSignalEvidenceKey(group.connector, index),
          connector: group.connector,
          status: group.status,
          confidence_score: group.confidence_score,
          item: item
        });
      });
    });
    return items;
  }

  function renderSignalEvidenceDetail(detailHost, selected) {
    var title = document.createElement('h4');
    title.className = 'signal-evidence-detail__title';
    title.textContent = selected ? 'Detalhe da evidência' : 'Detalhe indisponível';

    if (!selected) {
      var empty = document.createElement('p');
      empty.className = 'signal-evidence-empty-note';
      empty.textContent = 'Selecione uma evidência para inspecionar detalhe sanitizado.';
      detailHost.replaceChildren(title, empty);
      return;
    }

    var item = selected.item;
    var meta = document.createElement('div');
    meta.className = 'signal-evidence-row__meta';
    meta.append(
      createSignalPill(connectorLabel(selected.connector), selected.status),
      createSignalPill('status ' + selected.status, selected.status),
      createSignalPill('confidence ' + String(selected.confidence_score || 0), selected.status)
    );
    if (item.signal) meta.append(createSignalPill('signal ' + item.signal, selected.status));
    if (item.weight) meta.append(createSignalPill('weight ' + item.weight, 'uncertain'));

    var detail = document.createElement('p');
    detail.className = 'signal-evidence-detail__body';
    detail.textContent = item.detail || 'detalhe indisponível';

    detailHost.replaceChildren(title, meta, detail);
  }

  function renderSignalEvidence() {
    var title = document.getElementById('signalEvidenceTitle');
    var body = document.getElementById('signalEvidenceBody');
    if (!title || !body) return;

    var groups = getSignalEvidenceGroups();
    var evidence = flattenSignalEvidence(groups);

    if (!evidence.length) {
      title.textContent = getSignalResults().length ? 'Evidência indisponível' : 'Nada em fila';
      var strong = document.createElement('strong');
      strong.textContent = 'Sem evidência liberada';
      var p = document.createElement('p');
      p.textContent = getSignalResults().length
        ? 'Evidências aparecem quando conectores liberam payloads seguros. Signal não inventa evidência.'
        : 'Evidências aguardam resultados reais dos conectores. Sem achados simulados.';
      body.className = 'signal-empty';
      var emptyGroups = document.createElement('div');
      emptyGroups.className = 'signal-evidence-list';
      groups.forEach(function (group) {
        var groupEl = document.createElement('section');
        groupEl.className = 'signal-evidence-group';
        var heading = document.createElement('div');
        heading.className = 'signal-evidence-group__heading';
        var name = document.createElement('strong');
        name.textContent = connectorLabel(group.connector);
        heading.append(name, createSignalPill(group.status, group.status));
        groupEl.append(heading, makeSignalEmptyMessage('Sem evidência liberada'));
        emptyGroups.appendChild(groupEl);
      });
      body.replaceChildren(strong, p, emptyGroups);
      return;
    }

    title.textContent = 'Evidência recebida';
    if (!evidence.some(function (entry) { return entry.key === selectedSignalEvidenceKey; })) {
      selectedSignalEvidenceKey = evidence[0].key;
    }

    var wrapper = document.createElement('div');
    wrapper.className = 'signal-evidence-workspace';
    var groupsHost = document.createElement('div');
    groupsHost.className = 'signal-evidence-list';
    var detailHost = document.createElement('section');
    detailHost.className = 'signal-evidence-detail';
    detailHost.setAttribute('aria-live', 'polite');

    groups.forEach(function (group) {
      var groupEl = document.createElement('section');
      groupEl.className = 'signal-evidence-group';
      var heading = document.createElement('div');
      heading.className = 'signal-evidence-group__heading';
      var groupName = document.createElement('strong');
      groupName.textContent = connectorLabel(group.connector);
      heading.append(groupName, createSignalPill(group.status, group.status));
      groupEl.appendChild(heading);

      if (!group.evidence.length) {
        groupEl.appendChild(makeSignalEmptyMessage('Sem evidência liberada'));
      }

      group.evidence.forEach(function (item, index) {
        var key = makeSignalEvidenceKey(group.connector, index);
        var row = document.createElement('button');
        row.type = 'button';
        row.className = 'signal-evidence-row';
        if (key === selectedSignalEvidenceKey) row.className += ' signal-evidence-row--selected';
        row.setAttribute('aria-pressed', String(key === selectedSignalEvidenceKey));
        row.addEventListener('click', function () {
          selectedSignalEvidenceKey = key;
          renderSignalEvidence();
        });

        var top = document.createElement('div');
        top.className = 'signal-evidence-row__top';
        var name = document.createElement('strong');
        name.className = 'signal-evidence-row__title';
        name.textContent = item.title || connectorLabel(group.connector);
        top.append(name, createSignalPill(item.signal || item.type || 'evidence', group.status));

        var meta = document.createElement('div');
        meta.className = 'signal-evidence-row__meta';
        meta.append(createSignalPill('status ' + group.status, group.status));
        if (item.weight) meta.append(createSignalPill('weight ' + item.weight, 'uncertain'));
        if (item.source) meta.append(createSignalPill('source ' + item.source, 'uncertain'));

        row.append(top, meta);
        groupEl.appendChild(row);
      });
      groupsHost.appendChild(groupEl);
    });

    var selected = evidence.filter(function (entry) {
      return entry.key === selectedSignalEvidenceKey;
    })[0] || evidence[0];
    renderSignalEvidenceDetail(detailHost, selected);

    wrapper.append(groupsHost, detailHost);
    body.className = '';
    body.replaceChildren(wrapper);
  }

  function readSignalStorageList(key) {
    try {
      var raw = global.localStorage ? global.localStorage.getItem(key) : null;
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  }

  function safeStoredStatus(item) {
    var summary = item && item.summary_snapshot ? item.summary_snapshot : {};
    return normalizeStatus(summary.overall_status || item.status || item.overall_status || 'uncertain');
  }

  function safeStoredCase(item) {
    if (!item || typeof item !== 'object') return null;
    var hash = item.target_hash || item.targetHash || '';
    if (!hash || hash === 'legacy' || hash === 'unavailable') return null;
    var summary = item.summary_snapshot || {};
    return {
      id: item.id || '',
      target_hash: String(hash),
      target_type: String(item.target_type || item.targetType || 'target'),
      status: safeStoredStatus(item),
      confidence: Number(summary.overall_confidence || item.overall_confidence || 0),
      timestamp: item.updated_at || item.created_at || item.timestamp || '',
      found_count: Number(summary.found_count || 0),
      likely_count: Number(summary.likely_count || 0),
      blocked_count: Number(summary.blocked_count || 0),
      error_count: Number(summary.error_count || 0)
    };
  }

  function safeStoredHistory(item) {
    if (!item || typeof item !== 'object') return null;
    var hash = item.target_hash || item.targetHash || '';
    if (!hash) return null;
    return {
      id: item.job_id || item.id || '',
      target_hash: String(hash),
      target_type: String(item.target_type || item.targetType || 'target'),
      status: normalizeStatus(item.status || item.overall_status || 'uncertain'),
      confidence: Number(item.overall_confidence || item.confidence_score || 0),
      timestamp: item.timestamp || item.updated_at || item.created_at || '',
      found_count: 0,
      likely_count: 0,
      blocked_count: 0,
      error_count: 0
    };
  }

  function getSafeSignalCases() {
    var safeCases = readSignalStorageList('nx_cases').map(safeStoredCase).filter(Boolean);
    var safeHistory = readSignalStorageList('nx_history').map(safeStoredHistory).filter(Boolean);
    return safeCases.concat(safeHistory).sort(function (a, b) {
      return (Date.parse(b.timestamp || '') || 0) - (Date.parse(a.timestamp || '') || 0);
    }).slice(0, 4);
  }

  function renderSignalCases() {
    var title = document.getElementById('signalCasesTitle');
    var body = document.getElementById('signalCasesBody');
    if (!title || !body) return;

    var safeCases = getSafeSignalCases();
    if (!safeCases.length) {
      title.textContent = 'Nenhum caso local seguro';
      var strong = document.createElement('strong');
      strong.textContent = 'Sem metadados seguros de caso';
      var p = document.createElement('p');
      p.textContent = 'Signal mostra apenas casos locais com target_hash. Entradas legadas com alvo bruto ficam ocultas.';
      var foot = document.createElement('p');
      foot.className = 'signal-case-footnote';
      foot.textContent = 'Cases ficam só neste navegador.';
      body.className = 'signal-empty';
      body.replaceChildren(strong, p, foot);
      return;
    }

    title.textContent = 'Casos recentes';
    var list = document.createElement('div');
    list.className = 'signal-case-list';
    safeCases.forEach(function (item) {
      var card = document.createElement('article');
      card.className = 'signal-case-card signal-case-card--' + statusClass(item.status);
      var top = document.createElement('div');
      top.className = 'signal-case-card__top';
      var heading = document.createElement('strong');
      heading.textContent = 'Caso ' + String(item.target_type || 'target');
      top.appendChild(heading);

      var hash = document.createElement('div');
      hash.className = 'signal-case-card__hash';
      hash.textContent = 'target_hash ' + shortValue(item.target_hash, 'unavailable');

      var meta = document.createElement('div');
      meta.className = 'signal-case-card__meta';
      meta.append(
        createSignalPill('confidence ' + String(item.confidence || 0), item.status),
        createSignalPill('found ' + String(item.found_count || 0), 'found')
      );

      var foot = document.createElement('p');
      foot.className = 'signal-case-footnote';
      var footParts = ['status ' + signalStatusLabel(item.status)];
      if (item.likely_count) footParts.push('likely ' + String(item.likely_count));
      if (item.blocked_count) footParts.push('blocked ' + String(item.blocked_count));
      if (item.error_count) footParts.push('error ' + String(item.error_count));
      footParts.push('local ' + formatSignalTime(item.timestamp));
      foot.textContent = footParts.join(' / ');

      card.append(top, hash, meta, foot);
      list.appendChild(card);
    });
    body.className = '';
    body.replaceChildren(list);
  }

  function renderSignalUi() {
    if (!isSignalUiActive()) return;
    neutralizeSignalLegacyResults();
    renderSignalCases();
    if (!currentResult || !currentResult.v2) return;
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
      if (isSignalUiActive()) {
        neutralizeSignalLegacyResults();
        renderSignalUi();
        return;
      }
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
      clearSignalSearchInput();
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
  renderSignalUi();
})(window);
