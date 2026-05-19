// Signal v2 — analyst-mode results + Casebook PDF export + boards.
const { S, MicroSpark, Dial, SignalStatus, SignalConfBar, PanelHeader } = window;
const { C: Cb, Stamp, Seal, Citation, Concur } = window;
const { CAT, CatChip, ViewSwitch, SignalChromeQuiet,
  SignalV2Brief, ViewToggleSpec,
  SignalSimpleDashboard, GanttHero, SignalSimpleResults } = window;

// ──────────────────────────────────────────────────────────
// ANALYST VIEW · same case, full density.
function SignalAnalystResults() {
  return (
    <SignalChromeQuiet mode="analyst" active="cases"
      contextLine="case=0241 · workers=3/5 · live=true">
      <div style={{ padding: 18, display: 'grid',
        gridTemplateColumns: '1fr 320px', gap: 14 }}>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Compact title */}
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
            padding: '0 0 10px', borderBottom: `1px solid ${S.hair}` }}>
            <div>
              <span style={{ fontFamily: S.mono, fontSize: 11, color: S.tealDeep,
                letterSpacing: '0.16em' }}>№0241</span>
              <span style={{ fontFamily: S.mono, fontSize: 16, color: S.ink, marginLeft: 12 }}>
                lucas.silva@protonmail.com</span>
            </div>
            <div style={{ fontFamily: S.mono, fontSize: 11, color: S.inkMute }}>
              43 findings · 12 sources · live · last refresh 14s</div>
          </div>

          {/* Category quick switch */}
          <div style={{ display: 'flex', gap: 6 }}>
            <CatChip cat="exposure" n={4} active />
            <CatChip cat="identity" n={24} />
            <CatChip cat="social" n={13} />
            <CatChip cat="infra" n={2} />
          </div>

          {/* Same exposure data but full-density */}
          <div style={{ background: S.surface, border: `1px solid ${S.hair}`,
            borderTop: `2px solid ${CAT.exposure.color}` }}>
            <PanelHeader title="◆  Exposure · 4 findings"
              right="HIBP · OathNet · Stealer" />
            <div style={{ padding: '4px 12px 12px' }}>
              {[
                { n: 'Genesis Market log', date: '2022-11', sev: 'crit', src: 'OATH',
                  age: '2y', leak: 'cookies, fingerprint, password', w: 0.28 },
                { n: 'Antipublic 2.0', date: '2020-04', sev: 'crit', src: 'HIBP',
                  age: '4y', leak: 'email, password, ip', w: 0.18 },
                { n: 'Collection #1', date: '2019-01', sev: 'high', src: 'HIBP',
                  age: '6y', leak: 'email, sha1(password)', w: 0.14 },
                { n: 'Stealer log RC-2Z1L-088', date: '2024-04', sev: 'crit', src: 'STLR',
                  age: '11d', leak: '40 files · cookies + creds', w: 0.18 },
              ].map((b, i) => (
                <div key={i} style={{ display: 'grid',
                  gridTemplateColumns: '1.4fr 60px 50px 1.2fr 70px 60px',
                  gap: 10, padding: '8px 0', alignItems: 'center',
                  borderTop: i ? `1px solid ${S.hair}` : 'none' }}>
                  <div style={{ fontFamily: S.body, fontSize: 12, color: S.ink }}>{b.n}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute }}>{b.date}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 10, color: S.tealDeep }}>{b.src}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 10.5, color: S.inkMute }}>{b.leak}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 10, color: S.green }}>{b.age}</div>
                  <div style={{ fontFamily: S.mono, fontSize: 10,
                    color: b.sev === 'crit' ? S.red : S.amber,
                    letterSpacing: '0.14em', textTransform: 'uppercase' }}>{b.sev}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Event feed — only visible in analyst */}
          <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
            <PanelHeader title="Event feed · streaming" right="auto-tail · last 60s" />
            <div style={{ padding: '8px 14px 12px', fontFamily: S.mono, fontSize: 10.5,
              display: 'flex', flexDirection: 'column' }}>
              {[
                { t: '11:42:18', l: 'HIBP', m: 'breach.match collection-1', c: S.green },
                { t: '11:42:21', l: 'OATH', m: 'graph.match edges=12', c: S.green },
                { t: '11:42:26', l: 'HOLE', m: 'reg.found sites=23/130', c: S.green },
                { t: '11:42:29', l: 'WHOIS', m: 'domain.resolved proton.ag CH', c: S.green },
                { t: '11:42:30', l: 'DISC', m: 'username.collision · review needed', c: S.amber },
                { t: '11:42:39', l: 'SPDR', m: 'rate.limit retry=120s', c: S.amber },
                { t: '11:42:42', l: 'IMG', m: 'upstream.502 attempts=3 abort', c: S.red },
                { t: '11:42:45', l: 'SHER', m: 'crawl.progress 312/412', c: S.teal },
                { t: '11:42:51', l: 'STLR', m: 'cold.start eta=18s', c: S.teal },
              ].map((e, i) => (
                <div key={i} style={{ padding: '3px 0', display: 'grid',
                  gridTemplateColumns: '70px 50px 1fr', gap: 8 }}>
                  <span style={{ color: S.inkDim }}>{e.t}</span>
                  <span style={{ color: e.c, fontWeight: 600 }}>{e.l}</span>
                  <span style={{ color: S.inkMute }}>{e.m}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Evidence ledger — only analyst */}
          <div style={{ background: S.surface, border: `1px solid ${S.hair}` }}>
            <PanelHeader title="Evidence ledger · weighted" right="contribution per source" />
            <div style={{ padding: 14, fontFamily: S.mono, fontSize: 11 }}>
              {[
                { src: 'HIBP', w: 0.32, age: '4h', txt: 'breach.match collection-1 + antipublic' },
                { src: 'OATH', w: 0.28, age: '4h', txt: 'graph.match 12 vertices · sha1 chain' },
                { src: 'STLR', w: 0.18, age: '11d', txt: 'log RC-2Z1L-088 · session cookies present' },
                { src: 'HOLE', w: 0.12, age: '14h', txt: 'registration spread across 23 sites' },
                { src: 'DISC', w: 0.07, age: '20s', txt: 'username collision · MANUAL REVIEW' },
                { src: 'WHOIS', w: 0.03, age: '4h', txt: 'protonmail.com · Proton AG · CH' },
              ].map((e, i) => (
                <div key={i} style={{ display: 'grid',
                  gridTemplateColumns: '40px 50px 60px 1fr 80px', gap: 10,
                  alignItems: 'center', padding: '5px 0',
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

        {/* Right rail — heavy with telemetry */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 16 }}>
            <PanelHeader title="Confidence" right="-2pt from start" />
            <div style={{ paddingTop: 12, display: 'flex', justifyContent: 'space-around' }}>
              <Dial value={0.84} label="overall" size={84} color={S.teal} />
              <Dial value={0.74} label="risk" size={84} color={S.red} />
            </div>
          </div>

          <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 14 }}>
            <PanelHeader title="Source health" right="realtime · 5s" />
            <div style={{ paddingTop: 8 }}>
              {[
                { n: 'HIBP', l: '180ms', s: 'ok', sp: [9,9,8,9,9,9,8,9] },
                { n: 'OathNet', l: '420ms', s: 'ok', sp: [7,8,7,9,8,8,9,8] },
                { n: 'Holehe', l: '1.4s', s: 'ok', sp: [8,7,9,8,9,8,8,9] },
                { n: 'Sherlock', l: '2.1s', s: 'deg', sp: [6,4,8,3,7,5,6,4] },
                { n: 'Stealer', l: '6.8s', s: 'deg', sp: [4,3,6,2,5,3,7,2] },
                { n: 'SpiderFoot', l: '—', s: 'down', sp: [1,1,1,1,1,1,1,1] },
              ].map((s, i) => (
                <div key={s.n} style={{ display: 'grid',
                  gridTemplateColumns: '1fr 70px 50px 10px',
                  gap: 8, alignItems: 'center', padding: '6px 0',
                  borderTop: i ? `1px solid ${S.hair}` : 'none' }}>
                  <div style={{ fontFamily: S.mono, fontSize: 11, color: S.ink }}>{s.n}</div>
                  <MicroSpark values={s.sp} color={s.s === 'ok' ? S.green : s.s === 'deg' ? S.amber : S.red} width={70} height={14} />
                  <div style={{ fontFamily: S.mono, fontSize: 10, color: S.inkMute,
                    textAlign: 'right' }}>{s.l}</div>
                  <div style={{ width: 6, height: 6, borderRadius: 99,
                    background: s.s === 'ok' ? S.green : s.s === 'deg' ? S.amber : S.red }} />
                </div>
              ))}
            </div>
          </div>

          <div style={{ background: S.surface, border: `1px solid ${S.hair}`, padding: 14 }}>
            <PanelHeader title="Worker pool" right="3/5 sem" />
            <div style={{ display: 'flex', gap: 4, marginTop: 12 }}>
              {[1,1,1,0,0].map((on, i) => (
                <div key={i} style={{ flex: 1, height: 26,
                  background: on ? S.tealSoft : 'transparent',
                  border: `1px solid ${on ? S.tealBorder : S.hair}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: S.mono, fontSize: 9, color: on ? S.teal : S.inkDim,
                  letterSpacing: '0.1em', fontWeight: 600 }}>{on ? 'BUSY' : '—'}</div>
              ))}
            </div>
            <div style={{ marginTop: 10, fontFamily: S.mono, fontSize: 10,
              color: S.inkMute }}>
              ram · <span style={{ color: S.amber }}>178M</span> / 200M · cpu 38%
            </div>
          </div>
        </aside>
      </div>
    </SignalChromeQuiet>
  );
}

// ──────────────────────────────────────────────────────────
// CASEBOOK EXPORT — PDF/dossier styling
function CasebookExport() {
  return (
    <div style={{ width: '100%', height: '100%', background: '#2a2723', color: Cb.ink,
      fontFamily: Cb.body, padding: 36, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 18, overflow: 'hidden' }}>

      <div>
        <div style={{ fontFamily: S.mono, fontSize: 10, letterSpacing: '0.18em',
          textTransform: 'uppercase', color: S.sand }}>Export · dossier PDF</div>
        <div style={{ fontFamily: S.display, fontSize: 24, fontWeight: 600,
          letterSpacing: '-0.025em', marginTop: 6, color: S.ink }}>
          Same data, paper-bound.{' '}
          <span style={{ fontFamily: '"Instrument Serif", serif', fontStyle: 'italic',
            fontWeight: 400, color: S.sand }}>Casebook visual, for what leaves the app.</span>
        </div>
      </div>

      {/* Two PDF pages mocked side-by-side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18,
        flex: 1, overflow: 'hidden' }}>

        {/* Cover page */}
        <div style={{ background: Cb.paper, color: Cb.ink,
          fontFamily: Cb.body, padding: 32, position: 'relative',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          backgroundImage: 'radial-gradient(rgba(26,20,16,0.03) 1px, transparent 1px)',
          backgroundSize: '4px 4px', display: 'flex', flexDirection: 'column' }}>

          <div style={{ position: 'absolute', top: 24, right: 24, display: 'flex', gap: 10 }}>
            <Stamp label="confidential" tone="forensic" rotate={-3} />
            <Stamp label="case 0241" tone="brass" rotate={2} />
          </div>

          <div style={{ marginTop: 28, fontFamily: Cb.mono, fontSize: 9,
            letterSpacing: '0.18em', textTransform: 'uppercase',
            color: Cb.brassDeep }}>Nexus · Investigation Dossier</div>
          <div style={{ fontFamily: Cb.display, fontSize: 36, fontWeight: 600,
            letterSpacing: '-0.025em', marginTop: 6, lineHeight: 1.05 }}>
            Case<span style={{ fontStyle: 'italic', fontWeight: 400,
              color: Cb.brassDeep }}>book</span>
            <span style={{ fontFamily: Cb.mono, fontSize: 16, color: Cb.inkMute,
              marginLeft: 8, fontWeight: 400 }}>№0241</span>
          </div>

          <div style={{ marginTop: 24, padding: '12px 14px', background: Cb.cardCool,
            border: `1.5px solid ${Cb.ink}`,
            borderLeft: `4px solid ${Cb.brass}` }}>
            <div style={{ fontFamily: Cb.mono, fontSize: 9, color: Cb.brassDeep,
              letterSpacing: '0.14em', textTransform: 'uppercase' }}>Subject</div>
            <div style={{ fontFamily: Cb.mono, fontSize: 14, color: Cb.ink,
              marginTop: 4 }}>lucas.silva@protonmail.com</div>
          </div>

          <div style={{ marginTop: 18, display: 'grid',
            gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <div style={{ fontFamily: Cb.mono, fontSize: 9, color: Cb.inkDim,
                letterSpacing: '0.14em', textTransform: 'uppercase' }}>Verdict</div>
              <div style={{ fontFamily: Cb.display, fontSize: 28, fontWeight: 600,
                fontStyle: 'italic', color: Cb.forensic,
                letterSpacing: '-0.025em', marginTop: 4 }}>Critical</div>
            </div>
            <div>
              <div style={{ fontFamily: Cb.mono, fontSize: 9, color: Cb.inkDim,
                letterSpacing: '0.14em', textTransform: 'uppercase' }}>Concur</div>
              <div style={{ marginTop: 6 }}>
                <Concur confirmed={6} total={8} />
              </div>
            </div>
          </div>

          <div style={{ marginTop: 18, paddingTop: 14, borderTop: `1.5px solid ${Cb.ink}` }}>
            <div style={{ fontFamily: Cb.mono, fontSize: 9, color: Cb.inkDim,
              letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
              Source seals</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Seal letter="H" tone="moss" size={34} />
              <Seal letter="O" tone="moss" size={34} />
              <Seal letter="h" tone="moss" size={34} />
              <Seal letter="W" tone="moss" size={34} />
              <Seal letter="S" tone="forensic" size={34} />
              <Seal letter="D" tone="brass" size={34} />
              <Seal letter="!" tone="forensic" size={34} />
            </div>
          </div>

          <div style={{ marginTop: 'auto', paddingTop: 18,
            borderTop: `1px solid ${Cb.rule}`, fontFamily: Cb.displayItalic,
            fontStyle: 'italic', fontSize: 12, color: Cb.inkMute,
            lineHeight: 1.5 }}>
            Compiled by mattheus · 12 May 2026, 11:54 BRT · 8 sources, 43 findings ·
            Retention: 90 days · Signed nx-7c4f-9b3a
          </div>

          <div style={{ position: 'absolute', bottom: 20, right: 24,
            fontFamily: Cb.mono, fontSize: 9, color: Cb.inkDim,
            letterSpacing: '0.16em' }}>p. 01 / 12</div>
        </div>

        {/* Findings page */}
        <div style={{ background: Cb.paper, color: Cb.ink,
          fontFamily: Cb.body, padding: 32, position: 'relative',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          backgroundImage: 'radial-gradient(rgba(26,20,16,0.03) 1px, transparent 1px)',
          backgroundSize: '4px 4px', overflow: 'hidden' }}>

          <div style={{ fontFamily: Cb.mono, fontSize: 9,
            letterSpacing: '0.18em', textTransform: 'uppercase',
            color: Cb.brassDeep }}>Findings · § 1 of 4</div>
          <h2 style={{ fontFamily: Cb.display, fontSize: 22, fontWeight: 600,
            margin: '6px 0 4px', letterSpacing: '-0.02em' }}>
            Credential exposure</h2>
          <div style={{ fontFamily: Cb.displayItalic, fontStyle: 'italic',
            fontSize: 13, color: Cb.brassDeep }}>4 findings · 3 critical, 1 high</div>

          <hr style={{ border: 0, borderTop: `1.5px solid ${Cb.ink}`, margin: '14px 0' }} />

          <p style={{ fontFamily: Cb.display, fontSize: 13.5, lineHeight: 1.6,
            color: Cb.ink, margin: '0 0 12px', textWrap: 'pretty' }}>
            The subject's email appears in <em>four breach indices</em><Citation n="01" />,
            two with cleartext credentials<Citation n="02" />. A 2024 stealer log<Citation n="03" />
            contains active session cookies — recent device compromise.
          </p>

          {/* Mini breach table */}
          {[
            { n: 'Genesis Market log', date: '2022-11', sev: 'critical' },
            { n: 'Antipublic 2.0', date: '2020-04', sev: 'critical' },
            { n: 'Collection #1', date: '2019-01', sev: 'high' },
            { n: 'Stealer RC-2Z1L', date: '2024-04', sev: 'critical' },
          ].map((b, i) => (
            <div key={i} style={{ display: 'grid',
              gridTemplateColumns: '1.6fr 70px 80px',
              gap: 10, padding: '8px 0',
              borderTop: `1px solid ${Cb.rule}` }}>
              <div style={{ fontFamily: Cb.display, fontSize: 13,
                fontWeight: 600 }}>{b.n}</div>
              <div style={{ fontFamily: Cb.mono, fontSize: 10, color: Cb.inkMute }}>{b.date}</div>
              <div style={{ fontFamily: Cb.displayItalic, fontStyle: 'italic',
                fontSize: 13, color: b.sev === 'critical' ? Cb.forensic : Cb.ochre,
                fontWeight: 600, textAlign: 'right' }}>{b.sev}</div>
            </div>
          ))}

          {/* Footnotes */}
          <div style={{ marginTop: 14, paddingTop: 12,
            borderTop: `1.5px solid ${Cb.ink}`,
            fontFamily: Cb.mono, fontSize: 9, color: Cb.inkDim,
            letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
            Evidence</div>
          <ol style={{ paddingLeft: 16, margin: 0,
            fontFamily: Cb.displayItalic, fontStyle: 'italic',
            fontSize: 11.5, lineHeight: 1.55, color: Cb.inkMute }}>
            <li>HIBP indexed 2024-03-04 · fresh · weight 0.32</li>
            <li>OathNet credential graph · matched on email+sha1 · fresh</li>
            <li>Stealer log RC-2Z1L-088 · 40 files · captured 11d ago</li>
          </ol>

          <div style={{ position: 'absolute', bottom: 20, right: 24,
            fontFamily: Cb.mono, fontSize: 9, color: Cb.inkDim,
            letterSpacing: '0.16em' }}>p. 03 / 12</div>
        </div>
      </div>

      <div style={{ padding: '12px 16px',
        background: S.tealSoft, border: `1px solid ${S.tealBorder}`,
        fontSize: 12, color: S.ink, lineHeight: 1.55 }}>
        <strong>Por quê isso funciona:</strong> dentro do app, Signal vence em densidade e
        leitura ao vivo. Mas o que sai do app — o PDF que vai para um cliente, juiz, ou
        executivo — precisa <em>parecer</em> com a gravidade do conteúdo. Casebook entrega
        esse peso. Mesma fonte de dados, dois rostos.
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────
function SignalV2Boards() {
  return (
    <React.Fragment>
      <DCArtboard id="v2-brief" label="01 · Five refinements" width={1200} height={780}>
        <window.SignalV2Brief />
      </DCArtboard>
      <DCArtboard id="v2-toggle" label="02 · View toggle spec" width={1100} height={760}>
        <window.ViewToggleSpec />
      </DCArtboard>
      <DCArtboard id="v2-simple-dash" label="03 · Simple · Dashboard" width={1360} height={820}>
        <SignalSimpleDashboard />
      </DCArtboard>
      <DCArtboard id="v2-gantt" label="04 · Gantt as hero" width={1360} height={900}>
        <GanttHero />
      </DCArtboard>
      <DCArtboard id="v2-simple-results" label="05 · Simple · Results by category" width={1360} height={1060}>
        <SignalSimpleResults />
      </DCArtboard>
      <DCArtboard id="v2-analyst-results" label="06 · Analyst · Same case, full density" width={1360} height={1000}>
        <SignalAnalystResults />
      </DCArtboard>
      <DCArtboard id="v2-export" label="07 · Casebook export · PDF dossier" width={1200} height={820}>
        <CasebookExport />
      </DCArtboard>
    </React.Fragment>
  );
}

Object.assign(window, { SignalAnalystResults, CasebookExport, SignalV2Boards });
