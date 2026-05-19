// EvidenceDrawer renders connector evidence in an accessible slide-in panel.

(function (global) {
  'use strict';

  function closeExistingDrawer() {
    var existing = document.querySelector('.nx-evidence-shell');
    if (existing && existing.parentNode) {
      existing.parentNode.removeChild(existing);
    }
  }

  function addText(parent, tag, className, text) {
    var el = document.createElement(tag);
    el.className = className;
    el.textContent = text || '';
    parent.appendChild(el);
    return el;
  }

  function renderEvidenceList(parent, evidence) {
    var list = document.createElement('div');
    list.className = 'nx-evidence-list';

    if (!evidence || evidence.length === 0) {
      addText(list, 'p', 'nx-evidence-empty', 'No evidence available yet.');
      parent.appendChild(list);
      return;
    }

    evidence.forEach(function (item) {
      var row = document.createElement('article');
      row.className = 'nx-evidence-item';

      var top = document.createElement('div');
      top.className = 'nx-evidence-item__top';
      addText(top, 'span', 'nx-evidence-item__signal', item.signal || 'signal');
      addText(top, 'span', 'nx-evidence-item__weight', String(item.weight || 0));

      addText(row, 'p', 'nx-evidence-item__detail', item.detail || 'No detail provided.');
      row.insertBefore(top, row.firstChild);
      list.appendChild(row);
    });

    parent.appendChild(list);
  }

  function renderWarnings(parent, warnings) {
    if (!warnings || warnings.length === 0) return;

    var block = document.createElement('div');
    block.className = 'nx-evidence-warnings';
    addText(block, 'div', 'nx-evidence-section-title', 'Warnings');
    warnings.forEach(function (warning) {
      addText(block, 'div', 'nx-evidence-warning', warning);
    });
    parent.appendChild(block);
  }

  function createEvidenceDrawer(opts) {
    opts = opts || {};
    var result = opts.result || {};
    var evidence = opts.evidence || result.evidence || [];
    var warnings = opts.warnings || result.warnings || [];

    var shell = document.createElement('div');
    shell.className = 'nx-evidence-shell' + (opts.inline ? ' nx-evidence-shell--inline' : '');

    var backdrop = document.createElement('button');
    backdrop.className = 'nx-evidence-backdrop';
    backdrop.type = 'button';
    backdrop.setAttribute('aria-label', 'Close evidence drawer');

    var drawer = document.createElement('aside');
    drawer.className = 'nx-evidence-drawer';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', opts.inline ? 'false' : 'true');
    drawer.setAttribute('aria-label', opts.title || result.connector || 'Evidence');
    drawer.tabIndex = -1;

    var header = document.createElement('div');
    header.className = 'nx-evidence-drawer__header';
    var heading = addText(header, 'h2', 'nx-evidence-drawer__title', opts.title || result.connector || 'Evidence');
    heading.id = 'nx-evidence-title';
    drawer.setAttribute('aria-labelledby', heading.id);

    var close = document.createElement('button');
    close.className = 'nx-evidence-close';
    close.type = 'button';
    close.setAttribute('aria-label', 'Close evidence drawer');
    close.textContent = 'Close';
    header.appendChild(close);

    var body = document.createElement('div');
    body.className = 'nx-evidence-drawer__body';

    if (result.connector) {
      addText(body, 'div', 'nx-evidence-connector', result.connector);
    }
    renderEvidenceList(body, evidence);
    renderWarnings(body, warnings);

    function closeDrawer() {
      if (shell.parentNode) {
        shell.parentNode.removeChild(shell);
      }
      if (opts.returnFocusTo && typeof opts.returnFocusTo.focus === 'function') {
        opts.returnFocusTo.focus();
      }
    }

    close.addEventListener('click', closeDrawer);
    backdrop.addEventListener('click', closeDrawer);
    shell.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeDrawer();
      }
    });

    drawer.appendChild(header);
    drawer.appendChild(body);
    shell.appendChild(backdrop);
    shell.appendChild(drawer);

    shell.open = function () {
      closeExistingDrawer();
      document.body.appendChild(shell);
      drawer.focus();
    };

    return shell;
  }

  function openEvidenceDrawer(opts) {
    var drawer = createEvidenceDrawer(opts);
    drawer.open();
    return drawer;
  }

  global.createEvidenceDrawer = createEvidenceDrawer;
  global.openEvidenceDrawer = openEvidenceDrawer;
})(window);
