// ══════════════════════════════════════════════════════
//  ADMIN — NexusOSINT Admin Panel JavaScript
//  Extracted from admin.html inline <script> block.
//  Phase 09 Plan 03 — Wave 3 CSP preparation.
// ══════════════════════════════════════════════════════

// ── State ──────────────────────────────────────────────────────────────────
// VULN-01: zero localStorage — autenticação exclusivamente via cookie HttpOnly
let currentUser = null;
let logsOffset  = 0;
const LOGS_LIMIT = 25;

// ── API ───────────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  opts.headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  };
  opts.credentials = 'include';   // envia cookie nx_session automaticamente
  const r = await fetch(path, opts);
  if (r.status === 401 || r.status === 403) {
    window.location.reload();
    throw new Error('Unauthorized');
  }
  return r;
}

// ── Auth ──────────────────────────────────────────────────────────────────
async function init() {
  try {
    const r = await fetch('/api/me', { credentials: 'include' });
    if (r.ok) {
      const u = await r.json();
      if (u.role !== 'admin') {
        document.getElementById('loginError').style.display  = 'block';
        document.getElementById('loginError').textContent    = 'Admin access required.';
        document.getElementById('loginScreen').style.display = 'grid';
        return;
      }
      currentUser = u;
      showApp();
      return;
    }
  } catch(e) {}
  document.getElementById('loginScreen').style.display = 'grid';
}

async function doLogin() {
  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;
  const btn      = document.getElementById('loginBtn');
  const err      = document.getElementById('loginError');

  btn.disabled    = true;
  btn.textContent = 'Signing in…';
  err.style.display = 'none';

  try {
    const r = await fetch('/api/login', {
      method:      'POST',
      headers:     { 'Content-Type': 'application/json' },
      credentials: 'include',       // recebe Set-Cookie HttpOnly do backend
      body:        JSON.stringify({ username, password }),
    });
    const data = await r.json();
    if (r.ok && data.ok) {
      if (data.role !== 'admin') {
        err.textContent   = 'Admin access required.';
        err.style.display = 'block';
        return;
      }
      currentUser = { username: data.username, role: data.role };
      showApp();
    } else {
      err.style.display = 'block';
    }
  } catch(e) {
    err.textContent   = 'Connection error.';
    err.style.display = 'block';
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Sign In';
  }
}

function showApp() {
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('app').style.display         = 'block';
  document.getElementById('navUser').textContent       = currentUser.username;
  loadDashboard();
}

async function signOut() {
  currentUser = null;
  await fetch('/api/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
  window.location.reload();
}

// ── Navigation ────────────────────────────────────────────────────────────
function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('section-' + name).classList.add('active');
  document.getElementById('nav-' + name).classList.add('active');

  if (name === 'dashboard') loadDashboard();
  if (name === 'logs')      { logsOffset = 0; loadLogs(); }
  if (name === 'users')     loadUsers();
  if (name === 'uptime')    checkUptime();
  if (name === 'health')    loadHealth();
}

// ── Dashboard ─────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const r    = await api('/api/admin/stats');
    const data = await r.json();

    document.getElementById('statToday').textContent  = data.searches_today ?? 0;
    document.getElementById('statTotal').textContent  = data.searches_total ?? 0;
    document.getElementById('statUsers').textContent  = data.active_users ?? 0;
    document.getElementById('statQuota').textContent  = data.quota_left ?? '─';
    if (data.quota_used != null && data.quota_limit != null) {
      const detail = document.getElementById('statQuotaDetail');
      if (detail) detail.textContent = data.quota_used + ' used of ' + data.quota_limit;
    }
    document.getElementById('dashLastUpdate').textContent = 'Last updated: ' + new Date().toLocaleTimeString();

    // Top queries
    const tqBody = document.getElementById('topQueriesBody');
    if (data.top_queries_today?.length) {
      tqBody.innerHTML = data.top_queries_today.map(q =>
        `<tr><td class="td-amber">${esc(q.query)}</td><td class="td-mono">${q.cnt}</td></tr>`
      ).join('');
    } else {
      tqBody.innerHTML = '<tr><td colspan="2" class="empty-state">No searches today</td></tr>';
    }

    // Per user
    const puBody = document.getElementById('perUserBody');
    if (data.searches_per_user?.length) {
      puBody.innerHTML = data.searches_per_user.map(u =>
        `<tr><td class="td-amber">${esc(u.username)}</td><td class="td-mono">${u.cnt}</td></tr>`
      ).join('');
    } else {
      puBody.innerHTML = '<tr><td colspan="2" class="empty-state">No activity today</td></tr>';
    }

    // Chart — last 7 days from audit log
    loadChart();

  } catch(e) {
    console.error('Dashboard error:', e);
  }
}

async function loadChart() {
  try {
    // Get last 7 days of logs
    const r    = await api('/api/admin/logs?limit=500');
    const data = await r.json();
    const logs = data.logs || [];

    // Group by day
    const days = {};
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      days[key] = 0;
    }
    logs.forEach(l => {
      const day = (l.ts || '').slice(0, 10);
      if (day in days) days[day]++;
    });

    const vals   = Object.values(days);
    const keys   = Object.keys(days);
    const maxVal = Math.max(...vals, 1);
    const total  = vals.reduce((a, b) => a + b, 0);

    document.getElementById('chartTotal').textContent = total + ' total (7d)';

    const bars = document.getElementById('chartBars');
    bars.innerHTML = vals.map((v, i) => {
      const pct  = Math.round((v / maxVal) * 100);
      const date = keys[i].slice(5); // MM-DD
      // Note: style="height:..." on chart bars is set dynamically — CSP-compliant (JS inline style)
      return `<div class="chart-bar" style="height:${Math.max(pct,2)}%">
        <div class="chart-bar-tooltip">${date}: ${v}</div>
      </div>`;
    }).join('');
  } catch(e) {}
}

// ── Logs ──────────────────────────────────────────────────────────────────
async function loadLogs() {
  const user  = document.getElementById('logFilterUser').value.trim();
  const query = document.getElementById('logFilterQuery').value.trim();

  let url = `/api/admin/logs?limit=${LOGS_LIMIT}&offset=${logsOffset}`;
  if (user)  url += `&username=${encodeURIComponent(user)}`;

  try {
    const r    = await api(url);
    const data = await r.json();
    let logs   = data.logs || [];

    // Client-side query filter
    if (query) logs = logs.filter(l => l.query?.toLowerCase().includes(query.toLowerCase()));

    const body = document.getElementById('logsBody');
    if (!logs.length) {
      body.innerHTML = '<tr><td colspan="10" class="empty-state">No logs found</td></tr>';
    } else {
      body.innerHTML = logs.map(l => {
        const ts      = (l.ts || '').replace('T', ' ').slice(0, 19);
        const modules = (l.modules_run || '').split(',').filter(Boolean).length;
        const elapsed = l.elapsed_s ? `${l.elapsed_s}s` : '─';
        return `<tr>
          <td class="td-muted td-nowrap">${esc(ts)}</td>
          <td class="td-amber">${esc(l.username)}</td>
          <td class="td-ellipsis">${esc(l.query)}</td>
          <td><span class="badge badge-gray">${esc(l.query_type || '─')}</span></td>
          <td class="td-muted">${modules}m</td>
          <td class="${l.breach_count > 0 ? 'td-red' : 'td-muted'}">${l.breach_count ?? 0}</td>
          <td class="${l.stealer_count > 0 ? 'td-red' : 'td-muted'}">${l.stealer_count ?? 0}</td>
          <td class="td-muted">${l.social_count ?? 0}</td>
          <td class="td-muted td-ip">${esc((l.ip || '─').split(',')[0])}</td>
          <td class="td-muted">${elapsed}</td>
        </tr>`;
      }).join('');
    }

    const hasMore = logs.length === LOGS_LIMIT;
    document.getElementById('logsPaginationInfo').textContent =
      `Showing ${logsOffset + 1}–${logsOffset + logs.length}`;
    document.getElementById('logsPrev').disabled = logsOffset === 0;
    document.getElementById('logsNext').disabled = !hasMore;
  } catch(e) {
    console.error('Logs error:', e);
  }
}

function logsPage(dir) {
  logsOffset = Math.max(0, logsOffset + dir * LOGS_LIMIT);
  loadLogs();
}

async function exportLogsCSV() {
  try {
    const r    = await api('/api/admin/logs?limit=10000');
    const data = await r.json();
    const logs = data.logs || [];

    const rows = [['Timestamp','Username','IP','Query','Type','Mode','Modules','Breaches','Stealers','Social','Elapsed']];
    logs.forEach(l => rows.push([
      l.ts, l.username, l.ip, l.query, l.query_type,
      l.mode, l.modules_run, l.breach_count, l.stealer_count,
      l.social_count, l.elapsed_s
    ]));

    const csv  = rows.map(r => r.map(v => `"${String(v||'').replace(/"/g,'""')}"`).join(',')).join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `nexus_logs_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
  } catch(e) {
    showToast('Export failed: ' + e.message, true);
  }
}

// ── Users ─────────────────────────────────────────────────────────────────
async function loadUsers() {
  try {
    const r    = await api('/api/admin/users');
    const data = await r.json();
    const body = document.getElementById('usersBody');

    const entries = Object.entries(data);
    if (!entries.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-state">No users found</td></tr>';
      return;
    }

    body.innerHTML = entries.map(([uname, u]) => {
      const active  = u.active !== false;
      const created = (u.created_at || '').slice(0, 10);
      const isAdmin = u.role === 'admin';
      return `<tr>
        <td class="td-amber td-bold">${esc(uname)}</td>
        <td><span class="badge ${isAdmin ? 'badge-red' : 'badge-blue'}">${esc(u.role || 'user')}</span></td>
        <td class="td-muted">${esc(created)}</td>
        <td><span class="status-dot ${active ? 'green' : 'red'}"></span>${active ? 'Active' : 'Inactive'}</td>
        <td>
          ${active && uname !== currentUser?.username
            ? `<button class="btn btn-danger btn-sm" data-action="deactivate-user" data-username="${esc(uname)}">Deactivate</button>`
            : '<span class="td-muted">─</span>'}
        </td>
      </tr>`;
    }).join('');
  } catch(e) {
    console.error('Users error:', e);
  }
}

function openCreateUser() {
  document.getElementById('newUsername').value = '';
  document.getElementById('newPassword').value = '';
  document.getElementById('newRole').value = 'user';
  document.getElementById('createUserModal').classList.add('visible');
  setTimeout(() => document.getElementById('newUsername').focus(), 100);
}

function closeModal() {
  document.getElementById('createUserModal').classList.remove('visible');
}

async function createUser() {
  const username = document.getElementById('newUsername').value.trim();
  const password = document.getElementById('newPassword').value;
  const role     = document.getElementById('newRole').value;

  if (!username || !password) {
    showToast('Username and password required', true); return;
  }

  try {
    const r = await api('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify({ username, password, role }),
    });
    const data = await r.json();
    if (r.ok) {
      closeModal();
      showToast(`User "${username}" created successfully`);
      loadUsers();
    } else {
      showToast(data.detail || 'Failed to create user', true);
    }
  } catch(e) {
    showToast('Error: ' + e.message, true);
  }
}

async function deactivateUser(username) {
  if (!confirm(`Deactivate user "${username}"? They will lose access immediately.`)) return;
  try {
    const r = await api(`/api/admin/users/${encodeURIComponent(username)}`, { method: 'DELETE' });
    if (r.ok) {
      showToast(`User "${username}" deactivated`);
      loadUsers();
    } else {
      const d = await r.json();
      showToast(d.detail || 'Failed', true);
    }
  } catch(e) {
    showToast('Error: ' + e.message, true);
  }
}

// ── Uptime ────────────────────────────────────────────────────────────────
async function checkUptime() {
  const services = [
    { name: 'NexusOSINT API',    url: '/health',                    key: 'api' },
    { name: 'Login Endpoint',    url: '/api/login',                 key: 'login', method: 'POST' },
    { name: 'SpiderFoot',        url: '/api/spiderfoot/status',     key: 'sf' },
  ];

  const container = document.getElementById('uptimeServices');
  container.innerHTML = '<div class="empty-state p-12">Checking services…</div>';

  const results = await Promise.all(services.map(async s => {
    const start = Date.now();
    try {
      const r = await api(s.url, { method: s.method || 'GET',
        body: s.method === 'POST' ? '{}' : undefined });
      const ms = Date.now() - start;
      // 200/201=ok, 401=auth required (endpoint alive), 422=validation error (endpoint alive)
      const ok = r.ok || r.status === 401 || r.status === 405 || r.status === 422;
      return { ...s, ok, ms, status: r.status };
    } catch(e) {
      return { ...s, ok: false, ms: Date.now() - start, error: e.message };
    }
  }));

  container.innerHTML = results.map(r => `
    <div class="uptime-service-card">
      <div>
        <div class="uptime-name">${esc(r.name)}</div>
        <div class="uptime-url">${esc(r.url)}</div>
      </div>
      <div class="uptime-status">
        <span class="status-dot ${r.ok ? 'green' : 'red'}"></span>
        <span class="${r.ok ? 'text-green' : 'text-critical'}">${r.ok ? 'Online' : 'Down'}</span>
        <span class="text-dim td-xs">${r.ms}ms</span>
      </div>
    </div>`).join('');
}

function copyKumaCmd() {
  const cmd = document.getElementById('kumaCmd').textContent;
  navigator.clipboard.writeText(cmd).catch(() => {});
  showToast('Command copied to clipboard');
}

// ── Health ────────────────────────────────────────────────────────────────
async function loadHealth() {
  try {
    const r    = await api('/health');
    const data = await r.json();

    document.getElementById('apiHealthBody').innerHTML = `
      <div class="health-kv">
        <div><span class="text-dim">Status:</span> <span class="badge badge-green">${esc(data.status)}</span></div>
        <div><span class="text-dim">Version:</span> <span class="text-amber">${esc(data.version)}</span></div>
        <div><span class="text-dim">Time:</span> <span class="text-secondary">${esc((data.timestamp||'').replace('T',' ').slice(0,19))}</span></div>
      </div>`;
  } catch(e) {
    document.getElementById('apiHealthBody').innerHTML =
      '<div class="empty-state text-critical">API unreachable</div>';
  }

  // Load perf data
  try {
    const r    = await api('/api/admin/logs?limit=50');
    const data = await r.json();
    const logs = (data.logs || []).filter(l => l.elapsed_s > 0);

    const perfBody = document.getElementById('perfBody');
    if (!logs.length) {
      perfBody.innerHTML = '<tr><td colspan="6" class="empty-state">No data</td></tr>';
    } else {
      perfBody.innerHTML = logs.slice(0, 25).map(l => {
        const elapsed = parseFloat(l.elapsed_s) || 0;
        const color = elapsed > 15 ? 'td-red' : elapsed > 8 ? 'td-amber' : 'td-green';
        return `<tr>
          <td class="td-ellipsis td-narrow">${esc(l.query)}</td>
          <td><span class="badge badge-gray">${esc(l.mode || '─')}</span></td>
          <td class="${color}">${elapsed}s</td>
          <td class="${l.breach_count > 0 ? 'td-red' : 'td-muted'}">${l.breach_count ?? 0}</td>
          <td class="${l.stealer_count > 0 ? 'td-red' : 'td-muted'}">${l.stealer_count ?? 0}</td>
          <td class="td-muted">${esc((l.ts||'').slice(11,19))}</td>
        </tr>`;
      }).join('');
    }
  } catch(e) {}
}

// ── Utils ─────────────────────────────────────────────────────────────────
function esc(s) {
  if (!s && s !== 0) return '─';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function showToast(msg, isError = false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast visible' + (isError ? ' error' : '');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('visible'), 3500);
}

// ── Delegation — admin-specific data-action dispatcher ─────────────────
const ADMIN_ACTIONS = Object.create(null);
function adminRegisterAction(name, handler) { ADMIN_ACTIONS[name] = handler; }
function adminHandleAction(ev) {
  const el = ev.target.closest('[data-action]');
  if (!el) return;
  const fn = ADMIN_ACTIONS[el.dataset.action];
  if (!fn) { console.warn('NexusOSINT Admin: unregistered action:', el.dataset.action); return; }
  ev.preventDefault();
  fn(el, el.dataset, ev);
}

adminRegisterAction('do-login',          function () { doLogin(); });
adminRegisterAction('sign-out-admin',    function () { signOut(); });
adminRegisterAction('show-section',      function (el, ds) { showSection(ds.section); });
adminRegisterAction('export-logs-csv',   function () { exportLogsCSV(); });
adminRegisterAction('load-logs',         function () { loadLogs(); });
adminRegisterAction('logs-page',         function (el, ds) { logsPage(Number(ds.dir)); });
adminRegisterAction('open-create-user',  function () { openCreateUser(); });
adminRegisterAction('check-uptime',      function () { checkUptime(); });
adminRegisterAction('copy-kuma-cmd',     function () { copyKumaCmd(); });
adminRegisterAction('close-modal',       function () { closeModal(); });
adminRegisterAction('create-user',       function () { createUser(); });
adminRegisterAction('deactivate-user',   function (el, ds) { deactivateUser(ds.username); });

document.addEventListener('click', adminHandleAction);

// ── Keyboard shortcuts ────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
  if ((e.ctrlKey || e.metaKey) && e.key === 'r') { e.preventDefault(); loadDashboard(); }
});

document.getElementById('loginPass')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') doLogin();
});

document.getElementById('newPassword')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') createUser();
});

// ── Log filter inputs — oninput converted to addEventListener ─────────────
document.getElementById('logFilterUser')?.addEventListener('input', () => loadLogs());
document.getElementById('logFilterQuery')?.addEventListener('input', () => loadLogs());

// ── Boot ──────────────────────────────────────────────────────────────────
init();
