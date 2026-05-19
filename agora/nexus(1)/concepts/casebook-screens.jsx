// Casebook — remaining screens.
const { C, Seal, Stamp, Citation, Concur, CasebookChrome } = window;

// ──────────────────────────────────────────────────────────
// Search + real-time progress (as case-opening + live timeline)
function CasebookSearch() {
  return (
    <CasebookChrome activeTab={1} sub="Case №0241 · opened 12 min ago by mattheus">
      <div style={{ padding: '32px 36px', maxWidth: 1180, margin: '0 auto',
        display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 28 }}>
        {/* Left: cover sheet */}
        <div>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.18em',
            textTransform: 'uppercase', color: C.brassDeep }}>Cover sheet · №0241</div>
          <div style={{ fontFamily: C.display, fontSize: 36, fontWeight: 600,
            letterSpacing: '-0.02em', marginTop: 6, lineHeight: 1.1 }}>
            Subject of investigation
          </div>
          <div style={{ marginTop: 16, padding: '14px 18px', background: C.cardCool,
            border: `1.5px solid ${C.ink}`,
            borderLeft: `4px solid ${C.brass}`,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontFamily: C.mono, fontSize: 16, color: C.ink, fontWeight: 500 }}>
              lucas.silva@protonmail.com
            </div>
            <Stamp label="Email · auto" tone="brass" rotate={-2} />
          </div>

          <div style={{ marginTop: 24 }}>
            <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: C.inkDim, marginBottom: 10 }}>
              Scope · 11 sources enlisted</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {[
                { n: 'HIBP', kind: 'breaches' },
                { n: 'OathNet', kind: 'credentials' },
                { n: 'Holehe', kind: 'email intel' },
                { n: 'Sherlock', kind: 'social' },
                { n: 'Stealer index', kind: 'logs' },
                { n: 'Discord', kind: 'discord' },
                { n: 'Gaming', kind: 'gaming' },
                { n: 'WHOIS', kind: 'domain' },
                { n: 'SpiderFoot', kind: 'enrichment' },
              ].map(s => (
                <div key={s.n} style={{ padding: '10px 12px', border: `1px solid ${C.rule}`,
                  background: C.card }}>
                  <div style={{ fontFamily: C.display, fontSize: 13, fontWeight: 600,
                    fontStyle: 'italic', color: C.ink }}>{s.n}</div>
                  <div style={{ fontFamily: C.mono, fontSize: 10, color: C.inkDim,
                    marginTop: 2 }}>{s.kind}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 22, display: 'flex', gap: 10 }}>
            <button style={{ background: C.ink, color: C.paper, border: 0,
              padding: '11px 18px', fontFamily: C.display, fontSize: 13.5, fontWeight: 600,
              letterSpacing: '-0.005em', cursor: 'default' }}>Begin investigation →</button>
            <button style={{ background: 'transparent', color: C.ink,
              border: `1px solid ${C.ruleStrong}`, padding: '11px 14px',
              fontFamily: C.mono, fontSize: 11, cursor: 'default',
              textTransform: 'uppercase', letterSpacing: '0.08em' }}>Add note</button>
          </div>
        </div>

        {/* Right: live timeline */}
        <div style={{ borderLeft: `1.5px solid ${C.ruleStrong}`, paddingLeft: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <div style={{ width: 8, height: 8, borderRadius: 99, background: C.moss }} />
            <div style={{ fontFamily: C.display, fontSize: 16, fontWeight: 600,
              fontStyle: 'italic' }}>Live · 4 of 11 finished</div>
            <div style={{ fontFamily: C.mono, fontSize: 11, color: C.inkDim,
              marginLeft: 'auto' }}>00:08</div>
          </div>

          <div style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', left: 9, top: 6, bottom: 6, width: 1,
              background: C.ruleStrong }} />
            {[
              { t: '00:00', src: 'HIBP', state: 'found', n: 7,
                line: 'breach matches — collection-1, antipublic 2.0', tone: 'moss' },
              { t: '00:01', src: 'OathNet', state: 'found', n: 12,
                line: 'credential graph hits — sha1 chain confirmed', tone: 'moss' },
              { t: '00:02', src: 'WHOIS', state: 'found', n: 1,
                line: 'protonmail.com — Proton AG · CH', tone: 'moss' },
              { t: '00:03', src: 'Holehe', state: 'found', n: 23,
                line: '23 sites registered with this email', tone: 'moss' },
              { t: '00:04', src: 'Discord', state: 'likely', n: 1,
                line: 'username collision — needs review', tone: 'ochre' },
              { t: '00:06', src: 'Paste sites', state: 'not_found', n: 0,
                line: 'clean across 8 indices', tone: 'mute' },
              { t: '00:07', src: 'SpiderFoot', state: 'blocked',
                line: 'rate limit · retry in 2m', tone: 'ochre' },
              { t: '00:07', src: 'Reverse-image', state: 'error',
                line: '502 upstream · 3 retries failed', tone: 'forensic' },
              { t: '00:08', src: 'Sherlock', state: 'running',
                line: 'crawling 412 platforms · 312 done', tone: 'brass' },
              { t: '00:08', src: 'Stealer index', state: 'running',
                line: 'large index · cold start', tone: 'brass' },
            ].map((e, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 14,
                position: 'relative' }}>
                <div style={{ width: 18, paddingTop: 2, flexShrink: 0 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 99,
                    background: e.tone === 'moss' ? C.moss : e.tone === 'ochre' ? C.ochre
                      : e.tone === 'forensic' ? C.forensic : e.tone === 'brass' ? C.brass : C.inkFaint,
                    border: e.state === 'running' ? `2px solid ${C.brass}` : 'none',
                    background: e.state === 'running' ? C.card : undefined,
                    marginLeft: 4, position: 'relative', zIndex: 1 }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                    <div style={{ fontFamily: C.mono, fontSize: 10, color: C.inkDim,
                      letterSpacing: '0.06em' }}>{e.t}</div>
                    <div style={{ fontFamily: C.display, fontSize: 13, fontWeight: 600,
                      fontStyle: 'italic', color: C.ink }}>{e.src}</div>
                    {e.n != null && <div style={{ fontFamily: C.mono, fontSize: 11,
                      color: C.brassDeep }}>· {e.n} {e.n === 1 ? 'hit' : 'hits'}</div>}
                    <CasebookStatePill state={e.state} />
                  </div>
                  <div style={{ fontFamily: C.displayItalic, fontStyle: 'italic',
                    fontSize: 13, color: C.inkMute, marginTop: 2,
                    lineHeight: 1.4 }}>{e.line}<Citation n={(i+1).toString().padStart(2,'0')} /></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </CasebookChrome>
  );
}

function CasebookStatePill({ state }) {
  const map = {
    found:     { c: C.moss,     t: 'Found' },
    likely:    { c: C.ochre,    t: 'Likely' },
    uncertain: { c: C.brassDeep,t: 'Uncertain' },
    running:   { c: C.brass,    t: 'Running' },
    pending:   { c: C.inkDim,   t: 'Pending' },
    blocked:   { c: C.ochre,    t: 'Blocked' },
    error:     { c: C.forensic, t: 'Error' },
    not_found: { c: C.inkMute,  t: 'Not found' },
  }[state] || { c: C.inkDim, t: state };
  return (
    <div style={{ fontFamily: C.mono, fontSize: 9, color: map.c, fontWeight: 700,
      letterSpacing: '0.12em', textTransform: 'uppercase' }}>· {map.t}</div>
  );
}

// ──────────────────────────────────────────────────────────
// Results — document layout, evidence-as-citations
function CasebookResults() {
  return (
    <CasebookChrome activeTab={1} sub="Case №0241 · last refresh 14s · live">
      <div style={{ padding: '32px 36px', maxWidth: 1180, margin: '0 auto',
        display: 'grid', gridTemplateColumns: '1.6fr 360px', gap: 36 }}>
        {/* Main column — reads like a brief */}
        <article>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.18em',
            textTransform: 'uppercase', color: C.brassDeep }}>
            Case №0241 · Findings dossier</div>
          <h1 style={{ fontFamily: C.display, fontSize: 38, fontWeight: 600,
            letterSpacing: '-0.025em', margin: '8px 0 4px', lineHeight: 1.1 }}>
            <span style={{ fontFamily: C.mono, fontSize: 28, fontWeight: 500 }}>
              lucas.silva@protonmail.com</span>
          </h1>
          <div style={{ fontFamily: C.displayItalic, fontStyle: 'italic',
            fontSize: 18, color: C.brassDeep, fontWeight: 500 }}>
            43 findings · 8 sources confirming, 2 unable to verify
          </div>

          <hr style={{ border: 0, borderTop: `1.5px solid ${C.ink}`, margin: '20px 0' }} />

          {/* Credentials section */}
          <section style={{ marginBottom: 32 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <div style={{ fontFamily: C.mono, fontSize: 10, color: C.brassDeep,
                letterSpacing: '0.16em' }}>§ 1</div>
              <h2 style={{ fontFamily: C.display, fontSize: 22, fontWeight: 600,
                margin: 0, letterSpacing: '-0.015em' }}>
                Credential exposure</h2>
              <div style={{ marginLeft: 'auto' }}>
                <Stamp label="critical" tone="forensic" rotate={-3} />
              </div>
            </div>
            <p style={{ fontFamily: C.display, fontSize: 15, lineHeight: 1.6,
              color: C.ink, marginTop: 12, marginBottom: 14, textWrap: 'pretty' }}>
              The subject's email appears in <em>seven active breach indices</em><Citation n="01" />,
              including two with cleartext or reversible-hash credentials<Citation n="02" />.
              A 2022 stealer log<Citation n="03" /> contains session cookies and browser
              fingerprint suggesting recent compromise of the device.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
              marginTop: 8 }}>
              {[
                { n: 'Collection #1', date: '2019-01', sev: 'high' },
                { n: 'Antipublic 2.0', date: '2020-04', sev: 'critical' },
                { n: 'Spotify dump', date: '2021-09', sev: 'medium' },
                { n: 'Genesis Market', date: '2022-11', sev: 'critical' },
              ].map((b, i) => (
                <div key={i} style={{ padding: '10px 14px',
                  background: C.cardCool, border: `1px solid ${C.rule}`,
                  borderLeft: `3px solid ${b.sev === 'critical' ? C.forensic
                    : b.sev === 'high' ? C.ochre : C.brass}` }}>
                  <div style={{ fontFamily: C.display, fontSize: 14, fontWeight: 600 }}>{b.n}</div>
                  <div style={{ fontFamily: C.mono, fontSize: 10, color: C.inkDim,
                    marginTop: 3 }}>{b.date} · {b.sev}</div>
                </div>
              ))}
            </div>
          </section>

          {/* Footprint section */}
          <section style={{ marginBottom: 28 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <div style={{ fontFamily: C.mono, fontSize: 10, color: C.brassDeep,
                letterSpacing: '0.16em' }}>§ 2</div>
              <h2 style={{ fontFamily: C.display, fontSize: 22, fontWeight: 600,
                margin: 0, letterSpacing: '-0.015em' }}>Digital footprint</h2>
              <div style={{ marginLeft: 'auto' }}>
                <Stamp label="confirmed" tone="moss" rotate={2} />
              </div>
            </div>
            <p style={{ fontFamily: C.display, fontSize: 15, lineHeight: 1.6,
              color: C.ink, marginTop: 12, textWrap: 'pretty' }}>
              The email is registered on 23 services<Citation n="04" /> — most relevant for
              correlation are <em>twitter</em>, <em>github</em>, <em>steam</em>, and <em>airbnb</em>.
              A Discord username collision suggests a probable alt account<Citation n="05" />
              that remains <em>likely</em> rather than confirmed.
            </p>
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {['twitter','github','spotify','instagram','reddit','linkedin','medium',
                'pinterest','soundcloud','dropbox','figma','notion','airbnb','duolingo',
                'strava','goodreads','adobe','last.fm','steam','origin','epic'].map(s => (
                <div key={s} style={{ fontFamily: C.mono, fontSize: 10,
                  padding: '3px 8px', border: `1px solid ${C.rule}`,
                  background: C.card, color: C.ink }}>{s}</div>
              ))}
            </div>
          </section>

          {/* Footnote rail */}
          <section>
            <div style={{ borderTop: `1.5px solid ${C.ink}`, paddingTop: 16,
              fontFamily: C.mono, fontSize: 10, color: C.inkDim,
              letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 10 }}>
              Evidence · footnotes</div>
            <ol style={{ paddingLeft: 18, margin: 0,
              fontFamily: C.display, fontSize: 12.5, lineHeight: 1.55, color: C.inkMute }}>
              {[
                'HIBP indexed 2024-03-04 · fresh · weight 0.32',
                'OathNet credential graph · matched on email+sha1 · fresh',
                'Stealer log GE-9X3K-001 · captured 2024-05-12 · 47 files',
                'Holehe scan · 130 sites probed, 23 hits · confidence 0.74 (single source)',
                'Discord lookup · username collision · 0.52 — requires manual review',
              ].map((n, i) => (
                <li key={i} style={{ marginBottom: 4 }}>{n}</li>
              ))}
            </ol>
          </section>
        </article>

        {/* Right rail: case summary, like a tipped-in card */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ background: C.cardCool, border: `1.5px solid ${C.ink}`,
            padding: 22 }}>
            <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: C.brassDeep, marginBottom: 8 }}>
              Verdict</div>
            <div style={{ fontFamily: C.display, fontSize: 38, fontWeight: 600,
              letterSpacing: '-0.03em', lineHeight: 1, fontStyle: 'italic',
              color: C.forensic }}>Critical</div>
            <div style={{ fontFamily: C.displayItalic, fontStyle: 'italic',
              fontSize: 13.5, color: C.ink, marginTop: 10, lineHeight: 1.5 }}>
              Active credentials in recent dumps, including session cookies. Recommend
              immediate password rotation and 2FA audit.
            </div>
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px solid ${C.rule}` }}>
              <Concur confirmed={6} total={8} />
            </div>
          </div>

          <div style={{ padding: 18, background: C.card, border: `1px solid ${C.rule}` }}>
            <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
              textTransform: 'uppercase', color: C.inkDim, marginBottom: 12 }}>Source seals</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14,
              justifyItems: 'center' }}>
              {[
                { l: 'H', t: 'moss' }, { l: 'O', t: 'moss' },
                { l: 'h', t: 'moss' }, { l: 'W', t: 'moss' },
                { l: 'D', t: 'brass' }, { l: '?', t: 'brass' },
                { l: 'X', t: 'forensic' }, { l: '!', t: 'forensic' },
              ].map((s, i) => <Seal key={i} letter={s.l} tone={s.t} size={42} />)}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {['Bind to case','Export PDF dossier','Export raw JSON','Re-run failed'].map((t, i) => (
              <button key={t} style={{
                padding: '11px 14px', fontFamily: C.body, fontSize: 13,
                fontWeight: 500, cursor: 'default', textAlign: 'left',
                background: i === 0 ? C.ink : 'transparent',
                color: i === 0 ? C.paper : C.ink,
                border: i === 0 ? 'none' : `1px solid ${C.ruleStrong}`,
              }}>{t}</button>
            ))}
          </div>
        </aside>
      </div>
    </CasebookChrome>
  );
}

// ──────────────────────────────────────────────────────────
// Admin — looks like the "registry" of sources and personnel
function CasebookAdmin() {
  return (
    <CasebookChrome activeTab={0} sub="Registry · sources · personnel · audit ledger">
      <div style={{ padding: '32px 36px', maxWidth: 1180, margin: '0 auto',
        display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.18em',
            textTransform: 'uppercase', color: C.brassDeep }}>Registry</div>
          <div style={{ fontFamily: C.display, fontSize: 36, fontWeight: 600,
            letterSpacing: '-0.025em', marginTop: 4 }}>
            Source connectors <span style={{ fontStyle: 'italic', color: C.brassDeep,
              fontWeight: 400 }}>· health, freshness & quotas</span></div>
        </div>

        <div style={{ display: 'flex', gap: 24, borderBottom: `1.5px solid ${C.ink}` }}>
          {['Connectors','Workers · 3/5','Personnel · 4','Audit ledger','API keys','Billing']
            .map((t, i) => (
            <div key={t} style={{ padding: '0 0 12px', fontSize: 13,
              color: i === 0 ? C.ink : C.inkMute,
              fontFamily: C.display, fontStyle: i === 0 ? 'normal' : 'italic',
              fontWeight: i === 0 ? 600 : 500,
              borderBottom: i === 0 ? `2.5px solid ${C.ink}` : 'none',
              marginBottom: -1.5 }}>{t}</div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.7fr 1fr', gap: 20 }}>
          {/* Sources */}
          <div style={{ background: C.card, border: `1px solid ${C.rule}`, padding: 4 }}>
            {[
              { n: 'HIBP', t: 'Email breach index', h: 0.98, c: '4h TTL', l: '210ms', s: 'ok' },
              { n: 'OathNet', t: 'Credential graph', h: 0.94, c: '12h TTL', l: '430ms', s: 'ok' },
              { n: 'Sherlock', t: 'Handle discovery · 412 sites', h: 0.81, c: 'realtime', l: '2.4s', s: 'degraded' },
              { n: 'Holehe', t: 'Email registration · 130 sites', h: 0.92, c: '24h TTL', l: '1.5s', s: 'ok' },
              { n: 'Discord lookup', t: 'User & invite', h: 1.0, c: 'realtime', l: '95ms', s: 'ok' },
              { n: 'Stealer index', t: 'In-house log search', h: 0.55, c: '1h TTL', l: '7.1s', s: 'degraded' },
              { n: 'SpiderFoot', t: 'Multi-source enrichment', h: 0.0, c: '—', l: '—', s: 'down' },
            ].map((r, i) => (
              <div key={r.n} style={{ display: 'grid',
                gridTemplateColumns: '46px 1.6fr 100px 90px 100px',
                gap: 14, alignItems: 'center',
                padding: '12px 14px',
                borderBottom: i < 6 ? `1px solid ${C.rule}` : 'none' }}>
                <Seal letter={r.n[0]} tone={r.s === 'ok' ? 'moss' : r.s === 'degraded' ? 'brass' : 'forensic'} size={38} />
                <div>
                  <div style={{ fontFamily: C.display, fontSize: 16, fontWeight: 600,
                    fontStyle: 'italic', color: C.ink }}>{r.n}</div>
                  <div style={{ fontFamily: C.body, fontSize: 12, color: C.inkMute,
                    marginTop: 1 }}>{r.t}</div>
                </div>
                <div style={{ fontFamily: C.mono, fontSize: 11, color: C.inkMute }}>
                  cache · {r.c}</div>
                <div style={{ fontFamily: C.mono, fontSize: 11, color: C.inkMute }}>
                  p95 · {r.l}</div>
                <div><Stamp label={r.s === 'ok' ? 'online' : r.s}
                  tone={r.s === 'ok' ? 'moss' : r.s === 'degraded' ? 'ochre' : 'forensic'}
                  rotate={Math.sin(i * 7) * 3} /></div>
              </div>
            ))}
          </div>

          {/* Workers + audit */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ padding: 20, background: C.cardCool,
              border: `1.5px solid ${C.ink}` }}>
              <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
                textTransform: 'uppercase', color: C.brassDeep, marginBottom: 10 }}>
                Worker pool</div>
              <div style={{ fontFamily: C.display, fontSize: 38, fontWeight: 600,
                fontStyle: 'italic', color: C.ink, lineHeight: 1 }}>
                3 <span style={{ color: C.inkDim, fontWeight: 400, fontSize: 22 }}>/ 5</span>
              </div>
              <div style={{ fontSize: 12, color: C.inkMute, marginTop: 6,
                fontFamily: C.displayItalic, fontStyle: 'italic' }}>
                semaphore ceiling · async TaskGroup
              </div>
              <div style={{ display: 'flex', gap: 4, marginTop: 14 }}>
                {[1,1,1,0,0].map((on, i) => (
                  <div key={i} style={{ flex: 1, height: 34,
                    background: on ? C.brassSoft : 'transparent',
                    border: `1px solid ${on ? C.brassBorder : C.rule}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: C.mono, fontSize: 10, color: on ? C.brassDeep : C.inkDim,
                    fontWeight: 700, letterSpacing: '0.06em' }}>{on ? 'BUSY' : '—'}</div>
                ))}
              </div>
              <div style={{ fontSize: 11, color: C.inkMute, marginTop: 14,
                fontFamily: C.mono }}>memory · 178 / 200 MB</div>
              <div style={{ height: 3, background: C.rule, marginTop: 4 }}>
                <div style={{ height: '100%', width: '89%', background: C.ochre }} />
              </div>
            </div>

            <div style={{ padding: 20, background: C.card,
              border: `1px solid ${C.rule}` }}>
              <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
                textTransform: 'uppercase', color: C.inkDim, marginBottom: 12 }}>
                Audit ledger · last 24h</div>
              {[
                { t: '09:42', who: 'mattheus', a: 'opened case №0241' },
                { t: '09:43', who: 'system', a: '11 jobs enqueued' },
                { t: '11:18', who: 'system', a: 'Stealer degraded' },
                { t: '12:05', who: 'mattheus', a: 'exported dossier PDF' },
              ].map((e, i) => (
                <div key={i} style={{ padding: '6px 0',
                  borderTop: i ? `1px solid ${C.rule}` : 'none',
                  fontFamily: C.displayItalic, fontStyle: 'italic', fontSize: 12.5,
                  color: C.ink, lineHeight: 1.4 }}>
                  <span style={{ fontFamily: C.mono, fontStyle: 'normal',
                    fontSize: 10, color: C.brassDeep, marginRight: 6 }}>{e.t}</span>
                  <strong style={{ fontWeight: 600 }}>{e.who}</strong> {e.a}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </CasebookChrome>
  );
}

// ──────────────────────────────────────────────────────────
// Scoring detail board
function CasebookScoring() {
  return (
    <div style={{ width: '100%', height: '100%', background: C.paper, color: C.ink,
      fontFamily: C.body, padding: 36, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 22, overflow: 'hidden',
      backgroundImage: 'radial-gradient(rgba(26,20,16,0.025) 1px, transparent 1px)',
      backgroundSize: '4px 4px' }}>
      <div>
        <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.16em',
          textTransform: 'uppercase', color: C.brassDeep }}>Detail · Scoring vocabulary</div>
        <div style={{ fontFamily: C.display, fontSize: 26, fontWeight: 600,
          letterSpacing: '-0.025em', marginTop: 6 }}>
          Reading the dossier <span style={{ fontStyle: 'italic', color: C.brassDeep }}>at a glance.</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, flex: 1 }}>
        {/* Concur */}
        <div style={{ background: C.card, border: `1px solid ${C.rule}`, padding: 20 }}>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: C.inkDim, marginBottom: 14 }}>
            Confidence · "n/m sources concur"</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { c: 7, m: 8, l: 'Verified' },
              { c: 4, m: 8, l: 'Probable' },
              { c: 2, m: 8, l: 'Uncertain' },
              { c: 0, m: 8, l: 'Unverified' },
            ].map(r => (
              <div key={r.l} style={{ display: 'flex',
                justifyContent: 'space-between', alignItems: 'center' }}>
                <Concur confirmed={r.c} total={r.m} label="sources" />
                <div style={{ fontFamily: C.displayItalic, fontStyle: 'italic',
                  fontSize: 14, color: C.brassDeep }}>{r.l}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Source state stamps */}
        <div style={{ background: C.card, border: `1px solid ${C.rule}`, padding: 20 }}>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: C.inkDim, marginBottom: 14 }}>
            Source status · stamped, not pilled</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14,
            rowGap: 18, alignItems: 'center', justifyItems: 'center' }}>
            {[
              { l: 'pending', t: 'mute' },
              { l: 'running', t: 'brass' },
              { l: 'found', t: 'moss' },
              { l: 'likely', t: 'ochre' },
              { l: 'uncertain', t: 'brass' },
              { l: 'not found', t: 'mute' },
              { l: 'blocked', t: 'ochre' },
              { l: 'error', t: 'forensic' },
            ].map((s, i) => (
              <Stamp key={s.l} label={s.l} tone={s.t} rotate={Math.sin(i*3) * 3} />
            ))}
          </div>
        </div>

        {/* Severity */}
        <div style={{ background: C.card, border: `1px solid ${C.rule}`, padding: 20 }}>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: C.inkDim, marginBottom: 14 }}>
            Risk · serif weight</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 24 }}>
            {[
              { l: 'Critical', c: C.forensic, w: 700 },
              { l: 'High', c: C.ochre, w: 600 },
              { l: 'Medium', c: C.brassDeep, w: 500 },
              { l: 'Low', c: C.inkMute, w: 400 },
            ].map(r => (
              <div key={r.l} style={{ fontFamily: C.display, fontStyle: 'italic',
                fontSize: 22, color: r.c, fontWeight: r.w,
                letterSpacing: '-0.01em' }}>{r.l}</div>
            ))}
          </div>
          <div style={{ fontSize: 12, color: C.inkMute, marginTop: 16, lineHeight: 1.5,
            fontFamily: C.displayItalic, fontStyle: 'italic' }}>
            Severidade vira <em>peso tipográfico</em>: críticas em itálico encorpado, baixas
            em itálico fino — leitura ranqueia por gravidade sem precisar de ícone.
          </div>
        </div>

        {/* Evidence */}
        <div style={{ background: C.card, border: `1px solid ${C.rule}`, padding: 20 }}>
          <div style={{ fontFamily: C.mono, fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: C.inkDim, marginBottom: 14 }}>
            Evidence · footnote with weight</div>
          <p style={{ fontFamily: C.display, fontSize: 13.5, lineHeight: 1.55, color: C.ink,
            margin: 0 }}>
            <em>Email registered on Spotify</em><Citation n="04" /> — sourced from Holehe,
            indexed 14h ago.
          </p>
          <div style={{ marginTop: 14, padding: 12, background: C.cardCool,
            border: `1px solid ${C.rule}`, fontFamily: C.mono, fontSize: 11,
            color: C.inkMute, lineHeight: 1.55 }}>
            <div><span style={{ color: C.brassDeep }}>[04]</span> source · Holehe</div>
            <div><span style={{ color: C.brassDeep }}>     </span> age · 14h · fresh</div>
            <div><span style={{ color: C.brassDeep }}>     </span> weight · 0.18 of total</div>
            <div><span style={{ color: C.brassDeep }}>     </span> raw · GET /v1/holehe/spotify</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
function CasebookProsCons() {
  return <ProsConsCard
    title="Casebook — investigation workspace"
    accent={C.brass}
    pros={[
      'Metáfora clara: cada caso é um dossiê. Onboarding praticamente conta sozinho.',
      'Tipografia serif + footnotes elevam Nexus para "ferramenta séria de investigação"',
      'Diferenciação visual EXTREMA: zero concorrente OSINT usa essa direção',
      'Real-time vira diário do caso → narrativa, não apenas dados streaming',
      'PDF export é praticamente o próprio dossiê — coerência editorial completa',
    ]}
    cons={[
      'Mais opinativo: o usuário precisa "comprar" a metáfora ou estranha',
      'Serif para dados longos pode cansar — body fica sempre em sans-serif',
      'Tabs físicas + carimbos exigem mais carinho em estados pequenos (badge, hover)',
      'Light tone reduz a estética "cyber" — pode soar acadêmico demais para alguns',
    ]}
    riskGeneric={'MUITO BAIXO. É o conceito mais difícil de confundir com qualquer concorrente. Os carimbos, citações numeradas e papel manilla são uma assinatura visual inteira.'}
    riskImpl={'ALTO. Tipografia serif, carimbos rotacionados, footnotes vinculadas ao raw, paper grain — todos requerem polimento manual. ~3-4 semanas para chegar ao nível mostrado.'}
    recommendation={'Apostar aqui se Nexus quer mirar em profissionais de investigação (fraude, jurídico, jornalismo investigativo, due diligence). Cria identidade memorável e justifica preço premium.'}
  />;
}

// ──────────────────────────────────────────────────────────
function CasebookBoards() {
  return (
    <React.Fragment>
      <DCArtboard id="cb-identity" label="01 · Identity" width={1200} height={820}>
        <window.CasebookIdentity />
      </DCArtboard>
      <DCArtboard id="cb-dashboard" label="02 · Dashboard" width={1280} height={920}>
        <window.CasebookDashboard />
      </DCArtboard>
      <DCArtboard id="cb-search" label="03 · Search + live timeline" width={1280} height={920}>
        <CasebookSearch />
      </DCArtboard>
      <DCArtboard id="cb-results" label="04 · Results dossier" width={1280} height={1000}>
        <CasebookResults />
      </DCArtboard>
      <DCArtboard id="cb-admin" label="05 · Registry / admin" width={1280} height={820}>
        <CasebookAdmin />
      </DCArtboard>
      <DCArtboard id="cb-scoring" label="06 · Scoring system" width={1000} height={780}>
        <CasebookScoring />
      </DCArtboard>
      <DCArtboard id="cb-tradeoffs" label="07 · Trade-offs" width={780} height={780}>
        <CasebookProsCons />
      </DCArtboard>
    </React.Fragment>
  );
}

Object.assign(window, { CasebookSearch, CasebookResults, CasebookAdmin,
  CasebookScoring, CasebookProsCons, CasebookBoards });
