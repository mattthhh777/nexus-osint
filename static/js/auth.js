// ══════════════════════════════════════════════════════
//  AUTH — JWT authentication
// ══════════════════════════════════════════════════════
// VULN-01: token migrado para HttpOnly cookie — zero localStorage
let authUser = null;
const AUTH_CHECK_TIMEOUT_MS = 3500;

function showAuthScreen() {
  const authScreen = document.getElementById('authScreen');
  const app = document.getElementById('app');
  if (authScreen) authScreen.style.display = 'grid';
  if (app) app.style.display = 'none';
}

function showAppScreen() {
  const authScreen = document.getElementById('authScreen');
  const app = document.getElementById('app');
  if (authScreen) authScreen.style.display = 'none';
  if (app) app.style.display = 'block';
}

async function fetchWithTimeout(url, options = {}, timeoutMs = AUTH_CHECK_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

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
    showAuthScreen();
    throw new Error('Session expired — please sign in again');
  }
  return r;
}

async function checkAuth() {
  showAuthScreen();
  // Verifica sessão via cookie (browser envia automaticamente)
  try {
    const r = await fetchWithTimeout('/api/me', { credentials: 'include' });
    if (r.ok) {
      const data = await r.json();
      authUser = data;
      renderNavUser(data);
      showAppScreen();
      return;
    }
  } catch(e) {}

  // Sem cookie válido — verifica se auth é obrigatória
  try {
    const r = await fetchWithTimeout('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({}),
    });
    const data = await r.json();
    if (data.ok) {
      showAppScreen();
      return;
    }
  } catch(e) {}

  showAuthScreen();
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
      showAppScreen();
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
  const nameEl = document.getElementById('navUserName');
  if (nameEl) nameEl.textContent = user.username;
  const trigger = document.getElementById('navUserTrigger');
  if (trigger) trigger.style.display = 'flex';
  const adminItem = document.getElementById('userMenuAdmin');
  if (adminItem && user.role === 'admin') adminItem.removeAttribute('hidden');
}

async function signOut() {
  authUser = null;
  // Pede ao servidor para apagar o cookie HttpOnly (browser não consegue fazê-lo sozinho)
  await fetch('/api/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
  window.location.reload();
}
