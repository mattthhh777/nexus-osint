// Intro: diagnostic of current Meridian + system brief.

function IntroBrief() {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: '#fbfaf6', color: '#181612',
      fontFamily: 'Inter, system-ui, sans-serif',
      padding: 48, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 24,
    }}>
      <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 11,
        letterSpacing: '0.18em', textTransform: 'uppercase', color: '#a8744b' }}>
        Briefing · Exploração Visual
      </div>
      <div style={{ fontSize: 34, fontWeight: 600, letterSpacing: '-0.025em',
        lineHeight: 1.15, maxWidth: 720 }}>
        Tornar o Nexus uma ferramenta OSINT que parece <em style={{ fontFamily: 'Instrument Serif, serif', fontWeight: 400 }}>premium</em> sem virar genérica de IA, cópia da OathNet, ou cyberpunk de banco de imagem.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginTop: 8 }}>
        <div>
          <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
            letterSpacing: '0.16em', textTransform: 'uppercase',
            color: 'rgba(24,22,18,0.4)', marginBottom: 8 }}>Hoje · Meridian</div>
          <div style={{ fontSize: 13, lineHeight: 1.55, color: 'rgba(24,22,18,0.72)' }}>
            Amber #f0a030 sobre noir #060810. Space Grotesk + JetBrains Mono. Densidade alta,
            radii apertados (2–6px), severidade vermelha/laranja. Vibe "night command station".
            Funcional, mas a paleta amber+dark é o terreno mais saturado em ferramentas de
            cyber/OSINT — fácil cair na mesma cara que dezenas de concorrentes.
          </div>
        </div>
        <div>
          <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
            letterSpacing: '0.16em', textTransform: 'uppercase',
            color: 'rgba(24,22,18,0.4)', marginBottom: 8 }}>Pressão futura · Real-time</div>
          <div style={{ fontSize: 13, lineHeight: 1.55, color: 'rgba(24,22,18,0.72)' }}>
            O motor real-time muda o problema: status por fonte (pending/running/found/blocked/
            error), confidence score, evidence scoring, source health, anti-falso-positivo,
            partial results streaming. A UI precisa <strong>respirar movimento</strong> e
            mostrar <strong>incerteza</strong> sem virar uma soup de spinners.
          </div>
        </div>
        <div>
          <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
            letterSpacing: '0.16em', textTransform: 'uppercase',
            color: 'rgba(24,22,18,0.4)', marginBottom: 8 }}>Como leio o pedido</div>
          <div style={{ fontSize: 13, lineHeight: 1.55, color: 'rgba(24,22,18,0.72)' }}>
            Três direções genuinamente diferentes — não três variações da mesma. Cada uma
            assume um <em>ponto de vista</em> sobre o que o Nexus é: produto, dossiê, ou
            console. Você escolhe a postura primeiro; visual decorre disso.
          </div>
        </div>
      </div>

      <div style={{ marginTop: 'auto', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {[
          { tag: '01', name: 'Lumen',
            sub: 'SaaS premium · light · sage on bone',
            color: '#7a9580',
            line: 'Aposta: parecer um produto, não uma ferramenta. Stripe / Linear / Vercel-grade.' },
          { tag: '02', name: 'Casebook',
            sub: 'Investigation workspace · paper · serif',
            color: '#a8744b',
            line: 'Aposta: a investigação como documento. Manilla, evidência, dossiê.' },
          { tag: '03', name: 'Signal',
            sub: 'Analyst console · slate · calm density',
            color: '#7fa4b8',
            line: 'Aposta: console profissional sem hacker-cosplay. Bloomberg, não Mr. Robot.' },
        ].map(c => (
          <div key={c.tag} style={{ padding: 18, borderRadius: 10,
            background: 'white', border: '1px solid rgba(0,0,0,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
              <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
                color: c.color, letterSpacing: '0.15em' }}>{c.tag}</span>
              <span style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.015em' }}>{c.name}</span>
            </div>
            <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
              letterSpacing: '0.1em', textTransform: 'uppercase',
              color: 'rgba(24,22,18,0.4)', marginBottom: 8 }}>{c.sub}</div>
            <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'rgba(24,22,18,0.7)' }}>{c.line}</div>
            <div style={{ height: 3, background: c.color, marginTop: 14, borderRadius: 2,
              width: '40%' }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CurrentVsFuture() {
  return (
    <div style={{ width: '100%', height: '100%',
      background: '#0e1116', color: '#e4e8f0',
      fontFamily: 'Inter, system-ui, sans-serif',
      padding: 40, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
        letterSpacing: '0.18em', textTransform: 'uppercase',
        color: '#f0a030' }}>Diagnóstico · Meridian hoje</div>
      <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em', maxWidth: 640 }}>
        O que o Nexus já faz bem — e o que <span style={{ color: '#f0a030' }}>não</span> está pronto pro motor real-time.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28, marginTop: 8 }}>
        <div>
          <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 9,
            letterSpacing: '0.16em', textTransform: 'uppercase',
            color: 'rgba(228,232,240,0.5)', marginBottom: 10 }}>Forças</div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none',
            display: 'flex', flexDirection: 'column', gap: 9 }}>
            {[
              'Sistema de tokens Meridian (CSS vars) — fácil rebranding parcial',
              'Severidade já modelada (critical/high/medium/low + success/info)',
              'Hierarquia tipográfica clara: display, body, data',
              'Cards densos funcionam para discord/gaming/victim/SF findings',
            ].map(p => (
              <li key={p} style={{ fontSize: 13, lineHeight: 1.45,
                paddingLeft: 16, position: 'relative', color: 'rgba(228,232,240,0.85)' }}>
                <span style={{ position: 'absolute', left: 0, top: 7, width: 6, height: 6,
                  borderRadius: 99, background: '#22c55e' }} />{p}</li>
            ))}
          </ul>
        </div>
        <div>
          <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 9,
            letterSpacing: '0.16em', textTransform: 'uppercase',
            color: 'rgba(228,232,240,0.5)', marginBottom: 10 }}>Lacunas para o real-time</div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none',
            display: 'flex', flexDirection: 'column', gap: 9 }}>
            {[
              'Nenhuma linguagem visual para incerteza (likely / uncertain / blocked)',
              'Confidence score não tem componente — só severity binária',
              'Source health não existe como cidadão de primeira classe',
              'Nenhuma visão "live" — todos os layouts assumem dados terminais',
              'Amber+noir é o terreno mais saturado em OSINT — diferenciação fraca',
            ].map(p => (
              <li key={p} style={{ fontSize: 13, lineHeight: 1.45,
                paddingLeft: 16, position: 'relative', color: 'rgba(228,232,240,0.85)' }}>
                <span style={{ position: 'absolute', left: 0, top: 7, width: 6, height: 6,
                  borderRadius: 99, background: '#ef4444' }} />{p}</li>
            ))}
          </ul>
        </div>
      </div>

      <div style={{ marginTop: 'auto', padding: 18,
        background: 'rgba(240,160,48,0.08)',
        border: '1px solid rgba(240,160,48,0.25)',
        borderRadius: 8 }}>
        <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
          letterSpacing: '0.16em', textTransform: 'uppercase',
          color: '#f0a030', marginBottom: 6 }}>Tese</div>
        <div style={{ fontSize: 13.5, lineHeight: 1.55, color: 'rgba(228,232,240,0.9)' }}>
          O Meridian é bom, mas amarra o produto a <em>uma única estética</em>. As três propostas a
          seguir respeitam tudo que ele já fez bem (tokens, severidade, monoespaço para dados) e
          fazem três apostas diferentes sobre <strong>quem é o usuário</strong> e <strong>como ele
          se sente abrindo o app</strong>.
        </div>
      </div>
    </div>
  );
}

function IntroBoards() {
  return (
    <React.Fragment>
      <DCArtboard id="intro-brief" label="Briefing" width={1200} height={760}>
        <IntroBrief />
      </DCArtboard>
      <DCArtboard id="intro-diagnostic" label="Diagnóstico" width={1000} height={760}>
        <CurrentVsFuture />
      </DCArtboard>
    </React.Fragment>
  );
}

Object.assign(window, { IntroBoards });
