// Concept 1 — LUMEN
// SaaS premium · light · Stripe/Linear-grade polish.

const L = {
  bg: '#f5f3ed',
  bgRecess: '#ecebe4',
  surface: '#ffffff',
  ink: '#14110d',
  mute: 'rgba(20,17,13,0.62)',
  dim: 'rgba(20,17,13,0.38)',
  faint: 'rgba(20,17,13,0.18)',
  hair: 'rgba(20,17,13,0.08)',
  hairStrong: 'rgba(20,17,13,0.14)',
  sage: '#6f8a78',
  sageDeep: '#4d6557',
  sageSoft: 'rgba(111,138,120,0.12)',
  sageBorder: 'rgba(111,138,120,0.32)',
  gold: '#a8854a',
  goldSoft: 'rgba(168,133,74,0.12)',
  coral: '#b3553f',
  coralSoft: 'rgba(179,85,63,0.12)',
  taupe: '#8a7a68',
  taupeSoft: 'rgba(138,122,104,0.12)',
  display: '"Inter Tight", "Inter", system-ui, sans-serif',
  body: '"Inter", system-ui, sans-serif',
  serif: '"Instrument Serif", serif',
  mono: '"Geist Mono", "JetBrains Mono", monospace',
};

// ──────────────────────────────────────────────────────────
// Identity card
function LumenIdentity() {
  return (
    <div style={{ width: '100%', height: '100%', background: L.bg, color: L.ink,
      fontFamily: L.body, padding: 48, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 28 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.18em',
            textTransform: 'uppercase', color: L.sageDeep }}>Concept 01</div>
          <div style={{ fontSize: 56, fontFamily: L.display, fontWeight: 600,
            letterSpacing: '-0.035em', lineHeight: 1, marginTop: 6 }}>
            Lumen<span style={{ fontFamily: L.serif, fontStyle: 'italic',
              fontWeight: 400, color: L.sage, marginLeft: 4 }}>.</span>
          </div>
        </div>
        <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
          textTransform: 'uppercase', color: L.dim, textAlign: 'right' }}>
          Nexus OSINT ·<br/>SaaS Premium
        </div>
      </div>

      <div style={{ fontSize: 18, lineHeight: 1.45, color: L.mute, maxWidth: 720,
        fontFamily: L.body }}>
        Um produto que parece <span style={{ fontFamily: L.serif, fontStyle: 'italic',
          color: L.ink }}>caro</span>. Light, calmo, com hierarquia tipográfica óbvia
        e densidade restrita. A primeira impressão é a de uma ferramenta de finanças
        ou produtividade — não de uma ferramenta de segurança.
      </div>

      <div>
        <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
          textTransform: 'uppercase', color: L.dim, marginBottom: 12 }}>Paleta</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 10 }}>
          <Swatch hex="#f5f3ed" name="Bone" role="bg" />
          <Swatch hex="#ffffff" name="Paper" role="surface" />
          <Swatch hex="#14110d" name="Ink" role="text" />
          <Swatch hex="#6f8a78" name="Sage" role="primary" />
          <Swatch hex="#4d6557" name="Sage 700" role="primary deep" />
          <Swatch hex="#a8854a" name="Tarnish" role="likely" />
          <Swatch hex="#b3553f" name="Coral" role="error" />
          <Swatch hex="#8a7a68" name="Stone" role="blocked" />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 28,
        borderTop: `1px solid ${L.hair}`, paddingTop: 24 }}>
        <div>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: L.dim, marginBottom: 12 }}>Tipografia</div>
          <div style={{ fontFamily: L.display, fontSize: 48, fontWeight: 600,
            letterSpacing: '-0.035em', lineHeight: 1.05, color: L.ink }}>
            Investigate calmly.<br/>
            <span style={{ fontFamily: L.serif, fontStyle: 'italic',
              fontWeight: 400, color: L.sage }}>Render clearly.</span>
          </div>
          <div style={{ marginTop: 14, fontSize: 13.5, lineHeight: 1.55, color: L.mute,
            maxWidth: 480 }}>
            Inter Tight para display & UI. Instrument Serif italic em momentos editoriais (números
            grandes, ênfases). Geist Mono em todo dado: emails, IPs, hashes, IDs, métricas.
          </div>
          <div style={{ marginTop: 14, fontFamily: L.mono, fontSize: 12, color: L.sageDeep,
            background: L.sageSoft, padding: '6px 10px', borderRadius: 4,
            display: 'inline-block' }}>
            target@example.com · confidence 0.92 · 4 sources
          </div>
        </div>
        <div>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: L.dim, marginBottom: 12 }}>Sensação</div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none',
            display: 'flex', flexDirection: 'column', gap: 9 }}>
            {[
              'Whitespace generoso. Densidade só onde compensa.',
              'Cor é evento, não decoração. 80% da tela é tom de pergaminho.',
              'Cantos suaves (6–10px) — não SaaS-bubble, mas sem afiado.',
              'Animação restrita: fade + shimmer. Zero glow, zero glitch.',
              'Números viram protagonistas: confidence, freshness, source count.',
            ].map(t => (
              <li key={t} style={{ fontSize: 13, lineHeight: 1.45, color: L.ink,
                paddingLeft: 14, position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 7, width: 5, height: 5,
                  borderRadius: 99, background: L.sage }} />{t}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// Lumen shared chrome (sidebar + topbar)
function LumenChrome({ active = 'dashboard', children, breadcrumb }) {
  const nav = [
    { id: 'dashboard', label: 'Overview' },
    { id: 'search', label: 'New search' },
    { id: 'cases', label: 'Cases', badge: 12 },
    { id: 'history', label: 'History' },
    { id: 'sources', label: 'Sources' },
    { id: 'admin', label: 'Admin' },
  ];
  return (
    <div style={{ width: '100%', height: '100%', background: L.bg, color: L.ink,
      fontFamily: L.body, display: 'flex', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{ width: 220, background: L.bgRecess,
        borderRight: `1px solid ${L.hair}`,
        display: 'flex', flexDirection: 'column', padding: '18px 14px', gap: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 6px 16px' }}>
          <div style={{ width: 22, height: 22, borderRadius: 5, background: L.ink,
            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 8, height: 8, background: L.sage, borderRadius: 2 }} />
          </div>
          <div style={{ fontFamily: L.display, fontWeight: 600, fontSize: 15,
            letterSpacing: '-0.02em' }}>Nexus</div>
          <div style={{ fontFamily: L.mono, fontSize: 9, color: L.dim,
            marginLeft: 'auto', letterSpacing: '0.08em' }}>v4</div>
        </div>

        <div style={{ fontFamily: L.mono, fontSize: 9, letterSpacing: '0.14em',
          textTransform: 'uppercase', color: L.dim, padding: '8px 6px 4px' }}>Workspace</div>
        {nav.map(n => (
          <div key={n.id} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '7px 10px', borderRadius: 6, fontSize: 13,
            color: active === n.id ? L.ink : L.mute,
            background: active === n.id ? L.surface : 'transparent',
            border: active === n.id ? `1px solid ${L.hair}` : '1px solid transparent',
            fontWeight: active === n.id ? 500 : 400,
            cursor: 'default',
          }}>
            <div style={{ width: 4, height: 4, borderRadius: 99,
              background: active === n.id ? L.sage : L.faint }} />
            <span style={{ flex: 1 }}>{n.label}</span>
            {n.badge && <span style={{ fontFamily: L.mono, fontSize: 10,
              color: L.dim }}>{n.badge}</span>}
          </div>
        ))}

        <div style={{ marginTop: 'auto', padding: 12, background: L.surface,
          borderRadius: 8, border: `1px solid ${L.hair}` }}>
          <div style={{ fontFamily: L.mono, fontSize: 9, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: L.dim, marginBottom: 6 }}>Quota</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
            <span style={{ fontFamily: L.display, fontSize: 22, fontWeight: 600,
              letterSpacing: '-0.02em' }}>147</span>
            <span style={{ fontSize: 11, color: L.dim }}>/ 500 queries</span>
          </div>
          <div style={{ height: 3, background: L.hair, borderRadius: 2, marginTop: 8 }}>
            <div style={{ height: '100%', width: '29%', background: L.sage, borderRadius: 2 }} />
          </div>
        </div>
      </aside>

      {/* Topbar + content */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <header style={{ height: 52, borderBottom: `1px solid ${L.hair}`,
          display: 'flex', alignItems: 'center', padding: '0 28px', gap: 12,
          background: L.bg }}>
          <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute, display: 'flex',
            alignItems: 'center', gap: 8 }}>
            {breadcrumb || 'Overview'}
          </div>
          <div style={{ flex: 1 }} />
          <div style={{ height: 30, padding: '0 12px', borderRadius: 6,
            border: `1px solid ${L.hair}`, background: L.surface,
            display: 'flex', alignItems: 'center', gap: 8,
            fontSize: 12, color: L.dim, minWidth: 240, fontFamily: L.mono }}>
            <span>⌘K</span><span>Quick search</span>
          </div>
          <div style={{ width: 28, height: 28, borderRadius: 99, background: L.sage,
            color: 'white', fontSize: 11, fontWeight: 600,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: L.display }}>M</div>
        </header>
        <div style={{ flex: 1, overflow: 'auto' }}>{children}</div>
      </main>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Dashboard
function LumenDashboard() {
  return (
    <LumenChrome active="dashboard" breadcrumb={<><span>Workspace</span><span style={{color:L.dim}}>/</span><span style={{color:L.ink}}>Overview</span></>}>
      <div style={{ padding: '32px 36px', display: 'flex', flexDirection: 'column', gap: 28 }}>
        {/* Hero */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: L.dim }}>Good evening, Mattheus</div>
            <div style={{ fontFamily: L.display, fontSize: 30, fontWeight: 600,
              letterSpacing: '-0.025em', marginTop: 6 }}>
              <span>3 cases pending review,</span>{' '}
              <span style={{ fontFamily: L.serif, fontStyle: 'italic',
                fontWeight: 400, color: L.sage }}>1 finished overnight.</span>
            </div>
          </div>
          <button style={{ background: L.ink, color: L.bg, border: 0, borderRadius: 6,
            padding: '10px 16px', fontSize: 13, fontWeight: 500, fontFamily: L.body,
            cursor: 'default' }}>+ New investigation</button>
        </div>

        {/* Stats row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          {[
            { k: 'Active investigations', v: '7', sub: '+2 this week', tone: 'sage' },
            { k: 'Sources online', v: '14 / 16', sub: '2 degraded', tone: 'gold' },
            { k: 'Avg confidence', v: '0.78', sub: 'last 7 days', tone: 'plain' },
            { k: 'Median latency', v: '4.1s', sub: 'p95 11.7s', tone: 'plain' },
          ].map(s => (
            <div key={s.k} style={{ background: L.surface, border: `1px solid ${L.hair}`,
              borderRadius: 10, padding: 18 }}>
              <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.14em',
                textTransform: 'uppercase', color: L.dim }}>{s.k}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 10 }}>
                <div style={{ fontFamily: L.display, fontSize: 32, fontWeight: 600,
                  letterSpacing: '-0.03em', color: L.ink }}>{s.v}</div>
              </div>
              <div style={{ fontSize: 11, color: s.tone === 'sage' ? L.sageDeep
                : s.tone === 'gold' ? L.gold : L.mute, marginTop: 6,
                fontFamily: L.mono, letterSpacing: '0.04em' }}>{s.sub}</div>
            </div>
          ))}
        </div>

        {/* Two-col: recent + sources */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
          <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
            borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: `1px solid ${L.hair}`,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Recent investigations</div>
              <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>View all →</div>
            </div>
            {[
              { t: 'lucas.silva@protonmail.com', type: 'Email', n: 47, conf: 0.91, ago: '12m ago', status: 'found' },
              { t: '@nbreaker', type: 'Handle', n: 18, conf: 0.74, ago: '1h ago', status: 'partial' },
              { t: '189.45.221.103', type: 'IP', n: 6, conf: 0.42, ago: '3h ago', status: 'uncertain' },
              { t: 'discord.gg/x9k2', type: 'Discord', n: 23, conf: 0.88, ago: 'Yesterday', status: 'found' },
              { t: 'rafa_pkr', type: 'Gaming', n: 9, conf: 0.61, ago: 'Yesterday', status: 'partial' },
            ].map((r, i) => (
              <div key={i} style={{ padding: '13px 18px', borderTop: i ? `1px solid ${L.hair}` : 'none',
                display: 'grid', gridTemplateColumns: '1.8fr 0.6fr 0.5fr 0.7fr 0.6fr', gap: 12,
                alignItems: 'center' }}>
                <div>
                  <div style={{ fontFamily: L.mono, fontSize: 12.5, color: L.ink }}>{r.t}</div>
                  <div style={{ fontFamily: L.mono, fontSize: 10, color: L.dim, marginTop: 2 }}>
                    {r.type.toUpperCase()} · {r.ago}</div>
                </div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>
                  {r.n} <span style={{ color: L.dim }}>findings</span></div>
                <ConfidenceBar value={r.conf} />
                <StatusPill status={r.status} />
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.dim, textAlign: 'right' }}>›</div>
              </div>
            ))}
          </div>

          <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
            borderRadius: 10, padding: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Source health</div>
              <div style={{ fontFamily: L.mono, fontSize: 10, color: L.dim }}>realtime</div>
            </div>
            {[
              { n: 'HIBP', h: 0.98, lat: '180ms', state: 'ok' },
              { n: 'OathNet', h: 0.94, lat: '420ms', state: 'ok' },
              { n: 'Sherlock', h: 0.81, lat: '2.1s', state: 'degraded' },
              { n: 'Holehe', h: 0.92, lat: '1.4s', state: 'ok' },
              { n: 'Discord lookup', h: 1.0, lat: '90ms', state: 'ok' },
              { n: 'Stealer index', h: 0.55, lat: '6.8s', state: 'degraded' },
              { n: 'SpiderFoot', h: 0.0, lat: '—', state: 'down' },
            ].map(s => (
              <div key={s.n} style={{ display: 'grid',
                gridTemplateColumns: '1fr 60px 50px 14px', gap: 10, alignItems: 'center',
                padding: '7px 0', borderTop: `1px solid ${L.hair}` }}>
                <div style={{ fontSize: 12.5, color: L.ink }}>{s.n}</div>
                <Sparkline state={s.state} />
                <div style={{ fontFamily: L.mono, fontSize: 10.5, color: L.mute,
                  textAlign: 'right' }}>{s.lat}</div>
                <div style={{ width: 8, height: 8, borderRadius: 99,
                  background: s.state === 'ok' ? L.sage : s.state === 'degraded'
                    ? L.gold : L.coral }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </LumenChrome>
  );
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: L.hair, borderRadius: 2 }}>
        <div style={{ height: '100%', width: `${pct}%`,
          background: value > 0.7 ? L.sage : value > 0.5 ? L.gold : L.taupe,
          borderRadius: 2 }} />
      </div>
      <div style={{ fontFamily: L.mono, fontSize: 10.5, color: L.mute,
        width: 28, textAlign: 'right' }}>.{(pct).toString().padStart(2,'0')}</div>
    </div>
  );
}

function StatusPill({ status }) {
  const cfg = {
    found:     { c: L.sage, bg: L.sageSoft, t: 'Confirmed' },
    partial:   { c: L.gold, bg: L.goldSoft, t: 'Partial' },
    uncertain: { c: L.taupe, bg: L.taupeSoft, t: 'Uncertain' },
    blocked:   { c: L.taupe, bg: L.taupeSoft, t: 'Blocked' },
    error:     { c: L.coral, bg: L.coralSoft, t: 'Error' },
    running:   { c: L.sageDeep, bg: L.sageSoft, t: 'Running' },
  }[status] || { c: L.dim, bg: L.hair, t: status };
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 8px', borderRadius: 99, background: cfg.bg,
      fontFamily: L.mono, fontSize: 10, color: cfg.c, letterSpacing: '0.04em',
      width: 'fit-content' }}>
      <div style={{ width: 5, height: 5, borderRadius: 99, background: cfg.c }} />
      {cfg.t.toUpperCase()}
    </div>
  );
}

function Sparkline({ state }) {
  const c = state === 'ok' ? L.sage : state === 'degraded' ? L.gold : L.coral;
  const heights = state === 'down' ? [2,2,2,2,2,2,2,2]
    : state === 'degraded' ? [6,4,8,3,7,5,9,4,7,3,5]
    : [4,6,5,7,6,8,5,7,6,7,5,6];
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1.5, height: 14 }}>
      {heights.map((h, i) => (
        <div key={i} style={{ width: 2, height: h, background: c, opacity: 0.6 + (i / 20),
          borderRadius: 1 }} />
      ))}
    </div>
  );
}

Object.assign(window, { L, LumenIdentity, LumenChrome, LumenDashboard,
  ConfidenceBar, StatusPill, Sparkline });
