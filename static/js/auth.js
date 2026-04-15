// ══════════════════════════════════════════════════════
//  AUTH — JWT authentication
// ══════════════════════════════════════════════════════
// VULN-01: token migrado para HttpOnly cookie — zero localStorage
let authUser = null;

// authHeaders mantém apenas Content-Type; cookie é enviado automaticamente pelo browser
function authHeaders() {
  return { 'Content-Type': 'application/json' };
}

async function apiFetch(url, options = {}) {
  options.headers      = { ...authHeaders(), ...(options.headers || {}) };
  options.credentials  = 'include';   // envia/recebe cookie nx_session
  const r = await fetch(url, options);
  if (r.status === 401) {
    authUser = null;
    document.getElementById('authScreen').style.display = 'grid';
    throw new Error('Session expired — please sign in again');
  }
  return r;
}

async function checkAuth() {
  // Verifica sessão via cookie (browser envia automaticamente)
  try {
    const r = await fetch('/api/me', { credentials: 'include' });
    if (r.ok) {
      const data = await r.json();
      authUser = data;
      renderNavUser(data);
      document.getElementById('authScreen').style.display = 'none';
      document.getElementById('app').style.display = 'block';
      return;
    }
  } catch(e) {}

  // Sem cookie válido — verifica se auth é obrigatória
  try {
    const r = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({}),
    });
    const data = await r.json();
    if (data.ok) {
      document.getElementById('authScreen').style.display = 'none';
      document.getElementById('app').style.display = 'block';
      return;
    }
  } catch(e) {}

  document.getElementById('authScreen').style.display = 'grid';
  setTimeout(() => document.getElementById('authUsername')?.focus(), 100);
}

async function submitAuth() {
  const username = document.getElementById('authUsername')?.value?.trim() || 'admin';
  const password = document.getElementById('authInput')?.value || '';
  const btn      = document.getElementById('authBtn');
  const errEl    = document.getElementById('authError');

  if (!password) { errEl.style.display = 'block'; return; }

  btn.disabled    = true;
  btn.textContent = 'Signing in…';
  errEl.style.display = 'none';

  try {
    const r = await fetch('/api/login', {
      method:      'POST',
      headers:     { 'Content-Type': 'application/json' },
      credentials: 'include',           // recebe o Set-Cookie HttpOnly
      body:        JSON.stringify({ username, password }),
    });
    const data = await r.json();

    if (r.ok && data.ok) {
      authUser = { username: data.username, role: data.role };
      document.getElementById('authScreen').style.display = 'none';
      document.getElementById('app').style.display = 'block';
      renderNavUser(authUser);
    } else {
      errEl.style.display = 'block';
    }
  } catch(e) {
    errEl.textContent   = 'Connection error — try again';
    errEl.style.display = 'block';
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Sign In';
  }
}

function renderNavUser(user) {
  const el = document.getElementById('navUserBadge');
  if (el) {
    el.textContent = user.username;
    el.style.display = 'flex';
  }
  // Show admin link for admin users
  const adminLink = document.getElementById('navAdminLink');
  if (adminLink && user.role === 'admin') {
    adminLink.classList.add('visible');
  }
}

async function signOut() {
  authUser = null;
  // Pede ao servidor para apagar o cookie HttpOnly (browser não consegue fazê-lo sozinho)
  await fetch('/api/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
  window.location.reload();
}