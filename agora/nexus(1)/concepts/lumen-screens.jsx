// Lumen — remaining screens: search/progress, results, admin, scoring detail, pros/cons.
const { L, LumenChrome, ConfidenceBar, StatusPill, Sparkline } = window;

// ──────────────────────────────────────────────────────────
// Search + real-time progress (single screen, two states overlaid)
function LumenSearch() {
  return (
    <LumenChrome active="search" breadcrumb={<><span>Workspace</span><span style={{color:L.dim}}>/</span><span>New search</span><span style={{color:L.dim}}>/</span><span style={{color:L.ink}}>case-0241</span></>}>
      <div style={{ padding: '36px 36px 28px', display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Search input */}
        <div>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: L.dim }}>Target</div>
          <div style={{ fontFamily: L.display, fontSize: 36, fontWeight: 600,
            letterSpacing: '-0.03em', marginTop: 4, display: 'flex', alignItems: 'center', gap: 14 }}>
            <span style={{ fontFamily: L.mono, color: L.ink, fontWeight: 500 }}>lucas.silva@protonmail.com</span>
            <span style={{ fontSize: 11, fontFamily: L.mono, color: L.sageDeep,
              background: L.sageSoft, padding: '4px 10px', borderRadius: 99,
              border: `1px solid ${L.sageBorder}`, letterSpacing: '0.06em',
              fontWeight: 500, textTransform: 'uppercase' }}>Email · auto-detected</span>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 14, fontFamily: L.mono, fontSize: 11 }}>
            {['Breaches','Stealer logs','Social discovery','Email intel','Domain intel'].map((t, i) => (
              <div key={t} style={{ padding: '5px 10px', borderRadius: 4,
                background: i < 3 ? L.surface : 'transparent',
                border: `1px solid ${i < 3 ? L.hairStrong : L.hair}`,
                color: i < 3 ? L.ink : L.dim,
                display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 5, height: 5, borderRadius: 99,
                  background: i < 3 ? L.sage : L.faint }} />{t}
              </div>
            ))}
          </div>
        </div>

        {/* Real-time progress board */}
        <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
          borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: `1px solid ${L.hair}`,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 8, height: 8, borderRadius: 99, background: L.sage,
                boxShadow: `0 0 0 4px ${L.sageSoft}` }} />
              <div style={{ fontSize: 13, fontWeight: 600 }}>Live · 4 of 11 sources finished</div>
              <div style={{ fontFamily: L.mono, fontSize: 11, color: L.dim }}>elapsed 00:08</div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button style={{ fontFamily: L.mono, fontSize: 11, padding: '5px 10px',
                background: 'transparent', border: `1px solid ${L.hair}`, borderRadius: 5,
                color: L.mute, cursor: 'default' }}>Pause</button>
              <button style={{ fontFamily: L.mono, fontSize: 11, padding: '5px 10px',
                background: 'transparent', border: `1px solid ${L.hair}`, borderRadius: 5,
                color: L.coral, cursor: 'default' }}>Cancel</button>
            </div>
          </div>

          {/* Overall progress bar */}
          <div style={{ padding: '0 20px' }}>
            <div style={{ height: 3, background: L.hair, position: 'relative' }}>
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0,
                width: '36%', background: L.sage }} />
              <div style={{ position: 'absolute', left: '36%', top: 0, bottom: 0,
                width: '18%', background: `repeating-linear-gradient(90deg, ${L.sageSoft} 0 6px, transparent 6px 12px)` }} />
            </div>
          </div>

          {/* Source rows */}
          <div style={{ padding: '8px 20px 16px' }}>
            {[
              { n: 'HIBP — breach index', state: 'found', n2: 7, t: '180ms', conf: 0.96, evi: 'collection-1, exploit.in, antipublic' },
              { n: 'OathNet — credential graph', state: 'found', n2: 12, t: '420ms', conf: 0.88, evi: 'matched on email + sha1 hash' },
              { n: 'Holehe — email registration', state: 'found', n2: 23, t: '1.4s', conf: 0.74, evi: '23 sites: spotify, twitter, github, …' },
              { n: 'Sherlock — handle discovery', state: 'running', n2: null, t: '04:12', conf: null, evi: 'crawling 412 platforms · 312 done' },
              { n: 'Stealer logs index', state: 'running', n2: null, t: '06:18', conf: null, evi: 'large index · cold start' },
              { n: 'Discord lookup', state: 'likely', n2: 1, t: '90ms', conf: 0.52, evi: 'username collision — needs review' },
              { n: 'Gaming profiles', state: 'pending', n2: null, t: '—', conf: null, evi: 'queued · waiting for handle list' },
              { n: 'Domain WHOIS', state: 'found', n2: 1, t: '320ms', conf: 0.99, evi: 'protonmail.com — Proton AG · CH' },
              { n: 'SpiderFoot enrichment', state: 'blocked', n2: null, t: '—', conf: null, evi: 'rate-limited · retry in 2m' },
              { n: 'Reverse-image search', state: 'error', n2: null, t: '—', conf: null, evi: '502 upstream · 3 retries failed' },
              { n: 'Paste sites', state: 'not_found', n2: 0, t: '2.1s', conf: 0.95, evi: 'clean across 8 paste indices' },
            ].map((r, i) => (
              <div key={i} style={{ padding: '10px 0', borderTop: i ? `1px solid ${L.hair}` : 'none',
                display: 'grid', gridTemplateColumns: '1.4fr 110px 60px 90px 1.5fr', gap: 14,
                alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StateGlyph state={r.state} />
                  <div>
                    <div style={{ fontSize: 12.5, color: L.ink, fontWeight: 500 }}>{r.n}</div>
                    <div style={{ fontFamily: L.mono, fontSize: 10, color: L.dim, marginTop: 1 }}>
                      {r.evi}</div>
                  </div>
                </div>
                <LumenStatusLabel state={r.state} />
                <div style={{ fontFamily: L.mono, fontSize: 11, color: r.n2 != null ? L.ink : L.dim }}>
                  {r.n2 != null ? `${r.n2} hits` : '—'}</div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>{r.t}</div>
                <div>{r.conf != null ? <ConfidenceBar value={r.conf} /> :
                  <div style={{ height: 4, background: `repeating-linear-gradient(90deg, ${L.hair} 0 6px, transparent 6px 12px)`,
                    borderRadius: 2 }} />}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </LumenChrome>
  );
}

function StateGlyph({ state }) {
  const map = {
    found:     { c: L.sage,  fill: true },
    likely:    { c: L.gold,  fill: true },
    running:   { c: L.sageDeep, anim: true },
    pending:   { c: L.faint, dot: true },
    blocked:   { c: L.taupe, ring: true },
    error:     { c: L.coral, x: true },
    not_found: { c: L.dim,   dot: true },
    uncertain: { c: L.taupe, fill: true },
  }[state] || { c: L.dim, dot: true };
  return (
    <div style={{ width: 14, height: 14, position: 'relative', flexShrink: 0 }}>
      {map.fill && <div style={{ width: 10, height: 10, borderRadius: 99,
        background: map.c, position: 'absolute', top: 2, left: 2 }} />}
      {map.anim && <>
        <div style={{ width: 10, height: 10, borderRadius: 99,
          border: `1.5px solid ${map.c}`, position: 'absolute', top: 2, left: 2 }} />
        <div style={{ width: 5, height: 5, borderRadius: 99, background: map.c,
          position: 'absolute', top: 4.5, left: 4.5 }} />
      </>}
      {map.dot && <div style={{ width: 5, height: 5, borderRadius: 99,
        background: map.c, position: 'absolute', top: 4.5, left: 4.5 }} />}
      {map.ring && <div style={{ width: 10, height: 10, borderRadius: 99,
        border: `1.5px dashed ${map.c}`, position: 'absolute', top: 2, left: 2 }} />}
      {map.x && <div style={{ position: 'absolute', top: 2, left: 2, width: 10, height: 10,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: map.c, fontSize: 12, fontWeight: 700, lineHeight: 1 }}>×</div>}
    </div>
  );
}

function LumenStatusLabel({ state }) {
  const cfg = {
    found:     { c: L.sageDeep, t: 'Found' },
    likely:    { c: L.gold,    t: 'Likely' },
    uncertain: { c: L.taupe,   t: 'Uncertain' },
    running:   { c: L.sageDeep,t: 'Running' },
    pending:   { c: L.dim,     t: 'Pending' },
    blocked:   { c: L.taupe,   t: 'Blocked' },
    error:     { c: L.coral,   t: 'Error' },
    not_found: { c: L.mute,    t: 'Not found' },
  }[state] || { c: L.dim, t: state };
  return (
    <div style={{ fontFamily: L.mono, fontSize: 10.5, color: cfg.c,
      letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 600 }}>{cfg.t}</div>
  );
}

// ──────────────────────────────────────────────────────────
// Results
function LumenResults() {
  return (
    <LumenChrome active="cases" breadcrumb={<><span>Cases</span><span style={{color:L.dim}}>/</span><span>case-0241</span><span style={{color:L.dim}}>/</span><span style={{color:L.ink}}>Results</span></>}>
      <div style={{ padding: '32px 36px', display: 'grid',
        gridTemplateColumns: '1fr 320px', gap: 28, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Header */}
          <div>
            <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: L.dim }}>Investigation</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 4 }}>
              <div style={{ fontFamily: L.mono, fontSize: 26, fontWeight: 500,
                color: L.ink, letterSpacing: '-0.01em' }}>lucas.silva@protonmail.com</div>
              <div style={{ fontFamily: L.serif, fontStyle: 'italic', fontSize: 22,
                color: L.sage, fontWeight: 400 }}>43 findings across 8 sources</div>
            </div>
            <div style={{ display: 'flex', gap: 14, marginTop: 12, fontFamily: L.mono,
              fontSize: 11, color: L.mute }}>
              <span>opened 12 min ago</span>
              <span style={{ color: L.faint }}>·</span>
              <span>by mattheus</span>
              <span style={{ color: L.faint }}>·</span>
              <span>last refresh 14s</span>
              <span style={{ marginLeft: 'auto', color: L.sageDeep }}>● live</span>
            </div>
          </div>

          {/* Breach card */}
          <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
            borderRadius: 12, overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', borderBottom: `1px solid ${L.hair}`,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Credential breaches</div>
                <span style={{ fontFamily: L.mono, fontSize: 10, color: L.coral,
                  background: L.coralSoft, padding: '2px 7px', borderRadius: 99 }}>7 ACTIVE</span>
              </div>
              <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>HIBP · 180ms</div>
            </div>
            {[
              { n: 'Collection #1', date: '2019-01', sev: 'high', leak: 'email, sha1(password)' },
              { n: 'Antipublic 2.0', date: '2020-04', sev: 'critical', leak: 'email, password, ip' },
              { n: 'Spotify · informal dump', date: '2021-09', sev: 'medium', leak: 'email, password' },
              { n: 'Genesis Market log', date: '2022-11', sev: 'critical', leak: 'cookies, fingerprint, password' },
            ].map((b, i) => (
              <div key={i} style={{ padding: '12px 20px', borderTop: `1px solid ${L.hair}`,
                display: 'grid', gridTemplateColumns: '1.6fr 0.8fr 1.4fr 80px', gap: 14,
                alignItems: 'center' }}>
                <div style={{ fontSize: 13, color: L.ink, fontWeight: 500 }}>{b.n}</div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>{b.date}</div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>{b.leak}</div>
                <div><SeverityBadge sev={b.sev} /></div>
              </div>
            ))}
          </div>

          {/* Two col mini cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
              borderRadius: 12, padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Registered accounts</div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>23 sites</div>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {['twitter','github','spotify','instagram','reddit','linkedin','medium',
                  'pinterest','soundcloud','dropbox','figma','notion','vimeo','airbnb',
                  'duolingo','strava','goodreads','adobe','last.fm','steam','origin','epic','xbox']
                  .map(s => (
                    <div key={s} style={{ fontFamily: L.mono, fontSize: 10.5,
                      padding: '4px 9px', borderRadius: 4,
                      background: L.sageSoft, color: L.sageDeep,
                      border: `1px solid ${L.sageBorder}` }}>{s}</div>
                ))}
              </div>
            </div>
            <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
              borderRadius: 12, padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Stealer logs</div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.coral }}>2 hosts · 87 files</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[
                  { id: 'GE-9X3K-001', os: 'Win 10 · BR', n: 47, ago: '4 mo' },
                  { id: 'RC-2Z1L-088', os: 'Win 11 · BR', n: 40, ago: '11 d' },
                ].map(s => (
                  <div key={s.id} style={{ padding: 12, background: L.bgRecess,
                    borderRadius: 8, border: `1px solid ${L.hair}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between',
                      alignItems: 'baseline' }}>
                      <div style={{ fontFamily: L.mono, fontSize: 12, color: L.coral,
                        fontWeight: 600 }}>{s.id}</div>
                      <div style={{ fontFamily: L.mono, fontSize: 10, color: L.dim }}>{s.ago}</div>
                    </div>
                    <div style={{ fontFamily: L.mono, fontSize: 10.5, color: L.mute,
                      marginTop: 4 }}>{s.os} · {s.n} files</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right rail: confidence summary */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'sticky', top: 0 }}>
          <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
            borderRadius: 12, padding: 20 }}>
            <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: L.dim }}>Overall confidence</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8 }}>
              <div style={{ fontFamily: L.display, fontSize: 56, fontWeight: 600,
                letterSpacing: '-0.04em', lineHeight: 1, color: L.ink }}>0.84</div>
              <div style={{ fontSize: 11, color: L.sageDeep, fontFamily: L.mono }}>HIGH</div>
            </div>
            <div style={{ fontSize: 12, color: L.mute, marginTop: 10, lineHeight: 1.5 }}>
              <span style={{ fontFamily: L.serif, fontStyle: 'italic', color: L.ink }}>
                4 of 8</span> confirming sources agree on email ownership; 2 sources unable to verify.
            </div>
          </div>

          <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
            borderRadius: 12, padding: 20 }}>
            <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: L.dim, marginBottom: 12 }}>Risk</div>
            <div style={{ display: 'flex', gap: 4 }}>
              {['C','H','M','L'].map((l, i) => (
                <div key={l} style={{ flex: 1, height: 36, borderRadius: 4,
                  background: i === 0 ? L.coral : L.hair,
                  color: i === 0 ? 'white' : L.dim,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: L.mono, fontSize: 11, fontWeight: 600 }}>{l}</div>
              ))}
            </div>
            <div style={{ fontSize: 12, color: L.mute, marginTop: 12, lineHeight: 1.5 }}>
              Active credentials in 2 recent dumps, including session cookies. Recommend
              immediate password rotation and 2FA audit.
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {['Save to case','Export PDF','Export JSON','Re-run · 2 sources'].map((t, i) => (
              <button key={t} style={{
                padding: '10px 14px', borderRadius: 8, fontFamily: L.body, fontSize: 12.5,
                fontWeight: 500, cursor: 'default', textAlign: 'left',
                background: i === 0 ? L.ink : L.surface,
                color: i === 0 ? L.bg : L.ink,
                border: i === 0 ? 'none' : `1px solid ${L.hair}`,
              }}>{t}</button>
            ))}
          </div>
        </div>
      </div>
    </LumenChrome>
  );
}

function SeverityBadge({ sev }) {
  const cfg = {
    critical: { c: L.coral, t: 'Critical' },
    high:     { c: L.gold,  t: 'High' },
    medium:   { c: L.taupe, t: 'Medium' },
    low:      { c: L.dim,   t: 'Low' },
  }[sev];
  return (
    <div style={{ fontFamily: L.mono, fontSize: 10, fontWeight: 600,
      color: cfg.c, textTransform: 'uppercase', letterSpacing: '0.08em',
      display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 4, height: 4, borderRadius: 99, background: cfg.c }} />
      {cfg.t}
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Admin panel
function LumenAdmin() {
  return (
    <LumenChrome active="admin" breadcrumb={<><span>Admin</span><span style={{color:L.dim}}>/</span><span style={{color:L.ink}}>Sources & connectors</span></>}>
      <div style={{ padding: '32px 36px', display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
            textTransform: 'uppercase', color: L.dim }}>Admin</div>
          <div style={{ fontFamily: L.display, fontSize: 30, fontWeight: 600,
            letterSpacing: '-0.025em', marginTop: 4 }}>Source connectors</div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 24, borderBottom: `1px solid ${L.hair}` }}>
          {['Connectors','Workers & queue','Users · 4','Audit log','Billing','API keys'].map((t, i) => (
            <div key={t} style={{ padding: '0 0 12px', fontSize: 13,
              color: i === 0 ? L.ink : L.mute,
              borderBottom: i === 0 ? `2px solid ${L.ink}` : '2px solid transparent',
              fontWeight: i === 0 ? 600 : 400,
              marginBottom: -1 }}>{t}</div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.8fr 1fr', gap: 20 }}>
          {/* Connectors table */}
          <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
            borderRadius: 12, overflow: 'hidden' }}>
            <div style={{ padding: '12px 18px', borderBottom: `1px solid ${L.hair}`,
              display: 'grid', gridTemplateColumns: '1.4fr 80px 70px 100px 60px 20px',
              gap: 10, fontFamily: L.mono, fontSize: 10,
              letterSpacing: '0.1em', textTransform: 'uppercase', color: L.dim }}>
              <div>Connector</div><div>Health</div><div>Cache</div><div>Latency p95</div>
              <div>Quota</div><div></div>
            </div>
            {[
              { n: 'HIBP', t: 'Email breach index', h: 0.98, c: '4h TTL', l: '210ms', q: '78%', state: 'ok' },
              { n: 'OathNet', t: 'Credential graph API', h: 0.94, c: '12h TTL', l: '430ms', q: '54%', state: 'ok' },
              { n: 'Sherlock', t: 'Handle discovery · 412 sites', h: 0.81, c: 'realtime', l: '2.4s', q: 'n/a', state: 'degraded' },
              { n: 'Holehe', t: 'Email registration · 130 sites', h: 0.92, c: '24h TTL', l: '1.5s', q: 'n/a', state: 'ok' },
              { n: 'Discord', t: 'User & invite lookup', h: 1.0, c: 'realtime', l: '95ms', q: '12%', state: 'ok' },
              { n: 'Stealer index', t: 'In-house log search', h: 0.55, c: '1h TTL', l: '7.1s', q: '—', state: 'degraded' },
              { n: 'SpiderFoot', t: 'Multi-source enrichment', h: 0.0, c: '—', l: '—', q: '—', state: 'down' },
            ].map((r, i) => (
              <div key={r.n} style={{
                padding: '14px 18px', borderTop: `1px solid ${L.hair}`,
                display: 'grid', gridTemplateColumns: '1.4fr 80px 70px 100px 60px 20px',
                gap: 10, alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 13, color: L.ink, fontWeight: 500 }}>{r.n}</div>
                  <div style={{ fontSize: 11, color: L.dim, marginTop: 1 }}>{r.t}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Sparkline state={r.state} />
                </div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>{r.c}</div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>{r.l}</div>
                <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>{r.q}</div>
                <div style={{ width: 8, height: 8, borderRadius: 99,
                  background: r.state === 'ok' ? L.sage : r.state === 'degraded' ? L.gold : L.coral }} />
              </div>
            ))}
          </div>

          {/* Queue + workers */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
              borderRadius: 12, padding: 18 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 14 }}>Workers</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <div style={{ fontFamily: L.display, fontSize: 36, fontWeight: 600,
                  letterSpacing: '-0.03em' }}>3</div>
                <div style={{ fontSize: 11, color: L.dim, fontFamily: L.mono }}>/ 5 cap</div>
              </div>
              <div style={{ marginTop: 14, display: 'flex', gap: 4 }}>
                {[1,1,1,0,0].map((on, i) => (
                  <div key={i} style={{ flex: 1, height: 36, borderRadius: 4,
                    background: on ? L.sageSoft : L.hair,
                    border: `1px solid ${on ? L.sageBorder : L.hair}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: L.mono, fontSize: 10, color: on ? L.sageDeep : L.dim,
                    fontWeight: 600 }}>{on ? 'BUSY' : '—'}</div>
                ))}
              </div>
              <div style={{ fontSize: 11, color: L.mute, marginTop: 12, fontFamily: L.mono }}>
                memory · 178 MB / 200 MB target</div>
              <div style={{ height: 3, background: L.hair, borderRadius: 2, marginTop: 6 }}>
                <div style={{ height: '100%', width: '89%', background: L.gold, borderRadius: 2 }} />
              </div>
            </div>
            <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
              borderRadius: 12, padding: 18 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Queue · 7 pending</div>
              {[
                { id: 'job-8814', src: 'Sherlock', t: '2s' },
                { id: 'job-8815', src: 'Stealer', t: '3s' },
                { id: 'job-8816', src: 'SpiderFoot', t: '11s · blocked' },
              ].map(j => (
                <div key={j.id} style={{ display: 'flex', justifyContent: 'space-between',
                  padding: '6px 0', fontFamily: L.mono, fontSize: 11 }}>
                  <span style={{ color: L.ink }}>{j.id}</span>
                  <span style={{ color: L.mute }}>{j.src}</span>
                  <span style={{ color: L.dim }}>{j.t}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </LumenChrome>
  );
}

// ──────────────────────────────────────────────────────────
// Scoring detail — one tall card that shows confidence breakdown + source statuses + evidence
function LumenScoring() {
  return (
    <div style={{ width: '100%', height: '100%', background: L.bg, color: L.ink,
      fontFamily: L.body, padding: 36, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 22, overflow: 'hidden' }}>
      <div>
        <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.16em',
          textTransform: 'uppercase', color: L.sageDeep }}>Detail · Score system</div>
        <div style={{ fontFamily: L.display, fontSize: 26, fontWeight: 600,
          letterSpacing: '-0.025em', marginTop: 6 }}>
          How risk, confidence, source status, and evidence read.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, flex: 1 }}>
        {/* Confidence */}
        <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
          borderRadius: 10, padding: 20 }}>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: L.dim, marginBottom: 12 }}>Confidence · 0–1 bar</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { v: 0.96, l: 'Very high', sub: '3+ independent sources agree' },
              { v: 0.78, l: 'High', sub: '2 sources agree, 1 partial' },
              { v: 0.52, l: 'Likely', sub: '1 confirming · 1 contradicting' },
              { v: 0.24, l: 'Uncertain', sub: 'single weak source' },
            ].map(r => (
              <div key={r.v}>
                <div style={{ display: 'flex', justifyContent: 'space-between',
                  alignItems: 'baseline', marginBottom: 4 }}>
                  <div style={{ fontSize: 12, color: L.ink, fontWeight: 500 }}>{r.l}</div>
                  <div style={{ fontFamily: L.mono, fontSize: 11, color: L.mute }}>{r.sub}</div>
                </div>
                <ConfidenceBar value={r.v} />
              </div>
            ))}
          </div>
        </div>

        {/* Source status states */}
        <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
          borderRadius: 10, padding: 20 }}>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: L.dim, marginBottom: 12 }}>
            Source status · 8 states, one glyph each</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {[
              { s: 'pending', d: 'queued — not started' },
              { s: 'running', d: 'in flight — partial OK' },
              { s: 'found', d: 'confirmed match' },
              { s: 'likely', d: 'probable, needs review' },
              { s: 'uncertain', d: 'low-signal, mixed' },
              { s: 'not_found', d: 'verified absence' },
              { s: 'blocked', d: 'rate-limit / auth' },
              { s: 'error', d: 'upstream failure' },
            ].map(r => (
              <div key={r.s} style={{ display: 'flex', alignItems: 'center', gap: 10,
                padding: '7px 0' }}>
                <StateGlyph state={r.s} />
                <div>
                  <LumenStatusLabel state={r.s} />
                  <div style={{ fontSize: 11, color: L.mute, marginTop: 2 }}>{r.d}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk card */}
        <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
          borderRadius: 10, padding: 20 }}>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: L.dim, marginBottom: 12 }}>Risk · severity steps</div>
          <div style={{ display: 'flex', gap: 6 }}>
            {[
              { l: 'Crit', c: L.coral, bg: L.coralSoft },
              { l: 'High', c: L.gold, bg: L.goldSoft },
              { l: 'Med', c: L.taupe, bg: L.taupeSoft },
              { l: 'Low', c: L.dim, bg: L.hair },
            ].map(r => (
              <div key={r.l} style={{ flex: 1, padding: 12, borderRadius: 6,
                background: r.bg, border: `1px solid ${r.c}33`,
                textAlign: 'center' }}>
                <div style={{ fontFamily: L.mono, fontSize: 10, color: r.c,
                  fontWeight: 600, letterSpacing: '0.08em',
                  textTransform: 'uppercase' }}>{r.l}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 12, color: L.mute, marginTop: 14, lineHeight: 1.5 }}>
            Severidade é categórica e <em>discreta</em> — 4 níveis. Mostrada com cor + rótulo,
            nunca só cor (acessibilidade). Confidence é contínua e separada.
          </div>
        </div>

        {/* Evidence */}
        <div style={{ background: L.surface, border: `1px solid ${L.hair}`,
          borderRadius: 10, padding: 20 }}>
          <div style={{ fontFamily: L.mono, fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: L.dim, marginBottom: 12 }}>Evidence · what & why</div>
          <div style={{ padding: 12, background: L.bgRecess, borderRadius: 6,
            border: `1px solid ${L.hair}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between',
              alignItems: 'baseline' }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Email + SHA1 match</div>
              <div style={{ fontFamily: L.mono, fontSize: 10, color: L.sageDeep }}>weight 0.34</div>
            </div>
            <div style={{ fontFamily: L.mono, fontSize: 10.5, color: L.mute, marginTop: 4 }}>
              source: OathNet · age: 4h · freshness: <span style={{ color: L.sage }}>fresh</span>
            </div>
            <div style={{ fontFamily: L.mono, fontSize: 10.5, color: L.dim, marginTop: 6,
              padding: '6px 8px', background: L.surface, borderRadius: 4 }}>
              "match on lucas.silva@protonmail.com + sha1:9b3a... ↔ collection-1"
            </div>
          </div>
          <div style={{ fontSize: 12, color: L.mute, marginTop: 12, lineHeight: 1.5 }}>
            Toda finding mostra <em>por quê</em> ela é uma finding: source, age, freshness,
            weight numérico. Reduz falso-positivo perceptual.
          </div>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
// Pros / Cons
function LumenProsCons() {
  return <ProsConsCard
    title="Lumen — SaaS premium, light, calm"
    accent={L.sage}
    pros={[
      'Visualmente mais distante da concorrência OSINT (todos estão no dark amber/cyan)',
      'Posiciona Nexus como produto, abre porta pra clientes enterprise / corporativo',
      'Densidade restrita ajuda o real-time: status e movimento ressaltam contra calmaria',
      'Acessibilidade vence (contraste alto, cor não é único canal de status)',
      'Tipografia + whitespace fazem o trabalho — pouca dependência de "efeitos"',
    ]}
    cons={[
      'Quebra mais drasticamente com o Meridian atual — migração CSS substancial',
      'Pode parecer "menos sério" para o público OSINT acostumado com dark mode',
      'Bone bg em monitor mal-calibrado pode ficar amarelado/desagradável',
      'Light mode em sessões longas cansa mais a vista (compensar com modo escuro opcional)',
    ]}
    riskGeneric={'BAIXO. Light + sage + serif italic é raro em OSINT — quase nenhum concorrente direto. Risco real é parecer um SaaS de produtividade genérico, mitigado pelo serif italic e pela densidade de dados monoespaçados.'}
    riskImpl={'MÉDIO. Requer revisar todo o sistema de cores (tokens.css completo). Light mode pede ajustes finos de contraste em todos os badges. ~2 semanas de redesign + 1 semana de polish.'}
    recommendation={'Apostar aqui se o objetivo de médio prazo for VENDER o Nexus (B2B, white-label, enterprise). É o único conceito que não soa "para hackers" no primeiro segundo.'}
  />;
}

// ──────────────────────────────────────────────────────────
function LumenBoards() {
  return (
    <React.Fragment>
      <DCArtboard id="lumen-identity" label="01 · Identity" width={1200} height={780}>
        <window.LumenIdentity />
      </DCArtboard>
      <DCArtboard id="lumen-dashboard" label="02 · Dashboard" width={1280} height={820}>
        <window.LumenDashboard />
      </DCArtboard>
      <DCArtboard id="lumen-search" label="03 · Search + real-time" width={1280} height={900}>
        <LumenSearch />
      </DCArtboard>
      <DCArtboard id="lumen-results" label="04 · Results" width={1280} height={900}>
        <LumenResults />
      </DCArtboard>
      <DCArtboard id="lumen-admin" label="05 · Admin" width={1280} height={820}>
        <LumenAdmin />
      </DCArtboard>
      <DCArtboard id="lumen-scoring" label="06 · Scoring system" width={1000} height={780}>
        <LumenScoring />
      </DCArtboard>
      <DCArtboard id="lumen-tradeoffs" label="07 · Trade-offs" width={780} height={780}>
        <LumenProsCons />
      </DCArtboard>
    </React.Fragment>
  );
}

Object.assign(window, { LumenSearch, LumenResults, LumenAdmin, LumenScoring,
  LumenProsCons, LumenBoards });
