// ══════════════════════════════════════════════════════
//  BOOTSTRAP — App initialization for index.html
//  Runs last (after all module scripts at end of <body>).
//  Registers all data-action handlers, activates delegation,
//  then starts the app.
// ══════════════════════════════════════════════════════

// ── Auth actions ──────────────────────────────────────
registerAction('submit-auth',        function () { submitAuth(); });
registerAction('sign-out',           function () { signOut(); });

// ── Navigation / panels ───────────────────────────────
registerAction('toggle-cases-panel', function () { toggleCasesPanel(); });
registerAction('toggle-panel',       function (el, ds) { togglePanel(ds.panel); });

// ── Search ────────────────────────────────────────────
registerAction('start-search',       function () { startSearch(); });
registerAction('set-mode',           function (el, ds) { setMode(ds.mode); });
registerAction('set-sf-mode',        function (el, ds) { setSfMode(ds.mode, el); });
registerAction('select-cat',         function (el, ds) { selectCat(ds.name, el); });
registerAction('toggle-mod',         function (el, ds) { toggleMod(ds.mod, el); });
registerAction('new-search',         function () { newSearch(); });

// ── Result actions ────────────────────────────────────
registerAction('save-case',          function () { saveCase(); });
registerAction('copy-all',           function () { copyAll(); });
registerAction('export-pdf',         function () { exportPDF(); });
registerAction('export-json',        function () { exportJSON(); });
registerAction('export-csv',         function () { exportCSV(); });
registerAction('export-txt',         function () { exportTXT(); });
registerAction('copy-section',       function (el, ds) { copySection(ds.section); });

// ── Copy area (textarea select-all) ───────────────────
registerAction('select-copy-area',   function (el) { el.select(); });

// ── Breach cards ──────────────────────────────────────
registerAction('toggle-pwd',         function (el, ds) { togglePwd(ds.pwdid, ds.plain); });
registerAction('reveal-all-passwords', function () { revealAllPasswords(); });
registerAction('load-more-breaches', function () { loadMoreBreaches(); });
registerAction('copy-field',         function (el, ds) {
  if (!ds.val) return;
  writeClipboard(ds.val);
  el.classList.add('copied');
  setTimeout(() => el.classList.remove('copied'), 1500);
});

// ── Discord copy ──────────────────────────────────────
registerAction('copy-discord-id',    function (el, ds) {
  writeClipboard(ds.id);
  showToast(ds.toast || 'Copied');
});

// ── Victim / file tree ────────────────────────────────
registerAction('load-more-victims',  function () { loadMoreVictims(); });
registerAction('toggle-victim-tree', function (el, ds) {
  toggleVictimTree(ds.logid, Number(ds.idx));
});
registerAction('view-victim-file',   function (el, ds) {
  viewVictimFile(ds.logid, ds.fileid, ds.name);
});
registerAction('toggle-tree-dir',    function (el, ds) { toggleTreeDir(ds.nodeid); });

// ── File viewer ───────────────────────────────────────
registerAction('close-file-viewer',  function () { closeFileViewer(); });
registerAction('copy-file-content',  function () { copyFileContent(); });

// ── History ───────────────────────────────────────────
registerAction('rerun-search',       function (el, ds) { rerunSearch(ds.query); });

// ── Cases ─────────────────────────────────────────────
registerAction('load-case',          function (el, ds) { loadCase(ds.id); });
registerAction('delete-case',        function (el, ds) { deleteCase(ds.id); });
registerAction('clear-all-cases',    function () { clearAllCases(); });

// ── Summary Hero — stat card jump (Phase 17) ──────────
registerAction('jump-to-panel',      function (el, ds) {
  const panel = document.getElementById(ds.panel);
  if (!panel) return;
  if (!panel.classList.contains('open')) panel.classList.add('open');
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

// ── Activate delegation and start the app ────────────
initDelegation();
init();

// ── Non-click event listeners (input/keydown, not covered by delegation) ──
document.getElementById('authInput')?.addEventListener('keydown', function (e) {
  if (e.key === 'Enter') submitAuth();
});
document.getElementById('authUsername')?.addEventListener('keydown', function (e) {
  if (e.key === 'Enter') document.getElementById('authInput')?.focus();
});
document.getElementById('searchInput')?.addEventListener('input', function (e) {
  onQueryInput(e.target.value);
});
document.getElementById('searchInput')?.addEventListener('keydown', function (e) {
  if (e.key === 'Enter') startSearch();
});
