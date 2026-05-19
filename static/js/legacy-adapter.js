// Translates legacy /api/search SSE payloads into ConnectorResult-shaped data.
// Pure client-side shim. No backend behavior change.

(function (global) {
  'use strict';

  var SHERLOCK_STATUS_MAP = {
    confirmed: 'found',
    found: 'found',
    likely: 'likely',
    unconfirmed: 'uncertain',
    uncertain: 'uncertain',
    likely_false_positive: 'not_found',
    not_found: 'not_found',
    auth_blocked: 'blocked',
    cf_challenge: 'blocked',
    login_required: 'blocked',
    redirect_to_login: 'blocked',
    error: 'error',
    timeout: 'error',
    http_error: 'error',
    connection_error: 'error',
    proxy_unavailable: 'error',
    invalid: 'error'
  };

  function clampScore(score) {
    var n = Number(score);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, Math.round(n)));
  }

  function deriveConfidenceLevel(score) {
    if (score >= 85) return 'high';
    if (score >= 60) return 'medium';
    if (score >= 30) return 'low';
    return 'none';
  }

  function evidenceList(items) {
    if (!Array.isArray(items)) return [];
    return items.map(function (item) {
      return {
        signal: String(item.signal || 'signal'),
        weight: Number.isFinite(Number(item.weight)) ? Number(item.weight) : 0,
        detail: String(item.detail || '')
      };
    });
  }

  function sherlockStatus(legacy) {
    var validation = legacy.validation_status || legacy.state || legacy.status;
    var fetchStatus = legacy.fetch_status || legacy.error || '';

    if (validation === 'invalid') {
      if (SHERLOCK_STATUS_MAP[fetchStatus] === 'blocked') return 'blocked';
      return 'error';
    }
    if (SHERLOCK_STATUS_MAP[fetchStatus] === 'blocked') return 'blocked';
    return SHERLOCK_STATUS_MAP[validation] || SHERLOCK_STATUS_MAP[fetchStatus] || 'uncertain';
  }

  function adaptSherlockPlatform(legacy) {
    var status = sherlockStatus(legacy);
    var score = clampScore(
      legacy.confidence_score != null ? legacy.confidence_score : legacy.confidence
    );
    return {
      connector: 'sherlock:' + (legacy.platform || legacy.site || 'unknown'),
      target_type: 'username',
      status: status,
      confidence_score: score,
      confidence_level: deriveConfidenceLevel(score),
      evidence: evidenceList(legacy.evidence),
      warnings: Array.isArray(legacy.warnings) ? legacy.warnings.slice() : [],
      raw_url: legacy.url_original || legacy.url_final || legacy.url || null,
      data: {
        platform: legacy.platform || legacy.site || 'unknown',
        category: legacy.category || '',
        source: legacy.source || '',
        fetch_status: legacy.fetch_status || '',
        http_status: legacy.http_status || null,
        reliability: legacy.reliability || ''
      },
      fetched_at: legacy.checked_at || new Date().toISOString(),
      cache_hit: Boolean(legacy.cache_hit),
      elapsed_ms: Number(legacy.elapsed_ms) || 0
    };
  }

  function adaptSherlockEvent(eventData) {
    if (Array.isArray(eventData.platforms)) {
      return eventData.platforms.map(function (platform) {
        return adaptSherlockPlatform({
          source: eventData.source,
          cache_hit: eventData.cache_hit,
          platform: platform.platform,
          site: platform.site,
          category: platform.category,
          validation_status: platform.validation_status,
          confidence_score: platform.confidence_score,
          confidence_level: platform.confidence_level,
          evidence: platform.evidence,
          warnings: platform.warnings,
          url_original: platform.url_original,
          url_final: platform.url_final,
          fetch_status: platform.fetch_status,
          http_status: platform.http_status,
          error: platform.error,
          reliability: platform.reliability,
          checked_at: platform.checked_at
        });
      });
    }

    var found = Array.isArray(eventData.found) ? eventData.found : [];
    var likely = Array.isArray(eventData.likely) ? eventData.likely : [];
    return found.concat(likely).map(function (platform) {
      return adaptSherlockPlatform({
        source: eventData.source,
        cache_hit: eventData.cache_hit,
        platform: platform.platform,
        site: platform.site,
        category: platform.category,
        state: platform.state || 'confirmed',
        confidence: platform.confidence,
        url: platform.url,
        reliability: platform.reliability
      });
    });
  }

  function countEvidence(signal, count) {
    return [{
      signal: signal,
      weight: count > 0 ? 80 : 0,
      detail: count + ' records'
    }];
  }

  function adaptCountConnector(name, targetType, count, cacheHit, elapsedMs) {
    var safeCount = Math.max(0, Number(count) || 0);
    var score = safeCount > 0 ? Math.min(100, 50 + safeCount * 5) : 0;
    return {
      connector: name,
      target_type: targetType || 'email',
      status: safeCount > 0 ? 'found' : 'not_found',
      confidence_score: score,
      confidence_level: deriveConfidenceLevel(score),
      evidence: countEvidence(name.replace(/^[^:]+:/, '') + '_records', safeCount),
      warnings: [],
      raw_url: null,
      data: { record_count: safeCount },
      fetched_at: new Date().toISOString(),
      cache_hit: Boolean(cacheHit),
      elapsed_ms: Number(elapsedMs) || 0
    };
  }

  function adaptOathnetEvent(eventData) {
    var targetType = eventData.target_type || 'email';
    var results = [
      adaptCountConnector('oathnet:breach', targetType, eventData.breach_count, eventData.cache_hit, eventData.elapsed_ms),
      adaptCountConnector('oathnet:stealer', targetType, eventData.stealer_count, eventData.cache_hit, eventData.elapsed_ms)
    ];
    if (eventData.holehe_count != null) {
      results.push(adaptCountConnector('oathnet:holehe', 'email', eventData.holehe_count, eventData.cache_hit, eventData.elapsed_ms));
    }
    return results;
  }

  function adaptIpInfo(eventData) {
    var ok = Boolean(eventData.ok && eventData.data);
    var score = ok ? 70 : 0;
    return {
      connector: 'oathnet:ip',
      target_type: eventData.target_type || 'username',
      status: ok ? 'found' : (eventData.error ? 'error' : 'not_found'),
      confidence_score: score,
      confidence_level: deriveConfidenceLevel(score),
      evidence: [{
        signal: ok ? 'ip_info_available' : 'ip_info_missing',
        weight: ok ? 60 : 0,
        detail: ok ? 'IP metadata returned' : 'No IP metadata returned'
      }],
      warnings: eventData.error ? [String(eventData.error)] : [],
      raw_url: null,
      data: {
        fields_returned: eventData.data && typeof eventData.data === 'object'
          ? Object.keys(eventData.data).length
          : 0
      },
      fetched_at: new Date().toISOString(),
      cache_hit: Boolean(eventData.cache_hit),
      elapsed_ms: Number(eventData.elapsed_ms) || 0
    };
  }

  function adaptSpiderFoot(eventData) {
    if (eventData.available === false) {
      return {
        connector: 'spiderfoot:scan',
        target_type: 'username',
        status: 'error',
        confidence_score: 0,
        confidence_level: 'none',
        evidence: [],
        warnings: eventData.error ? [String(eventData.error)] : [],
        raw_url: null,
        data: {},
        fetched_at: new Date().toISOString(),
        cache_hit: false,
        elapsed_ms: 0
      };
    }

    var results = Array.isArray(eventData.results) ? eventData.results : [];
    var count = Number(eventData.total != null ? eventData.total : results.length) || 0;
    return {
      connector: 'spiderfoot:scan',
      target_type: 'username',
      status: count > 0 ? 'likely' : 'not_found',
      confidence_score: count > 0 ? 60 : 0,
      confidence_level: count > 0 ? 'medium' : 'none',
      evidence: [{
        signal: 'spiderfoot_events',
        weight: count > 0 ? 50 : 0,
        detail: count + ' events'
      }],
      warnings: [],
      raw_url: null,
      data: { event_count: count },
      fetched_at: new Date().toISOString(),
      cache_hit: false,
      elapsed_ms: Number(eventData.elapsed_ms) || 0
    };
  }

  function adaptModuleError(eventData) {
    return {
      connector: String(eventData.module || 'module') + ':error',
      target_type: eventData.target_type || 'username',
      status: 'error',
      confidence_score: 0,
      confidence_level: 'none',
      evidence: [],
      warnings: [String(eventData.error || 'module error')],
      raw_url: null,
      data: {},
      fetched_at: new Date().toISOString(),
      cache_hit: false,
      elapsed_ms: 0
    };
  }

  function adaptLegacyEvent(eventData) {
    if (!eventData || !eventData.type) return null;

    switch (eventData.type) {
      case 'sherlock':
      case 'sherlock_v2':
        return adaptSherlockEvent(eventData);
      case 'oathnet':
        return adaptOathnetEvent(eventData);
      case 'ip_info':
        return adaptIpInfo(eventData);
      case 'spiderfoot':
        return adaptSpiderFoot(eventData);
      case 'module_error':
        return adaptModuleError(eventData);
      default:
        return null;
    }
  }

  global.adaptLegacyEvent = adaptLegacyEvent;
  global.adaptLegacySherlockPlatform = adaptSherlockPlatform;
})(window);
