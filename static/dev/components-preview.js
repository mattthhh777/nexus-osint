(function () {
  'use strict';

  var statuses = ['pending', 'running', 'found', 'likely', 'uncertain', 'not_found', 'blocked', 'error'];
  var scores = [0, 29, 30, 59, 60, 84, 85, 100];

  function sampleResult(status, index) {
    var score = scores[index % scores.length];
    return {
      connector: 'preview:' + status,
      target_type: 'username',
      status: status,
      confidence_score: score,
      confidence_level: window.deriveConfidenceLevel(score),
      evidence: [
        { signal: 'status_' + status, weight: Math.max(0, score - 20), detail: 'Sample signal for ' + status + '.' },
        { signal: 'contract_state', weight: 10, detail: '8-state status preserved.' }
      ],
      warnings: status === 'blocked' ? ['blocked_by_upstream'] : [],
      raw_url: null,
      data: {},
      fetched_at: new Date().toISOString(),
      cache_hit: false,
      elapsed_ms: 120 + index * 24
    };
  }

  var pills = document.getElementById('statusPills');
  statuses.forEach(function (status) {
    pills.appendChild(window.createStatusPill({ status: status }));
  });

  var cards = document.getElementById('connectorCards');
  cards.appendChild(window.createConnectorCard({ empty: true }));
  cards.appendChild(window.createConnectorCard({
    connector: 'preview:loading',
    status: 'running',
    confidence_score: 0,
    confidence_level: 'none',
    evidence: [],
    elapsed_ms: 0,
    loading: true
  }));
  statuses.forEach(function (status, index) {
    cards.appendChild(window.createConnectorCard({ result: sampleResult(status, index) }));
  });

  var meters = document.getElementById('confidenceMeters');
  scores.forEach(function (score) {
    var wrap = document.createElement('div');
    wrap.className = 'nx-preview__meter-item';
    wrap.appendChild(window.createConfidenceMeter({ score: score }));
    meters.appendChild(wrap);
  });

  var drawers = document.getElementById('evidenceDrawers');
  drawers.appendChild(window.createEvidenceDrawer({
    inline: true,
    title: 'Empty evidence',
    evidence: []
  }));
  drawers.appendChild(window.createEvidenceDrawer({
    inline: true,
    title: 'Populated evidence',
    result: sampleResult('found', 6)
  }));
})();
