// ══════════════════════════════════════════════════════
//  STATE — Global variables and constants
// ══════════════════════════════════════════════════════
let mode = 'auto';
let sfMode = 'passive';
let selectedMods = new Set();
let activeCat = 'Data Leaks';
let currentResult = {};
let history = JSON.parse(localStorage.getItem('nx_history') || '[]');
let quotaData = null;
let modulesRan = new Set(); // tracks which modules actually ran in current search

const CATEGORIES = {
  'Data Leaks':        {icon:'🛡', mods:['breach','stealer']},
  'Social & Gaming':   {icon:'🎮', mods:['sherlock','discord']},
  'Email Intelligence':{icon:'📧', mods:['holehe','ghunt']},
  'Network':           {icon:'🌐', mods:['ip_info','subdomain']},
  'Gaming Platforms':  {icon:'🕹', mods:['steam','xbox','roblox','minecraft','discord_roblox']},
  'Deep OSINT':        {icon:'🔬', mods:['victims']},
  'SpiderFoot':        {icon:'🕷', mods:['spiderfoot']},
};

const MOD_LABELS = {
  breach:'Breaches', stealer:'Stealer', sherlock:'Sherlock',
  discord:'Discord', holehe:'Holehe', ip_info:'IP Info',
  subdomain:'Subdomains', spiderfoot:'SpiderFoot',
  steam:'Steam', xbox:'Xbox', roblox:'Roblox',
  ghunt:'GHunt (Google)', minecraft:'Minecraft',
  victims:'Victims (Stealer Logs)', discord_roblox:'Discord→Roblox',
};

// ══════════════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════════════
async function init() {
  await checkAuth();
  buildCatChips();
  buildModChips();
  checkSpiderFoot();
  renderHistory();
  updateCasesBadge();
  selectedMods = new Set(['breach','stealer']);
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      document.getElementById('searchInput').focus();
    }
    if (e.key === 'Escape') {
      const panel = document.getElementById('casesPanel');
      if (panel.classList.contains('visible')) toggleCasesPanel();
    }
  });
}

// ══════════════════════════════════════════════════════
//  DELEGATION — data-action click dispatcher
//  Single listener on document replaces all onclick= attrs.
//  Modules call registerAction(name, fn) at load time.
//  bootstrap.js calls initDelegation() to activate.
//
//  Registered actions (kebab-case):
//    submit-auth, sign-out, toggle-cases-panel, toggle-panel,
//    start-search, set-mode, set-sf-mode, select-cat, toggle-mod,
//    new-search, save-case, copy-all, export-pdf, export-json,
//    export-csv, export-txt, copy-section, select-copy-area,
//    toggle-pwd, reveal-all-passwords, load-more-breaches,
//    copy-discord-id, load-more-victims, toggle-victim-tree,
//    view-victim-file, toggle-tree-dir, close-file-viewer,
//    copy-file-content, rerun-search, load-case, delete-case,
//    clear-all-cases
// ══════════════════════════════════════════════════════
const ACTIONS = Object.create(null);

function registerAction(name, handler) {
  ACTIONS[name] = handler;
}

function handleAction(ev) {
  const el = ev.target.closest('[data-action]');
  if (!el) return;
  const name = el.dataset.action;
  const fn = ACTIONS[name];
  if (!fn) { console.warn('NexusOSINT: unregistered action:', name); return; }
  ev.preventDefault();
  fn(el, el.dataset, ev);
}

function initDelegation() {
  document.addEventListener('click', handleAction);
}
