// Concept 3 — SIGNAL
// Analyst console · slate not black · calm signal density · instrument-grade, not cyberpunk.

const S = {
  bg: '#0e1116',
  bgRecess: '#0a0d12',
  surface: '#161a22',
  surface2: '#1c222d',
  surface3: '#242b38',
  ink: '#ecedf0',
  inkMute: 'rgba(236,237,240,0.62)',
  inkDim: 'rgba(236,237,240,0.40)',
  inkFaint: 'rgba(236,237,240,0.22)',
  hair: 'rgba(255,255,255,0.06)',
  hairStrong: 'rgba(255,255,255,0.12)',
  // Two signal accents — teal (cool, primary) + warm sand (preserves a hint of Meridian amber DNA)
  teal: '#8ec4d4',
  tealDeep: '#5897ab',
  tealSoft: 'rgba(142,196,212,0.10)',
  tealBorder: 'rgba(142,196,212,0.30)',
  sand: '#d4b88e',
  sandDeep: '#a08658',
  sandSoft: 'rgba(212,184,142,0.10)',
  // severity, restrained
  red: '#ea5b56',
  redSoft: 'rgba(234,91,86,0.10)',
  amber: '#e9a35f',
  amberSoft: 'rgba(233,163,95,0.10)',
  yellow: '#d9c25f',
  yellowSoft: 'rgba(217,194,95,0.10)',
  green: '#7fbf8b',
  greenSoft: 'rgba(127,191,139,0.10)',
  display: '"Sora", "Inter", system-ui, sans-serif',
  body: '"Inter", system-ui, sans-serif',
  mono: '"JetBrains Mono", monospace',
};

// Dotted micro-sparkline — instrument feel
function MicroSpark({ values, color, height = 18, width = 80 }) {
  const max = Math.max(...values);
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - (v / max) * (height - 2);
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline points={pts} stroke={color} strokeWidth={1.2} fill="none" />
      {values.map((v, i) => {
        const x = (i / (values.length - 1)) * width;
        const y = height - (v / max) * (height - 2);
        return <circle key={i} cx={x} cy={y} r={1.2} fill={color} opacity={0.7} />;
      })}
    </svg>
  );
}

// Numeric dial (0–1) — concentric arc instrument
function Dial({ value, label, size = 86, color = S.teal }) {
  const r = size / 2 - 6;
  const C2 = 2 * Math.PI * r;
  const off = C2 * (1 - value);
  return (
    <div style={{ width: size, position: 'relative', display: 'inline-block' }}>
      <svg width={size} height={size} style={{ display: 'block', transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} stroke={S.hair} strokeWidth={2} fill="none" />
        <circle cx={size/2} cy={size/2} r={r} stroke={color} strokeWidth={2} fill="none"
          strokeDasharray={C2} strokeDashoffset={off} strokeLinecap="round" />
        {/* tick marks */}
        {Array.from({ length: 24 }).map((_, i) => {
          const a = (i / 24) * Math.PI * 2;
          const inner = r - 2, outer = r + 2;
          return <line key={i}
            x1={size/2 + Math.cos(a) * inner} y1={size/2 + Math.sin(a) * inner}
            x2={size/2 + Math.cos(a) * outer} y2={size/2 + Math.sin(a) * outer}
            stroke={S.hair} strokeWidth={1} />;
        })}
      </svg>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center' }}>
        <div style={{ fontFamily: S.display, fontSize: size * 0.26, fontWeight: 600,
          color: S.ink, letterSpacing: '-0.02em', lineHeight: 1 }}>
          {value.toFixed(2)}</div>
        {label && <div style={{ fontFamily: S.mono, fontSize: 8.5,
          color: S.inkDim, letterSpacing: '0.1em', marginTop: 2, textTransform: 'uppercase'
        }}>{label}</div>}
      </div>
    </div>
  );
}

// Status chip — single-letter glyph in a thin-bordered box
function SignalStatus({ state }) {
  const cfg = {
    found:     { c: S.green, l: 'FND', sym: '●' },
    likely:    { c: S.amber, l: 'LKY', sym: '◐' },
    uncertain: { c: S.sand,  l: 'UNC', sym: '◔' },
    running:   { c: S.teal,  l: 'RUN', sym: '◇' },
    pending:   { c: S.inkDim,l: 'PND', sym: '○' },
    blocked:   { c: S.amber, l: 'BLK', sym: '⊘' },
    error:     { c: S.red,   l: 'ERR', sym: '×' },
    not_found: { c: S.inkMute, l: '404', sym: '·' },
  }[state] || { c: S.inkDim, l: '—', sym: '·' };
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 8px',
      border: `1px solid ${cfg.c}40`,
      background: 'transparent',
      fontFamily: S.mono, fontSize: 9.5, color: cfg.c, letterSpacing: '0.14em',
      fontWeight: 600 }}>
      <span style={{ fontSize: 11, lineHeight: 1 }}>{cfg.sym}</span>
      {cfg.l}
    </div>
  );
}

// ──────────────────────────────────────────────────────────
function SignalIdentity() {
  return (
    <div style={{ width: '100%', height: '100%', background: S.bg, color: S.ink,
      fontFamily: S.body, padding: 48, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 28,
      // subtle grid overlay
      backgroundImage: `
        linear-gradient(to right, ${S.hair} 1px, transparent 1px),
        linear-gradient(to bottom, ${S.hair} 1px, transparent 1px)`,
      backgroundSize: '40px 40px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.18em',
            textTransform: 'uppercase', color: S.teal }}>Concept 03</div>
          <div style={{ fontFamily: S.display, fontSize: 64, fontWeight: 600,
            letterSpacing: '-0.035em', lineHeight: 1, marginTop: 6 }}>
            Signal<span style={{ color: S.teal }}>.</span>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: S.inkDim }}>Analyst Console</div>
          <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
            <Dial value={0.84} label="confidence" size={68} />
            <Dial value={0.42} label="risk" size={68} color={S.amber} />
          </div>
        </div>
      </div>

      <div style={{ fontSize: 18, lineHeight: 1.45, color: S.inkMute, maxWidth: 740 }}>
        Console profissional <em>sem</em> cosplay de hacker. Slate, não preto. Cor é sinal, não
        atmosfera. Instrumentos pequenos (dials, sparklines, hairlines) substituem efeitos.
        A referência é uma sala de controle — Apollo, CERN, Bloomberg — não Mr. Robot.
      </div>

      <div>
        <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.16em',
          textTransform: 'uppercase', color: S.inkDim, marginBottom: 12 }}>Paleta</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 10 }}>
          <Swatch hex="#0e1116" name="Slate" role="bg" dark />
          <Swatch hex="#161a22" name="Surface" role="panel" dark />
          <Swatch hex="#ecedf0" name="Bright" role="text" dark />
          <Swatch hex="#8ec4d4" name="Teal" role="primary" dark />
          <Swatch hex="#d4b88e" name="Sand" role="secondary" dark />
          <Swatch hex="#ea5b56" name="Red" role="critical" dark />
          <Swatch hex="#e9a35f" name="Amber" role="high" dark />
          <Swatch hex="#7fbf8b" name="Verdant" role="confirmed" dark />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 28,
        borderTop: `1px solid ${S.hair}`, paddingTop: 24 }}>
        <div>
          <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: S.inkDim, marginBottom: 12 }}>Tipografia</div>
          <div style={{ fontFamily: S.display, fontSize: 48, fontWeight: 600,
            letterSpacing: '-0.035em', lineHeight: 1.05 }}>
            Density without noise.<br/>
            <span style={{ color: S.teal, fontWeight: 500 }}>Clarity without quiet.</span>
          </div>
          <div style={{ marginTop: 14, fontSize: 13.5, lineHeight: 1.55, color: S.inkMute,
            maxWidth: 480 }}>
            Sora para display + UI · Inter para body · JetBrains Mono em tudo que é dado.
            Cor aparece <em>só</em> onde indica estado. 80% da tela é graytones desaturados.
          </div>
          <div style={{ marginTop: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
            <SignalStatus state="found" />
            <SignalStatus state="running" />
            <SignalStatus state="likely" />
            <SignalStatus state="blocked" />
            <SignalStatus state="error" />
          </div>
          <div style={{ marginTop: 14, fontFamily: S.mono, fontSize: 11, color: S.tealDeep,
            padding: '8px 12px',
            background: S.tealSoft, border: `1px solid ${S.tealBorder}` }}>
            target=lucas.silva@protonmail.com · conf=0.84 · srcs=4/8 · age=14s
          </div>
        </div>
        <div>
          <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: S.inkDim, marginBottom: 12 }}>Sensação</div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none',
            display: 'flex', flexDirection: 'column', gap: 9 }}>
            {[
              'Densidade alta, mas calma — hairlines, não bordas grossas',
              'Dials e sparklines em todo lugar — sensação de "instrumento"',
              'Zero glow, zero neon, zero scan-line. Sem efeitos cinematográficos.',
              'Foreground é cinza-claro, não branco — fadiga visual menor',
              'Real-time é ambiente: 30 microsinais simultâneos vivendo na tela',
            ].map(t => (
              <li key={t} style={{ fontSize: 13, lineHeight: 1.45, color: S.ink,
                paddingLeft: 14, position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 7, width: 5, height: 5,
                  borderRadius: 99, background: S.teal }} />{t}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// Shared chrome — narrow icon rail + top status strip
function SignalChrome({ active = 'home', children, contextLine }) {
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
        padding: '14px 0 14px', gap: 4 }}>
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
          color: S.inkDim, letterSpacing: '0.1em' }}>v4.0</div>
      </aside>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Status strip */}
        <header style={{ height: 32, borderBottom: `1px solid ${S.hair}`,
          background: S.bgRecess, padding: '0 16px',
          display: 'flex', alignItems: 'center', gap: 16,
          fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
          letterSpacing: '0.05em' }}>
          <span style={{ color: S.ink }}>NEXUS</span>
          <span style={{ color: S.hairStrong }}>│</span>
          <span>{contextLine || 'mattheus@nexus · workspace=ops · cases=12'}</span>
          <span style={{ flex: 1 }} />
          <span>workers <span style={{ color: S.teal }}>3/5</span></span>
          <span style={{ color: S.hairStrong }}>│</span>
          <span>ram <span style={{ color: S.amber }}>178M</span>/200M</span>
          <span style={{ color: S.hairStrong }}>│</span>
          <span>srcs <span style={{ color: S.green }}>14</span>/16</span>
          <span style={{ color: S.hairStrong }}>│</span>
          <span>queue <span style={{ color: S.sand }}>7</span></span>
          <span style={{ color: S.hairStrong }}>│</span>
          <span style={{ color: S.green }}>● LIVE</span>
        </header>

        <div style={{ flex: 1, overflow: 'auto' }}>{children}</div>
      </main>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Dashboard
function SignalDashboard() {
  return (
    <SignalChrome active="home"
      contextLine="mattheus@nexus · workspace=ops · cases=12 · uptime=7d 04:18">
      <div style={{ padding: 20, display: 'grid',
        gridTemplateColumns: 'repeat(12, 1fr)', gridAutoRows: 'min-content', gap: 12 }}>

        {/* Hero block */}
        <div style={{ gridColumn: 'span 12',
          background: S.surface, border: `1px solid ${S.hair}`, padding: 22,
          display: 'grid', gridTemplateColumns: '2fr 1.2fr 1.2fr 1.2fr 1fr', gap: 24,
          alignItems: 'center' }}>
          <div>
            <div style={{ fontFamily: S.mono, fontSize: 9, letterSpacing: '0.16em',
              color: S.tealDeep, textTransform: 'uppercase' }}>System state</div>
            <div style={{ fontFamily: S.display, fontSize: 24, fontWeight: 600,
              letterSpacing: '-0.02em', marginTop: 6 }}>
              All sources nominal. <span style={{ color: S.amber }}>2 degraded.</span>
            </div>
            <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
              marginTop: 8 }}>
              7d uptime · 14/16 connectors green · 3 active workers · 7 jobs queued
            </div>
          </div>
          <DashStat label="Active" value="7" unit="cases" tint="teal" trend={[3,4,3,5,6,7,7,8,7]} />
          <DashStat label="Avg conf" value="0.78" unit="last 7d" tint="sand" trend={[0.62,0.71,0.74,0.81,0.77,0.79,0.78,0.78]} />
          <DashStat label="p50 latency" value="4.1" unit="seconds" tint="green" trend={[5,4,4,3,4,4,4,4]} />
          <Dial value={0.84} label="health" size={86} color={S.teal} />
        </div>

        {/* Investigations table */}
        <div style={{ gridColumn: 'span 7', background: S.surface,
          border: `1px solid ${S.hair}` }}>
          <PanelHeader title="Active investigations" right="6 of 7 visible" />
          <div style={{ padding: '4px 14px 12px' }}>
            <div style={{ display: 'grid',
              gridTemplateColumns: '20px 1.6fr 70px 90px 60px 70px',
              gap: 12, fontFamily: S.mono, fontSize: 9,
              color: S.inkDim, letterSpacing: '0.1em', textTransform: 'uppercase',
              padding: '8px 0', borderBottom: `1px solid ${S.hair}` }}>
              <div></div><div>target</div><div>kind</div><div>confidence</div>
              <div>findings</div><div>age</div>
            </div>
            {[
              { id: '0241', t: 'lucas.silva@protonmail.com', k: 'EMAIL', c: 0.84, n: 43, a: '12m', state: 'running' },
              { id: '0240', t: '@nbreaker', k: 'HANDLE', c: 0.71, n: 18, a: '1h', state: 'found' },
              { id: '0239', t: '189.45.221.103', k: 'IP', c: 0.42, n: 6, a: '3h', state: 'uncertain' },
              { id: '0238', t: 'discord.gg/x9k2', k: 'INVITE', c: 0.88, n: 23, a: '1d', state: 'found' },
              { id: '0237', t: 'rafa_pkr', k: 'GAMER', c: 0.61, n: 9, a: '1d', state: 'likely' },
              { id: '0236', t: 'aurora.cargo.br', k: 'DOMAIN', c: 0.92, n: 14, a: '2d', state: 'found' },
            ].map((r, i) => (
              <div key={r.id} style={{ display: 'grid',
                gridTemplateColumns: '20px 1.6fr 70px 90px 60px 70px',
                gap: 12, alignItems: 'center', padding: '10px 0',
                borderBottom: `1px solid ${S.hair}` }}>
                <div style={{ fontFamily: S.mono, fontSize: 10, color: S.tealDeep }}>{r.id}</div>
                <div style={{ fontFamily: S.mono, fontSize: 12, color: S.ink }}>{r.t}</div>
                <div><SignalStatus state={r.state} /></div>
                <SignalConfBar value={r.c} />
                <div style={{ fontFamily: S.mono, fontSize: 11, color: S.ink }}>{r.n}</div>
                <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkDim }}>{r.a}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Source health panel */}
        <div style={{ gridColumn: 'span 5', background: S.surface,
          border: `1px solid ${S.hair}` }}>
          <PanelHeader title="Source health" right="realtime · 5s" />
          <div style={{ padding: '6px 14px 12px' }}>
            {[
              { n: 'HIBP', h: 0.98, l: '180ms', s: 'ok', cache: '4h', spark: [9,9,8,9,9,9,9,8,9,9] },
              { n: 'OathNet', h: 0.94, l: '420ms', s: 'ok', cache: '12h', spark: [7,8,7,9,8,8,9,8,9,8] },
              { n: 'Holehe', h: 0.92, l: '1.4s', s: 'ok', cache: '24h', spark: [8,7,9,8,9,8,8,9,8,9] },
              { n: 'Sherlock', h: 0.81, l: '2.1s', s: 'deg', cache: '—', spark: [6,4,8,3,7,5,6,4,7,3] },
              { n: 'Discord', h: 1.00, l: '95ms', s: 'ok', cache: '—', spark: [9,9,9,9,9,9,9,9,9,9] },
              { n: 'Stealer idx', h: 0.55, l: '6.8s', s: 'deg', cache: '1h', spark: [4,3,6,2,5,3,7,2,5,3] },
              { n: 'SpiderFoot', h: 0.00, l: '—', s: 'down', cache: '—', spark: [1,1,1,1,1,1,1,1,1,1] },
            ].map((s, i) => (
              <div key={s.n} style={{ display: 'grid',
                gridTemplateColumns: '1.1fr 70px 1fr 50px 14px',
                gap: 10, alignItems: 'center', padding: '8px 0',
                borderTop: i ? `1px solid ${S.hair}` : 'none' }}>
                <div style={{ fontFamily: S.mono, fontSize: 12, color: S.ink }}>{s.n}</div>
                <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkMute }}>{s.h.toFixed(2)}</div>
                <MicroSpark values={s.spark} color={s.s === 'ok' ? S.green : s.s === 'deg' ? S.amber : S.red} width={84} height={16} />
                <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkMute, textAlign: 'right' }}>{s.l}</div>
                <div style={{ width: 8, height: 8, borderRadius: 99,
                  background: s.s === 'ok' ? S.green : s.s === 'deg' ? S.amber : S.red,
                  boxShadow: s.s === 'ok' ? `0 0 0 2px ${S.greenSoft}` : 'none' }} />
              </div>
            ))}
          </div>
        </div>

        {/* Recent events */}
        <div style={{ gridColumn: 'span 8', background: S.surface,
          border: `1px solid ${S.hair}` }}>
          <PanelHeader title="Event feed" right="last 1h · auto-tail" />
          <div style={{ padding: '8px 14px 12px', fontFamily: S.mono, fontSize: 11,
            display: 'flex', flexDirection: 'column' }}>
            {[
              { t: '11:42:18', l: 'HIBP', m: 'breach.match target=lucas.silva conf=0.96', c: S.green },
              { t: '11:42:21', l: 'OATH', m: 'graph.match target=lucas.silva edges=12', c: S.green },
              { t: '11:42:26', l: 'HOLE', m: 'reg.found sites=23/130 lat=1418ms', c: S.green },
              { t: '11:42:29', l: 'WHOIS', m: 'domain.resolved proton.ag CH', c: S.green },
              { t: '11:42:30', l: 'DISC', m: 'username.collision · review needed', c: S.amber },
              { t: '11:42:34', l: 'PASTE', m: 'no.match 8/8 indices clean', c: S.inkMute },
              { t: '11:42:39', l: 'SPDR', m: 'rate.limit retry=120s', c: S.amber },
              { t: '11:42:42', l: 'IMG', m: 'upstream.502 attempts=3 abort', c: S.red },
              { t: '11:42:45', l: 'SHER', m: 'crawl.progress 312/412 platforms', c: S.teal },
              { t: '11:42:51', l: 'STLR', m: 'cold.start eta=18s', c: S.teal },
            ].map((e, i) => (
              <div key={i} style={{ padding: '4px 0', display: 'grid',
                gridTemplateColumns: '70px 50px 1fr', gap: 8 }}>
                <span style={{ color: S.inkDim }}>{e.t}</span>
                <span style={{ color: e.c, fontWeight: 600 }}>{e.l}</span>
                <span style={{ color: S.inkMute }}>{e.m}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Worker pool detail */}
        <div style={{ gridColumn: 'span 4', background: S.surface,
          border: `1px solid ${S.hair}` }}>
          <PanelHeader title="Worker pool" right="cap 5" />
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { id: 'w-01', src: 'Sherlock', t: 'crawling', el: '04:12', state: 'running' },
              { id: 'w-02', src: 'Stealer idx', t: 'cold start', el: '06:18', state: 'running' },
              { id: 'w-03', src: 'Holehe', t: 'wrapping up', el: '01:24', state: 'running' },
              { id: 'w-04', src: '—', t: 'idle', el: '—', state: 'pending' },
              { id: 'w-05', src: '—', t: 'idle', el: '—', state: 'pending' },
            ].map(w => (
              <div key={w.id} style={{ display: 'grid',
                gridTemplateColumns: '50px 1fr 50px 60px', gap: 8, alignItems: 'center' }}>
                <div style={{ fontFamily: S.mono, fontSize: 10, color: S.tealDeep }}>{w.id}</div>
                <div style={{ fontFamily: S.mono, fontSize: 11,
                  color: w.state === 'running' ? S.ink : S.inkDim }}>{w.src} <span style={{ color: S.inkDim }}>· {w.t}</span></div>
                <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkMute }}>{w.el}</div>
                <SignalStatus state={w.state} />
              </div>
            ))}
            <div style={{ marginTop: 8, padding: '8px 0',
              borderTop: `1px solid ${S.hair}`,
              fontFamily: S.mono, fontSize: 10.5, color: S.inkMute }}>
              ram <span style={{ color: S.amber }}>178M</span>/200M ·
              cpu <span style={{ color: S.green }}> 38%</span>
            </div>
          </div>
        </div>

      </div>
    </SignalChrome>
  );
}

function PanelHeader({ title, right }) {
  return (
    <div style={{ padding: '10px 14px', borderBottom: `1px solid ${S.hair}`,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.14em',
        textTransform: 'uppercase', color: S.tealDeep, fontWeight: 600 }}>{title}</div>
      <div style={{ fontFamily: S.mono, fontSize: 9.5, color: S.inkDim,
        letterSpacing: '0.06em' }}>{right}</div>
    </div>
  );
}

function DashStat({ label, value, unit, tint, trend }) {
  const c = tint === 'teal' ? S.teal : tint === 'sand' ? S.sand
    : tint === 'green' ? S.green : S.ink;
  return (
    <div>
      <div style={{ fontFamily: S.mono, fontSize: 9, letterSpacing: '0.14em',
        textTransform: 'uppercase', color: S.inkDim }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 8 }}>
        <div style={{ fontFamily: S.display, fontSize: 30, fontWeight: 600,
          letterSpacing: '-0.03em', color: c }}>{value}</div>
        <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkDim }}>{unit}</div>
      </div>
      <div style={{ marginTop: 6 }}>
        <MicroSpark values={trend} color={c} width={130} height={20} />
      </div>
    </div>
  );
}

function SignalConfBar({ value }) {
  const pct = Math.round(value * 100);
  const c = value > 0.7 ? S.green : value > 0.5 ? S.amber : S.sand;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 3, background: S.hair, position: 'relative' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: c }} />
        {/* tick at 50 */}
        <div style={{ position: 'absolute', top: -2, bottom: -2, left: '50%',
          width: 1, background: S.hairStrong }} />
      </div>
      <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkMute, width: 26,
        textAlign: 'right' }}>.{pct.toString().padStart(2,'0')}</div>
    </div>
  );
}

Object.assign(window, { S, MicroSpark, Dial, SignalStatus, SignalChrome, PanelHeader,
  DashStat, SignalConfBar, SignalIdentity, SignalDashboard });
