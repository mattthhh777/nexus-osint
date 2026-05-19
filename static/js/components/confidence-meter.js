// ConfidenceMeter renders a 0-100 score with none/low/medium/high zones.

(function (global) {
  'use strict';

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

  function labelForLevel(level) {
    if (level === 'high') return 'High';
    if (level === 'medium') return 'Medium';
    if (level === 'low') return 'Low';
    return 'None';
  }

  function createConfidenceMeter(opts) {
    opts = opts || {};
    var score = clampScore(opts.score);
    var level = opts.level || deriveConfidenceLevel(score);
    var label = opts.label || labelForLevel(level);

    var el = document.createElement('div');
    el.className = 'nx-confidence nx-confidence--' + level;
    el.setAttribute('role', 'meter');
    el.setAttribute('aria-valuemin', '0');
    el.setAttribute('aria-valuemax', '100');
    el.setAttribute('aria-valuenow', String(score));
    el.setAttribute('aria-label', 'Confidence ' + label + ' ' + score + ' percent');

    var header = document.createElement('div');
    header.className = 'nx-confidence__header';

    var text = document.createElement('span');
    text.className = 'nx-confidence__label';
    text.textContent = label;

    var value = document.createElement('span');
    value.className = 'nx-confidence__value';
    value.textContent = score + '%';

    var track = document.createElement('div');
    track.className = 'nx-confidence__track';

    var fill = document.createElement('div');
    fill.className = 'nx-confidence__fill';
    fill.style.width = score + '%';

    header.appendChild(text);
    header.appendChild(value);
    track.appendChild(fill);
    el.appendChild(header);
    el.appendChild(track);

    return el;
  }

  global.deriveConfidenceLevel = deriveConfidenceLevel;
  global.createConfidenceMeter = createConfidenceMeter;
})(window);
