// ══════════════════════════════════════════════════════
//  CASES — Saved investigation cases
// ══════════════════════════════════════════════════════
let cases = JSON.parse(localStorage.getItem('nx_cases') || '[]');
const CASE_STORAGE_WARN_BYTES = 4.5 * 1024 * 1024;

function caseNowIso() {
  return new Date().toISOString();
}

async function sha256Hex12(str) {
  if (!window.crypto || !window.crypto.subtle) {
    throw new Error('SubtleCrypto unavailable');
  }
  const enc = new TextEncoder();
  const buf = await crypto.subtle.digest('SHA-256', enc.encode(String(str || '')));
  return Array.from(new Uint8Array(buf))
    .map(function (b) { return b.toString(16).padStart(2, '0'); })
    .join('')
    .slice(0, 12);
}

function storageBytes(value) {
  if (window.TextEncoder) return new TextEncoder().encode(value).length;
  return new Blob([value]).size;
}

function persistCases() {
  const payload = JSON.stringify(cases);
  const bytes = storageBytes(payload);
  if (bytes >= CASE_STORAGE_WARN_BYTES) {
    showToast('Saved cases near browser storage limit. Delete old cases soon.', 'warn');
  }
  try {
    localStorage.setItem('nx_cases', payload);
    return true;
  } catch (err) {
    showToast('Could not save case: browser storage limit reached.', 'error');
    return false;
  }
}

function normalizeCaseTargetType(query) {
  const type = typeof detectType === 'function' ? detectType(query) : null;
  if (type === 'email' || type === 'phone') return type;
  return 'username';
}

function emptySummarySnapshot() {
  return {
    overall_status: 'pending',
    overall_confidence: 0,
    found_count: 0,
    likely_count: 0,
    not_found_count: 0,
    blocked_count: 0,
    error_count: 0
  };
}

function statusListFromCurrentResult() {
  if (Array.isArray(currentResult.connectorResults) && currentResult.connectorResults.length) {
    return currentResult.connectorResults.map(result => ({
      status: result.status || 'uncertain',
      confidence_score: Number(result.confidence_score || 0)
    }));
  }

  const o = currentResult.oathnet || {};
  const s = currentResult.sherlock || {};
  const statuses = [];

  statuses.push({
    status: Number(o.breach_count || 0) > 0 ? 'found' : 'not_found',
    confidence_score: Number(o.breach_count || 0) > 0 ? 80 : 0
  });
  statuses.push({
    status: Number(o.stealer_count || 0) > 0 ? 'found' : 'not_found',
    confidence_score: Number(o.stealer_count || 0) > 0 ? 85 : 0
  });
  if (o.holehe_count != null) {
    statuses.push({
      status: Number(o.holehe_count || 0) > 0 ? 'found' : 'not_found',
      confidence_score: Number(o.holehe_count || 0) > 0 ? 65 : 0
    });
  }
  if (Array.isArray(s.platforms)) {
    s.platforms.forEach(platform => {
      const fetchStatus = platform.fetch_status || platform.error || '';
      const validation = platform.validation_status || '';
      const score = Number(platform.confidence_score || 0);
      if (
        fetchStatus === 'cf_challenge' ||
        fetchStatus === 'auth_blocked' ||
        fetchStatus === 'login_required' ||
        fetchStatus === 'redirect_to_login' ||
        fetchStatus === 'rate_limit' ||
        fetchStatus === 'anti_bot'
      ) {
        statuses.push({ status: 'blocked', confidence_score: 0 });
      } else if (validation === 'confirmed') {
        statuses.push({ status: 'found', confidence_score: score });
      } else if (validation === 'likely') {
        statuses.push({ status: 'likely', confidence_score: score });
      } else if (validation === 'uncertain') {
        statuses.push({ status: 'uncertain', confidence_score: score });
      } else if (validation === 'likely_false_positive' || validation === 'not_found') {
        statuses.push({ status: 'not_found', confidence_score: score });
      } else {
        statuses.push({ status: 'error', confidence_score: 0 });
      }
    });
  } else if (s.found_count != null || s.likely_count != null) {
    const found = Number(s.found_count || 0);
    const likely = Number(s.likely_count || 0);
    if (found > 0) {
      statuses.push({ status: 'found', confidence_score: 80 });
    }
    if (likely > 0) {
      statuses.push({ status: 'likely', confidence_score: 65 });
    }
    if (found === 0 && likely === 0) {
      statuses.push({ status: 'not_found', confidence_score: 0 });
    }
  }
  return statuses;
}

function buildSummarySnapshot() {
  const summary = emptySummarySnapshot();
  const statuses = statusListFromCurrentResult();

  statuses.forEach(item => {
    if (item.status === 'found') summary.found_count += 1;
    else if (item.status === 'likely') summary.likely_count += 1;
    else if (item.status === 'not_found') summary.not_found_count += 1;
    else if (item.status === 'blocked') summary.blocked_count += 1;
    else if (item.status === 'error') summary.error_count += 1;
    summary.overall_confidence = Math.max(
      summary.overall_confidence,
      Math.max(0, Math.min(100, Number(item.confidence_score || 0)))
    );
  });

  if (summary.found_count >= 2) summary.overall_status = 'found';
  else if (summary.found_count === 1 || summary.likely_count > 0) summary.overall_status = 'likely';
  else if (summary.blocked_count > 0) summary.overall_status = 'blocked';
  else if (summary.error_count > 0) summary.overall_status = 'error';
  else if (summary.not_found_count > 0) summary.overall_status = 'not_found';
  else summary.overall_status = 'uncertain';

  return summary;
}

function caseSortTime(c) {
  return Date.parse(c.updated_at || c.timestamp || c.created_at || '') || 0;
}

function caseStatus(c) {
  return c.summary_snapshot?.overall_status || (c.risk >= 50 ? 'likely' : 'not_found');
}

function caseResultFromSummary(c) {
  const summary = c.summary_snapshot || emptySummarySnapshot();
  return {
    query: c.query || c.name || '',
    oathnet: {
      query_type: c.target_type || 'username',
      breach_count: c.breach_count || summary.found_count || 0,
      stealer_count: c.stealer_count || 0,
      holehe_count: 0,
      breaches: [],
      stealers: [],
      holehe_domains: []
    },
    sherlock: {
      found_count: c.social_count || 0,
      likely_count: summary.likely_count || 0,
      total_checked: 0,
      found: []
    },
    extras: {},
    elapsed: 0,
    timestamp: c.updated_at || c.created_at || c.timestamp || caseNowIso(),
    case_id: c.id
  };
}

function toggleCasesPanel() {
  const panel   = document.getElementById('casesPanel');
  const overlay = document.getElementById('casesOverlay');
  const isOpen  = panel.classList.contains('visible');
  panel.classList.toggle('visible', !isOpen);
  overlay.classList.toggle('visible', !isOpen);
  if (!isOpen) renderCasesPanel();
}

async function saveCase() {
  const o   = currentResult.oathnet;
  const s   = currentResult.sherlock;
  const q   = currentResult.query;
  if (!q) return;
  const risk  = Math.min((o?.breach_count||0)*15 + (o?.stealer_count||0)*20, 100);
  const [rl]  = riskLabel(risk);
  const id    = 'case_' + Date.now();
  const now   = caseNowIso();
  let targetHash = '';
  try {
    targetHash = await sha256Hex12(q);
  } catch (err) {
    targetHash = 'unavailable';
    showToast('Case saved without target hash: browser crypto unavailable.', 'warn');
  }

  // Snapshot intentionally excluded. Store lightweight metadata only to avoid
  // PII accumulation in localStorage; re-run search for full result detail.
  const savedCase = {
    id,
    name: q,
    query: q,
    created_at: now,
    updated_at: now,
    target_hash: targetHash,
    target_type: normalizeCaseTargetType(q),
    summary_snapshot: buildSummarySnapshot(),
    risk, rl,
    breach_count:  o?.breach_count  || 0,
    stealer_count: o?.stealer_count || 0,
    social_count:  s?.found_count   || 0,
    timestamp: currentResult.timestamp?.slice(0,16) || new Date().toISOString().slice(0,16),
    note: '',
  };
  currentResult.case_id = id;
  cases.unshift(savedCase);
  cases = cases.slice(0, 50);
  if (!persistCases()) {
    cases = cases.filter(c => c.id !== id);
    return;
  }
  updateCasesBadge();
  const btn = document.getElementById('btnSaveCase');
  if (btn) {
    const originalHtml = btn.dataset.originalHtml || btn.innerHTML;
    btn.dataset.originalHtml = originalHtml;
    btn.classList.add('saved');
    btn.innerHTML = 'Saved';
    setTimeout(() => { btn.classList.remove('saved'); btn.innerHTML = originalHtml; }, 2000);
  }
  showToast('Case saved: ' + q);
}

function deleteCase(id) {
  cases = cases.filter(c => c.id !== id);
  persistCases();
  updateCasesBadge();
  renderCasesPanel();
}

function clearAllCases() {
  if (!confirm('Clear all saved cases?')) return;
  cases = [];
  persistCases();
  updateCasesBadge();
  renderCasesPanel();
}

function saveCaseNote(id, note) {
  const c = cases.find(c => c.id === id);
  if (c) {
    c.note = note;
    c.updated_at = caseNowIso();
    persistCases();
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
    showToast('Case ' + c.id + ' · hash ' + (c.target_hash || '─') + ' · re-run search to view full results.');
    document.getElementById('searchInput').value = c.query;
    toggleCasesPanel();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function exportCasePDF(id) {
  const c = cases.find(c => c.id === id);
  if (!c) return;
  const loadedMatches = currentResult && currentResult.query === c.query;
  const result = loadedMatches ? { ...currentResult, case_id: c.id } : caseResultFromSummary(c);
  exportPDF({
    caseId: c.id,
    generatedAt: caseNowIso(),
    result
  });
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
    body.innerHTML = '<div class="text-dim-mono-center">No saved cases yet.<br>Run a search and click Save Case.</div>';
    return;
  }
  const sortedCases = [...cases].sort((a, b) => caseSortTime(b) - caseSortTime(a));
  body.innerHTML = sortedCases.map(c => {
    const riskClass = c.risk >= 75 ? 'text-critical'
      : c.risk >= 25 ? 'text-amber'
      : 'text-green';
    const summary = c.summary_snapshot || emptySummarySnapshot();
    const created = formatTimestamp(c.created_at || c.timestamp);
    const updated = formatTimestamp(c.updated_at || c.timestamp);
    const status = caseStatus(c);
    return `<div class="case-card">
      <div class="case-card-header">
        <div>
          <div class="case-card-target" data-action="load-case" data-id="${esc(c.id)}">${esc(c.name || c.query)}</div>
          <div class="case-card-meta">
            <span class="${riskClass}">${esc(c.rl)} ${esc(String(c.risk || 0))}</span> ·
            ${esc(String(c.breach_count || 0))}B ${esc(String(c.stealer_count || 0))}S ${esc(String(c.social_count || 0))}Soc
          </div>
        </div>
        <button class="case-card-del" data-action="delete-case" data-id="${esc(c.id)}" title="Delete" aria-label="Delete case">×</button>
      </div>
      <div class="case-card-meta">
        <span class="case-status-slot" data-status="${esc(status)}"></span>
        <span>case_id ${esc(c.id)}</span>
      </div>
      <div class="case-card-meta">created ${esc(created)} · updated ${esc(updated)}</div>
      <div class="case-card-meta">target_hash ${esc(c.target_hash || 'legacy')}</div>
      <div class="case-card-meta">
        found ${esc(String(summary.found_count || 0))} · likely ${esc(String(summary.likely_count || 0))} ·
        not_found ${esc(String(summary.not_found_count || 0))} · blocked ${esc(String(summary.blocked_count || 0))} ·
        error ${esc(String(summary.error_count || 0))}
      </div>
      <button class="btn btn-secondary btn-sm btn-full mt-10" data-action="export-case-pdf" data-id="${esc(c.id)}">Export PDF</button>
      ${c.note ? `<div class="case-card-note">${esc(c.note)}</div>` : ''}
      <textarea class="case-note-input" placeholder="Add notes…"
        data-caseid="${esc(c.id)}"
      >${esc(c.note||'')}</textarea>
    </div>`;
  }).join('');

  // Wire textarea blur/focus via event delegation on the panel body
  // (cannot use data-action for non-click events)
  body.querySelectorAll('.case-status-slot').forEach(slot => {
    const status = slot.dataset.status || 'pending';
    if (typeof createStatusPill === 'function') {
      slot.replaceChildren(createStatusPill({ status }));
    } else {
      slot.textContent = status;
    }
  });
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
