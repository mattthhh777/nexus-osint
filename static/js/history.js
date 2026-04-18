// ══════════════════════════════════════════════════════
//  HISTORY — Recent search history
// ══════════════════════════════════════════════════════
function saveHistory() {
  const o = currentResult.oathnet;
  const s = currentResult.sherlock;
  const nBreach  = o?.breach_count  || 0;
  const nStealer = o?.stealer_count || 0;
  const nSocial  = s?.found_count   || 0;
  const risk = Math.min(nBreach*15 + nStealer*20, 100);
  const [rl] = riskLabel(risk);
  history.unshift({
    query: currentResult.query,
    risk, rl,
    total: nBreach + nStealer + nSocial,
    timestamp: currentResult.timestamp||'',
  });
  history = history.slice(0, 20);
  localStorage.setItem('nx_history', JSON.stringify(history));
  renderHistory();
}

function renderHistory() {
  const el = document.getElementById('historyGrid');
  const sec = document.getElementById('historySection');
  if (!history.length) { sec.style.display = 'none'; return; }
  sec.style.display = 'block';
  el.innerHTML = history.map(h => {
    const [, rc] = riskLabel(h.risk);
    const riskClass = rc === 'var(--red)' ? 'text-critical'
      : rc === 'var(--orange)' ? 'text-amber'
      : 'text-green';
    return `<div class="history-card" data-action="rerun-search" data-query="${escAttr(h.query)}">
      <div class="history-target">${esc(h.query)}</div>
      <div class="history-meta">
        <span class="${riskClass}">${h.rl} ${h.risk}</span>${h.total?' · '+h.total+' found':''} · ${esc(formatTimestamp(h.timestamp))}
      </div>
    </div>`;
  }).join('');
}

function rerunSearch(q) {
  document.getElementById('searchInput').value = q;
  window.scrollTo({top:0,behavior:'smooth'});
  document.getElementById('searchInput').focus();
}
