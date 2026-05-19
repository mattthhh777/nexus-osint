// Signal v2 — screens (Simple/Analyst dashboards, Gantt hero, categorized results, Casebook export).
const { S, MicroSpark, Dial, SignalStatus, SignalConfBar, PanelHeader } = window;
const { C: Cb, Stamp, Seal, Citation, Concur } = window;
const { CAT, CatChip, ViewSwitch, SignalChromeQuiet } = window;

// ──────────────────────────────────────────────────────────
// SIMPLE VIEW · DASHBOARD
function SignalSimpleDashboard() {
  return (
    <SignalChromeQuiet mode="simple" active="home"
      contextLine="mattheus@nexus · 12 cases">
      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 18,
        maxWidth: 1200, margin: '0 auto' }}>

        {/* Hero greeting */}
        <div style={{ display: 'flex', justifyContent: 'space-between',
          alignItems: 'flex-end', paddingBottom: 12,
          borderBottom: `1px solid ${S.hair}` }}>
          <div>
            <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: S.tealDeep }}>Good evening, Mattheus</div>
            <div style={{ fontFamily: S.display, fontSize: 30, fontWeight: 600,
              letterSpacing: '-0.025em', marginTop: 6, lineHeight: 1.1 }}>
              3 cases pending review,{' '}
              <span style={{ color: S.green }}>1 closed overnight.</span>
            </div>
          </div>
          <button style={{
            background: S.tealSoft, color: S.teal,
            border: `1px solid ${S.tealBorder}`,
            padding: '10px 16px', fontFamily: S.body, fontSize: 13, fontWeight: 500,
            letterSpacing: '-0.005em', cursor: 'default' }}>+ New investigation</button>
        </div>

        {/* Stat row — only what matters to a normal user */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {[
            { k: 'Active investigations', v: '7', sub: '+2 this week', c: S.ink },
            { k: 'Findings · last 7d', v: '184', sub: 'across 6 cases', c: S.ink },
            { k: 'Avg confidence', v: '0.78', sub: 'high', c: S.green },
          ].map(s => (
            <div key={s.k} style={{ background: S.surface, border: `1px solid ${S.hair}`,
              padding: 18 }}>
              <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.14em',
                textTransform: 'uppercase', color: S.inkDim }}>{s.k}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8 }}>
                <div style={{ fontFamily: S.display, fontSize: 34, fontWeight: 600,
                  letterSpacing: '-0.03em', color: s.c }}>{s.v}</div>
              </div>
              <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
                marginTop: 6, letterSpacing: '0.04em' }}>{s.sub}</div>
            </div>
          ))}
        </div>

        {/* Recent investigations — clean list, NO technical metrics */}
        <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
          <PanelHeader title="Recent investigations" right="view all →" />
          <div style={{ padding: '4px 16px 12px' }}>
            {[
              { id: '0241', t: 'lucas.silva@protonmail.com', kind: 'email',
                conf: 0.84, verdict: 'critical', ago: '12 min', n: 43 },
              { id: '0240', t: '@nbreaker', kind: 'handle',
                conf: 0.71, verdict: 'high', ago: '1 h', n: 18 },
              { id: '0239', t: '189.45.221.103', kind: 'ip',
                conf: 0.42, verdict: 'medium', ago: '3 h', n: 6 },
              { id: '0238', t: 'discord.gg/x9k2', kind: 'invite',
                conf: 0.88, verdict: 'high', ago: 'yesterday', n: 23 },
              { id: '0237', t: 'rafa_pkr', kind: 'gamer',
                conf: 0.61, verdict: 'medium', ago: 'yesterday', n: 9 },
              { id: '0236', t: 'aurora.cargo.br', kind: 'domain',
                conf: 0.92, verdict: 'low', ago: '2 d', n: 14 },
            ].map((r, i) => (
              <div key={r.id} style={{ display: 'grid',
                gridTemplateColumns: '50px 1.5fr 60px 80px 90px 80px',
                gap: 12, alignItems: 'center', padding: '12px 0',
                borderTop: i ? `1px solid ${S.hair}` : 'none' }}>
                <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.tealDeep }}>
                  №{r.id}</div>
                <div>
                  <div style={{ fontFamily: S.mono, fontSize: 13, color: S.ink }}>{r.t}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 9.5, color: S.inkDim,
                    marginTop: 2, letterSpacing: '0.08em',
                    textTransform: 'uppercase' }}>{r.kind} · {r.ago}</div>
                </div>
                <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>
                  {r.n} <span style={{ color: S.inkDim }}>finds</span></div>
                <SignalConfBar value={r.conf} />
                <VerdictTag v={r.verdict} />
                <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkDim,
                  textAlign: 'right' }}>open →</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SignalChromeQuiet>
  );
}

function VerdictTag({ v }) {
  const cfg = {
    critical: { c: S.red, t: 'Critical' },
    high:     { c: S.amber, t: 'High' },
    medium:   { c: S.yellow, t: 'Medium' },
    low:      { c: S.green, t: 'Low' },
  }[v] || { c: S.inkDim, t: v };
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 10px', border: `1px solid ${cfg.c}40`,
      background: 'transparent',
      fontFamily: S.mono, fontSize: 10, color: cfg.c,
      letterSpacing: '0.12em', textTransform: 'uppercase', fontWeight: 600 }}>
      <div style={{ width: 4, height: 4, borderRadius: 99, background: cfg.c }} />
      {cfg.t}
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// HERO GANTT BOARD — the central piece, given full real estate
function GanttHero() {
  // Build source rows with start/end seconds and final state
  const rows = [
    { n: 'HIBP', cat: 'exposure', desc: 'breach index', state: 'found', n2: 7, start: 0, end: 0.5, conf: 0.96 },
    { n: 'OathNet', cat: 'exposure', desc: 'credential graph', state: 'found', n2: 12, start: 1, end: 8, conf: 0.88 },
    { n: 'Stealer index', cat: 'exposure', desc: 'in-house logs', state: 'running', n2: null, start: 0, end: null, prog: 0.42 },

    { n: 'WHOIS', cat: 'identity', desc: 'domain owner', state: 'found', n2: 1, start: 0, end: 4, conf: 0.99 },
    { n: 'Holehe', cat: 'identity', desc: 'email registrations', state: 'found', n2: 23, start: 0, end: 24, conf: 0.74 },
    { n: 'Phone intel', cat: 'identity', desc: 'reverse lookup', state: 'not_found', n2: 0, start: 1, end: 6, conf: 0.95 },

    { n: 'Sherlock', cat: 'social', desc: '412 social platforms', state: 'running', n2: null, start: 0, end: null, prog: 0.76 },
    { n: 'Discord', cat: 'social', desc: 'username lookup', state: 'likely', n2: 1, start: 0, end: 1, conf: 0.52 },
    { n: 'Gaming profiles', cat: 'social', desc: 'steam/origin/epic', state: 'pending', n2: null, start: null, end: null },

    { n: 'GeoIP', cat: 'infra', desc: 'maxmind', state: 'found', n2: 2, start: 0, end: 0.3, conf: 0.92 },
    { n: 'SpiderFoot', cat: 'infra', desc: 'enrichment', state: 'blocked', n2: null, start: 0, end: 2 },
    { n: 'Reverse-image', cat: 'infra', desc: 'context match', state: 'error', n2: null, start: 0, end: 14 },
  ];

  const T = 60; // total seconds shown
  const groupedByCat = ['exposure','identity','social','infra'].map(catId => ({
    cat: catId, rows: rows.filter(r => r.cat === catId),
  }));

  return (
    <div style={{ width: '100%', height: '100%', background: S.bg, color: S.ink,
      fontFamily: S.body, padding: 24, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 14, overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
        paddingBottom: 12, borderBottom: `1px solid ${S.hair}` }}>
        <div>
          <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.18em',
            textTransform: 'uppercase', color: S.teal }}>Source timeline · live</div>
          <div style={{ fontFamily: S.display, fontSize: 26, fontWeight: 600,
            letterSpacing: '-0.025em', marginTop: 4 }}>
            <span style={{ fontFamily: S.mono, color: S.ink, fontSize: 18 }}>
              lucas.silva@protonmail.com</span>
            <span style={{ color: S.inkMute, marginLeft: 12, fontWeight: 400, fontSize: 22 }}>
              · 4 of 12 sources finished</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <Dial value={0.84} label="confidence" size={62} color={S.teal} />
          <Dial value={4 / 12} label="progress" size={62} color={S.green} />
          <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute,
            textAlign: 'right', lineHeight: 1.5 }}>
            <div>elapsed · <span style={{ color: S.ink }}>00:08</span></div>
            <div>eta · <span style={{ color: S.sand }}>00:46</span></div>
          </div>
        </div>
      </div>

      {/* Category legend */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {['exposure','identity','social','infra'].map(id => {
          const count = rows.filter(r => r.cat === id).length;
          return <CatChip key={id} cat={id} n={count} active />;
        })}
      </div>

      {/* Gantt */}
      <div style={{ background: S.surface, border: `1px solid ${S.hair}`, flex: 1,
        display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Time scale header */}
        <div style={{ display: 'grid',
          gridTemplateColumns: '220px 90px 60px 1fr 70px',
          gap: 14, padding: '12px 18px', borderBottom: `1px solid ${S.hair}`,
          fontFamily: S.mono, fontSize: 9, color: S.inkDim,
          letterSpacing: '0.12em', textTransform: 'uppercase',
          alignItems: 'center' }}>
          <div>source · description</div>
          <div>state</div>
          <div>hits</div>
          <div style={{ position: 'relative', height: 16 }}>
            {[0, 15, 30, 45, 60].map(t => (
              <div key={t} style={{ position: 'absolute',
                left: `${(t / T) * 100}%`, top: 0, bottom: 0,
                fontFamily: S.mono, fontSize: 9, color: S.inkDim,
                transform: t === 60 ? 'translateX(-100%)' : 'none' }}>{t}s</div>
            ))}
            {/* Vertical guides */}
            {[15, 30, 45].map(t => (
              <div key={t} style={{ position: 'absolute',
                left: `${(t / T) * 100}%`, top: 16, height: 8, width: 1,
                background: S.hair }} />
            ))}
          </div>
          <div style={{ textAlign: 'right' }}>conf</div>
        </div>

        {/* Rows grouped by category */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {groupedByCat.map(({ cat, rows: catRows }, gi) => {
            const c = CAT[cat];
            return (
              <div key={cat}>
                {/* Category header */}
                <div style={{ display: 'grid',
                  gridTemplateColumns: '220px 1fr',
                  gap: 14, padding: '10px 18px',
                  background: S.bgRecess,
                  borderTop: gi ? `1px solid ${S.hair}` : 'none',
                  alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ color: c.color, fontSize: 13 }}>{c.icon}</span>
                    <span style={{ fontFamily: S.mono, fontSize: 10,
                      color: c.color, letterSpacing: '0.14em',
                      textTransform: 'uppercase', fontWeight: 600 }}>{c.label}</span>
                    <span style={{ fontFamily: S.mono, fontSize: 10,
                      color: S.inkDim, letterSpacing: '0.06em' }}>{c.sub}</span>
                  </div>
                  <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkDim }}>
                    {catRows.filter(r => r.state === 'found' || r.state === 'likely').length}
                    {' '}signal · {catRows.filter(r => r.state === 'running').length} running ·
                    {' '}{catRows.filter(r => r.state === 'blocked' || r.state === 'error').length} failed
                  </div>
                </div>

                {/* Bars */}
                {catRows.map((r, i) => {
                  const tone = r.state === 'found' ? c.color :
                    r.state === 'likely' ? S.amber :
                    r.state === 'running' ? S.teal :
                    r.state === 'blocked' ? S.amber :
                    r.state === 'error' ? S.red :
                    r.state === 'not_found' ? S.inkMute : S.inkDim;
                  return (
                    <div key={i} style={{ display: 'grid',
                      gridTemplateColumns: '220px 90px 60px 1fr 70px',
                      gap: 14, padding: '10px 18px', alignItems: 'center',
                      borderTop: `1px solid ${S.hair}` }}>
                      <div>
                        <div style={{ fontFamily: S.mono, fontSize: 12, color: S.ink }}>{r.n}</div>
                        <div style={{ fontFamily: S.mono, fontSize: 9.5, color: S.inkDim,
                          marginTop: 2 }}>{r.desc}</div>
                      </div>
                      <SignalStatus state={r.state} />
                      <div style={{ fontFamily: S.mono, fontSize: 11,
                        color: r.n2 != null ? S.ink : S.inkDim }}>
                        {r.n2 != null ? `${r.n2}` : '—'}</div>
                      <div style={{ position: 'relative', height: 20,
                        background: S.bgRecess, border: `1px solid ${S.hair}` }}>
                        {/* Grid lines */}
                        {[15, 30, 45].map(t => (
                          <div key={t} style={{ position: 'absolute',
                            left: `${(t / T) * 100}%`, top: 0, bottom: 0,
                            width: 1, background: S.hair }} />
                        ))}
                        {/* Bar */}
                        {r.start != null && (
                          <div style={{ position: 'absolute', top: 1, bottom: 1,
                            left: `${(r.start / T) * 100}%`,
                            width: r.end != null
                              ? `${((r.end - r.start) / T) * 100}%`
                              : `${((r.prog || 0.1) * 8 / T) * 100}%`,
                            background: r.state === 'running'
                              ? `repeating-linear-gradient(45deg, ${tone}30 0 8px, ${tone}70 8px 16px)`
                              : tone + '35',
                            borderLeft: `2px solid ${tone}`,
                            borderRight: r.end != null ? `1px solid ${tone}80` : 'none' }} />
                        )}
                        {/* "now" indicator at 8s */}
                        <div style={{ position: 'absolute', left: `${(8 / T) * 100}%`,
                          top: -2, bottom: -2, width: 1, background: S.teal,
                          boxShadow: `0 0 0 1px ${S.tealSoft}` }} />
                      </div>
                      <div style={{ fontFamily: S.mono, fontSize: 10.5,
                        textAlign: 'right',
                        color: r.conf != null ? tone : S.inkDim }}>
                        {r.conf != null ? `.${Math.round(r.conf * 100)}` :
                          r.prog != null ? `${Math.round(r.prog * 100)}%` : '—'}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* Footer ribbon: "now" marker explanation */}
        <div style={{ padding: '8px 18px', borderTop: `1px solid ${S.hair}`,
          background: S.bgRecess,
          display: 'flex', alignItems: 'center', gap: 16,
          fontFamily: S.mono, fontSize: 10, color: S.inkMute,
          letterSpacing: '0.06em' }}>
          <span>● now · 00:08</span>
          <span style={{ color: S.hairStrong }}>│</span>
          <span style={{ color: S.green }}>▮ found · 7</span>
          <span style={{ color: S.amber }}>▮ likely/blocked · 2</span>
          <span style={{ color: S.teal }}>▮ running · 2</span>
          <span style={{ color: S.inkMute }}>▮ not found · 1</span>
          <span style={{ color: S.red }}>▮ error · 1</span>
          <span style={{ flex: 1 }} />
          <span>auto-scroll on</span>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// SIMPLE VIEW · RESULTS (findings grouped by category)
function SignalSimpleResults() {
  return (
    <SignalChromeQuiet mode="simple" active="cases" live={false}
      contextLine="case №0241 · lucas.silva@protonmail.com">
      <div style={{ padding: 24, display: 'grid',
        gridTemplateColumns: '1fr 300px', gap: 18,
        maxWidth: 1280, margin: '0 auto', alignItems: 'start' }}>

        {/* Main column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Title */}
          <div>
            <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.18em',
              textTransform: 'uppercase', color: S.tealDeep }}>Case №0241</div>
            <div style={{ fontFamily: S.mono, fontSize: 22, color: S.ink,
              marginTop: 4 }}>lucas.silva@protonmail.com</div>
            <div style={{ fontFamily: S.display, fontSize: 16, color: S.inkMute,
              marginTop: 6 }}>43 findings · 8 sources confirming · 2 manual review</div>
          </div>

          {/* Category navigator */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <CatChip cat="exposure" n={4} active />
            <CatChip cat="identity" n={24} active />
            <CatChip cat="social" n={13} active />
            <CatChip cat="infra" n={2} active />
          </div>

          {/* § Exposure */}
          <CategorySection
            cat="exposure"
            count={4}
            note="Credenciais e dados vazados — atenção urgente."
            items={[
              <BreachItem n="Genesis Market log" date="2022-11" src="OathNet" sev="critical"
                leak="cookies, fingerprint, password" />,
              <BreachItem n="Antipublic 2.0" date="2020-04" src="HIBP" sev="critical"
                leak="email, password, ip" />,
              <BreachItem n="Collection #1" date="2019-01" src="HIBP" sev="high"
                leak="email, sha1(password)" />,
              <StealerItem id="RC-2Z1L-088" os="Win 11 · pt-BR" ago="11d" n={40} sev="critical" />,
            ]} />

          {/* § Identity */}
          <CategorySection
            cat="identity"
            count={24}
            note="Sinais que confirmam a pessoa."
            items={[
              <KvItem k="Primary email" v="lucas.silva@protonmail.com" src="OathNet · HIBP"
                conf={0.96} />,
              <KvItem k="Domain owner" v="protonmail.com · Proton AG · CH" src="WHOIS" conf={0.99} />,
              <KvItem k="Linked emails" v="22 alt addresses found" src="Holehe" conf={0.74} sub="see all" />,
              <KvItem k="Phone" v="—" src="phone intel" conf={null}
                stateLabel="not found" />,
            ]} />

          {/* § Social */}
          <CategorySection
            cat="social"
            count={13}
            note="Pegada pública — twitter, github, discord, gaming."
            items={[
              <TagCloud sites={['twitter','github','spotify','instagram','reddit',
                'linkedin','medium','pinterest','soundcloud','dropbox','figma',
                'notion','vimeo','airbnb','duolingo','strava','goodreads','adobe',
                'last.fm','steam','origin','epic','xbox']} />,
              <KvItem k="Discord" v="lucas#0117 (likely)" src="Discord lookup"
                conf={0.52} stateLabel="needs review" />,
            ]} />

          {/* § Infra */}
          <CategorySection
            cat="infra"
            count={2}
            note="Contexto técnico ao redor."
            items={[
              <KvItem k="Geo (last login)" v="São Paulo · BR · AS28573" src="GeoIP · MaxMind"
                conf={0.92} />,
              <KvItem k="ASN history" v="vivo broadband · stable 11mo" src="GeoIP" conf={0.88} />,
            ]} />
        </div>

        {/* Right rail */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 12,
          position: 'sticky', top: 0 }}>
          <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
            <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: S.tealDeep }}>Overall</div>
            <div style={{ display: 'flex', gap: 14, marginTop: 12 }}>
              <Dial value={0.84} label="conf" size={76} color={S.teal} />
              <Dial value={0.74} label="risk" size={76} color={S.red} />
            </div>
          </div>

          <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
            <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: S.inkDim }}>Verdict</div>
            <div style={{ fontFamily: S.display, fontSize: 28, fontWeight: 600,
              color: S.red, letterSpacing: '-0.025em', marginTop: 8 }}>Critical</div>
            <div style={{ fontSize: 12.5, color: S.inkMute, lineHeight: 1.55,
              marginTop: 10 }}>
              Credenciais ativas em 2 dumps recentes, incluindo session cookies.
              Recomendar rotação de senha e auditoria 2FA imediatas.
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[
              ['save to case', S.teal],
              ['export · dossier PDF', S.sand],
              ['export · raw JSON', null],
              ['share read-only link', null],
            ].map(([t, c], i) => (
              <button key={t} style={{
                padding: '11px 14px', textAlign: 'left',
                background: c ? c + '10' : 'transparent',
                color: c || S.inkMute,
                border: `1px solid ${c ? c + '40' : S.hair}`,
                fontFamily: S.mono, fontSize: 11, letterSpacing: '0.08em',
                textTransform: 'uppercase', cursor: 'default',
                fontWeight: c ? 600 : 500 }}>{t}</button>
            ))}
          </div>
        </aside>
      </div>
    </SignalChromeQuiet>
  );
}

function CategorySection({ cat, count, note, items }) {
  const c = CAT[cat];
  return (
    <section style={{ background: S.surface, border: `1px solid ${S.hair}`,
      borderTop: `2px solid ${c.color}` }}>
      <div style={{ padding: '12px 18px', borderBottom: `1px solid ${S.hair}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: c.color, fontSize: 13 }}>{c.icon}</span>
          <div>
            <div style={{ fontFamily: S.mono, fontSize: 10.5, color: c.color,
              letterSpacing: '0.14em', textTransform: 'uppercase',
              fontWeight: 600 }}>{c.label}</div>
            <div style={{ fontFamily: S.mono, fontSize: 9.5, color: S.inkDim,
              letterSpacing: '0.06em', marginTop: 2 }}>{c.sub}</div>
          </div>
        </div>
        <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>
          <span style={{ color: c.color, fontWeight: 600 }}>{count}</span> findings
        </div>
      </div>
      <div style={{ padding: '4px 18px 14px', fontSize: 12, color: S.inkMute,
        lineHeight: 1.5, paddingTop: 10, fontStyle: 'italic' }}>{note}</div>
      <div style={{ padding: '0 18px 14px', display: 'flex', flexDirection: 'column',
        gap: 8 }}>
        {items.map((it, i) => <div key={i}>{it}</div>)}
      </div>
    </section>
  );
}

function BreachItem({ n, date, src, sev, leak }) {
  const c = sev === 'critical' ? S.red : sev === 'high' ? S.amber
    : sev === 'medium' ? S.yellow : S.green;
  return (
    <div style={{ display: 'grid',
      gridTemplateColumns: '1.4fr 70px 60px 1.4fr 80px',
      gap: 12, padding: '10px 12px', alignItems: 'center',
      background: S.bgRecess, borderLeft: `3px solid ${c}` }}>
      <div style={{ fontFamily: S.body, fontSize: 13, color: S.ink, fontWeight: 500 }}>{n}</div>
      <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>{date}</div>
      <div style={{ fontFamily: S.mono, fontSize: 10, color: S.tealDeep,
        letterSpacing: '0.06em' }}>{src}</div>
      <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>{leak}</div>
      <div style={{ fontFamily: S.mono, fontSize: 10, color: c,
        letterSpacing: '0.14em', textTransform: 'uppercase',
        fontWeight: 700 }}>{sev}</div>
    </div>
  );
}

function StealerItem({ id, os, ago, n, sev }) {
  const c = sev === 'critical' ? S.red : S.amber;
  return (
    <div style={{ display: 'grid',
      gridTemplateColumns: '1.4fr 70px 60px 1.4fr 80px',
      gap: 12, padding: '10px 12px', alignItems: 'center',
      background: S.bgRecess, borderLeft: `3px solid ${c}` }}>
      <div>
        <div style={{ fontFamily: S.mono, fontSize: 12, color: c, fontWeight: 600 }}>
          stealer log · {id}</div>
        <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkDim, marginTop: 2 }}>
          {n} files · device compromised</div>
      </div>
      <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>{ago}</div>
      <div style={{ fontFamily: S.mono, fontSize: 10, color: S.tealDeep }}>stealer</div>
      <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>{os}</div>
      <div style={{ fontFamily: S.mono, fontSize: 10, color: c,
        letterSpacing: '0.14em', textTransform: 'uppercase',
        fontWeight: 700 }}>{sev}</div>
    </div>
  );
}

function KvItem({ k, v, src, conf, sub, stateLabel }) {
  return (
    <div style={{ display: 'grid',
      gridTemplateColumns: '1fr 1.6fr 90px 90px',
      gap: 12, padding: '10px 12px', alignItems: 'center',
      background: S.bgRecess }}>
      <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkDim,
        letterSpacing: '0.06em', textTransform: 'uppercase' }}>{k}</div>
      <div>
        <div style={{ fontFamily: S.mono, fontSize: 12.5, color: S.ink }}>{v}</div>
        {sub && <div style={{ fontFamily: S.mono, fontSize: 10, color: S.tealDeep,
          marginTop: 2 }}>{sub} ›</div>}
      </div>
      <div style={{ fontFamily: S.mono, fontSize: 10, color: S.tealDeep,
        letterSpacing: '0.06em' }}>{src}</div>
      <div style={{ textAlign: 'right' }}>
        {conf != null
          ? <SignalConfBar value={conf} />
          : <span style={{ fontFamily: S.mono, fontSize: 10, color: S.inkDim,
              letterSpacing: '0.1em', textTransform: 'uppercase' }}>{stateLabel || '—'}</span>}
      </div>
    </div>
  );
}

function TagCloud({ sites }) {
  return (
    <div style={{ padding: '4px 0', display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {sites.map(s => (
        <span key={s} style={{ fontFamily: S.mono, fontSize: 10.5,
          padding: '3px 8px', border: `1px solid ${CAT.social.border}`,
          background: CAT.social.soft, color: CAT.social.color }}>{s}</span>
      ))}
    </div>
  );
}

Object.assign(window, { SignalSimpleDashboard, VerdictTag, GanttHero,
  SignalSimpleResults, CategorySection, BreachItem, StealerItem, KvItem, TagCloud });
