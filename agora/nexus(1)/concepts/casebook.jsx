// Concept 2 — CASEBOOK
// Investigation workspace · paper-toned · editorial serif · folder-as-metaphor.

const C = {
  paper: '#f1ebe0',
  paperDeep: '#e8e1d2',
  card: '#faf6ec',
  cardCool: '#f6f1e3',
  ink: '#1a1410',
  inkMute: 'rgba(26,20,16,0.62)',
  inkDim: 'rgba(26,20,16,0.38)',
  inkFaint: 'rgba(26,20,16,0.18)',
  rule: 'rgba(26,20,16,0.10)',
  ruleStrong: 'rgba(26,20,16,0.20)',
  brass: '#a87544',
  brassDeep: '#7e5530',
  brassSoft: 'rgba(168,117,68,0.12)',
  brassBorder: 'rgba(168,117,68,0.32)',
  forensic: '#b04030',
  forensicSoft: 'rgba(176,64,48,0.10)',
  ochre: '#b8902a',
  ochreSoft: 'rgba(184,144,42,0.12)',
  moss: '#5d7244',
  mossSoft: 'rgba(93,114,68,0.12)',
  // editorial
  display: '"Source Serif 4", "Newsreader", Georgia, serif',
  displayItalic: '"Newsreader", "Source Serif 4", Georgia, serif',
  body: '"Inter", system-ui, sans-serif',
  mono: '"JetBrains Mono", monospace',
};

// Wax-seal style source confirmation badge
function Seal({ tone = 'brass', size = 36, letter = 'O' }) {
  const fill = tone === 'brass' ? C.brass : tone === 'forensic' ? C.forensic
    : tone === 'moss' ? C.moss : C.inkDim;
  return (
    <div style={{ width: size, height: size, borderRadius: 99,
      background: `radial-gradient(circle at 30% 30%, ${fill}f0, ${fill}c0 60%, ${fill}90 100%)`,
      border: `1.5px dashed ${fill}`,
      boxShadow: `inset 0 0 0 3px ${C.paper}, inset 0 0 0 4px ${fill}40`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: C.paper, fontFamily: C.display, fontWeight: 700,
      fontSize: size * 0.42, textTransform: 'uppercase',
      letterSpacing: 0, fontStyle: 'italic' }}>{letter}</div>
  );
}

// "Stamped" status — typewriter, slightly rotated, with thin double border
function Stamp({ label, tone = 'brass', rotate = -2 }) {
  const c = tone === 'brass' ? C.brass : tone === 'forensic' ? C.forensic
    : tone === 'moss' ? C.moss : tone === 'ochre' ? C.ochre : C.inkMute;
  return (
    <div style={{ display: 'inline-block', padding: '4px 10px',
      border: `1.5px solid ${c}`, color: c, transform: `rotate(${rotate}deg)`,
      fontFamily: C.mono, fontSize: 9.5, letterSpacing: '0.14em',
      textTransform: 'uppercase', fontWeight: 700, boxShadow: `inset 0 0 0 3px ${C.card}, inset 0 0 0 3.5px ${c}` }}>
      {label}
    </div>
  );
}

// Footnote-style evidence citation marker
function Citation({ n }) {
  return (
    <sup style={{ fontFamily: C.displayItalic, fontStyle: 'italic',
      color: C.brassDeep, fontWeight: 600, fontSize: '0.78em', marginLeft: 2 }}>
      [{n}]
    </sup>
  );
}

// Confidence as "n/m sources concur" + tick marks
function Concur({ confirmed, total, label = 'sources concur' }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: C.display, fontSize: 22, fontWeight: 600,
          color: C.ink, lineHeight: 1, fontStyle: 'italic' }}>
          {confirmed}<span style={{ color: C.inkDim, fontStyle: 'normal' }}>/{total}</span>
        </span>
        <span style={{ fontSize: 11, color: C.inkMute, fontFamily: C.mono,
          letterSpacing: '0.06em' }}>{label}</span>
      </div>
      <div style={{ display: 'flex', gap: 3, marginTop: 6 }}>
        {Array.from({ length: total }).map((_, i) => (
          <div key={i} style={{ width: 14, height: 3,
            background: i < confirmed ? C.brass : C.rule, borderRadius: 1 }} />
        ))}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Identity card
function CasebookIdentity() {
  return (
    <div style={{ width: '100%', height: '100%', background: C.paper, color: C.ink,
      fontFamily: C.body, padding: 48, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 26, position: 'relative',
      // paper grain
      backgroundImage: 'radial-gradient(rgba(26,20,16,0.03) 1px, transparent 1px)',
      backgroundSize: '4px 4px' }}>

      {/* Top stamp marks */}
      <div style={{ position: 'absolute', top: 24, right: 36, display: 'flex', gap: 12 }}>
        <Stamp label="Concept 02" tone="brass" rotate={-3} />
        <Stamp label="Casebook" tone="forensic" rotate={2} />
      </div>

      <div style={{ marginTop: 30 }}>
        <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.18em',
          textTransform: 'uppercase', color: C.brassDeep }}>Investigation Workspace</div>
        <div style={{ fontFamily: C.display, fontSize: 64, fontWeight: 600,
          letterSpacing: '-0.025em', lineHeight: 1, marginTop: 8, color: C.ink }}>
          Case<span style={{ fontStyle: 'italic', fontWeight: 400, color: C.brassDeep }}>book</span>
        </div>
      </div>

      <div style={{ fontFamily: C.display, fontSize: 21, lineHeight: 1.4, color: C.ink,
        maxWidth: 720, fontStyle: 'italic', fontWeight: 400 }}>
        "Toda investigação é um documento sendo escrito. O Nexus é a mesa do investigador —
        evidências empilham, fontes carimbam, e a história se costura por notas de rodapé."
      </div>

      <div>
        <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
          textTransform: 'uppercase', color: C.inkDim, marginBottom: 12 }}>Paleta</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 10 }}>
          <Swatch hex="#f1ebe0" name="Manilla" role="bg" />
          <Swatch hex="#faf6ec" name="Vellum" role="surface" />
          <Swatch hex="#1a1410" name="Ink" role="text" />
          <Swatch hex="#a87544" name="Brass" role="primary" />
          <Swatch hex="#7e5530" name="Brass 700" role="primary deep" />
          <Swatch hex="#b04030" name="Forensic" role="critical" />
          <Swatch hex="#b8902a" name="Ochre" role="likely" />
          <Swatch hex="#5d7244" name="Moss" role="confirmed" />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 28,
        borderTop: `1px solid ${C.rule}`, paddingTop: 24 }}>
        <div>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: C.inkDim, marginBottom: 12 }}>Tipografia & sinais</div>
          <div style={{ fontFamily: C.display, fontSize: 44, fontWeight: 600,
            letterSpacing: '-0.025em', lineHeight: 1.05, color: C.ink }}>
            The evidence,<br/>
            <span style={{ fontStyle: 'italic', fontWeight: 400, color: C.brassDeep }}>
              annotated.</span>
          </div>
          <div style={{ marginTop: 14, fontSize: 13.5, lineHeight: 1.55, color: C.inkMute,
            maxWidth: 480 }}>
            Source Serif 4 (display + body editorial), Inter para UI corrida, JetBrains
            Mono para dados. Itálicos do serif marcam ênfase + nomes de fonte. Citações
            por nota de rodapé numerada<Citation n="01" /> ligam evidência ao raw.
          </div>
          <div style={{ marginTop: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
            <Seal letter="O" tone="brass" />
            <Seal letter="H" tone="moss" />
            <Seal letter="!" tone="forensic" />
            <div style={{ fontSize: 11, fontFamily: C.mono, color: C.inkMute, marginLeft: 6 }}>
              source seals · OathNet, HIBP, alert
            </div>
          </div>
        </div>
        <div>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: C.inkDim, marginBottom: 12 }}>Sensação</div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none',
            display: 'flex', flexDirection: 'column', gap: 9 }}>
            {[
              'Cada caso é uma "pasta" — tabs físicas no topo do workspace',
              'Findings vêm com nota de rodapé numerada → evidência raw clicável',
              'Status de fonte = stamp (carimbo) com leve rotação, não pill genérica',
              'Confidence = "4/8 sources concur" em tipo serif, não barra de progresso',
              'Real-time = diário do caso (timeline) atualizando ao vivo',
            ].map(t => (
              <li key={t} style={{ fontSize: 13, lineHeight: 1.45, color: C.ink,
                paddingLeft: 14, position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 7, width: 5, height: 5,
                  borderRadius: 99, background: C.brass }} />{t}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// Shared chrome: top with folder tabs
function CasebookChrome({ activeTab = 0, tabs, children, sub }) {
  const _tabs = tabs || [
    { id: 'home', label: 'Home' },
    { id: 'c-0241', label: 'lucas.silva', n: '0241', kind: 'EMAIL' },
    { id: 'c-0238', label: '@nbreaker',  n: '0238', kind: 'HANDLE' },
    { id: 'c-0237', label: '189.45.221', n: '0237', kind: 'IP' },
  ];
  return (
    <div style={{ width: '100%', height: '100%', background: C.paper, color: C.ink,
      fontFamily: C.body, display: 'flex', flexDirection: 'column', overflow: 'hidden',
      backgroundImage: 'radial-gradient(rgba(26,20,16,0.025) 1px, transparent 1px)',
      backgroundSize: '4px 4px' }}>
      {/* Top bar */}
      <div style={{ padding: '14px 28px 0', display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 18, height: 22, background: C.ink,
            position: 'relative', clipPath: 'polygon(0 0, 70% 0, 100% 25%, 100% 100%, 0 100%)' }} />
          <div style={{ fontFamily: C.display, fontWeight: 600, fontSize: 18,
            letterSpacing: '-0.02em' }}>Nexus<span style={{ fontStyle: 'italic',
              fontWeight: 400, color: C.brassDeep }}>·Casebook</span></div>
        </div>
        <div style={{ height: 18, width: 1, background: C.ruleStrong }} />
        <div style={{ fontFamily: C.mono, fontSize: 11, color: C.inkMute }}>
          {sub || 'Workspace · 12 open cases · 3 awaiting review'}</div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ fontFamily: C.mono, fontSize: 11, color: C.inkMute }}>⌘K · go to case</div>
          <div style={{ width: 30, height: 30, borderRadius: 99, background: C.brass,
            color: C.paper, fontSize: 12, fontWeight: 600, fontFamily: C.display,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontStyle: 'italic' }}>m</div>
        </div>
      </div>

      {/* Folder tabs */}
      <div style={{ padding: '18px 28px 0', display: 'flex', alignItems: 'flex-end', gap: -1,
        borderBottom: `1.5px solid ${C.ink}` }}>
        {_tabs.map((t, i) => (
          <div key={t.id} style={{
            padding: '10px 18px 12px', marginRight: -1,
            background: i === activeTab ? C.card : C.paperDeep,
            border: `1px solid ${i === activeTab ? C.ink : C.rule}`,
            borderBottom: i === activeTab ? `1.5px solid ${C.card}` : `1.5px solid ${C.ink}`,
            marginBottom: i === activeTab ? -1.5 : 0,
            borderTopLeftRadius: 8, borderTopRightRadius: 8,
            position: 'relative', zIndex: i === activeTab ? 2 : 1,
            display: 'flex', alignItems: 'center', gap: 8,
            fontFamily: C.body, fontSize: 12.5, color: i === activeTab ? C.ink : C.inkMute,
            fontWeight: i === activeTab ? 600 : 400 }}>
            {t.n && <span style={{ fontFamily: C.mono, fontSize: 10,
              color: i === activeTab ? C.brassDeep : C.inkDim }}>№{t.n}</span>}
            <span>{t.label}</span>
            {t.kind && <span style={{ fontFamily: C.mono, fontSize: 9, color: C.inkDim,
              letterSpacing: '0.1em' }}>{t.kind}</span>}
          </div>
        ))}
        <div style={{ marginLeft: 8, padding: '8px 12px', fontSize: 12, color: C.inkMute,
          fontFamily: C.mono }}>+ new</div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', background: C.card }}>{children}</div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Dashboard — "home" of casebook
function CasebookDashboard() {
  return (
    <CasebookChrome activeTab={0}>
      <div style={{ padding: '32px 36px', display: 'flex', flexDirection: 'column', gap: 28,
        maxWidth: 1180, margin: '0 auto' }}>
        {/* Cover heading */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 36,
          alignItems: 'end', borderBottom: `1.5px solid ${C.ink}`, paddingBottom: 20 }}>
          <div>
            <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.18em',
              textTransform: 'uppercase', color: C.brassDeep }}>Daybook · Friday, 12 Set</div>
            <div style={{ fontFamily: C.display, fontSize: 44, fontWeight: 600,
              letterSpacing: '-0.025em', marginTop: 8, lineHeight: 1.05 }}>
              Three cases waiting,<br/>
              <span style={{ fontStyle: 'italic', fontWeight: 400, color: C.brassDeep }}>
                one closed overnight.</span>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8,
            fontFamily: C.mono, fontSize: 11, color: C.inkMute, textAlign: 'right' }}>
            <div>active investigations · <span style={{ color: C.ink, fontWeight: 600 }}>7</span></div>
            <div>sources online · <span style={{ color: C.ink, fontWeight: 600 }}>14 / 16</span></div>
            <div>avg confidence · <span style={{ color: C.brassDeep, fontWeight: 600 }}>0.78</span></div>
            <div>median lat. · <span style={{ color: C.ink, fontWeight: 600 }}>4.1s</span></div>
          </div>
        </div>

        {/* Open cases as folder cards */}
        <div>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: C.inkDim, marginBottom: 14 }}>Open cases</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            {[
              { n: '0241', t: 'lucas.silva@protonmail.com', kind: 'Email',
                conf: { c: 7, m: 8 }, sev: 'critical', ago: '12 min', notes: 47 },
              { n: '0238', t: '@nbreaker', kind: 'Handle',
                conf: { c: 4, m: 7 }, sev: 'high', ago: '1 h', notes: 18 },
              { n: '0237', t: '189.45.221.103', kind: 'IP',
                conf: { c: 2, m: 6 }, sev: 'medium', ago: '3 h', notes: 6 },
              { n: '0236', t: 'discord.gg/x9k2', kind: 'Discord',
                conf: { c: 5, m: 6 }, sev: 'high', ago: 'yesterday', notes: 23 },
              { n: '0235', t: 'rafa_pkr', kind: 'Gaming',
                conf: { c: 3, m: 6 }, sev: 'medium', ago: 'yesterday', notes: 9 },
              { n: '0234', t: 'aurora.cargo.br', kind: 'Domain',
                conf: { c: 6, m: 7 }, sev: 'low', ago: '2 d', notes: 14 },
            ].map(c => (
              <div key={c.n} style={{ background: C.card,
                border: `1px solid ${C.rule}`, borderTop: `3px solid ${
                  c.sev === 'critical' ? C.forensic : c.sev === 'high' ? C.ochre
                  : c.sev === 'medium' ? C.brass : C.moss }`,
                padding: 16, position: 'relative',
                boxShadow: '2px 3px 0 rgba(26,20,16,0.04)' }}>
                <div style={{ display: 'flex', alignItems: 'baseline',
                  justifyContent: 'space-between' }}>
                  <div style={{ fontFamily: C.mono, fontSize: 10, color: C.brassDeep,
                    letterSpacing: '0.1em' }}>№{c.n} · {c.kind.toUpperCase()}</div>
                  <div style={{ fontFamily: C.mono, fontSize: 10, color: C.inkDim }}>{c.ago}</div>
                </div>
                <div style={{ fontFamily: C.display, fontSize: 18, fontWeight: 600,
                  marginTop: 6, letterSpacing: '-0.01em',
                  fontFamily: c.kind === 'Email' || c.kind === 'IP' || c.kind === 'Domain'
                    ? C.mono : C.display,
                  fontStyle: c.kind === 'Handle' ? 'italic' : 'normal',
                  fontSize: c.kind === 'Email' || c.kind === 'IP' || c.kind === 'Domain' ? 14 : 19 }}>
                  {c.t}
                </div>
                <div style={{ marginTop: 14 }}>
                  <Concur confirmed={c.conf.c} total={c.conf.m} />
                </div>
                <div style={{ marginTop: 12, paddingTop: 12,
                  borderTop: `1px solid ${C.rule}`,
                  display: 'flex', justifyContent: 'space-between',
                  alignItems: 'center', fontSize: 11, color: C.inkMute }}>
                  <span style={{ fontFamily: C.displayItalic, fontStyle: 'italic' }}>
                    {c.notes} findings</span>
                  <Stamp label={c.sev} tone={c.sev === 'critical' ? 'forensic'
                    : c.sev === 'high' ? 'ochre' : c.sev === 'medium' ? 'brass' : 'moss'}
                    rotate={Math.sin(parseInt(c.n)) * 3} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Source ledger */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 20 }}>
          <div style={{ background: C.cardCool, border: `1px solid ${C.rule}`, padding: 22 }}>
            <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: C.inkDim, marginBottom: 14 }}>
              Source ledger · live</div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ fontFamily: C.mono, fontSize: 9, color: C.inkDim,
                  letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  <th style={{ textAlign: 'left', padding: '6px 0',
                    borderBottom: `1.5px solid ${C.ink}` }}>Source</th>
                  <th style={{ textAlign: 'right', padding: '6px 0',
                    borderBottom: `1.5px solid ${C.ink}` }}>Health</th>
                  <th style={{ textAlign: 'right', padding: '6px 0',
                    borderBottom: `1.5px solid ${C.ink}` }}>p95</th>
                  <th style={{ textAlign: 'right', padding: '6px 0',
                    borderBottom: `1.5px solid ${C.ink}` }}>State</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { n: 'HIBP', h: '0.98', l: '180ms', s: 'ok' },
                  { n: 'OathNet', h: '0.94', l: '420ms', s: 'ok' },
                  { n: 'Holehe', h: '0.92', l: '1.4s', s: 'ok' },
                  { n: 'Sherlock', h: '0.81', l: '2.1s', s: 'degraded' },
                  { n: 'Stealer index', h: '0.55', l: '6.8s', s: 'degraded' },
                  { n: 'SpiderFoot', h: '—', l: '—', s: 'down' },
                ].map((r, i) => (
                  <tr key={r.n} style={{ borderBottom: `1px solid ${C.rule}` }}>
                    <td style={{ padding: '10px 0', fontFamily: C.display, fontSize: 13,
                      fontStyle: 'italic', color: C.ink }}>{r.n}</td>
                    <td style={{ padding: '10px 0', textAlign: 'right', fontFamily: C.mono,
                      fontSize: 11, color: C.inkMute }}>{r.h}</td>
                    <td style={{ padding: '10px 0', textAlign: 'right', fontFamily: C.mono,
                      fontSize: 11, color: C.inkMute }}>{r.l}</td>
                    <td style={{ padding: '10px 0', textAlign: 'right' }}>
                      <Stamp label={r.s === 'ok' ? 'online' : r.s} tone={
                        r.s === 'ok' ? 'moss' : r.s === 'degraded' ? 'ochre' : 'forensic'
                      } rotate={r.s === 'ok' ? -1 : 2} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Daybook entry */}
          <div style={{ padding: 22, background: C.card,
            border: `1px solid ${C.rule}`, position: 'relative' }}>
            <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: C.inkDim, marginBottom: 14 }}>
              Daybook entry</div>
            <div style={{ fontFamily: C.displayItalic, fontStyle: 'italic',
              fontSize: 15, lineHeight: 1.55, color: C.ink }}>
              <span style={{ fontWeight: 600, color: C.brassDeep, fontStyle: 'normal',
                fontFamily: C.mono, fontSize: 11 }}>09:42 ·</span>{' '}
              Caso №0241 reaberto. OathNet confirma vínculo email↔hash em <em>collection-1</em>.
              <Citation n="03" /> Aguardando Sherlock para mapear handles correlatos.
            </div>
            <div style={{ marginTop: 14, fontFamily: C.displayItalic, fontStyle: 'italic',
              fontSize: 15, lineHeight: 1.55, color: C.inkMute }}>
              <span style={{ fontWeight: 600, color: C.brassDeep, fontStyle: 'normal',
                fontFamily: C.mono, fontSize: 11 }}>11:18 ·</span>{' '}
              Stealer index degradado — latência subiu para 6.8s.<Citation n="04" /> Avaliando
              fallback para cache local.
            </div>
          </div>
        </div>
      </div>
    </CasebookChrome>
  );
}

Object.assign(window, { C, Seal, Stamp, Citation, Concur, CasebookChrome,
  CasebookIdentity, CasebookDashboard });
