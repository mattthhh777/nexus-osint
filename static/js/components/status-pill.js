// StatusPill renders the 8-state ConnectorStatus as a chip.

(function (global) {
  'use strict';

  var STATUS_META = {
    pending: { icon: 'P', label: 'Pending', color: 'var(--text-3)' },
    running: { icon: 'R', label: 'Running', color: 'var(--accent)' },
    found: { icon: 'F', label: 'Found', color: 'var(--status-found)' },
    likely: { icon: 'L', label: 'Likely', color: 'var(--status-likely)' },
    uncertain: { icon: 'U', label: 'Uncertain', color: 'var(--status-uncertain)' },
    not_found: { icon: 'N', label: 'Not found', color: 'var(--status-not-found)' },
    blocked: { icon: 'B', label: 'Blocked', color: 'var(--status-blocked)' },
    error: { icon: 'E', label: 'Error', color: 'var(--status-error)' }
  };

  function createStatusPill(opts) {
    opts = opts || {};
    var status = opts.status || 'pending';
    var meta = STATUS_META[status];
    if (!meta) throw new Error('Invalid status: ' + status);

    var el = document.createElement('span');
    el.className = 'nx-status-pill nx-status-pill--' + status;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-label', opts.label || meta.label);
    el.setAttribute('data-status', status);
    el.style.color = meta.color;

    var icon = document.createElement('span');
    icon.className = 'nx-status-pill__icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = opts.icon || meta.icon;

    var label = document.createElement('span');
    label.className = 'nx-status-pill__label';
    label.textContent = opts.label || meta.label;

    el.appendChild(icon);
    el.appendChild(label);

    if (opts.tooltip) {
      el.setAttribute('title', opts.tooltip);
    }
    return el;
  }

  global.NX_STATUS_META = STATUS_META;
  global.createStatusPill = createStatusPill;
})(window);
