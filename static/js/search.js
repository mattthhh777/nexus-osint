// ══════════════════════════════════════════════════════
//  SPIDERFOOT STATUS
// ══════════════════════════════════════════════════════
async function checkSpiderFoot() {
  try {
    // Use plain fetch — apiFetch re-shows authScreen on 401 which causes a
    // race condition when this runs before the user has authenticated.
    const r = await fetch('/api/spiderfoot/status', { credentials: 'include' });
    if (!r.ok) return;
    const data = await r.json();
    const dot = document.getElementById('sfDot');
    const lbl = document.getElementById('sfLabel');
    if (data.available) {
      dot.classList.remove('offline');
      dot.classList.add('online');
      lbl.textContent = 'spiderfoot online';
    } else {
      dot.classList.remove('online');
      dot.classList.add('offline');
      lbl.textContent = 'spiderfoot offline';
    }
  } catch(e) {}
}

// ══════════════════════════════════════════════════════
//  MODE & CHIPS
// ══════════════════════════════════════════════════════
function setMode(m) {
  mode = m;
  document.getElementById('btnAuto').classList.toggle('active', m === 'auto');
  document.getElementById('btnManual').classList.toggle('active', m === 'manual');
  document.getElementById('manualSection').classList.toggle('visible', m === 'manual');
}

function setSfMode(m, el) {
  sfMode = m;
  document.querySelectorAll('#sfOptions .chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
}

function buildCatChips() {
  const el = document.getElementById('catChips');
  el.innerHTML = Object.entries(CATEGORIES).map(([name, cat]) =>
    `<button class="chip cat-chip ${name===activeCat?'active':''}"
      data-action="select-cat" data-name="${esc(name)}">${cat.icon} ${esc(name)}</button>`
  ).join('');
}

function selectCat(name, el) {
  activeCat = name;
  document.querySelectorAll('#catChips .chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  // Select all mods of this category
  selectedMods = new Set(CATEGORIES[name].mods);
  buildModChips();
  // Show SpiderFoot options if SpiderFoot selected
  document.getElementById('sfOptions').classList.toggle('visible', selectedMods.has('spiderfoot'));
}

function buildModChips() {
  const mods = CATEGORIES[activeCat].mods;
  const el = document.getElementById('modChips');
  el.innerHTML = mods.map(m =>
    `<button class="chip ${selectedMods.has(m)?'active':''}"
      data-action="toggle-mod" data-mod="${esc(m)}">${esc(MOD_LABELS[m]||m)}</button>`
  ).join('');
}

function toggleMod(m, el) {
  if (selectedMods.has(m)) selectedMods.delete(m);
  else selectedMods.add(m);
  el.classList.toggle('active', selectedMods.has(m));
  document.getElementById('sfOptions').classList.toggle('visible', selectedMods.has('spiderfoot'));
}

// ══════════════════════════════════════════════════════
//  SEARCH
// ══════════════════════════════════════════════════════
async function startSearch() {
  const query = document.getElementById('searchInput').value.trim();
  if (!query) return;

  // Reset UI
  document.getElementById('results').classList.remove('visible');
  document.getElementById('scanStatus').classList.add('visible');
  document.getElementById('scanModules').innerHTML = '';
  document.getElementById('searchBtn').disabled = true;
  setScanProgress(0, 'Initializing…');

  currentResult = { query, oathnet: null, sherlock: null, extras: {} };

  const body = {
    query,
    mode: mode === 'auto' ? 'automated' : 'manual',
    modules: [...selectedMods],
    spiderfoot_mode: sfMode,
  };

  try {
    const resp = await apiFetch('/api/search', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const evt = JSON.parse(line.slice(6));
            handleEvent(evt);
          } catch(e) {}
        }
      }
    }
  } catch(e) {
    showToast('Search failed: ' + e.message);
    document.getElementById('scanStatus').classList.remove('visible');
  }

  document.getElementById('searchBtn').disabled = false;
}

function handleEvent(evt) {
  switch(evt.type) {
    case 'start':
      modulesRan = new Set();
      addModuleRow(evt.query_type, 'active');
      break;
    case 'progress':
      setScanProgress(evt.pct, evt.label);
      addModuleRow(evt.label, 'active');
      break;
    case 'oathnet':
      currentResult.oathnet = evt;
      currentResult.breachCursor = evt.next_cursor || '';
      currentResult.breachTotal  = evt.results_found || evt.breach_count || 0;
      updateQuota(evt);
      markModuleDone('Breach');
      break;
    case 'sherlock':
      currentResult.sherlock = evt;
      markModuleDone('Sherlock');
      break;
    case 'discord':
      // Accumulate multiple discord lookups (auto-extracted from breach data)
      if (!currentResult.extras.discords) currentResult.extras.discords = [];
      currentResult.extras.discords.push(evt);
      // Keep single for compat
      currentResult.extras.discord = evt;
      break;
    case 'ip_info':
      currentResult.extras.ip = evt;
      break;
    case 'subdomains':
      currentResult.extras.subdomains = evt;
      break;
    case 'spiderfoot':
    case 'spiderfoot_started':
    case 'spiderfoot_progress':
      currentResult.extras.spiderfoot = (currentResult.extras.spiderfoot || []);
      if (evt.type === 'spiderfoot') currentResult.extras.sf_final = evt;
      break;
    case 'steam':
      currentResult.extras.steam = evt;
      break;
    case 'xbox':
      currentResult.extras.xbox = evt;
      break;
    case 'roblox':
      currentResult.extras.roblox = evt;
      break;
    case 'ghunt':
      currentResult.extras.ghunt = evt;
      break;
    case 'minecraft':
      currentResult.extras.minecraft = evt;
      break;
    case 'victims':
      currentResult.extras.victims = evt;
      break;
    case 'discord_roblox':
      currentResult.extras.discord_roblox = evt;
      break;
    case 'module_error':
      addModuleRow(`⚠ ${evt.module}: ${evt.error.slice(0,40)}`, 'error');
      break;
    case 'done':
      currentResult.elapsed = evt.elapsed_s;
      currentResult.timestamp = evt.timestamp;
      modulesRan = new Set(evt.modules_run || []);
      setScanProgress(100, 'Complete');
      setTimeout(() => {
        document.getElementById('scanStatus').classList.remove('visible');
        renderResults();
        saveHistory();
      }, 600);
      break;
  }
}
