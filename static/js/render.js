// ══════════════════════════════════════════════════════
//  RENDER — Results rendering and victim file viewer
// ══════════════════════════════════════════════════════
let breachPage = 0;
const BREACH_PAGE_SIZE = 25;
let pwdVisible = {};
let openVictimTrees = {};   // {log_id: treeData}
let openTreeDirs    = {};   // {node_id: bool}

// ── Render results entry point ───────────────────────
function renderResults() {
  const o = currentResult.oathnet;
  const s = currentResult.sherlock;
  const q = currentResult.query;

  const nBreach  = o ? o.breach_count  : 0;
  const nStealer = o ? o.stealer_count : 0;
  const nSocial  = s ? s.found_count   : 0;
  const nHolehe  = o ? o.holehe_count  : 0;
  const nTotal   = nBreach + nStealer + nSocial + nHolehe;

  const risk = Math.min(nBreach*15 + nStealer*20 + nHolehe*3, 100);
  const [rl, rc] = riskLabel(risk);

  // Header
  document.getElementById('resTarget').textContent = q;
  document.getElementById('resSub').textContent =
    `${nTotal} results found · ${currentResult.elapsed || 0}s · ${currentResult.timestamp?.slice(0,16) || ''}`;
  document.getElementById('riskBadge').textContent = `${risk} — ${rl}`;
  document.getElementById('riskBadge').style.cssText =
    `background:${rc}18;border:1px solid ${rc}44;color:${rc}`;

  // Stat grid
  const grid = document.getElementById('statGrid');
  grid.innerHTML = [
    {val:nTotal,   lbl:'Total Found',   bar:'#888',    note:''},
    {val:nBreach,  lbl:'Breaches',      bar:'#e84040', note: nBreach>10?'⚠ High risk':nBreach>0?'⚠ Attention':'✓ Clean', nc: nBreach>10?'var(--red)':nBreach>0?'var(--orange)':'var(--green)'},
    {val:nStealer, lbl:'Stolen Info',   bar:'#e8822a', note: nStealer>0?'🚨 Device compromised':'✓ Clean', nc: nStealer>0?'var(--red)':'var(--green)'},
    {val:nSocial,  lbl:'Social',        bar:'#4a9eff', note: `${s?.total_checked||0} checked`},
    {val:nHolehe,  lbl:'Email Svcs',    bar:'#9b59b6', note:''},
  ].map((c, i) => `
    <div class="stat-card animated" style="animation-delay:${i * 0.07}s">
      <div class="stat-card-bar" style="background:${c.bar}"></div>
      <div class="stat-card-val">${c.val}</div>
      <div class="stat-card-lbl">${c.lbl}</div>
      ${c.note?`<div class="stat-card-note" style="color:${c.nc||'var(--text3)'};">${c.note}</div>`:''}
    </div>`
  ).join('');

  // Apply panel visibility based on modules that ran
  applyPanelVisibility();

  // Render content
  renderBreaches(o);
  renderStealers(o);
  renderSocial(s);
  renderHolehe(o);
  renderExtras();
  renderSpiderFoot();

  document.getElementById('results').classList.add('visible');
  document.getElementById('results').scrollIntoView({behavior:'smooth', block:'start'});
}

// ── Breach severity helper ───────────────────────────
function breachSeverity(b) {
  if (b.password && b.password !== '─' && b.password !== '') return 'critical';
  if (b.email    && b.email    !== '─' && b.email    !== '') return 'high';
  if (b.username && b.username !== '─' && b.username !== '') return 'medium';
  return 'low';
}

// ── Breaches ─────────────────────────────────────────
function renderBreaches(o) {
  breachPage = 0;
  pwdVisible = {};
  const el    = document.getElementById('breachBody');
  const badge = document.getElementById('breachBadge');
  if (!o || !o.breaches || o.breaches.length === 0) {
    badge.textContent = '0';
    el.innerHTML = '<div style="color:var(--green);font-family:var(--mono);font-size:.8rem">✓ No breaches found.</div>';
    return;
  }
  badge.textContent = o.breach_count;
  _renderBreachPage(o, el);
}

function _renderBreachPage(o, el) {
  const end     = (breachPage + 1) * BREACH_PAGE_SIZE;
  const rows    = o.breaches.slice(0, end);
  const hasMore = o.breaches.length > end;
  const total   = o.breach_count;
  const hasIP   = rows.some(b => b.ip    && b.ip    !== '─' && b.ip    !== '');
  const hasPh   = rows.some(b => b.phone && b.phone !== '─' && b.phone !== '');

  const tableRows = rows.map((b, i) => {
    const sev   = breachSeverity(b);
    const hasPwd = b.password && b.password !== '─' && b.password !== '';
    const pwdId  = 'pwd_' + i;
    const isVis  = pwdVisible[pwdId];
    const pwdCell = hasPwd
      ? '<div class="pwd-cell"><span class="pwd-text ' + (isVis ? '' : 'masked') + '" id="' + pwdId + '">' + (isVis ? esc(b.password) : '••••••••') + '</span><button class="pwd-toggle" onclick="togglePwd(\'' + pwdId + '\',\'' + escAttr(b.password) + '\')">' + (isVis ? '🙈' : '👁') + '</button></div>'
      : '<span style="color:var(--text3)">─</span>';
    return '<tr class="sev-' + sev + '"><td><span class="sev-breach-badge">' + sev + '</span></td>'
      + '<td class="val-amber">' + esc(b.dbname) + '</td>'
      + '<td>' + esc(b.email) + '</td>'
      + '<td>' + esc(b.username) + '</td>'
      + '<td>' + pwdCell + '</td>'
      + (hasIP ? '<td class="val-muted">' + esc(b.ip) + '</td>' : '')
      + (hasPh ? '<td class="val-muted">' + esc(b.phone) + '</td>' : '')
      + '<td>' + esc(b.country) + '</td>'
      + '<td class="val-muted">' + esc((b.date||'').slice(0,10)) + '</td></tr>';
  }).join('');

  el.innerHTML = '<table class="data-table"><thead><tr>'
    + '<th>SEV</th><th>Database</th><th>Email</th><th>Username</th><th>Password</th>'
    + (hasIP ? '<th>IP</th>' : '') + (hasPh ? '<th>Phone</th>' : '')
    + '<th>Country</th><th>Date</th>'
    + '</tr></thead><tbody>' + tableRows + '</tbody></table>'
    + '<div style="display:flex;align-items:center;justify-content:space-between;margin-top:10px;font-family:var(--mono);font-size:.7rem;color:var(--text3)">'
    + '<span>Showing ' + rows.length + ' of ' + total.toLocaleString() + (currentResult.breachCursor ? ' (API: ' + currentResult.breachTotal.toLocaleString() + ' total)' : '') + '</span>'
    + '<button class="btn-copy" onclick="revealAllPasswords()" style="font-size:.62rem">👁 Reveal All</button>'
    + '</div>'
    + (hasMore || currentResult.breachCursor
      ? '<button class="load-more-btn" onclick="loadMoreBreaches()">↓ Load more · ' + total.toLocaleString() + ' total</button>'
      : '');
}

function togglePwd(id, plain) {
  pwdVisible[id] = !pwdVisible[id];
  const el = document.getElementById(id);
  if (!el) return;
  if (pwdVisible[id]) {
    el.textContent = plain;
    el.classList.remove('masked');
    if (el.nextElementSibling) el.nextElementSibling.textContent = '🙈';
  } else {
    el.textContent = '••••••••';
    el.classList.add('masked');
    if (el.nextElementSibling) el.nextElementSibling.textContent = '👁';
  }
}

function revealAllPasswords() {
  const o = currentResult.oathnet;
  if (!o?.breaches) return;
  o.breaches.forEach((b, i) => {
    if (b.password && b.password !== '─') {
      const id = 'pwd_' + i;
      pwdVisible[id] = true;
      const el = document.getElementById(id);
      if (el) {
        el.textContent = b.password;
        el.classList.remove('masked');
        if (el.nextElementSibling) el.nextElementSibling.textContent = '🙈';
      }
    }
  });
}

async function loadMoreBreaches() {
  const o      = currentResult.oathnet;
  const cursor = currentResult.breachCursor;
  const query  = currentResult.query;
  const btn    = document.querySelector('.load-more-btn');

  // If we still have local data to show, paginate locally first
  const shownCount = (breachPage + 1) * BREACH_PAGE_SIZE;
  if (shownCount < (o.breaches || []).length) {
    breachPage++;
    const el = document.getElementById('breachBody');
    _renderBreachPage(o, el);
    return;
  }

  // Local data exhausted — fetch next page from API
  if (!cursor || !query) return;

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Loading from API…';
  }

  try {
    const r = await apiFetch('/api/search/more-breaches', {
      method: 'POST',
      body: JSON.stringify({ query, cursor }),
    });

    if (!r.ok) {
      showToast('Failed to load more breaches', true);
      if (btn) { btn.disabled = false; btn.textContent = '↓ Retry'; }
      return;
    }

    const data = await r.json();
    const newBreaches = data.breaches || [];

    if (newBreaches.length === 0) {
      if (btn) { btn.textContent = '✓ All results loaded'; btn.disabled = true; }
      return;
    }

    // Append to existing breaches
    o.breaches       = [...(o.breaches || []), ...newBreaches];
    o.breach_count   = data.results_found || o.breach_count;
    currentResult.breachCursor = data.next_cursor || '';

    breachPage++;
    const el = document.getElementById('breachBody');
    _renderBreachPage(o, el);

    showToast(`Loaded ${newBreaches.length} more breaches`);
  } catch(e) {
    showToast('Error: ' + e.message, true);
    if (btn) { btn.disabled = false; btn.textContent = '↓ Retry'; }
  }
}

// ── Stealers ─────────────────────────────────────────
function renderStealers(o) {
  const el = document.getElementById('stealerBody');
  const badge = document.getElementById('stealerBadge');
  if (!o || !o.stealers || o.stealers.length === 0) {
    badge.textContent = '0';
    el.innerHTML = `<div style="color:var(--green);font-family:var(--mono);font-size:.8rem">✓ No stealer logs found.</div>`;
    return;
  }
  badge.textContent = o.stealer_count;
  el.innerHTML = `
    <div style="color:var(--red);font-family:var(--mono);font-size:.78rem;margin-bottom:12px;padding:8px 12px;background:var(--red-lo);border:1px solid rgba(232,64,64,.2);border-radius:6px">
      🚨 Credentials found in malware stealer logs. A device may be compromised.
    </div>
    <table class="data-table">
      <thead><tr><th>URL</th><th>Username</th><th>Domain</th><th>Date</th></tr></thead>
      <tbody>${o.stealers.slice(0,50).map(s => `
        <tr>
          <td style="max-width:200px">${esc((s.url||'').slice(0,60))}</td>
          <td class="val-amber">${esc(s.username)}</td>
          <td>${esc((s.domain||[]).slice(0,2).join(', '))}</td>
          <td class="val-muted">${esc((s.pwned_at||'').slice(0,10))}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

// ── Social profiles ───────────────────────────────────
function renderSocial(s) {
  const el = document.getElementById('socialBody');
  const badge = document.getElementById('socialBadge');
  if (!s || !s.found || s.found.length === 0) {
    badge.textContent = '0';
    el.innerHTML = `<div style="color:var(--text3);font-family:var(--mono);font-size:.8rem">No profiles found.</div>`;
    return;
  }
  badge.textContent = s.found_count;
  const badges = s.found.map(p =>
    `<a href="${esc(p.url)}" target="_blank" class="social-badge">${p.icon||'🔗'} ${esc(p.platform)}</a>`
  ).join('');
  el.innerHTML = `
    <div class="social-grid">${badges}</div>
    <table class="data-table">
      <thead><tr><th>Platform</th><th>URL</th><th>Category</th></tr></thead>
      <tbody>${s.found.map(p => `
        <tr>
          <td class="val-amber">${esc(p.platform)}</td>
          <td><a href="${esc(p.url)}" target="_blank" style="color:var(--blue);font-size:.76rem">${esc(p.url.slice(0,60))}</a></td>
          <td class="val-muted">${esc(p.category)}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

// ── Holehe email registrations ────────────────────────
function renderHolehe(o) {
  const el = document.getElementById('emailBody');
  const badge = document.getElementById('emailBadge');
  if (!o || !o.holehe_domains || o.holehe_domains.length === 0) {
    badge.textContent = '0';
    el.innerHTML = `<div style="color:var(--text3);font-family:var(--mono);font-size:.8rem">No email registrations found.</div>`;
    return;
  }
  badge.textContent = o.holehe_count;
  el.innerHTML = `<div class="social-grid">
    ${o.holehe_domains.map(d => `<span class="social-badge">📌 ${esc(d)}</span>`).join('')}
  </div>`;
}

// ── Extras panel (IP, subdomains, Discord, gaming) ───
function renderExtras() {
  const el = document.getElementById('extrasBody');
  const parts = [];

  // IP Info
  const ip = currentResult.extras.ip;
  if (ip?.ok && ip.data) {
    const d = ip.data;
    parts.push(`<div style="margin-bottom:16px">
      <div class="section-label" style="margin-bottom:8px">IP Information</div>
      <table class="data-table" style="max-width:500px">
        <tr><th>Country</th><td>${esc(d.country)} (${esc(d.countryCode)})</td></tr>
        <tr><th>City</th><td>${esc(d.city)}</td></tr>
        <tr><th>ISP</th><td>${esc(d.isp)}</td></tr>
        <tr><th>Org</th><td>${esc(d.org)}</td></tr>
        <tr><th>ASN</th><td class="val-muted">${esc(d.as||d.asn||'─')}</td></tr>
        <tr><th>Proxy/VPN</th><td class="${d.proxy?'val-warn':'val-safe'}">${d.proxy?'⚠ Yes':'✓ No'}</td></tr>
        <tr><th>Hosting</th><td class="${d.hosting?'val-warn':'val-muted'}">${d.hosting?'⚠ Yes':'No'}</td></tr>
      </table>
    </div>`);
  }

  // Subdomains
  const subs = currentResult.extras.subdomains;
  if (subs?.ok && subs.data?.length) {
    parts.push(`<div>
      <div class="section-label" style="margin-bottom:8px">Subdomains (${subs.count})</div>
      <div style="font-family:var(--mono);font-size:.76rem;color:var(--text2);columns:3;column-gap:16px">
        ${subs.data.slice(0,90).map(d=>`<div>${esc(d)}</div>`).join('')}
      </div>
    </div>`);
  }

  // Discord — support multiple lookups (auto-extracted from breach)
  const discList = currentResult.extras.discords || (currentResult.extras.discord ? [currentResult.extras.discord] : []);
  for (const disc of discList) {
    if (!disc) continue;
    if (disc.error) {
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:8px">Discord Lookup</div>
        <div style="background:var(--amber-lo);border:1px solid rgba(245,166,35,.2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--amber)">
          ⚠ ${esc(disc.error)}
          ${disc.hint ? `<div style="color:var(--text3);font-size:.68rem;margin-top:6px">${esc(disc.hint)}</div>` : ''}
        </div>
      </div>`);
      continue;
    }
    if (!disc.user) continue;
    const u = disc.user;
    const histList = disc.history?.usernames || [];
    const safeAvatarUrl = sanitizeImageUrl(u.avatar_url);
    const avatarHtml = safeAvatarUrl
      ? `<img class="discord-avatar" src="${safeAvatarUrl}" alt="avatar" data-fallback="true">`
        + `<div class="discord-avatar-placeholder" style="display:none">💬</div>`
      : `<div class="discord-avatar-placeholder">💬</div>`;
    const safeBannerUrl = sanitizeImageUrl(u.banner_url);
    const bannerStyle = safeBannerUrl
      ? `class="discord-banner has-banner" style="background-image:url('${safeBannerUrl}')"`
      : `class="discord-banner"`;
    const histHtml = histList.length
      ? `<div class="discord-history-section">
           <div class="discord-history-label">Username History</div>
           ${histList.map(h => `
             <div class="discord-history-item">
               <span class="discord-history-name">${esc(h.username)}</span>
               <span class="discord-history-date">${esc((h.timestamp||'').slice(0,10))}</span>
             </div>`).join('')}
         </div>` : '';
    const badgesHtml = u.badges?.length
      ? `<div class="discord-badges">${u.badges.map(b=>`<span class="discord-badge">${esc(b)}</span>`).join('')}</div>` : '';

    parts.push(`<div>
      <div class="section-label" style="margin-bottom:10px">Discord Profile</div>
      <div class="discord-card">
        <div class="discord-card-inner">
          <div class="discord-avatar-wrap"><div style="width:56px;height:56px;border-radius:8px;background:var(--bg4);display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0">🟥</div></div>
          <div class="discord-card-content">
            <div class="discord-global-name">${esc(u.global_name || u.username || 'Unknown')}</div>
            <div class="discord-username">@${esc(u.username || '─')}</div>
            <div class="discord-id-row">
              <span>#</span>
              <span class="discord-id-val" onclick="writeClipboard('${esc(u.id||'')}');showToast('Discord ID copied')" title="Click to copy">${esc(u.id || '─')}</span>
            </div>
            ${u.creation_date ? `<div class="discord-created">📅 ${esc(u.creation_date)}</div>` : ''}
            ${badgesHtml}
          </div>
        </div>
        ${histList.length ? `
        <div class="discord-history-section">
          <div class="discord-history-label">Username History (${histList.length})</div>
          <div class="discord-history-list">
            ${histList.map((h,i) => `
              <div class="discord-history-item">
                <span class="discord-history-name">${i===0?'<span style="color:var(--amber)">▶ </span>':''}${esc(h.username)}</span>
                <span class="discord-history-date">${esc((h.timestamp||'').slice(0,10))}</span>
              </div>`).join('')}
          </div>
        </div>` : ''}
        <div class="discord-card-footer">
          <a class="discord-view-btn" href="https://discord.com/users/${esc(u.id||'')}" target="_blank" rel="noopener">
            ↗ Open Profile
          </a>
          <button class="discord-view-btn" onclick="writeClipboard('${esc(u.id||'')}');showToast('ID copied')">
            📋 Copy ID
          </button>
        </div>
      </div>
    </div>`);
  }

  // Steam
  const steam = currentResult.extras.steam;
  if (steam?.ok && steam.data) {
    const d = steam.data;
    const profile = d.response?.players?.[0] || d;
    if (profile.personaname) {
      const safeSteamUrl = sanitizeImageUrl(profile.profileurl);
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:8px">Steam Profile</div>
        <div class="gaming-card">
          <div class="gaming-card-header">
            <span class="gaming-card-icon">🎮</span>
            <div>
              <div class="gaming-card-title">${esc(profile.personaname)}</div>
              <div class="gaming-card-sub">SteamID: ${esc(profile.steamid||'─')}</div>
            </div>
          </div>
          <div class="gaming-kv">
            <div class="gaming-kv-item">
              <span class="gaming-kv-key">Real Name</span>
              <span class="gaming-kv-val">${esc(profile.realname||'─')}</span>
            </div>
            <div class="gaming-kv-item">
              <span class="gaming-kv-key">Country</span>
              <span class="gaming-kv-val">${esc(profile.loccountrycode||'─')}</span>
            </div>
            <div class="gaming-kv-item">
              <span class="gaming-kv-key">Profile URL</span>
              <span class="gaming-kv-val" style="font-size:.7rem">
                ${safeSteamUrl ? `<a href="${safeSteamUrl}" target="_blank" style="color:var(--blue)">${esc(profile.profileurl.slice(0,40))}</a>` : '─'}
              </span>
            </div>
            <div class="gaming-kv-item">
              <span class="gaming-kv-key">Visibility</span>
              <span class="gaming-kv-val">${profile.communityvisibilitystate===3?'Public':'Private'}</span>
            </div>
          </div>
        </div>
      </div>`);
    }
  }

  // Xbox
  const xbox = currentResult.extras.xbox;
  if (xbox?.ok && xbox.data) {
    const d   = xbox.data;
    const m   = d.meta?.meta || d.meta || {};
    const scr = d.meta?.scraper_data || {};
    const gamerscore = scr.gamerscore || m.gamerscore || '─';
    const tier       = m.accounttier  || m.accountTier || '─';
    const rep        = m.xboxonerep   || m.xboxOneRep  || '';
    const gamesPlayed= scr.games_played || 0;
    const gameHistory= scr.game_history || [];
    parts.push(`<div>
      <div class="section-label" style="margin-bottom:8px">Xbox Live Profile</div>
      <div class="gaming-card">
        <div class="gaming-card-header">
          <span class="gaming-card-icon">🎮</span>
          <div style="flex:1">
            <div class="gaming-card-title">${esc(d.username||d.gamertag||d.Gamertag||'Unknown')}</div>
            <div class="gaming-card-sub">Gamertag: ${esc(d.id||d.xuid||'─')}</div>
          </div>
          <div style="text-align:right;font-family:var(--mono);font-size:.72rem">
            <div style="color:var(--amber);font-size:1rem;font-weight:700">${esc(String(gamerscore))}</div>
            <div style="color:var(--text3)">Gamerscore</div>
          </div>
        </div>
        <div class="gaming-kv">
          <div class="gaming-kv-item">
            <span class="gaming-kv-key">Tier</span>
            <span class="gaming-kv-val" style="color:${tier==='Gold'?'var(--amber)':tier==='Silver'?'var(--text2)':'var(--text3)'}">${esc(tier)}</span>
          </div>
          <div class="gaming-kv-item">
            <span class="gaming-kv-key">Reputation</span>
            <span class="gaming-kv-val">${esc(rep||'─')}</span>
          </div>
          <div class="gaming-kv-item">
            <span class="gaming-kv-key">Games Played</span>
            <span class="gaming-kv-val">${esc(String(gamesPlayed))}</span>
          </div>
        </div>
        ${gameHistory.length ? `<div style="border-top:1px solid var(--line);padding:10px 14px">
          <div class="gaming-kv-key" style="margin-bottom:8px">Recent Games</div>
          <div style="display:flex;flex-direction:column;gap:4px">
            ${gameHistory.slice(0,5).map(g => `<div style="display:flex;align-items:center;justify-content:space-between;font-family:var(--mono);font-size:.72rem;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.04)"><span style="color:var(--text)">${esc(g.title||'─')}</span><span style="color:var(--text3)">${g.completionPercentage!=null ? esc(String(g.completionPercentage))+'%' : ''}</span></div>`).join('')}
          </div>
        </div>` : ''}
        <div style="padding:10px 14px 14px">
          <a class="discord-view-btn" href="https://www.xbox.com/play/user/${esc(d.id||d.xuid||'')}"
             target="_blank" rel="noopener" style="font-size:.7rem;text-decoration:none">
            ↗ View Xbox Profile
          </a>
        </div>
      </div>
    </div>`);
  }

  // Roblox
  const roblox = currentResult.extras.roblox;
  if (roblox?.ok && roblox.data) {
    const d = roblox.data;
    // OathNet uses string keys with spaces — support both formats
    const rName    = d['Current Username'] || d.username || d.name || 'Unknown';
    const rId      = d['User ID']          || d.user_id  || d.id   || '─';
    const rDisplay = d['Display Name']     || d.displayName || '─';
    const rJoined  = d['Join Date']        || d.created     || '─';
    const rOld     = d['Old Usernames']    || '';
    const rAvatar  = d['Avatar URL']       || d.avatar      || '';
    const rDesc    = d.description || '';
    const rDiscord = d.Discord || d.discord || '';
    parts.push(`<div>
      <div class="section-label" style="margin-bottom:8px">Roblox Profile</div>
      <div class="gaming-card">
        <div class="gaming-card-header">
          <span class="gaming-card-icon">🟥</span>
          <div>
            <div class="gaming-card-title">${esc(rName)}</div>
            <div class="gaming-card-sub">ID: ${esc(String(rId))}</div>
          </div>
        </div>
        <div class="gaming-kv">
          <div class="gaming-kv-item">
            <span class="gaming-kv-key">Display Name</span>
            <span class="gaming-kv-val">${esc(rDisplay)}</span>
          </div>
          <div class="gaming-kv-item">
            <span class="gaming-kv-key">Joined</span>
            <span class="gaming-kv-val">${esc(rJoined.slice(0,10))}</span>
          </div>
          ${rOld && rOld !== 'None' && rOld !== '' ? `
          <div class="gaming-kv-item" style="grid-column:span 2">
            <span class="gaming-kv-key">Old Usernames</span>
            <span class="gaming-kv-val" style="color:var(--amber)">${esc(Array.isArray(rOld) ? rOld.join(', ') : rOld)}</span>
          </div>` : ''}
          ${d['is_banned'] ? `
          <div class="gaming-kv-item" style="grid-column:span 2">
            <span class="gaming-kv-key">Status</span>
            <span class="gaming-kv-val" style="color:var(--red)">⛔ BANNED</span>
          </div>` : ''}
          ${rDiscord ? `
          <div class="gaming-kv-item">
            <span class="gaming-kv-key">Discord</span>
            <span class="gaming-kv-val" style="color:var(--blue)">${esc(rDiscord)}</span>
          </div>` : ''}
          ${rDesc ? `
          <div class="gaming-kv-item" style="grid-column:span 2">
            <span class="gaming-kv-key">Description</span>
            <span class="gaming-kv-val" style="font-size:.7rem;color:var(--text2)">${esc(rDesc.slice(0,120))}</span>
          </div>` : ''}
        </div>
        ${rId && rId !== '─' ? `
        <div style="padding:10px 14px 14px">
          <a class="discord-view-btn" href="https://www.roblox.com/users/${esc(String(rId))}/profile"
             target="_blank" rel="noopener" style="font-size:.7rem;text-decoration:none">
            ↗ View Roblox Profile
          </a>
        </div>` : ''}
      </div>
    </div>`);
  }

  // GHunt (Google Account)
  const ghunt = currentResult.extras.ghunt;
  if (ghunt) {
    if (!ghunt.ok || ghunt.error) {
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:8px">Google Account (GHunt)</div>
        <div style="background:var(--amber-lo);border:1px solid rgba(245,166,35,.2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--amber)">
          ⚠ ${esc(ghunt.error || 'GHunt lookup failed — upstream API may be unavailable.')}
        </div>
      </div>`);
    } else {
      const d = ghunt.data || {};
      const profile = d.data?.profile || d.profile || {};
      const gaia_id = profile['Gaia ID'] || d.gaia_id || '';
      const name    = profile['Name']    || d.name    || '';
      const pic     = profile['Profile Picture'] || d.profile_pic || '';
      const last_edit = profile['Last Update'] || d.last_update || '';
      const reviews_url = d.data?.maps_reviews || d.maps_reviews || '';
      const photos_url  = d.data?.photos_url   || d.photos_url  || '';
      const safePic = sanitizeImageUrl(pic);
      const safeReviewsUrl = sanitizeImageUrl(reviews_url);
      const safePhotosUrl = sanitizeImageUrl(photos_url);
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:10px">Google Account (GHunt)</div>
        <div class="gaming-card" style="display:flex;gap:14px;align-items:flex-start">
          ${safePic ? `<img src="${safePic}" alt="Google avatar"
            style="width:56px;height:56px;border-radius:50%;border:2px solid var(--line2);flex-shrink:0"
            data-fallback="true">` : ''}
          <div style="flex:1">
            <div style="font-weight:700;font-size:.92rem;color:var(--text);margin-bottom:4px">${esc(name||'Unknown')}</div>
            ${gaia_id ? `<div style="font-family:var(--mono);font-size:.72rem;color:var(--text3)">Gaia ID: <span style="color:var(--amber)">${esc(gaia_id)}</span></div>` : ''}
            ${last_edit ? `<div style="font-family:var(--mono);font-size:.68rem;color:var(--text3);margin-top:4px">Last Update: ${esc(last_edit)}</div>` : ''}
            <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
              ${safeReviewsUrl ? `<a href="${safeReviewsUrl}" target="_blank" class="discord-view-btn" style="font-size:.7rem">📍 Maps Reviews ↗</a>` : ''}
              ${safePhotosUrl  ? `<a href="${safePhotosUrl}"  target="_blank" class="discord-view-btn" style="font-size:.7rem">📷 Photos ↗</a>`        : ''}
            </div>
          </div>
        </div>
      </div>`);
    }
  }

  // Minecraft
  const mc = currentResult.extras.minecraft;
  if (mc) {
    if (!mc.ok || mc.error) {
      const mcErr = mc.error || '';
      const is503 = mcErr.includes('503') || mcErr.includes('server error');
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:8px">Minecraft Account</div>
        <div style="background:var(--bg3);border:1px solid var(--line2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--text3)">
          ${is503
            ? '⚠ Minecraft lookup unavailable — OathNet Mojang endpoint is temporarily down (HTTP 503). Try again later.'
            : '⚠ ' + esc(mcErr || 'Minecraft lookup failed.')}
        </div>
      </div>`);
    } else {
      const d = mc.data || {};
      const uuid = d.uuid || '';
      const currentName = d.username || d['Current Username'] || '';
      const history = d.history || [];
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:10px">Minecraft Account</div>
        <div class="gaming-card">
          <div class="gaming-card-header">
            <span class="gaming-card-icon">⛏</span>
            <div>
              <div class="gaming-card-title">${esc(currentName || 'Unknown')}</div>
              ${uuid ? `<div class="gaming-card-sub">UUID: <span style="color:var(--amber);font-size:.68rem">${esc(uuid)}</span></div>` : ''}
            </div>
          </div>
          ${history.length ? `
          <div class="discord-history-section" style="border-top:1px solid var(--line);padding-top:10px;margin-top:10px">
            <div class="discord-history-label">Username History (${history.length})</div>
            <div class="discord-history-list">
              ${history.map((h,i) => `
                <div class="discord-history-item">
                  <span class="discord-history-name">${i===0?'<span style="color:var(--green)">▶ </span>':''}${esc(h.username||h)}</span>
                  <span class="discord-history-date">${esc((h.changed_at||'Origin').slice(0,10))}</span>
                </div>`).join('')}
            </div>
          </div>` : ''}
        </div>
      </div>`);
    }
  }

  // Victims (Compromised Machines)
  const victims = currentResult.extras.victims;
  if (victims) {
    if (!victims.ok || victims.error) {
      const noResults = victims.items?.length === 0;
      if (!noResults) {
        parts.push(`<div>
          <div class="section-label" style="margin-bottom:8px">Compromised Machines (Victims)</div>
          <div style="background:var(--green-lo);border:1px solid rgba(62,199,140,.2);border-radius:6px;padding:10px 14px;font-family:var(--mono);font-size:.76rem;color:var(--green)">
            ✓ No victim logs found for this target.
          </div>
        </div>`);
      }
    } else if (victims.items?.length) {
      parts.push(`<div>
        <div class="section-label" style="margin-bottom:4px">
          Compromised Machines (Victims)
          <span style="color:var(--red);margin-left:6px;font-family:var(--mono);font-size:.68rem">
            🚨 ${victims.total} machine${victims.total !== 1 ? 's' : ''} compromised
          </span>
        </div>
        <div style="background:var(--red-lo);border:1px solid rgba(232,64,64,.2);border-radius:6px;padding:8px 12px;font-family:var(--mono);font-size:.72rem;color:var(--red);margin-bottom:10px">
          ⚠ Stealer malware logs found. These machines had credentials harvested by malware.
        </div>
        <div id="victimsList">
          ${victims.items.map((v, i) => buildVictimCard(v, i)).join('')}
        </div>
        ${victims.has_more ? `
        <button class="load-more-btn" onclick="loadMoreVictims()">
          ↓ Load more victims (${victims.total - victims.items.length} more)
        </button>` : ''}
      </div>`);
    }
  }

  // Discord → Roblox
  const d2r = currentResult.extras.discord_roblox;
  if (d2r?.ok && d2r.data) {
    const d = d2r.data;
    const rId = d.roblox_id || d['User ID'] || '';
    const name = d.name || d.username || d['Current Username'] || 'Unknown';
    const avatar = d.avatar || d['Avatar URL'] || '';
    parts.push(`<div>
      <div class="section-label" style="margin-bottom:10px">Linked Roblox Account</div>
      <div class="gaming-card" style="display:flex;gap:14px;align-items:flex-start">
        <div style="width:56px;height:56px;border-radius:8px;background:var(--bg4);display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0">🟥</div>
        <div style="flex:1">
          <div style="font-weight:700;font-size:.92rem;color:var(--text)">${esc(name)}</div>
          ${rId ? `<div style="font-family:var(--mono);font-size:.72rem;color:var(--amber);margin-top:2px">ID: ${esc(rId)}</div>` : ''}
          ${d.created && d.created !== 'N/A' ? `<div style="font-family:var(--mono);font-size:.68rem;color:var(--text3);margin-top:4px">Joined: ${esc((d.created||'').slice(0,10))}</div>` : ''}
          ${d.groupCount ? `<div style="font-family:var(--mono);font-size:.68rem;color:var(--text3)">Groups: ${esc(String(d.groupCount))}</div>` : ''}
          ${rId ? `<a class="discord-view-btn" style="margin-top:10px;font-size:.7rem;text-decoration:none;display:inline-flex"
            href="https://www.roblox.com/users/${esc(rId)}/profile" target="_blank" rel="noopener">
            ↗ View Roblox Profile
          </a>` : ''}
        </div>
      </div>
    </div>`);
  }

  el.innerHTML = parts.length
    ? parts.join('<hr style="border-color:var(--line);margin:14px 0">')
    : `<div style="color:var(--text3);font-family:var(--mono);font-size:.8rem">No network or gaming data.</div>`;

  // Attach error handlers to images with data-fallback (replaces inline onerror)
  el.querySelectorAll('img[data-fallback]').forEach(img => {
    img.addEventListener('error', function() {
      this.style.display = 'none';
      const sibling = this.nextElementSibling;
      if (sibling) sibling.style.display = 'flex';
    });
  });
}

// ── SpiderFoot ────────────────────────────────────────
function renderSpiderFoot() {
  const el = document.getElementById('sfBody');
  const badge = document.getElementById('sfBadge');
  const sf = currentResult.extras.sf_final;

  if (!sf) {
    badge.textContent = '─';
    return;
  }
  if (!sf.available) {
    el.innerHTML = `<div style="color:var(--text3);font-family:var(--mono);font-size:.8rem">
      ⚠ SpiderFoot unavailable: ${esc(sf.error||'')}
    </div>`;
    return;
  }

  const results = sf.results || [];
  badge.textContent = results.length;

  if (results.length === 0) {
    el.innerHTML = `<div style="color:var(--green);font-family:var(--mono);font-size:.8rem">✓ No findings.</div>`;
    return;
  }

  el.innerHTML = results.slice(0, 100).map(r => `
    <div class="sf-finding">
      <div class="sf-type">${esc(r.type)}</div>
      <div>
        <div class="sf-data">${esc(r.data?.slice(0,200)||'')}</div>
        <div class="sf-source">${esc(r.source||'')}</div>
      </div>
    </div>`).join('');
}

// ══════════════════════════════════════════════════════
//  VICTIMS — File tree + viewer
// ══════════════════════════════════════════════════════
function buildVictimCard(v, idx) {
  const logId   = v.log_id || '';
  const users   = (v.device_users || []).slice(0,3).map(u => esc(u)).join(', ');
  const ips     = (v.device_ips   || []).slice(0,2).map(u => esc(u)).join(', ');
  const emails  = (v.device_emails|| []).slice(0,2).map(u => esc(u)).join(', ');
  const discs   = (v.discord_ids  || []).slice(0,2).map(u => esc(u)).join(', ');
  const hwids   = (v.hwids        || []).slice(0,1).map(u => esc(u)).join(', ');
  const docs    = v.total_docs || 0;
  const pwned   = (v.pwned_at  || '').slice(0,10);

  return `<div class="victim-card" id="victim-card-${idx}">
    <div class="victim-card-header" onclick="toggleVictimTree('${esc(logId)}', ${idx})">
      <div class="victim-card-left">
        <div class="victim-log-id">
          🚨 <span>${esc(logId)}</span>
          <button class="victim-expand-btn" onclick="event.stopPropagation();toggleVictimTree('${esc(logId)}', ${idx})">
            Browse Files ▾
          </button>
        </div>
        <div class="victim-meta-grid">
          ${users ? `<span class="victim-meta-chip highlight">👤 ${users}</span>` : ''}
          ${ips   ? `<span class="victim-meta-chip">🌐 ${ips}</span>` : ''}
          ${emails? `<span class="victim-meta-chip">📧 ${emails}</span>` : ''}
          ${discs ? `<span class="victim-meta-chip">💬 ${discs}</span>` : ''}
          ${hwids ? `<span class="victim-meta-chip">🔑 ${hwids}</span>` : ''}
          ${pwned ? `<span class="victim-meta-chip">📅 ${esc(pwned)}</span>` : ''}
        </div>
      </div>
      <div class="victim-docs-count">
        <span>${docs.toLocaleString()}</span>
        <span class="victim-docs-label">files</span>
      </div>
    </div>
    <div class="victim-file-tree" id="victim-tree-${idx}" style="display:none">
      <div style="font-family:var(--mono);font-size:.74rem;color:var(--text3)">Loading file tree…</div>
    </div>
  </div>`;
}

async function toggleVictimTree(logId, idx) {
  const treeEl = document.getElementById(`victim-tree-${idx}`);
  if (!treeEl) return;

  const isOpen = treeEl.style.display !== 'none';
  if (isOpen) {
    treeEl.style.display = 'none';
    return;
  }

  treeEl.style.display = 'block';

  // Already loaded
  if (openVictimTrees[logId]) {
    treeEl.innerHTML = renderTree(openVictimTrees[logId].victim_tree, logId, 0);
    return;
  }

  // Fetch manifest
  treeEl.innerHTML = '<div style="font-family:var(--mono);font-size:.74rem;color:var(--text3)">⏳ Loading file tree…</div>';
  try {
    const r = await apiFetch(`/api/victims/${encodeURIComponent(logId)}/manifest`);
    if (!r.ok) {
      const err = await r.json();
      treeEl.innerHTML = `<div style="color:var(--red);font-family:var(--mono);font-size:.74rem">✗ ${esc(err.detail||'Failed')}</div>`;
      return;
    }
    const data = await r.json();
    openVictimTrees[logId] = data;
    treeEl.innerHTML = renderTree(data.victim_tree, logId, 0);
  } catch(e) {
    treeEl.innerHTML = `<div style="color:var(--red);font-family:var(--mono);font-size:.74rem">✗ ${esc(e.message)}</div>`;
  }
}

function renderTree(node, logId, depth) {
  if (!node) return '';
  if (node.type === 'file') {
    const size = formatBytes(node.size_bytes || 0);
    return `<div class="tree-node">
      <div class="tree-file">
        <span style="color:var(--text3);margin-right:4px">📄</span>
        <span class="tree-file-name" title="${esc(node.name)}">${esc(node.name)}</span>
        <span class="tree-file-size">${size}</span>
        <button class="tree-file-btn"
          onclick="viewVictimFile('${esc(logId)}','${esc(node.id)}','${esc(node.name)}')">
          View
        </button>
      </div>
    </div>`;
  }

  // Directory
  const nodeId   = `tree-${logId}-${node.id}`.replace(/[^a-zA-Z0-9-_]/g,'_');
  const children = (node.children || []).sort((a,b) => {
    // dirs first, then files, alphabetical
    if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
    return (a.name||'').localeCompare(b.name||'');
  });

  if (!children.length) return '';

  return `<div class="tree-node">
    <div class="tree-dir" onclick="toggleTreeDir('${nodeId}')">
      <span class="tree-dir-icon" id="icon-${nodeId}">▶</span>
      <span>📁 ${esc(node.name || '/')}</span>
      <span style="font-size:.62rem;color:var(--text3);margin-left:4px">(${children.length})</span>
    </div>
    <div class="tree-children" id="${nodeId}" style="display:none">
      ${children.map(c => renderTree(c, logId, depth+1)).join('')}
    </div>
  </div>`;
}

function toggleTreeDir(nodeId) {
  const el   = document.getElementById(nodeId);
  const icon = document.getElementById(`icon-${nodeId}`);
  if (!el) return;
  const isOpen = el.style.display !== 'none';
  el.style.display   = isOpen ? 'none' : 'block';
  if (icon) icon.textContent = isOpen ? '▶' : '▼';
}

async function viewVictimFile(logId, fileId, fileName) {
  const overlay  = document.getElementById('fileViewerOverlay');
  const titleEl  = document.getElementById('fileViewerTitle');
  const contentEl= document.getElementById('fileViewerContent');
  const metaEl   = document.getElementById('fileViewerMeta');

  titleEl.textContent   = fileName;
  contentEl.textContent = '⏳ Loading…';
  metaEl.textContent    = '';
  overlay.classList.add('visible');

  try {
    const r = await apiFetch(
      `/api/victims/${encodeURIComponent(logId)}/files/${encodeURIComponent(fileId)}`
    );
    if (!r.ok) {
      const err = await r.json().catch(() => ({detail:'Failed'}));
      contentEl.textContent = `✗ Error: ${err.detail||'File not found'}`;
      return;
    }
    const text = await r.text();
    contentEl.textContent = text || '(empty file)';
    metaEl.textContent    = `${text.split('\n').length} lines · ${formatBytes(text.length)}`;
  } catch(e) {
    contentEl.textContent = `✗ ${e.message}`;
  }
}

function closeFileViewer() {
  document.getElementById('fileViewerOverlay').classList.remove('visible');
}

function copyFileContent() {
  const text = document.getElementById('fileViewerContent').textContent;
  writeClipboard(text);
  showToast('File content copied');
}

async function loadMoreVictims() {
  const v = currentResult.extras.victims;
  if (!v?.next_cursor) return;
  const q = currentResult.query;
  try {
    const r = await apiFetch(`/api/victims/search?q=${encodeURIComponent(q)}&cursor=${encodeURIComponent(v.next_cursor)}&page_size=10`);
    const data = await r.json();
    const newItems = data.items || [];
    v.items        = [...v.items, ...newItems];
    v.next_cursor  = data.next_cursor || '';
    v.has_more     = data.meta?.has_more || false;
    // Re-render victims list
    const list = document.getElementById('victimsList');
    if (list) {
      const startIdx = v.items.length - newItems.length;
      list.innerHTML += newItems.map((vi, i) => buildVictimCard(vi, startIdx + i)).join('');
    }
  } catch(e) {
    showToast('Failed to load more victims', true);
  }
}

// Close file viewer on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeFileViewer();
});
