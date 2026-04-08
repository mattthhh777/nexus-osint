// ══════════════════════════════════════════════════════
//  EXPORT — Copy, PDF, JSON, CSV, TXT
// ══════════════════════════════════════════════════════

// ── Copy helpers ─────────────────────────────────────
function flashCopyBtn(id) {
  const btn = document.getElementById('copyBtn_' + id);
  if (!btn) return;
  btn.classList.add('copied');
  btn.textContent = '✓ Copied';
  setTimeout(() => {
    btn.classList.remove('copied');
    btn.textContent = '📋 Copy';
  }, 2000);
}

async function writeClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch(e) {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    return true;
  }
}

function copySection(section) {
  const o = currentResult.oathnet;
  const s = currentResult.sherlock;
  let lines = [];

  if (section === 'breach') {
    if (!o?.breaches?.length) { showToast('No breaches to copy'); return; }
    lines.push(`=== NEXUSOSINT — SECURITY BREACHES ===`);
    lines.push(`Target:  ${currentResult.query}`);
    lines.push(`Found:   ${o.breach_count} records`);
    lines.push(`Date:    ${currentResult.timestamp?.slice(0,16)||new Date().toISOString().slice(0,16)}`);
    lines.push('');
    o.breaches.forEach((b, i) => {
      lines.push(`[${i+1}] Database: ${b.dbname||'─'}`);
      if (b.email)    lines.push(`    Email:    ${b.email}`);
      if (b.username) lines.push(`    Username: ${b.username}`);
      if (b.password) lines.push(`    Password: ${b.password}`);
      if (b.country)  lines.push(`    Country:  ${b.country}`);
      if (b.date)     lines.push(`    Date:     ${b.date}`);
      lines.push('');
    });
    lines.push(`=== END BREACHES ===`);

  } else if (section === 'stealer') {
    if (!o?.stealers?.length) { showToast('No stealer logs to copy'); return; }
    lines.push(`=== NEXUSOSINT — STEALER LOGS ===`);
    lines.push(`Target:  ${currentResult.query}`);
    lines.push(`Found:   ${o.stealer_count} credentials`);
    lines.push('');
    o.stealers.forEach((s, i) => {
      lines.push(`[${i+1}] URL:      ${s.url||'─'}`);
      if (s.username) lines.push(`    Username: ${s.username}`);
      if (s.password) lines.push(`    Password: ${s.password}`);
      if (s.domain)   lines.push(`    Domain:   ${Array.isArray(s.domain)?s.domain.join(', '):s.domain}`);
      if (s.pwned_at) lines.push(`    Date:     ${s.pwned_at?.slice(0,10)}`);
      lines.push('');
    });
    lines.push(`=== END STEALER LOGS ===`);

  } else if (section === 'social') {
    if (!s?.found?.length) { showToast('No social profiles to copy'); return; }
    lines.push(`=== NEXUSOSINT — SOCIAL PROFILES ===`);
    lines.push(`Target:  ${currentResult.query}`);
    lines.push(`Found:   ${s.found_count} of ${s.total_checked} checked`);
    lines.push('');
    s.found.forEach(p => {
      lines.push(`${p.platform.padEnd(20)} ${p.url}`);
    });
    lines.push('');
    lines.push(`=== END SOCIAL PROFILES ===`);

  } else if (section === 'email') {
    if (!o?.holehe_domains?.length) { showToast('No email services to copy'); return; }
    lines.push(`=== NEXUSOSINT — EMAIL SERVICES ===`);
    lines.push(`Target:  ${currentResult.query}`);
    lines.push(`Found:   ${o.holehe_count} registrations`);
    lines.push('');
    o.holehe_domains.forEach(d => lines.push(`  • ${d}`));
    lines.push('');
    lines.push(`=== END EMAIL SERVICES ===`);
  }

  writeClipboard(lines.join('\n'));
  flashCopyBtn(section);
}

async function copyAll() {
  const o = currentResult.oathnet;
  const s = currentResult.sherlock;
  const ts = currentResult.timestamp?.slice(0,16) || new Date().toISOString().slice(0,16);
  const risk = Math.min((o?.breach_count||0)*15 + (o?.stealer_count||0)*20, 100);
  const [rl] = riskLabel(risk);

  const lines = [
    `╔══════════════════════════════════════════════════════╗`,
    `║              NEXUSOSINT v2 — FULL REPORT             ║`,
    `╚══════════════════════════════════════════════════════╝`,
    ``,
    `  Target  : ${currentResult.query}`,
    `  Date    : ${ts}`,
    `  Risk    : ${risk} — ${rl}`,
    `  Results : ${(o?.breach_count||0)+(o?.stealer_count||0)+(s?.found_count||0)+(o?.holehe_count||0)} total`,
    ``,
  ];

  if (o?.breaches?.length) {
    lines.push(`──────────────────────────────────────────────────────`);
    lines.push(`  SECURITY BREACHES  (${o.breach_count})`);
    lines.push(`──────────────────────────────────────────────────────`);
    o.breaches.forEach((b, i) => {
      lines.push(`  [${i+1}] ${b.dbname||'─'}`);
      if (b.email)    lines.push(`      Email:    ${b.email}`);
      if (b.username) lines.push(`      Username: ${b.username}`);
      if (b.password) lines.push(`      Password: ${b.password}`);
      if (b.country)  lines.push(`      Country:  ${b.country}  ${b.date?.slice(0,10)||''}`);
      lines.push('');
    });
  }

  if (o?.stealers?.length) {
    lines.push(`──────────────────────────────────────────────────────`);
    lines.push(`  STEALER LOGS  (${o.stealer_count})`);
    lines.push(`──────────────────────────────────────────────────────`);
    o.stealers.forEach((st, i) => {
      lines.push(`  [${i+1}] ${st.url||'─'}`);
      if (st.username) lines.push(`      User: ${st.username}`);
      if (st.password) lines.push(`      Pass: ${st.password}`);
      if (st.pwned_at) lines.push(`      Date: ${st.pwned_at?.slice(0,10)}`);
      lines.push('');
    });
  }

  if (s?.found?.length) {
    lines.push(`──────────────────────────────────────────────────────`);
    lines.push(`  SOCIAL PROFILES  (${s.found_count}/${s.total_checked} checked)`);
    lines.push(`──────────────────────────────────────────────────────`);
    s.found.forEach(p => lines.push(`  ${p.platform.padEnd(20)} ${p.url}`));
    lines.push('');
  }

  if (o?.holehe_domains?.length) {
    lines.push(`──────────────────────────────────────────────────────`);
    lines.push(`  EMAIL SERVICES  (${o.holehe_count})`);
    lines.push(`──────────────────────────────────────────────────────`);
    o.holehe_domains.forEach(d => lines.push(`  • ${d}`));
    lines.push('');
  }

  lines.push(`╔══════════════════════════════════════════════════════╗`);
  lines.push(`║                    END OF REPORT                    ║`);
  lines.push(`╚══════════════════════════════════════════════════════╝`);

  const text = lines.join('\n');
  await writeClipboard(text);

  // Flash Copy All button
  const btn = document.getElementById('btnCopyAll');
  if (btn) {
    const orig = btn.innerHTML;
    btn.innerHTML = '✓ Copied!';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    setTimeout(() => { btn.innerHTML = orig; btn.style.borderColor=''; btn.style.color=''; }, 2000);
  }

  // Also show in textarea
  const area = document.getElementById('copyArea');
  area.value = text;
  area.classList.add('visible');
  document.getElementById('panelExport').classList.add('open');
}

// ── PDF export ────────────────────────────────────────
function exportPDF() {
  const o = currentResult.oathnet;
  const s = currentResult.sherlock;
  const ts = currentResult.timestamp || new Date().toISOString();
  const q = currentResult.query || '─';
  const risk = Math.min((o?.breach_count||0)*15 + (o?.stealer_count||0)*20, 100);
  const [rl, rc] = riskLabel(risk);
  const nTotal = (o?.breach_count||0)+(o?.stealer_count||0)+(s?.found_count||0)+(o?.holehe_count||0);

  const buildBreachRows = () => {
    if (!o?.breaches?.length) return `<tr><td colspan="6" class="empty">✓ No security breaches found</td></tr>`;
    return o.breaches.map((b,i) => `
      <tr>
        <td class="idx">${e(i+1)}</td>
        <td class="amber">${e(b.dbname)}</td>
        <td>${e(b.email)}</td>
        <td>${e(b.username)}</td>
        <td class="${b.password?'warn':''}">${e(b.password||'─')}</td>
        <td class="muted">${e(b.country)} ${e((b.date||'').slice(0,10))}</td>
      </tr>`).join('');
  };

  const buildStealerRows = () => {
    if (!o?.stealers?.length) return `<tr><td colspan="4" class="empty">✓ No stealer logs found</td></tr>`;
    return o.stealers.map((st,i) => `
      <tr>
        <td class="idx">${e(i+1)}</td>
        <td class="amber" style="max-width:220px;word-break:break-all">${e((st.url||'─').slice(0,80))}</td>
        <td>${e(st.username)}</td>
        <td class="muted">${e((st.pwned_at||'').slice(0,10))}</td>
      </tr>`).join('');
  };

  const buildSocialRows = () => {
    if (!s?.found?.length) return `<tr><td colspan="3" class="empty">No social profiles found</td></tr>`;
    return s.found.map((p,i) => `
      <tr>
        <td class="idx">${e(i+1)}</td>
        <td class="amber">${e(p.platform)}</td>
        <td><a href="${e(p.url)}">${e(p.url)}</a></td>
      </tr>`).join('');
  };

  const buildHolehe = () => {
    if (!o?.holehe_domains?.length) return `<p class="empty">No email service registrations found</p>`;
    return `<div class="tag-grid">${o.holehe_domains.map(d=>`<span class="tag">${e(d)}</span>`).join('')}</div>`;
  };

  function e(v) {
    if (!v) return '─';
    return String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  const riskHex = rc;
  const dateStr = ts.slice(0,16).replace('T',' ');

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>NexusOSINT Report — ${e(q)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

  :root {
    --bg: #080a0f;
    --bg2: #0c0e15;
    --bg3: #11141e;
    --amber: #f5a623;
    --amber-lo: rgba(245,166,35,.12);
    --green: #3ec78c;
    --green-lo: rgba(62,199,140,.12);
    --red: #e84040;
    --red-lo: rgba(232,64,64,.12);
    --orange: #e8822a;
    --blue: #4a9eff;
    --text: #dde2f0;
    --text2: #9aa0b8;
    --text3: #454a63;
    --line: rgba(255,255,255,.08);
    --mono: 'JetBrains Mono', monospace;
    --sans: 'Space Grotesk', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 13px;
    line-height: 1.5;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  /* Grid texture */
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0;
    background-image:
      linear-gradient(rgba(255,255,255,.012) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.012) 1px, transparent 1px);
    background-size: 36px 36px;
    pointer-events: none;
  }

  .wrap { position: relative; z-index: 1; max-width: 900px; margin: 0 auto; padding: 40px 40px 60px; }

  /* ── Cover / Header ── */
  .cover {
    display: flex; align-items: flex-start; justify-content: space-between;
    border-bottom: 1px solid var(--line); padding-bottom: 28px; margin-bottom: 32px;
  }
  .cover-left {}
  .cover-logo {
    display: flex; align-items: center; gap: 10px;
    font-family: var(--mono); font-weight: 700; font-size: .82rem;
    letter-spacing: .12em; color: var(--text3);
    text-transform: uppercase; margin-bottom: 18px;
  }
  .cover-logo-mark {
    width: 26px; height: 26px; background: var(--amber);
    border-radius: 5px; display: grid; place-items: center;
    font-size: 14px; color: var(--bg); font-weight: 900;
  }
  .cover-title {
    font-size: 2rem; font-weight: 700; color: var(--text);
    letter-spacing: -.03em; line-height: 1.1; margin-bottom: 6px;
  }
  .cover-title span { color: var(--amber); }
  .cover-sub { font-family: var(--mono); font-size: .72rem; color: var(--text3); }
  .cover-meta {
    text-align: right; font-family: var(--mono); font-size: .72rem;
    color: var(--text3); line-height: 1.8;
  }
  .cover-meta strong { color: var(--text2); display: block; }

  /* ── Stats row ── */
  .stats-row {
    display: grid; grid-template-columns: repeat(5,1fr); gap: 8px; margin-bottom: 32px;
  }
  .stat {
    background: var(--bg2); border: 1px solid var(--line);
    border-radius: 8px; padding: 14px 10px; text-align: center;
    position: relative; overflow: hidden;
  }
  .stat-bar { position: absolute; top: 0; left: 0; right: 0; height: 2px; }
  .stat-val {
    font-family: var(--mono); font-size: 1.7rem; font-weight: 700;
    letter-spacing: -.04em; color: var(--text); line-height: 1; margin-bottom: 5px;
  }
  .stat-lbl {
    font-size: .58rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .1em; color: var(--text3);
  }
  .stat-note { font-family: var(--mono); font-size: .6rem; margin-top: 4px; }

  /* ── Risk badge ── */
  .risk-strip {
    display: flex; align-items: center; gap: 14px;
    background: var(--bg2); border: 1px solid var(--line);
    border-radius: 8px; padding: 14px 18px; margin-bottom: 28px;
  }
  .risk-pill {
    font-family: var(--mono); font-weight: 700; font-size: .82rem;
    padding: 6px 16px; border-radius: 6px; white-space: nowrap;
  }
  .risk-info { font-family: var(--mono); font-size: .74rem; color: var(--text2); }

  /* ── Section ── */
  .section { margin-bottom: 28px; }
  .section-head {
    display: flex; align-items: center; gap: 10px;
    border-bottom: 1px solid var(--line); padding-bottom: 10px; margin-bottom: 14px;
  }
  .section-icon { font-size: 1rem; }
  .section-title {
    font-weight: 700; font-size: .92rem; color: var(--text); flex: 1;
  }
  .section-badge {
    font-family: var(--mono); font-size: .68rem; font-weight: 700;
    background: var(--bg3); border: 1px solid var(--line);
    border-radius: 4px; padding: 2px 8px; color: var(--text2);
  }

  /* ── Tables ── */
  table { width: 100%; border-collapse: collapse; font-family: var(--mono); font-size: .76rem; }
  thead th {
    text-align: left; padding: 7px 10px;
    font-size: .6rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .08em; color: var(--text3);
    border-bottom: 1px solid var(--line); background: var(--bg2);
  }
  tbody td {
    padding: 7px 10px; border-bottom: 1px solid rgba(255,255,255,.04);
    color: var(--text2); vertical-align: top; max-width: 260px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  tr:last-child td { border-bottom: none; }
  .idx { color: var(--text3); width: 28px; }
  .amber { color: var(--amber); }
  .warn  { color: var(--orange); }
  .muted { color: var(--text3); }
  .empty { text-align: center; padding: 14px; color: var(--green); font-family: var(--mono); }
  .empty::before { content: '✓ '; }
  a { color: var(--blue); text-decoration: none; }

  /* ── Tag grid ── */
  .tag-grid { display: flex; flex-wrap: wrap; gap: 6px; }
  .tag {
    background: var(--green-lo); border: 1px solid rgba(62,199,140,.2);
    color: var(--green); border-radius: 4px; padding: 3px 9px;
    font-family: var(--mono); font-size: .72rem;
  }

  /* ── Footer ── */
  .footer {
    margin-top: 40px; padding-top: 16px;
    border-top: 1px solid var(--line);
    display: flex; justify-content: space-between; align-items: center;
    font-family: var(--mono); font-size: .66rem; color: var(--text3);
  }

  /* ── Print ── */
  @media print {
    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    body { background: #080a0f !important; }
    .no-print { display: none !important; }
    .wrap { padding: 24px; }
    @page { margin: 12mm; size: A4; }
  }

  /* ── Print button ── */
  .print-bar {
    position: fixed; top: 0; left: 0; right: 0;
    background: rgba(8,10,15,.95); border-bottom: 1px solid rgba(245,166,35,.2);
    padding: 10px 24px; display: flex; align-items: center; gap: 12px;
    z-index: 100; backdrop-filter: blur(12px);
  }
  .print-bar span { font-family: var(--mono); font-size: .74rem; color: var(--text2); }
  .pbtn {
    padding: 7px 18px; border-radius: 6px; border: none; cursor: pointer;
    font-family: var(--mono); font-size: .76rem; font-weight: 700; transition: all .15s;
  }
  .pbtn-primary { background: var(--amber); color: #080a0f; }
  .pbtn-primary:hover { filter: brightness(1.1); }
  .pbtn-sec { background: var(--bg3); color: var(--text2); border: 1px solid var(--line); }
  .pbtn-sec:hover { color: var(--text); }
  body.has-bar .wrap { padding-top: 76px; }
<\/style>
<\/head>
<body class="has-bar">

<div class="print-bar no-print">
  <span>⬡ NexusOSINT Report — ${e(q)}<\/span>
  <button class="pbtn pbtn-primary" id="print-btn">⬇ Save as PDF<\/button>
  <button class="pbtn pbtn-sec" id="close-btn">✕ Close<\/button>
<\/div>

<div class="wrap">

  <!-- Cover -->
  <div class="cover">
    <div class="cover-left">
      <div class="cover-logo">
        <div class="cover-logo-mark">⬡<\/div>
        NEXUSOSINT
      <\/div>
      <div class="cover-title">Intelligence<br><span>Report<\/span><\/div>
      <div class="cover-sub">Generated by NexusOSINT v2 · ${dateStr}<\/div>
    <\/div>
    <div class="cover-meta">
      <strong>TARGET<\/strong>${e(q)}
      <strong>TYPE<\/strong>${e(currentResult.oathnet?.query_type||'username')}
      <strong>ELAPSED<\/strong>${currentResult.elapsed||0}s
      <strong>RISK SCORE<\/strong><span style="color:${riskHex}">${risk} — ${rl}<\/span>
    <\/div>
  <\/div>

  <!-- Stats -->
  <div class="stats-row">
    ${[
      {val: nTotal,              lbl:'Total Found',  bar:'#555',    note:''},
      {val: o?.breach_count||0,  lbl:'Breaches',     bar:'#e84040', note: (o?.breach_count||0)>0?'⚠ Attention':'✓ Clean', nc:(o?.breach_count||0)>0?'var(--orange)':'var(--green)'},
      {val: o?.stealer_count||0, lbl:'Stolen Info',  bar:'#e8822a', note: (o?.stealer_count||0)>0?'🚨 Compromised':'✓ Clean', nc:(o?.stealer_count||0)>0?'var(--red)':'var(--green)'},
      {val: s?.found_count||0,   lbl:'Social',       bar:'#4a9eff', note:`${s?.total_checked||0} checked`},
      {val: o?.holehe_count||0,  lbl:'Email Svcs',   bar:'#9b59b6', note:''},
    ].map(c=>`
      <div class="stat">
        <div class="stat-bar" style="background:${c.bar}"><\/div>
        <div class="stat-val">${c.val}<\/div>
        <div class="stat-lbl">${c.lbl}<\/div>
        ${c.note?`<div class="stat-note" style="color:${c.nc||'var(--text3)'}">${c.note}<\/div>`:''}
      <\/div>`).join('')}
  <\/div>

  <!-- Risk strip -->
  <div class="risk-strip">
    <div class="risk-pill" style="background:${riskHex}22;border:1px solid ${riskHex}55;color:${riskHex}">
      ${risk} — ${rl}
    <\/div>
    <div class="risk-info">
      ${risk>=75?'Critical exposure. Immediate action required. Change all passwords and enable 2FA.'
        :risk>=50?'High risk. Multiple data points compromised. Review and update credentials.'
        :risk>=25?'Medium risk. Breaches found. Review affected accounts.'
        :'Low risk. No significant exposure detected. Stay vigilant.'}
    <\/div>
  <\/div>

  <!-- Breaches -->
  <div class="section">
    <div class="section-head">
      <span class="section-icon">🔓<\/span>
      <span class="section-title">Security Breaches<\/span>
      <span class="section-badge">${o?.breach_count||0} records<\/span>
    <\/div>
    <table>
      <thead><tr>
        <th>#<\/th><th>Database<\/th><th>Email<\/th>
        <th>Username<\/th><th>Password<\/th><th>Country / Date<\/th>
      <\/tr><\/thead>
      <tbody>${buildBreachRows()}<\/tbody>
    <\/table>
    ${(o?.breach_count||0)>50?`<p style="font-family:var(--mono);font-size:.66rem;color:var(--text3);margin-top:8px;text-align:center">Showing 50 of ${o.breach_count} — export JSON for full data<\/p>`:''}
  <\/div>

  <!-- Stealers -->
  <div class="section">
    <div class="section-head">
      <span class="section-icon">⚠<\/span>
      <span class="section-title">Stolen Information (Stealer Logs)<\/span>
      <span class="section-badge">${o?.stealer_count||0} credentials<\/span>
    <\/div>
    ${(o?.stealer_count||0)>0?`<div style="background:var(--red-lo);border:1px solid rgba(232,64,64,.2);border-radius:6px;padding:8px 12px;margin-bottom:10px;font-family:var(--mono);font-size:.72rem;color:var(--red)">🚨 Credentials found in malware stealer logs. A device associated with this target may be compromised.<\/div>`:''}
    <table>
      <thead><tr><th>#<\/th><th>URL<\/th><th>Username<\/th><th>Date<\/th><\/tr><\/thead>
      <tbody>${buildStealerRows()}<\/tbody>
    <\/table>
  <\/div>

  <!-- Social -->
  <div class="section">
    <div class="section-head">
      <span class="section-icon">🌐<\/span>
      <span class="section-title">Social Profiles<\/span>
      <span class="section-badge">${s?.found_count||0} found · ${s?.total_checked||0} checked<\/span>
    <\/div>
    <table>
      <thead><tr><th>#<\/th><th>Platform<\/th><th>URL<\/th><\/tr><\/thead>
      <tbody>${buildSocialRows()}<\/tbody>
    <\/table>
  <\/div>

  <!-- Email services -->
  <div class="section">
    <div class="section-head">
      <span class="section-icon">📧<\/span>
      <span class="section-title">Email Service Registrations<\/span>
      <span class="section-badge">${o?.holehe_count||0} found<\/span>
    <\/div>
    ${buildHolehe()}
  <\/div>

  <!-- Footer -->
  <div class="footer">
    <span>⬡ NexusOSINT v2 · Intelligence Report · ${dateStr}<\/span>
    <span>Target: ${e(q)} · Risk: <span style="color:${riskHex}">${risk} ${rl}<\/span><\/span>
  <\/div>

<\/div>
<script>
  // Auto-trigger print if loaded with ?print=1
  if (location.search.includes('print=1')) window.print();
  // Attach print/close handlers (no onclick= — CSP compliance)
  document.getElementById('print-btn').addEventListener('click', function () { window.print(); });
  document.getElementById('close-btn').addEventListener('click', function () { window.close(); });
<\/script>
<\/body>
<\/html>`;

  const win = window.open('', '_blank');
  win.document.write(html);
  win.document.close();
}

// ── JSON export ───────────────────────────────────────
function exportJSON() {
  const data = {
    meta: { tool:'NexusOSINT v2', exported: new Date().toISOString() },
    query: currentResult.query,
    oathnet: currentResult.oathnet,
    sherlock: currentResult.sherlock,
    extras: currentResult.extras,
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `nexus_${currentResult.query}_${Date.now()}.json`;
  a.click();
}

// ── CSV export ────────────────────────────────────────
function exportCSV() {
  const o = currentResult.oathnet;
  const s = currentResult.sherlock;
  const q = currentResult.query;
  const rows = [];
  const ts = new Date().toISOString().slice(0,19);

  // Helper: escape CSV field
  const csv = v => {
    if (!v || v === '─') return '';
    const str = String(v).replace(/"/g,'""');
    return str.includes(',') || str.includes('"') || str.includes('\n') ? `"${str}"` : str;
  };

  // Breaches sheet
  rows.push(['NEXUSOSINT BREACH EXPORT']);
  rows.push(['Target', q, 'Exported', ts]);
  rows.push([]);
  rows.push(['Database','Email','Username','Password','IP','Country','Date']);
  (o?.breaches || []).forEach(b => {
    rows.push([b.dbname, b.email, b.username, b.password, b.ip, b.country, (b.date||'').slice(0,10)]);
  });

  rows.push([]);
  rows.push(['STEALER LOGS']);
  rows.push(['URL','Username','Password','Domain','Date']);
  (o?.stealers || []).forEach(s => {
    rows.push([s.url, s.username, s.password, Array.isArray(s.domain)?s.domain.join(';'):s.domain, (s.pwned_at||'').slice(0,10)]);
  });

  rows.push([]);
  rows.push(['SOCIAL PROFILES']);
  rows.push(['Platform','URL','Category']);
  (s?.found || []).forEach(p => {
    rows.push([p.platform, p.url, p.category]);
  });

  rows.push([]);
  rows.push(['EMAIL SERVICES (HOLEHE)']);
  rows.push(['Domain']);
  (o?.holehe_domains || []).forEach(d => rows.push([d]));

  const csvContent = rows.map(r => r.map(csv).join(',')).join('\n');
  const blob = new Blob(['\uFEFF' + csvContent], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `nexus_${q}_${Date.now()}.csv`;
  a.click();
}

// ── TXT export ────────────────────────────────────────
function exportTXT() {
  const o = currentResult.oathnet;
  const s = currentResult.sherlock;
  const q = currentResult.query;
  const risk = Math.min((o?.breach_count||0)*15+(o?.stealer_count||0)*20,100);
  const [rl] = riskLabel(risk);
  const ts = currentResult.timestamp?.slice(0,16) || new Date().toISOString().slice(0,16);
  const lines = [];

  const hr  = (char='─', len=56) => char.repeat(len);
  const row = (k, v) => `  ${k.padEnd(16)} ${v||'─'}`;

  lines.push(hr('═'));
  lines.push('  NEXUSOSINT v2 — INTELLIGENCE REPORT');
  lines.push(hr('═'));
  lines.push('');
  lines.push(row('Target:',  q));
  lines.push(row('Date:',    ts));
  lines.push(row('Risk:',    `${risk} — ${rl}`));
  lines.push(row('Breaches:', String(o?.breach_count||0)));
  lines.push(row('Stealers:', String(o?.stealer_count||0)));
  lines.push(row('Social:',  String(s?.found_count||0)));
  lines.push(row('Email Svcs:', String(o?.holehe_count||0)));
  lines.push('');

  if (o?.breaches?.length) {
    lines.push(hr());
    lines.push(`  SECURITY BREACHES (${o.breach_count})`);
    lines.push(hr());
    o.breaches.forEach((b, i) => {
      lines.push('');
      lines.push(`  [${i+1}] ${b.dbname||'Unknown'}`);
      if (b.email)    lines.push(row('    Email:', b.email));
      if (b.username) lines.push(row('    Username:', b.username));
      if (b.password) lines.push(row('    Password:', b.password));
      if (b.ip)       lines.push(row('    IP:', b.ip));
      if (b.country)  lines.push(row('    Country:', b.country));
      if (b.date)     lines.push(row('    Date:', b.date.slice(0,10)));
    });
    lines.push('');
  }

  if (o?.stealers?.length) {
    lines.push(hr());
    lines.push(`  STEALER LOGS (${o.stealer_count})`);
    lines.push(hr());
    o.stealers.forEach((st, i) => {
      lines.push('');
      lines.push(`  [${i+1}] ${(st.url||'─').slice(0,70)}`);
      if (st.username) lines.push(row('    Username:', st.username));
      if (st.password) lines.push(row('    Password:', st.password));
      if (st.pwned_at) lines.push(row('    Date:', st.pwned_at.slice(0,10)));
    });
    lines.push('');
  }

  if (s?.found?.length) {
    lines.push(hr());
    lines.push(`  SOCIAL PROFILES (${s.found_count}/${s.total_checked} checked)`);
    lines.push(hr());
    lines.push('');
    s.found.forEach(p => lines.push(`  ${p.platform.padEnd(22)} ${p.url}`));
    lines.push('');
  }

  if (o?.holehe_domains?.length) {
    lines.push(hr());
    lines.push(`  EMAIL SERVICE REGISTRATIONS (${o.holehe_count})`);
    lines.push(hr());
    lines.push('');
    o.holehe_domains.forEach(d => lines.push(`  • ${d}`));
    lines.push('');
  }

  lines.push(hr('═'));
  lines.push('  END OF REPORT — NexusOSINT v2');
  lines.push(hr('═'));

  const blob = new Blob([lines.join('\n')], {type:'text/plain;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `nexus_${q}_${Date.now()}.txt`;
  a.click();
}

function copyFormatted() { copyAll(); }

function formatBreach(breaches) {
  return breaches.map(b => [
    `=== INTELLIGENCE ===`,
    `Found via     NexusOSINT v2`,
    `Database:     ${b.dbname}`,
    b.email    ? `Email:        ${b.email}`    : null,
    b.username ? `Username:     ${b.username}` : null,
    b.password ? `Password:     ${b.password}` : null,
    b.country  ? `Country:      ${b.country}`  : null,
    `=== END ===`,
    ``
  ].filter(Boolean).join('\n')).join('\n');
}
