// Job replay client for /api/v2/search SSE streams.

(function (global) {
  'use strict';

  var TERMINAL_EVENTS = Object.freeze({
    job_done: true,
    job_failed: true
  });

  var EVENT_TYPES = Object.freeze([
    'job_started',
    'job_running',
    'connector_started',
    'connector_result',
    'connector_done',
    'connector_blocked',
    'connector_error',
    'summary',
    'heartbeat',
    'job_done',
    'job_failed'
  ]);

  function locationOrigin() {
    return global.location && global.location.origin
      ? global.location.origin
      : 'http://localhost';
  }

  function buildReplayUrl(baseUrl, fromSeq) {
    var url = new URL(baseUrl, locationOrigin());
    var seq = Number(fromSeq || 0);
    if (!Number.isFinite(seq) || seq < 0) seq = 0;
    url.searchParams.set('from_seq', String(Math.floor(seq)));
    if (/^https?:\/\//i.test(baseUrl)) return url.href;
    return url.pathname + url.search + url.hash;
  }

  function safeCall(fn, arg) {
    if (typeof fn === 'function') fn(arg);
  }

  function connect(opts) {
    opts = opts || {};
    if (!opts.url) throw new Error('missing SSE URL');
    if (typeof global.EventSource !== 'function') {
      throw new Error('SSE unavailable in this browser');
    }

    var state = {
      closed: false,
      terminal: false,
      retryDelayMs: Number(opts.retryDelayMs || 800),
      retryTimer: null,
      source: null,
      lastSeq: Number(opts.fromSeq || 0) || 0
    };

    function close() {
      state.closed = true;
      if (state.retryTimer) clearTimeout(state.retryTimer);
      if (state.source) state.source.close();
    }

    function handleEvent(evt) {
      var data = JSON.parse(evt.data);
      var seq = Number(data.seq || 0);
      if (seq <= state.lastSeq) return;
      state.lastSeq = seq;
      safeCall(opts.onEvent, data);
      if (TERMINAL_EVENTS[data.event_type]) {
        state.terminal = true;
        close();
      }
    }

    function scheduleReconnect() {
      if (state.closed || state.terminal) return;
      safeCall(opts.onState, { type: 'reconnecting', from_seq: state.lastSeq });
      state.retryTimer = setTimeout(open, state.retryDelayMs);
    }

    function open() {
      if (state.closed || state.terminal) return;
      var streamUrl = buildReplayUrl(opts.url, state.lastSeq);
      safeCall(opts.onState, { type: 'connecting', from_seq: state.lastSeq });
      try {
        state.source = new global.EventSource(streamUrl, { withCredentials: true });
      } catch (err) {
        safeCall(opts.onError, err);
        scheduleReconnect();
        return;
      }

      EVENT_TYPES.forEach(function (type) {
        state.source.addEventListener(type, function (evt) {
          try {
            handleEvent(evt);
          } catch (err) {
            safeCall(opts.onError, err);
          }
        });
      });

      state.source.onerror = function () {
        if (state.source) state.source.close();
        scheduleReconnect();
      };
    }

    open();

    return {
      close: close,
      getLastSeq: function () { return state.lastSeq; },
      getReplayUrl: function () { return buildReplayUrl(opts.url, state.lastSeq); }
    };
  }

  global.NXJobReplay = {
    buildReplayUrl: buildReplayUrl,
    connect: connect
  };
})(window);
