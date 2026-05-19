// Signal — remaining screens.
const { S, MicroSpark, Dial, SignalStatus, SignalChrome, PanelHeader, SignalConfBar } = window;

// ──────────────────────────────────────────────────────────
// Search + real-time progress
function SignalSearch() {
  return (
    <SignalChrome active="search"
      contextLine="case=0241 · target=lucas.silva@protonmail.com · elapsed=00:08">
      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Command bar */}
        <div style={{ background: S.surface, border: `1px solid ${S.hair}`,
          padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ fontFamily: S.mono, fontSize: 11, color: S.tealDeep,
            letterSpacing: '0.1em' }}>QUERY ›</div>
          <div style={{ fontFamily: S.mono, fontSize: 18, color: S.ink, flex: 1 }}>
            lucas.silva@protonmail.com</div>
          <div style={{ fontFamily: S.mono, fontSize: 10, color: S.teal,
            border: `1px solid ${S.tealBorder}`, background: S.tealSoft,
            padding: '4px 10px', letterSpacing: '0.12em' }}>EMAIL · 11 SOURCES</div>
          <button style={{ background: 'transparent', color: S.amber,
            border: `1px solid ${S.amber}40`, padding: '6px 14px',
            fontFamily: S.mono, fontSize: 10, letterSpacing: '0.14em',
            cursor: 'default' }}>PAUSE</button>
          <button style={{ background: 'transparent', color: S.red,
            border: `1px solid ${S.red}40`, padding: '6px 14px',
            fontFamily: S.mono, fontSize: 10, letterSpacing: '0.14em',
            cursor: 'default' }}>CANCEL</button>
        </div>

        {/* Top KPI strip */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
          {[
            { l: 'completed', v: '4', u: '/ 11', c: S.green },
            { l: 'running', v: '2', u: 'workers', c: S.teal },
            { l: 'queued', v: '3', u: 'waiting', c: S.sand },
            { l: 'blocked / error', v: '2', u: 'sources', c: S.amber },
            { l: 'elapsed', v: '00:08', u: 'eta 00:46', c: S.ink },
          ].map(k => (
            <div key={k.l} style={{ background: S.surface,
              border: `1px solid ${S.hair}`, padding: '12px 16px' }}>
              <div style={{ fontFamily: S.mono, fontSize: 9, color: S.inkDim,
                letterSpacing: '0.14em', textTransform: 'uppercase' }}>{k.l}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 6 }}>
                <div style={{ fontFamily: S.display, fontSize: 24, fontWeight: 600,
                  color: k.c, letterSpacing: '-0.02em' }}>{k.v}</div>
                <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkDim }}>{k.u}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Overall progress as Gantt of sources */}
        <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
          <PanelHeader title="Source timeline" right="autoscroll · 5s" />
          <div style={{ padding: '12px 16px' }}>
            {/* Time scale */}
            <div style={{ display: 'grid',
              gridTemplateColumns: '180px 70px 70px 1fr 70px',
              gap: 14, fontFamily: S.mono, fontSize: 9,
              color: S.inkDim, letterSpacing: '0.1em', textTransform: 'uppercase',
              padding: '6px 0', borderBottom: `1px solid ${S.hair}` }}>
              <div>source</div>
              <div>state</div>
              <div>hits</div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>00s</span><span>15s</span><span>30s</span><span>45s</span><span>60s</span>
              </div>
              <div style={{ textAlign: 'right' }}>conf</div>
            </div>
            {[
              { n: 'HIBP — breaches', state: 'found', n2: 7, start: 0, end: 0.5, conf: 0.96 },
              { n: 'OathNet — graph', state: 'found', n2: 12, start: 1, end: 8, conf: 0.88 },
              { n: 'WHOIS — domain', state: 'found', n2: 1, start: 0, end: 4, conf: 0.99 },
              { n: 'Holehe — registrations', state: 'found', n2: 23, start: 0, end: 24, conf: 0.74 },
              { n: 'Discord — lookup', state: 'likely', n2: 1, start: 0, end: 1, conf: 0.52 },
              { n: 'Paste sites', state: 'not_found', n2: 0, start: 1, end: 36, conf: 0.95 },
              { n: 'Sherlock — handles', state: 'running', n2: null, start: 0, end: null, prog: 0.76, conf: null },
              { n: 'Stealer index', state: 'running', n2: null, start: 0, end: null, prog: 0.42, conf: null },
              { n: 'Gaming profiles', state: 'pending', n2: null, start: null, end: null, conf: null },
              { n: 'SpiderFoot', state: 'blocked', n2: null, start: 0, end: 2, conf: null },
              { n: 'Reverse-image', state: 'error', n2: null, start: 0, end: 14, conf: null },
            ].map((r, i) => {
              const tone = r.state === 'found' ? S.green :
                r.state === 'likely' ? S.amber :
                r.state === 'running' ? S.teal :
                r.state === 'blocked' ? S.amber :
                r.state === 'error' ? S.red :
                r.state === 'not_found' ? S.inkMute : S.inkDim;
              return (
                <div key={i} style={{ display: 'grid',
                  gridTemplateColumns: '180px 70px 70px 1fr 70px',
                  gap: 14, alignItems: 'center', padding: '8px 0',
                  borderTop: i ? `1px solid ${S.hair}` : 'none' }}>
                  <div style={{ fontFamily: S.mono, fontSize: 11, color: S.ink }}>{r.n}</div>
                  <SignalStatus state={r.state} />
                  <div style={{ fontFamily: S.mono, fontSize: 11,
                    color: r.n2 != null ? S.ink : S.inkDim }}>{r.n2 != null ? `${r.n2}` : '—'}</div>
                  <div style={{ position: 'relative', height: 16, background: S.bgRecess,
                    border: `1px solid ${S.hair}` }}>
                    {r.start != null && (
                      <div style={{ position: 'absolute', top: 0, bottom: 0,
                        left: `${(r.start / 60) * 100}%`,
                        right: r.end != null ? `${(1 - r.end / 60) * 100}%`
                          : `${100 - (r.prog || 0.1) * 100}%`,
                        background: r.state === 'running' ?
                          `repeating-linear-gradient(45deg, ${tone}40 0 6px, ${tone}80 6px 12px)`
                          : tone + '40',
                        borderLeft: `2px solid ${tone}` }} />
                    )}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    {r.conf != null
                      ? <span style={{ fontFamily: S.mono, fontSize: 10.5, color: tone }}>
                          .{Math.round(r.conf * 100)}</span>
                      : r.prog != null
                      ? <span style={{ fontFamily: S.mono, fontSize: 10.5, color: S.tealDeep }}>
                          {Math.round(r.prog * 100)}%</span>
                      : <span style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkDim }}>—</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Live evidence stream + partial results */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 12 }}>
          <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
            <PanelHeader title="Partial findings · streaming" right="44 so far" />
            <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 6,
              maxHeight: 220, overflow: 'hidden' }}>
              {[
                { src: 'HIBP', t: 'collection-1', meta: 'email+sha1 · 2019-01', sev: 'high' },
                { src: 'HIBP', t: 'antipublic 2.0', meta: 'email+pass · 2020-04', sev: 'crit' },
                { src: 'OATH', t: 'credential edge', meta: 'sha1↔email · 12 vertices', sev: 'high' },
                { src: 'HOLE', t: 'twitter.com', meta: 'registered · fresh', sev: 'low' },
                { src: 'HOLE', t: 'github.com', meta: 'registered · fresh', sev: 'low' },
                { src: 'HOLE', t: 'spotify.com', meta: 'registered · fresh', sev: 'low' },
                { src: 'WHOIS', t: 'protonmail.com', meta: 'Proton AG · CH', sev: 'info' },
                { src: 'DISC', t: 'lucas#0117', meta: 'username match · review', sev: 'med' },
              ].map((f, i) => (
                <div key={i} style={{ display: 'grid',
                  gridTemplateColumns: '50px 1.4fr 1fr 50px', gap: 10, alignItems: 'center',
                  fontFamily: S.mono, fontSize: 11,
                  padding: '4px 0', borderBottom: i < 7 ? `1px solid ${S.hair}` : 'none' }}>
                  <span style={{ color: S.tealDeep, fontWeight: 600 }}>{f.src}</span>
                  <span style={{ color: S.ink }}>{f.t}</span>
                  <span style={{ color: S.inkDim }}>{f.meta}</span>
                  <span style={{ color: f.sev === 'crit' ? S.red : f.sev === 'high' ? S.amber
                    : f.sev === 'med' ? S.yellow : f.sev === 'low' ? S.green : S.inkDim,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    textAlign: 'right' }}>{f.sev}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ background: S.surface, border: `1px solid ${S.hair}`,
            padding: 18 }}>
            <PanelHeader title="Confidence · live" right="-2px from start" />
            <div style={{ paddingTop: 12, display: 'flex', alignItems: 'center', gap: 16 }}>
              <Dial value={0.84} label="overall" size={100} color={S.teal} />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Tier label="High (≥.80)" count={4} total={11} c={S.green} />
                <Tier label="Likely (.50-.79)" count={2} total={11} c={S.amber} />
                <Tier label="Uncertain (<.50)" count={1} total={11} c={S.sand} />
                <Tier label="Inconclusive" count={4} total={11} c={S.inkDim} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </SignalChrome>
  );
}

function Tier({ label, count, total, c }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between',
        fontFamily: S.mono, fontSize: 10, color: S.inkMute }}>
        <span>{label}</span><span style={{ color: c }}>{count}/{total}</span>
      </div>
      <div style={{ height: 2, background: S.hair, marginTop: 4 }}>
        <div style={{ height: '100%', width: `${(count/total)*100}%`, background: c }} />
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Results
function SignalResults() {
  return (
    <SignalChrome active="cases"
      contextLine="case=0241 · finalized · 43 findings · 8 sources · live=false">
      <div style={{ padding: 20, display: 'grid',
        gridTemplateColumns: '300px 1fr', gap: 14 }}>

        {/* Left rail — case summary */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ background: S.surface, border: `1px solid ${S.hair}`,
            padding: 18 }}>
            <div style={{ fontFamily: S.mono, fontSize: 9, letterSpacing: '0.16em',
              color: S.tealDeep, textTransform: 'uppercase' }}>Case 0241</div>
            <div style={{ fontFamily: S.mono, fontSize: 14, color: S.ink, marginTop: 6 }}>
              lucas.silva@protonmail.com</div>
            <div style={{ display: 'flex', gap: 14, marginTop: 18 }}>
              <Dial value={0.84} label="conf" size={76} color={S.teal} />
              <Dial value={0.74} label="risk" size={76} color={S.red} />
            </div>
            <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
              marginTop: 14, lineHeight: 1.55 }}>
              <div>findings · <span style={{ color: S.ink }}>43</span></div>
              <div>sources · <span style={{ color: S.green }}>8</span> ok ·
                {' '}<span style={{ color: S.amber }}>2</span> partial</div>
              <div>age · 12m · <span style={{ color: S.green }}>fresh</span></div>
              <div>fp · <span style={{ color: S.ink }}>2</span> manual review</div>
            </div>
          </div>

          <div style={{ background: S.surface, border: `1px solid ${S.hair}`,
            padding: 16 }}>
            <div style={{ fontFamily: S.mono, fontSize: 9, letterSpacing: '0.16em',
              color: S.inkDim, textTransform: 'uppercase', marginBottom: 12 }}>Verdict</div>
            <div style={{ fontFamily: S.display, fontSize: 28, fontWeight: 600,
              color: S.red, letterSpacing: '-0.025em' }}>Critical</div>
            <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
              marginTop: 8, lineHeight: 1.55 }}>
              active creds in 2 recent dumps · session cookies present · rotate now
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {['save to case', 'export · pdf', 'export · json', 're-run · 2'].map((t, i) => (
              <button key={t} style={{
                padding: '10px 12px', textAlign: 'left',
                background: i === 0 ? S.tealSoft : 'transparent',
                color: i === 0 ? S.teal : S.inkMute,
                border: `1px solid ${i === 0 ? S.tealBorder : S.hair}`,
                fontFamily: S.mono, fontSize: 11, letterSpacing: '0.08em',
                textTransform: 'uppercase', cursor: 'default' }}>{t}</button>
            ))}
          </div>
        </aside>

        {/* Right panels */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Breach panel */}
          <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
            <PanelHeader title="Credential exposure · HIBP + OathNet"
              right="7 active · 4 historical" />
            <div style={{ padding: '6px 14px 12px' }}>
              {[
                { n: 'Antipublic 2.0', date: '2020-04', sev: 'crit', src: 'HIBP', age: '4y', leak: 'email, password, ip' },
                { n: 'Genesis Market log', date: '2022-11', sev: 'crit', src: 'OATH', age: '2y', leak: 'cookies, fingerprint, password' },
                { n: 'Collection #1', date: '2019-01', sev: 'high', src: 'HIBP', age: '6y', leak: 'email, sha1(password)' },
                { n: 'Spotify informal dump', date: '2021-09', sev: 'med', src: 'HIBP', age: '4y', leak: 'email, password' },
              ].map((b, i) => (
                <div key={i} style={{ display: 'grid',
                  gridTemplateColumns: '1.4fr 70px 50px 1.4fr 80px',
                  gap: 12, alignItems: 'center', padding: '9px 0',
                  borderTop: i ? `1px solid ${S.hair}` : 'none' }}>
                  <div style={{ fontFamily: S.body, fontSize: 13, color: S.ink }}>{b.n}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>{b.date}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 10, color: S.tealDeep }}>{b.src}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>{b.leak}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 10,
                    color: b.sev === 'crit' ? S.red : b.sev === 'high' ? S.amber
                      : b.sev === 'med' ? S.yellow : S.inkDim,
                    letterSpacing: '0.14em', textTransform: 'uppercase' }}>{b.sev}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Two-col mini panels */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 12 }}>
            <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
              <PanelHeader title="Stealer logs" right="2 hosts · 87 files" />
              <div style={{ padding: 14 }}>
                {[
                  { id: 'GE-9X3K-001', os: 'Win 10 · pt-BR', n: 47, ago: '4mo', sev: 'high' },
                  { id: 'RC-2Z1L-088', os: 'Win 11 · pt-BR', n: 40, ago: '11d', sev: 'crit' },
                ].map(s => (
                  <div key={s.id} style={{ padding: 12, marginBottom: 8,
                    background: S.bgRecess, border: `1px solid ${S.hair}`,
                    borderLeft: `3px solid ${s.sev === 'crit' ? S.red : S.amber}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <div style={{ fontFamily: S.mono, fontSize: 12, color: s.sev === 'crit' ? S.red : S.amber,
                        fontWeight: 600 }}>{s.id}</div>
                      <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkDim }}>{s.ago}</div>
                    </div>
                    <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute,
                      marginTop: 4 }}>{s.os} · {s.n} files</div>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
              <PanelHeader title="Footprint · Holehe + Sherlock" right="23 sites" />
              <div style={{ padding: 14, display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {['twitter','github','spotify','instagram','reddit','linkedin','medium',
                  'pinterest','soundcloud','dropbox','figma','notion','vimeo','airbnb',
                  'duolingo','strava','goodreads','adobe','last.fm','steam','origin','epic','xbox']
                  .map(s => (
                    <span key={s} style={{ fontFamily: S.mono, fontSize: 10,
                      padding: '3px 7px', border: `1px solid ${S.tealBorder}`,
                      background: S.tealSoft, color: S.teal }}>{s}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Evidence ledger */}
          <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
            <PanelHeader title="Evidence ledger" right="weighted contributions" />
            <div style={{ padding: 14, fontFamily: S.mono, fontSize: 11 }}>
              {[
                { src: 'HIBP', w: 0.32, age: '4h', f: 'fresh', txt: 'breach.match collection-1 + antipublic 2.0' },
                { src: 'OATH', w: 0.28, age: '4h', f: 'fresh', txt: 'graph.match 12 vertices · sha1 chain confirmed' },
                { src: 'STLR', w: 0.18, age: '11d', f: 'fresh', txt: 'log RC-2Z1L-088 · session cookies present' },
                { src: 'HOLE', w: 0.12, age: '14h', f: 'fresh', txt: 'registration spread across 23 sites' },
                { src: 'DISC', w: 0.07, age: '20s', f: 'fresh', txt: 'username collision · MANUAL REVIEW' },
                { src: 'WHOIS', w: 0.03, age: '4h', f: 'fresh', txt: 'protonmail.com · Proton AG · CH' },
              ].map((e, i) => (
                <div key={i} style={{ display: 'grid',
                  gridTemplateColumns: '40px 50px 60px 1fr 60px', gap: 10,
                  alignItems: 'center', padding: '6px 0',
                  borderTop: i ? `1px solid ${S.hair}` : 'none' }}>
                  <span style={{ color: S.tealDeep, fontWeight: 600 }}>{e.src}</span>
                  <span style={{ color: S.ink }}>{e.w.toFixed(2)}</span>
                  <span style={{ color: S.green }}>{e.age}</span>
                  <span style={{ color: S.inkMute }}>{e.txt}</span>
                  <div style={{ height: 4, background: S.hair }}>
                    <div style={{ height: '100%', width: `${e.w * 100 / 0.32}%`,
                      background: S.teal }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </SignalChrome>
  );
}

// ──────────────────────────────────────────────────────────
// Admin
function SignalAdmin() {
  return (
    <SignalChrome active="admin"
      contextLine="admin · sources=16 · workers=3/5 · audit=7d retained">
      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
          <div style={{ fontFamily: S.display, fontSize: 26, fontWeight: 600,
            letterSpacing: '-0.02em' }}>Sources</div>
          <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkDim,
            letterSpacing: '0.06em' }}>16 connectors · 14 nominal · 2 degraded · 0 down</div>
          <div style={{ flex: 1 }} />
          <div style={{ display: 'flex', gap: 6 }}>
            {['connectors','workers','users','audit','keys','billing'].map((t, i) => (
              <div key={t} style={{ padding: '5px 12px',
                background: i === 0 ? S.tealSoft : S.surface,
                color: i === 0 ? S.teal : S.inkMute,
                border: `1px solid ${i === 0 ? S.tealBorder : S.hair}`,
                fontFamily: S.mono, fontSize: 10.5, letterSpacing: '0.08em',
                textTransform: 'uppercase' }}>{t}</div>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.8fr 1fr', gap: 12 }}>
          {/* Big connectors table */}
          <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
            <div style={{ display: 'grid',
              gridTemplateColumns: '14px 1.6fr 70px 90px 70px 70px 60px 30px',
              gap: 10, padding: '10px 16px',
              borderBottom: `1px solid ${S.hair}`,
              fontFamily: S.mono, fontSize: 9, color: S.inkDim,
              letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              <div></div><div>connector</div><div>health</div><div>trend</div>
              <div>p95</div><div>cache</div><div>quota</div><div></div>
            </div>
            {[
              { n: 'HIBP', t: 'breaches', h: 0.98, l: '210ms', c: '4h', q: '78%', s: 'ok',
                sp: [9,9,8,9,9,9,9,8,9,9,9,8,9] },
              { n: 'OathNet', t: 'cred graph', h: 0.94, l: '430ms', c: '12h', q: '54%', s: 'ok',
                sp: [7,8,7,9,8,8,9,8,9,8,9,9,9] },
              { n: 'Sherlock', t: '412 sites', h: 0.81, l: '2.4s', c: '—', q: 'n/a', s: 'deg',
                sp: [6,4,8,3,7,5,6,4,7,3,5,4,7] },
              { n: 'Holehe', t: '130 sites', h: 0.92, l: '1.5s', c: '24h', q: 'n/a', s: 'ok',
                sp: [8,7,9,8,9,8,8,9,8,9,9,8,9] },
              { n: 'Discord', t: 'user lookup', h: 1.0, l: '95ms', c: '—', q: '12%', s: 'ok',
                sp: [9,9,9,9,9,9,9,9,9,9,9,9,9] },
              { n: 'Stealer index', t: 'in-house', h: 0.55, l: '7.1s', c: '1h', q: '—', s: 'deg',
                sp: [4,3,6,2,5,3,7,2,5,3,5,4,5] },
              { n: 'SpiderFoot', t: 'enrichment', h: 0.0, l: '—', c: '—', q: '—', s: 'down',
                sp: [1,1,1,1,1,1,1,1,1,1,1,1,1] },
              { n: 'GeoIP', t: 'maxmind', h: 0.99, l: '14ms', c: '7d', q: '21%', s: 'ok',
                sp: [9,9,9,9,9,9,9,9,9,9,9,9,9] },
              { n: 'Twitter', t: 'snscrape', h: 0.88, l: '1.8s', c: '12h', q: '64%', s: 'ok',
                sp: [8,7,9,8,7,9,8,8,9,8,9,8,9] },
            ].map((r, i) => (
              <div key={r.n} style={{ display: 'grid',
                gridTemplateColumns: '14px 1.6fr 70px 90px 70px 70px 60px 30px',
                gap: 10, padding: '12px 16px',
                borderTop: `1px solid ${S.hair}`, alignItems: 'center' }}>
                <div style={{ width: 6, height: 6, borderRadius: 99,
                  background: r.s === 'ok' ? S.green : r.s === 'deg' ? S.amber : S.red }} />
                <div>
                  <div style={{ fontFamily: S.mono, fontSize: 12, color: S.ink }}>{r.n}</div>
                  <div style={{ fontSize: 10, color: S.inkDim, marginTop: 1,
                    fontFamily: S.mono }}>{r.t}</div>
                </div>
                <div style={{ fontFamily: S.mono, fontSize: 11, color: S.ink }}>{r.h.toFixed(2)}</div>
                <MicroSpark values={r.sp} color={r.s === 'ok' ? S.green : r.s === 'deg' ? S.amber : S.red} width={88} height={16} />
                <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute }}>{r.l}</div>
                <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute }}>{r.c}</div>
                <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute }}>{r.q}</div>
                <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkDim,
                  textAlign: 'right' }}>›</div>
              </div>
            ))}
          </div>

          {/* Side panels */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
              <PanelHeader title="System gauge" right="last 60s" />
              <div style={{ display: 'flex', gap: 16, marginTop: 14,
                justifyContent: 'space-around' }}>
                <Dial value={0.89} label="ram" size={78} color={S.amber} />
                <Dial value={0.38} label="cpu" size={78} color={S.green} />
                <Dial value={0.60} label="sem" size={78} color={S.teal} />
              </div>
              <div style={{ marginTop: 14, fontFamily: S.mono, fontSize: 10,
                color: S.inkMute, lineHeight: 1.55 }}>
                <div>memory · <span style={{ color: S.amber }}>178M</span> / 200M target ·
                  swap idle</div>
                <div>tasks · 3/5 sem · 7 queued · 0 orphan</div>
                <div>uptime · 7d 04:18 · last restart graceful</div>
              </div>
            </div>

            <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 16 }}>
              <PanelHeader title="Audit log · last 6 events" right="7d retained" />
              <div style={{ marginTop: 10, fontFamily: S.mono, fontSize: 10.5 }}>
                {[
                  { t: '11:42', who: 'matt', a: 'open case 0241' },
                  { t: '11:42', who: 'sys', a: 'enqueue 11 jobs · case 0241' },
                  { t: '11:43', who: 'sys', a: 'sherlock.degraded p95>2s' },
                  { t: '11:18', who: 'sys', a: 'stealer.degraded p95>6s' },
                  { t: '11:05', who: 'matt', a: 'export.pdf case 0238' },
                  { t: '10:52', who: 'admin', a: 'invite user · ana.r' },
                ].map((e, i) => (
                  <div key={i} style={{ display: 'grid',
                    gridTemplateColumns: '46px 40px 1fr', gap: 6,
                    padding: '4px 0',
                    borderTop: i ? `1px solid ${S.hair}` : 'none' }}>
                    <span style={{ color: S.inkDim }}>{e.t}</span>
                    <span style={{ color: S.teal }}>{e.who}</span>
                    <span style={{ color: S.inkMute }}>{e.a}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </SignalChrome>
  );
}

// ──────────────────────────────────────────────────────────
// Scoring detail
function SignalScoring() {
  return (
    <div style={{ width: '100%', height: '100%', background: S.bg, color: S.ink,
      fontFamily: S.body, padding: 32, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 18, overflow: 'hidden' }}>
      <div>
        <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.18em',
          textTransform: 'uppercase', color: S.tealDeep }}>Scoring system</div>
        <div style={{ fontFamily: S.display, fontSize: 24, fontWeight: 600,
          letterSpacing: '-0.025em', marginTop: 4 }}>
          Confidence · risk · status · evidence
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, flex: 1 }}>
        {/* Confidence */}
        <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
          <PanelHeader title="Confidence · 0–1 dial" right="continuous" />
          <div style={{ marginTop: 14, display: 'flex', gap: 14, alignItems: 'center' }}>
            <Dial value={0.96} label="very high" size={70} color={S.green} />
            <Dial value={0.78} label="high" size={70} color={S.teal} />
            <Dial value={0.52} label="likely" size={70} color={S.amber} />
            <Dial value={0.24} label="uncertain" size={70} color={S.sand} />
          </div>
          <div style={{ marginTop: 14, fontSize: 12, color: S.inkMute, lineHeight: 1.5 }}>
            Cada finding tem confidence contínua. Em listas viram <em>barras</em> de 3px com tick
            em 0.5; em painéis viram <em>dials</em> com anel concêntrico — instrumento, não decoração.
          </div>
        </div>

        {/* Status states */}
        <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
          <PanelHeader title="Source status · 8 states" right="hairline boxes" />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
            marginTop: 14 }}>
            {[
              { s: 'found', d: 'confirmed match' },
              { s: 'likely', d: 'probable · review' },
              { s: 'uncertain', d: 'mixed signal' },
              { s: 'running', d: 'in flight · partial' },
              { s: 'pending', d: 'queued' },
              { s: 'not_found', d: 'verified absence' },
              { s: 'blocked', d: 'rate-limit / auth' },
              { s: 'error', d: 'upstream failed' },
            ].map(r => (
              <div key={r.s} style={{ display: 'flex', alignItems: 'center', gap: 10,
                padding: '6px 0' }}>
                <SignalStatus state={r.s} />
                <div style={{ fontSize: 11, color: S.inkMute }}>{r.d}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk */}
        <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
          <PanelHeader title="Risk · 4 discrete steps" right="categorical" />
          <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
            {[
              { l: 'CRIT', c: S.red },
              { l: 'HIGH', c: S.amber },
              { l: 'MED', c: S.yellow },
              { l: 'LOW', c: S.inkDim },
            ].map(r => (
              <div key={r.l} style={{ flex: 1, padding: '14px 8px',
                border: `1px solid ${r.c}40`,
                background: 'transparent', textAlign: 'center',
                fontFamily: S.mono, fontSize: 11, fontWeight: 600,
                color: r.c, letterSpacing: '0.14em' }}>{r.l}</div>
            ))}
          </div>
          <div style={{ marginTop: 14, fontSize: 12, color: S.inkMute, lineHeight: 1.5 }}>
            Risk é categórico — 4 níveis com label sempre presente (acessibilidade).
            Confidence é contínuo e <em>separado</em>: 0.42 + HIGH é válido (alta gravidade,
            baixa certeza — exatamente o caso que merece revisão).
          </div>
        </div>

        {/* Evidence */}
        <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 18 }}>
          <PanelHeader title="Evidence · weighted ledger" right="contribution per source" />
          <div style={{ marginTop: 12, fontFamily: S.mono, fontSize: 11 }}>
            {[
              { src: 'HIBP', w: 0.32, c: S.green },
              { src: 'OATH', w: 0.28, c: S.green },
              { src: 'STLR', w: 0.18, c: S.amber },
              { src: 'HOLE', w: 0.12, c: S.green },
              { src: 'DISC', w: 0.07, c: S.amber },
              { src: 'WHOIS', w: 0.03, c: S.green },
            ].map((e, i) => (
              <div key={i} style={{ display: 'grid',
                gridTemplateColumns: '40px 50px 1fr', gap: 8,
                alignItems: 'center', padding: '5px 0' }}>
                <span style={{ color: S.tealDeep }}>{e.src}</span>
                <span style={{ color: S.ink }}>{e.w.toFixed(2)}</span>
                <div style={{ height: 4, background: S.hair }}>
                  <div style={{ height: '100%', width: `${e.w * 100 / 0.32}%`,
                    background: e.c }} />
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 12, fontSize: 11, color: S.inkMute, lineHeight: 1.5 }}>
            Cada finding contribui um <em>peso</em> ao score total. Amarelo aqui = source
            com freshness/age fora do ideal — sinaliza onde o cético deve olhar primeiro.
          </div>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
function SignalProsCons() {
  return <ProsConsCard
    title="Signal — analyst console, evolved Meridian"
    dark
    accent={S.teal}
    pros={[
      'Caminho de menor atrito: preserva tokens.css, severidade e mono já existentes',
      'Real-time é onde brilha — dials, sparklines e gantts SÃO o engine',
      'Dark slate (não preto) e teal+sand fogem do clichê amber-on-black',
      'Densidade altíssima sem ruído: cabe muito mais informação por tela',
      'Onboarding zero: quem usa Meridian hoje continua produtivo no dia 1',
    ]}
    cons={[
      'Visualmente o mais próximo do que já existe — diferenciação depende de detalhes finos',
      'Dark mode é cansativo em sessões longas (mitigar com modo claro opcional)',
      'Dials e sparklines exigem polimento extremo para não parecer "gauge slop"',
      'Risco de ser lido como "outra ferramenta de cyber" se a paleta não for executada com calma',
    ]}
    riskGeneric={'MÉDIO. Console + dark + dials já existe em muitas ferramentas SOC/threat-intel. A diferenciação aqui mora no slate-não-preto, na paleta teal+sand (rara em OSINT), e na recusa de cyberpunk. Se o time relaxar, vira genérico rápido.'}
    riskImpl={'BAIXO/MÉDIO. Reutiliza grande parte do Meridian. Principais entregas novas: SignalStatus pill, Dial component, MicroSpark, Gantt por source. ~1.5-2 semanas com base já existente.'}
    recommendation={'Apostar aqui se a prioridade é shippar o motor real-time RÁPIDO e o Nexus permanecer "ferramenta de analista". É a opção de menor risco técnico e maior reuso do trabalho já feito.'}
  />;
}

// ──────────────────────────────────────────────────────────
function SignalBoards() {
  return (
    <React.Fragment>
      <DCArtboard id="sg-identity" label="01 · Identity" width={1200} height={800}>
        <window.SignalIdentity />
      </DCArtboard>
      <DCArtboard id="sg-dashboard" label="02 · Dashboard" width={1360} height={880}>
        <window.SignalDashboard />
      </DCArtboard>
      <DCArtboard id="sg-search" label="03 · Search + Gantt" width={1360} height={920}>
        <SignalSearch />
      </DCArtboard>
      <DCArtboard id="sg-results" label="04 · Results" width={1360} height={900}>
        <SignalResults />
      </DCArtboard>
      <DCArtboard id="sg-admin" label="05 · Admin" width={1360} height={820}>
        <SignalAdmin />
      </DCArtboard>
      <DCArtboard id="sg-scoring" label="06 · Scoring system" width={1040} height={800}>
        <SignalScoring />
      </DCArtboard>
      <DCArtboard id="sg-tradeoffs" label="07 · Trade-offs" width={780} height={780}>
        <SignalProsCons />
      </DCArtboard>
    </React.Fragment>
  );
}

Object.assign(window, { SignalSearch, SignalResults, SignalAdmin, SignalScoring,
  SignalProsCons, SignalBoards });
