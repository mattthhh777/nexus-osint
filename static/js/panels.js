// ══════════════════════════════════════════════════════
//  PANELS — Scan status, panel visibility, quota UI
// ══════════════════════════════════════════════════════

// ── Scan progress UI ────────────────────────────────
function setScanProgress(pct, label) {
  document.getElementById('scanPct').textContent = pct + '%';
  document.getElementById('scanFill').style.width = pct + '%';
  document.getElementById('scanTitle').textContent = label;
}

let moduleRows = {};
function addModuleRow(label, state) {
  const el = document.getElementById('scanModules');
  const id = 'mod_' + label.replace(/\W/g,'_');
  if (moduleRows[id]) {
    moduleRows[id].className = `scan-module ${state}`;
    return;
  }
  const row = document.createElement('div');
  row.id = id;
  row.className = `scan-module ${state}`;
  row.innerHTML = `<div class="scan-module-dot"></div><span>${esc(label)}</span>`;
  el.appendChild(row);
  moduleRows[id] = row;
  // Mark previous as done
  el.querySelectorAll('.scan-module.active').forEach(r => {
    if (r !== row) r.className = 'scan-module done';
  });
}

function markModuleDone(label) {
  document.querySelectorAll('.scan-module').forEach(r => {
    if (r.textContent.toLowerCase().includes(label.toLowerCase()))
      r.className = 'scan-module done';
  });
}

// ── Panel visibility based on modules_run ───────────
function applyPanelVisibility() {
  // Map panel id → module name(s) that must have run
  const panelModuleMap = {
    'panelBreach':  ['breach'],
    'panelStealer': ['stealer'],
    'panelSocial':  ['sherlock'],
    'panelEmail':   ['holehe'],
    'panelExtras':  ['ip_info', 'subdomain', 'discord', 'steam', 'xbox', 'roblox', 'ghunt', 'victims', 'discord_roblox'],
    'panelExport':  null, // always visible after any search
  };

  const searchRan = modulesRan.size > 0;

  for (const [panelId, mods] of Object.entries(panelModuleMap)) {
    const panel = document.getElementById(panelId);
    if (!panel) continue;
    if (!mods) { // always show
      panel.classList.remove('not-run');
      continue;
    }
    const wasRun = mods.some(m => modulesRan.has(m));
    if (wasRun || !searchRan) {
      panel.classList.remove('not-run');
    } else {
      panel.classList.add('not-run');
      // Remove open state for not-run panels
      panel.classList.remove('open');
      // Add "not run" badge to header
      const badge = panel.querySelector('.panel-not-run-badge');
      if (!badge) {
        const actions = panel.querySelector('.panel-header-actions') || panel.querySelector('.panel-header');
        if (actions) {
          const b = document.createElement('span');
          b.className = 'panel-not-run-badge';
          b.textContent = 'not run';
          actions.insertBefore(b, actions.firstChild);
        }
      }
    }
  }
}

// ── Quota ────────────────────────────────────────────
function updateQuota(data) {
  if (!data.daily_limit) return;
  quotaData = data;
  const pct  = (data.used_today / data.daily_limit) * 100;
  const left = data.left_today;
  const critPct = 100 - pct; // % remaining

  // Quota pill in navbar
  const pill = document.getElementById('quotaPill');
  const fill = document.getElementById('quotaPillFill');
  const txt  = document.getElementById('quotaPillText');
  if (pill) {
    pill.style.display = 'flex';
    fill.style.width   = critPct + '%';
    fill.className     = 'quota-pill-fill' + (pct >= 90 ? ' crit' : pct >= 70 ? ' warn' : '');
    txt.textContent    = left;
    txt.style.color    = pct >= 90 ? 'var(--red)' : pct >= 70 ? 'var(--orange)' : 'var(--amber)';
  }

  // Legacy quota bar inside search (keep for compat)
  const bar = document.getElementById('quotaBar');
  if (bar) {
    bar.style.display = 'flex';
    const qfill = document.getElementById('quotaFill');
    const qtext = document.getElementById('quotaText');
    if (qfill) qfill.style.width = pct + '%';
    if (qfill) qfill.className = 'quota-fill' + (pct >= 90 ? ' crit' : pct >= 70 ? ' warn' : '');
    if (qtext) qtext.textContent = left;
  }
}

// ── Panel toggle helpers ─────────────────────────────
function togglePanel(id) {
  document.getElementById(id).classList.toggle('open');
}

function toggleCopy(id) {
  document.getElementById(id).classList.toggle('visible');
}

function newSearch() {
  document.getElementById('results').classList.remove('visible');
  document.getElementById('searchInput').value = '';
  document.getElementById('searchInput').focus();
  window.scrollTo({top:0, behavior:'smooth'});
  modulesRan = new Set();
  currentResult.breachCursor = '';
  currentResult.breachTotal  = 0;
  breachPage = 0;
  // Reset panels — remove not-run state and any hide-on-zero display override
  ['Breach','Stealer','Social','Email'].forEach(p => {
    const el = document.getElementById('panel'+p);
    if (el) {
      el.classList.add('open');
      el.classList.remove('not-run');
      el.style.display = '';
    }
  });
  // Remove not-run badges
  document.querySelectorAll('.panel-not-run-badge').forEach(b => b.remove());
}
