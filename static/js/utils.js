// ══════════════════════════════════════════════════════
//  UTILITIES — Helper functions used across modules
// ══════════════════════════════════════════════════════

// ── Query type detection (realtime badge) ──
const TYPE_LABELS = {
  email:'EMAIL', ip:'IP ADDR', domain:'DOMAIN', discord_id:'DISCORD ID',
  phone:'PHONE', username:'USERNAME', steam_id:'STEAM ID'
};

function detectType(q) {
  q = q.trim();
  if (!q) return null;
  if (/^\d{14,19}$/.test(q))                                          return 'discord_id';
  if (/^\+\d{7,15}$/.test(q))                                         return 'phone';
  if (/^[\w.+\-]+@[\w\-]+\.[\w.]{2,}$/.test(q))                       return 'email';
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(q))                              return 'ip';
  if (/^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$/.test(q)) return 'domain';
  return 'username';
}

function onQueryInput(val) {
  const badge = document.getElementById('queryTypeBadge');
  const type = detectType(val);
  if (!val.trim() || !type) {
    badge.className = 'query-type-badge';
    return;
  }
  badge.textContent = TYPE_LABELS[type] || type.toUpperCase();
  badge.className = `query-type-badge visible type-${type}`;
}

// ── Risk scoring ──
function riskLabel(score) {
  if (score >= 75) return ['CRITICAL', '#e84040'];
  if (score >= 50) return ['HIGH',     '#e8822a'];
  if (score >= 25) return ['MEDIUM',   '#f5a623'];
  return ['LOW', '#3ec78c'];
}

// ── HTML escaping ──
function esc(s) {
  if (!s) return '─';
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function escAttr(s) {
  if (!s) return '';
  return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;');
}

// ── URL sanitization ──
function sanitizeImageUrl(url) {
  if (!url) return '';
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' ? url : '';
  } catch (e) {
    return '';
  }
}

// ── Link URL sanitization — blocks javascript:, data:, vbscript: in hrefs ──
function sanitizeUrl(url) {
  if (!url || typeof url !== 'string') return '#';
  try {
    const parsed = new URL(url);
    if (!['https:', 'http:'].includes(parsed.protocol)) {
      console.warn('[NexusOSINT] URL bloqueada (protocolo inválido):', url.slice(0, 80));
      return '#';
    }
    return url;
  } catch (e) {
    return '#';
  }
}

// ── Toast notification ──
function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  // type: 'error' | 'success' | 'info' | 'warn' | true (legacy error)
  t.className = 'toast';
  if (type === true || type === 'error') t.classList.add('toast-error');
  else if (type === 'success') t.classList.add('toast-success');
  else if (type === 'info')    t.classList.add('toast-info');
  else if (type === 'warn')    t.classList.add('toast-warn');
  t.classList.add('visible');
  setTimeout(() => t.classList.remove('visible'), 4000);
}

// ── File size formatter ──
function formatBytes(bytes) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/1048576).toFixed(1) + ' MB';
}