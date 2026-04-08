// ══════════════════════════════════════════════════════
//  CASES — Saved investigation cases
// ══════════════════════════════════════════════════════
let cases = JSON.parse(localStorage.getItem('nx_cases') || '[]');

function toggleCasesPanel() {
  const panel   = document.getElementById('casesPanel');
  const overlay = document.getElementById('casesOverlay');
  const isOpen  = panel.classList.contains('visible');
  panel.classList.toggle('visible', !isOpen);
  overlay.classList.toggle('visible', !isOpen);
  if (!isOpen) renderCasesPanel();
}

function saveCase() {
  const o   = currentResult.oathnet;
  const s   = currentResult.sherlock;
  const q   = currentResult.query;
  if (!q) return;
  const risk  = Math.min((o?.breach_count||0)*15 + (o?.stealer_count||0)*20, 100);
  const [rl]  = riskLabel(risk);
  const id    = 'case_' + Date.now();
  // FIND-09: snapshot intentionally excluded — fetch from /api/cases/:id when needed.
  // Only store lightweight metadata to avoid PII accumulation in localStorage.
  cases.unshift({
    id, query: q,
    risk, rl,
    breach_count:  o?.breach_count  || 0,
    stealer_count: o?.stealer_count || 0,
    social_count:  s?.found_count   || 0,
    timestamp: currentResult.timestamp?.slice(0,16) || new Date().toISOString().slice(0,16),
    note: '',
  });
  cases = cases.slice(0, 50);
  localStorage.setItem('nx_cases', JSON.stringify(cases));
  updateCasesBadge();
  const btn = document.getElementById('btnSaveCase');
  if (btn) {
    btn.classList.add('saved');
    btn.innerHTML = '✓ Saved';
    setTimeout(() => { btn.classList.remove('saved'); btn.innerHTML = '💾 Save Case'; }, 2000);
  }
  showToast('Case saved: ' + q);
}

function deleteCase(id) {
  cases = cases.filter(c => c.id !== id);
  localStorage.setItem('nx_cases', JSON.stringify(cases));
  updateCasesBadge();
  renderCasesPanel();
}

function clearAllCases() {
  if (!confirm('Clear all saved cases?')) return;
  cases = [];
  localStorage.setItem('nx_cases', JSON.stringify(cases));
  updateCasesBadge();
  renderCasesPanel();
}

function saveCaseNote(id, note) {
  const c = cases.find(c => c.id === id);
  if (c) {
    c.note = note;
    localStorage.setItem('nx_cases', JSON.stringify(cases));
  }
}

function loadCase(id) {
  const c = cases.find(c => c.id === id);
  if (!c) return;
  // FIND-09: snapshot removed from localStorage — cases now store metadata only.
  // Re-render from stored metadata (no full result data available without re-search).
  if (c.snapshot) {
    // Legacy case (pre-FIND-09 fix): still has snapshot, use it
    currentResult = {
      query:     c.query,
      oathnet:   c.snapshot.oathnet,
      sherlock:  c.snapshot.sherlock,
      extras:    c.snapshot.extras || {},
      elapsed:   c.snapshot.elapsed,
      timestamp: c.timestamp + ':00',
    };
    toggleCasesPanel();
    renderResults();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else {
    // New case format: show toast directing user to re-search
    showToast('Case "' + esc(c.query) + '" — re-run search to view results.');
    document.getElementById('searchInput').value = c.query;
    toggleCasesPanel();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function updateCasesBadge() {
  const badge = document.getElementById('casesBadge');
  if (!badge) return;
  if (cases.length > 0) {
    badge.style.display = 'flex';
    badge.textContent   = cases.length > 99 ? '99+' : cases.length;
  } else {
    badge.style.display = 'none';
  }
}

function renderCasesPanel() {
  const body = document.getElementById('casesPanelBody');
  if (!cases.length) {
    body.innerHTML = '<div class="text-dim-mono-center">No saved cases yet.<br>Run a search and click 💾 Save Case.</div>';
    return;
  }
  body.innerHTML = cases.map(c => {
    const [,rc] = riskLabel(c.risk);
    // Determine risk color class
    const riskClass = rc === 'var(--red)' ? 'text-critical'
      : rc === 'var(--orange)' ? 'text-amber'
      : 'text-green';
    return `<div class="case-card">
      <div class="case-card-header">
        <div>
          <div class="case-card-target" data-action="load-case" data-id="${esc(c.id)}">${esc(c.query)}</div>
          <div class="case-card-meta">
            <span class="${riskClass}">${c.rl} ${c.risk}</span> ·
            ${c.breach_count}B ${c.stealer_count}S ${c.social_count}Soc ·
            ${esc(c.timestamp)}
          </div>
        </div>
        <button class="case-card-del" data-action="delete-case" data-id="${esc(c.id)}" title="Delete">✕</button>
      </div>
      ${c.note ? `<div class="case-card-note">${esc(c.note)}</div>` : ''}
      <textarea class="case-note-input" placeholder="Add notes…"
        data-caseid="${esc(c.id)}"
      >${esc(c.note||'')}</textarea>
    </div>`;
  }).join('');

  // Wire textarea blur/focus via event delegation on the panel body
  // (cannot use data-action for non-click events)
  body.querySelectorAll('.case-note-input').forEach(ta => {
    const cid = ta.dataset.caseid;
    ta.addEventListener('focus', function () {
      const c = cases.find(x => x.id === cid);
      this.value = c?.note || '';
    });
    ta.addEventListener('blur', function () {
      saveCaseNote(cid, this.value);
    });
  });
}
