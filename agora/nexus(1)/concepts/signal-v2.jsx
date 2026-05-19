// Signal v2 — refinements applied per feedback.
// Reuses S tokens + SignalChrome + SignalStatus + Dial + MicroSpark + PanelHeader from concepts/signal.jsx.
// Also reuses C tokens + Stamp + Seal + Citation from concepts/casebook.jsx (for the PDF export).

const { S, MicroSpark, Dial, SignalStatus, SignalConfBar, PanelHeader } = window;
const { C: Cb, Stamp, Seal, Citation, Concur } = window;

// ──────────────────────────────────────────────────────────
// Finding category system — the 4 buckets the user asked for
const CAT = {
  exposure: {
    id: 'exposure',
    label: 'Exposição sensível',
    sub: 'breach · stealer · credenciais',
    icon: '◆',
    color: S.red,
    soft: S.redSoft,
    border: 'rgba(234,91,86,0.30)',
    hint: 'Dados vazados ou credenciais comprometidas — leitura urgente.',
  },
  identity: {
    id: 'identity',
    label: 'Sinais de identidade',
    sub: 'email · telefone · documento',
    icon: '◉',
    color: S.teal,
    soft: S.tealSoft,
    border: 'rgba(142,196,212,0.30)',
    hint: 'Confirmações de quem é a pessoa — base para correlação.',
  },
  social: {
    id: 'social',
    label: 'Descoberta pública',
    sub: 'social · gaming · presença online',
    icon: '◍',
    color: S.sand,
    soft: S.sandSoft,
    border: 'rgba(212,184,142,0.30)',
    hint: 'Pegada digital pública — não-sensível, alto volume.',
  },
  infra: {
    id: 'infra',
    label: 'Infraestrutura',
    sub: 'network · domain · whois · geo',
    icon: '◇',
    color: S.green,
    soft: S.greenSoft,
    border: 'rgba(127,191,139,0.30)',
    hint: 'Contexto técnico em torno do alvo — domínios, IPs, hosts.',
  },
};

// Category chip
function CatChip({ cat, n, active }) {
  const c = CAT[cat];
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      padding: '6px 12px',
      background: active ? c.soft : 'transparent',
      border: `1px solid ${active ? c.border : S.hair}`,
      cursor: 'default' }}>
      <span style={{ fontSize: 12, color: c.color }}>{c.icon}</span>
      <span style={{ fontFamily: S.mono, fontSize: 10.5,
        color: active ? c.color : S.inkMute,
        letterSpacing: '0.08em', textTransform: 'uppercase',
        fontWeight: active ? 600 : 500 }}>{c.label}</span>
      {n != null && <span style={{ fontFamily: S.mono, fontSize: 10,
        color: active ? c.color : S.inkDim }}>· {n}</span>}
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Brief intro board — the 5 refinements explained
function SignalV2Brief() {
  return (
    <div style={{ width: '100%', height: '100%', background: S.bg, color: S.ink,
      fontFamily: S.body, padding: 44, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 22,
      backgroundImage: `
        linear-gradient(to right, ${S.hair} 1px, transparent 1px),
        linear-gradient(to bottom, ${S.hair} 1px, transparent 1px)`,
      backgroundSize: '40px 40px' }}>
      <div>
        <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.18em',
          textTransform: 'uppercase', color: S.teal }}>Signal · v2 · refinements</div>
        <div style={{ fontFamily: S.display, fontSize: 44, fontWeight: 600,
          letterSpacing: '-0.03em', lineHeight: 1.05, marginTop: 8, maxWidth: 880 }}>
          Same console.{' '}
          <span style={{ color: S.teal }}>Two modes.</span>{' '}
          <span style={{ color: S.sand }}>Findings, by meaning.</span>{' '}
          <span style={{ fontStyle: 'italic',
            fontFamily: '"Instrument Serif", serif', fontWeight: 400 }}>
            Exports, by hand.</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14,
        flex: 1, alignContent: 'start' }}>
        {[
          { n: '01', t: 'Topbar mais quieto',
            d: 'workers · RAM · queue saem do strip de cima por padrão. Aparecem só em Admin e no modo Analyst.',
            tag: 'STRIP' },
          { n: '02', t: 'Simple ↔ Analyst',
            d: 'Toggle único na topbar. Simple: dashboard de casos. Analyst: timeline, event feed, dials, source health.',
            tag: 'MODE' },
          { n: '03', t: 'Gantt como peça central',
            d: 'O Source Timeline vira hero do progresso real-time — uma única visualização que conta a história inteira.',
            tag: 'HERO' },
          { n: '04', t: 'Findings em 4 baldes',
            d: 'Exposure (breach/stealer) · Identity (email/phone) · Social (social/gaming) · Infra (domain/network).',
            tag: 'GROUP' },
          { n: '05', t: 'Export em Casebook',
            d: 'PDF/dossiê herda visual editorial: serif, citações numeradas, carimbos. Coerente com identidade da investigação.',
            tag: 'EXPORT' },
        ].map(s => (
          <div key={s.n} style={{ background: S.surface,
            border: `1px solid ${S.hair}`, padding: 18,
            display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between',
              alignItems: 'baseline' }}>
              <div style={{ fontFamily: S.mono, fontSize: 10, color: S.teal,
                letterSpacing: '0.14em' }}>{s.n}</div>
              <div style={{ fontFamily: S.mono, fontSize: 8.5, color: S.inkDim,
                letterSpacing: '0.14em', padding: '2px 6px',
                border: `1px solid ${S.hair}` }}>{s.tag}</div>
            </div>
            <div style={{ fontFamily: S.display, fontSize: 16, fontWeight: 600,
              letterSpacing: '-0.015em', color: S.ink, lineHeight: 1.2 }}>{s.t}</div>
            <div style={{ fontSize: 12, lineHeight: 1.55, color: S.inkMute }}>{s.d}</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 'auto', padding: 16,
        background: S.tealSoft, border: `1px solid ${S.tealBorder}`,
        fontSize: 13, color: S.ink, lineHeight: 1.55 }}>
        Tudo abaixo é <strong>aditivo</strong> ao Signal mostrado antes — o conceito original
        permanece intocado. Estas telas refletem só as 5 mudanças pedidas, com componentes
        reusados (SignalChrome, Dial, MicroSpark, SignalStatus, status pills).
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// View toggle — visual showing how Simple ↔ Analyst lives in the chrome.
function ViewToggleSpec() {
  return (
    <div style={{ width: '100%', height: '100%', background: S.bg, color: S.ink,
      fontFamily: S.body, padding: 36, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div>
        <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.18em',
          textTransform: 'uppercase', color: S.teal }}>Component · view mode</div>
        <div style={{ fontFamily: S.display, fontSize: 28, fontWeight: 600,
          letterSpacing: '-0.025em', marginTop: 6 }}>
          One toggle. Two faces.{' '}
          <span style={{ color: S.inkDim, fontWeight: 400 }}>Same data.</span>
        </div>
      </div>

      {/* Two topbars stacked, showing the diff */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Simple */}
        <div>
          <div style={{ fontFamily: S.mono, fontSize: 9.5, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: S.inkDim, marginBottom: 6 }}>
            Simple · default for most users</div>
          <div style={{ height: 36, background: S.bgRecess,
            border: `1px solid ${S.hair}`,
            padding: '0 16px', display: 'flex', alignItems: 'center', gap: 16,
            fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
            letterSpacing: '0.05em' }}>
            <span style={{ color: S.ink }}>NEXUS</span>
            <span style={{ color: S.hairStrong }}>│</span>
            <span>mattheus@nexus · 12 cases</span>
            <span style={{ flex: 1 }} />
            <ViewSwitch active="simple" />
            <span style={{ color: S.hairStrong }}>│</span>
            <span>⌘K</span>
            <span style={{ color: S.hairStrong }}>│</span>
            <span style={{ color: S.green }}>● LIVE</span>
          </div>
          <div style={{ marginTop: 8, fontSize: 11.5, color: S.inkMute, lineHeight: 1.5 }}>
            Quem somos. Quantos casos. Live/idle. Nada mais. Workers, RAM e queue ficam
            em <em>Admin</em> — usuário comum nunca precisa ver.
          </div>
        </div>

        {/* Analyst */}
        <div>
          <div style={{ fontFamily: S.mono, fontSize: 9.5, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: S.teal, marginBottom: 6 }}>
            Analyst · opt-in via toggle</div>
          <div style={{ height: 36, background: S.bgRecess,
            border: `1px solid ${S.tealBorder}`,
            padding: '0 16px', display: 'flex', alignItems: 'center', gap: 14,
            fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
            letterSpacing: '0.05em' }}>
            <span style={{ color: S.ink }}>NEXUS</span>
            <span style={{ color: S.hairStrong }}>│</span>
            <span>mattheus@nexus · 12 cases</span>
            <span style={{ flex: 1 }} />
            <span>workers <span style={{ color: S.teal }}>3/5</span></span>
            <span style={{ color: S.hairStrong }}>│</span>
            <span>ram <span style={{ color: S.amber }}>178M</span>/200M</span>
            <span style={{ color: S.hairStrong }}>│</span>
            <span>srcs <span style={{ color: S.green }}>14</span>/16</span>
            <span style={{ color: S.hairStrong }}>│</span>
            <span>queue <span style={{ color: S.sand }}>7</span></span>
            <span style={{ color: S.hairStrong }}>│</span>
            <ViewSwitch active="analyst" />
            <span style={{ color: S.hairStrong }}>│</span>
            <span style={{ color: S.green }}>● LIVE</span>
          </div>
          <div style={{ marginTop: 8, fontSize: 11.5, color: S.inkMute, lineHeight: 1.5 }}>
            Telemetria do sistema volta. Painéis ganham event feed, Gantt detalhado, source
            health com sparklines. Persiste por workspace.
          </div>
        </div>
      </div>

      {/* What each mode reveals */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, flex: 1 }}>
        <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
          <PanelHeader title="Simple shows" right="user-facing" />
          <ul style={{ margin: 0, padding: '12px 0 0', listStyle: 'none',
            display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              ['Casos abertos com confidence + verdict'],
              ['Findings agrupadas por categoria (4 baldes)'],
              ['Progresso em uma única linha por fonte'],
              ['Verdict claro: Critical / High / Medium / Low'],
              ['Botões para salvar caso, exportar dossiê'],
            ].map((r, i) => (
              <li key={i} style={{ fontSize: 12.5, color: S.ink, lineHeight: 1.5,
                paddingLeft: 16, position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 8, width: 4, height: 4,
                  background: S.teal }} />{r[0]}</li>
            ))}
          </ul>
        </div>
        <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
          <PanelHeader title="Analyst adds" right="opt-in" />
          <ul style={{ margin: 0, padding: '12px 0 0', listStyle: 'none',
            display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              ['Gantt detalhado por source com timestamps'],
              ['Event feed streaming (autoscroll)'],
              ['Source health · sparklines + p95/quota/cache'],
              ['Worker pool ao vivo + memory/cpu'],
              ['Evidence ledger com weight per source'],
              ['Toggles para incluir blocked/error nas listas'],
            ].map((r, i) => (
              <li key={i} style={{ fontSize: 12.5, color: S.ink, lineHeight: 1.5,
                paddingLeft: 16, position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 8, width: 4, height: 4,
                  background: S.sand }} />{r[0]}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// View switch component — segmented control
function ViewSwitch({ active = 'simple' }) {
  return (
    <div style={{ display: 'inline-flex', height: 22, border: `1px solid ${S.hair}` }}>
      {['simple', 'analyst'].map(m => (
        <div key={m} style={{
          padding: '0 12px', display: 'flex', alignItems: 'center',
          background: active === m ? (m === 'analyst' ? S.tealSoft : S.surface2) : 'transparent',
          color: active === m ? (m === 'analyst' ? S.teal : S.ink) : S.inkDim,
          fontFamily: S.mono, fontSize: 9.5, letterSpacing: '0.14em',
          textTransform: 'uppercase', fontWeight: active === m ? 600 : 500,
          borderRight: m === 'simple' ? `1px solid ${S.hair}` : 'none',
          cursor: 'default' }}>{m}</div>
      ))}
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Quieter chrome — Simple version of SignalChrome (no telemetry strip)
function SignalChromeQuiet({ active = 'home', children, contextLine, mode = 'simple', live = true }) {
  const items = [
    { id: 'home', g: '◉', t: 'Overview' },
    { id: 'search', g: '◇', t: 'New' },
    { id: 'cases', g: '▤', t: 'Cases' },
    { id: 'history', g: '↺', t: 'History' },
    { id: 'sources', g: '▣', t: 'Sources' },
    { id: 'admin', g: '⚙', t: 'Admin' },
  ];
  return (
    <div style={{ width: '100%', height: '100%', background: S.bg, color: S.ink,
      fontFamily: S.body, display: 'flex', overflow: 'hidden' }}>
      <aside style={{ width: 54, background: S.bgRecess,
        borderRight: `1px solid ${S.hair}`,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '14px 0', gap: 4 }}>
        <div style={{ width: 28, height: 28, background: S.surface2,
          border: `1px solid ${S.hairStrong}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: S.display, fontWeight: 700, fontSize: 14, color: S.teal,
          marginBottom: 12 }}>n</div>
        {items.map(it => (
          <div key={it.id} title={it.t} style={{
            width: 34, height: 34,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: S.mono, fontSize: 14,
            background: active === it.id ? S.tealSoft : 'transparent',
            color: active === it.id ? S.teal : S.inkDim,
            border: active === it.id ? `1px solid ${S.tealBorder}` : '1px solid transparent',
            cursor: 'default' }}>{it.g}</div>
        ))}
        <div style={{ marginTop: 'auto', fontFamily: S.mono, fontSize: 8,
          color: S.inkDim, letterSpacing: '0.1em' }}>v4</div>
      </aside>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <header style={{ height: 36, borderBottom: `1px solid ${S.hair}`,
          background: S.bgRecess, padding: '0 16px',
          display: 'flex', alignItems: 'center', gap: 14,
          fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
          letterSpacing: '0.05em' }}>
          <span style={{ color: S.ink }}>NEXUS</span>
          <span style={{ color: S.hairStrong }}>│</span>
          <span>{contextLine || 'mattheus@nexus · 12 cases'}</span>
          <span style={{ flex: 1 }} />

          {/* Analyst-only telemetry */}
          {mode === 'analyst' && (
            <React.Fragment>
              <span>workers <span style={{ color: S.teal }}>3/5</span></span>
              <span style={{ color: S.hairStrong }}>│</span>
              <span>ram <span style={{ color: S.amber }}>178M</span>/200M</span>
              <span style={{ color: S.hairStrong }}>│</span>
              <span>srcs <span style={{ color: S.green }}>14</span>/16</span>
              <span style={{ color: S.hairStrong }}>│</span>
              <span>queue <span style={{ color: S.sand }}>7</span></span>
              <span style={{ color: S.hairStrong }}>│</span>
            </React.Fragment>
          )}

          <ViewSwitch active={mode} />
          <span style={{ color: S.hairStrong }}>│</span>
          <span style={{ color: live ? S.green : S.inkDim }}>
            {live ? '● LIVE' : '○ IDLE'}</span>
        </header>

        <div style={{ flex: 1, overflow: 'auto' }}>{children}</div>
      </main>
    </div>
  );
}

Object.assign(window, { CAT, CatChip, ViewSwitch, SignalChromeQuiet,
  SignalV2Brief, ViewToggleSpec });
