// ConnectorCard renders a ConnectorResult-shaped object.

(function (global) {
  'use strict';

  function makeEl(tag, className, text) {
    var el = document.createElement(tag);
    el.className = className;
    if (text !== undefined && text !== null) {
      el.textContent = String(text);
    }
    return el;
  }

  function normalizeResult(opts) {
    opts = opts || {};
    if (opts.result) return opts.result;
    return opts;
  }

  function appendMeta(parent, label, value) {
    var item = makeEl('div', 'nx-connector-card__meta-item');
    item.appendChild(makeEl('span', 'nx-connector-card__meta-label', label));
    item.appendChild(makeEl('span', 'nx-connector-card__meta-value', value));
    parent.appendChild(item);
  }

  function createConnectorCard(opts) {
    opts = opts || {};
    var result = normalizeResult(opts);
    var hasData = Boolean(result.connector || result.status || result.confidence_score);
    var status = opts.loading ? 'running' : (result.status || (hasData ? 'uncertain' : 'pending'));
    var isEmpty = opts.empty || !hasData;
    var connector = result.connector || opts.connector || 'No connector selected';
    var evidence = result.evidence || [];

    var card = makeEl('article', 'nx-connector-card');
    card.className += ' nx-connector-card--' + (isEmpty ? 'empty' : status);
    if (status === 'running') {
      card.className += ' nx-connector-card--loading';
    }
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', connector + ' evidence');
    card.setAttribute('data-status', status);

    var header = makeEl('div', 'nx-connector-card__header');
    var titleWrap = makeEl('div', 'nx-connector-card__title-wrap');
    titleWrap.appendChild(makeEl('h3', 'nx-connector-card__title', connector));
    titleWrap.appendChild(makeEl('p', 'nx-connector-card__subtitle', isEmpty ? 'No data yet' : (result.target_type || 'connector')));

    var pill = global.createStatusPill
      ? global.createStatusPill({ status: status })
      : makeEl('span', 'nx-status-pill', status);

    header.appendChild(titleWrap);
    header.appendChild(pill);
    card.appendChild(header);

    if (isEmpty) {
      card.appendChild(makeEl('p', 'nx-connector-card__empty', 'No connector result available yet.'));
    } else {
      var score = Number(result.confidence_score || 0);
      var meter = global.createConfidenceMeter
        ? global.createConfidenceMeter({ score: score, level: result.confidence_level })
        : makeEl('div', 'nx-confidence', score + '%');
      card.appendChild(meter);

      var meta = makeEl('div', 'nx-connector-card__meta');
      appendMeta(meta, 'Evidence', evidence.length);
      appendMeta(meta, 'Cache', result.cache_hit ? 'hit' : 'miss');
      appendMeta(meta, 'Elapsed', Number(result.elapsed_ms || 0) + 'ms');
      card.appendChild(meta);

      if (result.raw_url) {
        card.appendChild(makeEl('span', 'nx-connector-card__url', 'Source URL available'));
      }
    }

    function openDrawer(event) {
      if (event) {
        event.preventDefault();
      }
      if (global.openEvidenceDrawer) {
        global.openEvidenceDrawer({
          title: connector,
          result: result,
          returnFocusTo: card
        });
      }
    }

    card.addEventListener('click', openDrawer);
    card.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        openDrawer(event);
      }
    });

    return card;
  }

  global.createConnectorCard = createConnectorCard;
})(window);
