// Final comparison + recommendation.

function ComparisonMatrix() {
  const rows = [
    { k: 'Distintividade visual',
      L: { score: 4, t: 'Light + sage + serif italic é raro em OSINT' },
      C: { score: 5, t: 'Quase impossível confundir com algo' },
      S: { score: 3, t: 'Mais próximo do estado da arte atual' } },
    { k: 'Encaixe com motor real-time',
      L: { score: 3, t: 'Bom — status/movimento ressaltam contra calma' },
      C: { score: 3, t: 'Diário do caso é elegante mas mais lento' },
      S: { score: 5, t: 'Gantt, dials e event feed FORAM feitos para isso' } },
    { k: 'Densidade de informação',
      L: { score: 3, t: 'Restrita por escolha — pode apertar com muitas fontes' },
      C: { score: 3, t: 'Editorial limita densidade extrema' },
      S: { score: 5, t: 'Cabe muita coisa por tela sem ruído' } },
    { k: 'Risco "parece genérico"',
      L: { score: 4, t: 'Baixo — mas pode soar "SaaS qualquer"' },
      C: { score: 5, t: 'Muito baixo — direção única' },
      S: { score: 3, t: 'Médio — depende de polimento fino' } },
    { k: 'Esforço de implementação',
      L: { score: 2, t: 'Alto — revisão completa de tokens.css' },
      C: { score: 1, t: 'Muito alto — tipografia, citações, carimbos' },
      S: { score: 4, t: 'Baixo/médio — reutiliza Meridian' } },
    { k: 'Apelo enterprise / B2B',
      L: { score: 5, t: 'Vence — único conceito "corporativo"' },
      C: { score: 4, t: 'Forte para jurídico, jornalismo, due diligence' },
      S: { score: 3, t: 'Forte para SOC, threat intel, analistas' } },
    { k: 'Continuidade com o existente',
      L: { score: 2, t: 'Quebra significativa do Meridian' },
      C: { score: 1, t: 'Reescrita visual completa' },
      S: { score: 5, t: 'Evolução do que já existe' } },
  ];

  const Score = ({ n }) => (
    <div style={{ display: 'flex', gap: 3 }}>
      {[1,2,3,4,5].map(i => (
        <div key={i} style={{ width: 14, height: 6, borderRadius: 1,
          background: i <= n ? '#181612' : 'rgba(24,22,18,0.10)' }} />
      ))}
    </div>
  );

  return (
    <div style={{ width: '100%', height: '100%', background: '#fbfaf6', color: '#181612',
      fontFamily: 'Inter, system-ui, sans-serif', padding: 36, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div>
        <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
          letterSpacing: '0.18em', textTransform: 'uppercase',
          color: 'rgba(24,22,18,0.45)' }}>Side-by-side</div>
        <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: '-0.025em',
          marginTop: 6, fontFamily: '"Inter Tight", system-ui, sans-serif' }}>
          Como cada conceito se sai em <em style={{
            fontFamily: 'Instrument Serif, serif', fontStyle: 'italic',
            fontWeight: 400 }}>sete</em> eixos.
        </div>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
        <thead>
          <tr style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
            color: 'rgba(24,22,18,0.45)', letterSpacing: '0.12em',
            textTransform: 'uppercase' }}>
            <th style={{ width: '22%', textAlign: 'left', padding: '10px 0',
              borderBottom: '2px solid #181612' }}>Eixo</th>
            <th style={{ width: '26%', textAlign: 'left', padding: '10px 0',
              borderBottom: '2px solid #181612' }}>
              <span style={{ color: '#4d6557', fontWeight: 700 }}>Lumen</span></th>
            <th style={{ width: '26%', textAlign: 'left', padding: '10px 0',
              borderBottom: '2px solid #181612' }}>
              <span style={{ color: '#a87544', fontWeight: 700 }}>Casebook</span></th>
            <th style={{ width: '26%', textAlign: 'left', padding: '10px 0',
              borderBottom: '2px solid #181612' }}>
              <span style={{ color: '#5897ab', fontWeight: 700 }}>Signal</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ verticalAlign: 'top',
              borderBottom: '1px solid rgba(24,22,18,0.08)' }}>
              <td style={{ padding: '14px 8px 14px 0', fontSize: 13, fontWeight: 500 }}>
                {r.k}</td>
              {['L','C','S'].map(k => (
                <td key={k} style={{ padding: '14px 12px 14px 0' }}>
                  <Score n={r[k].score} />
                  <div style={{ fontSize: 11.5, color: 'rgba(24,22,18,0.6)',
                    marginTop: 6, lineHeight: 1.45 }}>{r[k].t}</div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FinalPick() {
  return (
    <div style={{ width: '100%', height: '100%',
      background: '#0e1116', color: '#ecedf0',
      fontFamily: 'Inter, system-ui, sans-serif', padding: 44, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 22, position: 'relative',
      overflow: 'hidden' }}>
      {/* Decorative grid */}
      <div style={{ position: 'absolute', inset: 0, opacity: 0.4,
        backgroundImage: `
          linear-gradient(to right, rgba(255,255,255,0.04) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(255,255,255,0.04) 1px, transparent 1px)`,
        backgroundSize: '48px 48px', pointerEvents: 'none' }} />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
          letterSpacing: '0.18em', textTransform: 'uppercase',
          color: '#8ec4d4' }}>Recomendação final</div>

        <div style={{ fontSize: 56, fontWeight: 600, letterSpacing: '-0.035em',
          marginTop: 8, lineHeight: 1.05, fontFamily: '"Sora", system-ui, sans-serif',
          maxWidth: 880 }}>
          <span style={{ color: '#5897ab' }}>Signal</span> agora,{' '}
          <span style={{ fontFamily: 'Instrument Serif, serif', fontStyle: 'italic',
            color: '#d4b88e', fontWeight: 400 }}>Casebook</span> depois.
        </div>
      </div>

      <div style={{ position: 'relative', zIndex: 1, display: 'grid',
        gridTemplateColumns: '1.4fr 1fr', gap: 32, flex: 1 }}>
        <div>
          <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
            letterSpacing: '0.16em', textTransform: 'uppercase',
            color: 'rgba(236,237,240,0.45)', marginBottom: 12 }}>Por quê</div>
          <div style={{ fontSize: 15.5, lineHeight: 1.6, color: 'rgba(236,237,240,0.88)',
            display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 580 }}>
            <p style={{ margin: 0 }}>
              O Nexus está em pleno milestone <strong>v4.0</strong> com motor real-time como
              próxima grande feature. <strong>Signal</strong> é o único conceito que <em>nasce
              pronto</em> para isso — Gantt por fonte, dials de confidence, sparklines de
              source health e event feed live <em>são</em> a estética dele, não enfeite.
            </p>
            <p style={{ margin: 0 }}>
              Reutiliza ~80% do Meridian (tokens, severidade, mono, hierarquia), o que respeita
              a regra dura do <code style={{ fontFamily: 'JetBrains Mono, monospace',
                background: 'rgba(142,196,212,0.10)', padding: '1px 6px', color: '#8ec4d4',
                borderRadius: 3, fontSize: 13 }}>CLAUDE.md</code>:{' '}
              <em>"brand Amber/Noir — nenhuma mudança sem aprovação explícita"</em>. Signal{' '}
              <strong>evolui</strong>: slate (não preto), teal+sand (o sand é o amber em
              repouso). Não é um rebrand, é um upgrade.
            </p>
            <p style={{ margin: 0 }}>
              <strong>Casebook</strong> é tentador — visualmente é o mais memorável e o mais
              defensável. Mas pede 3–4 semanas só de tipografia e polimento. Faz mais sentido
              como <em>segundo</em> movimento, depois do motor real-time estável: aí o
              dossiê-como-export-PDF vira o killer feature do produto pago.
            </p>
            <p style={{ margin: 0 }}>
              <strong>Lumen</strong> fica como referência para um futuro tier{' '}
              <em>Enterprise</em>: se um dia o Nexus for vendido para times de compliance,
              jurídico ou fraude corporativa, a versão Lumen é a que abre essa porta.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ padding: 18, background: 'rgba(142,196,212,0.06)',
            border: '1px solid rgba(142,196,212,0.30)' }}>
            <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
              letterSpacing: '0.18em', textTransform: 'uppercase',
              color: '#8ec4d4' }}>ship next</div>
            <div style={{ fontSize: 26, fontWeight: 600, marginTop: 6,
              fontFamily: '"Sora", system-ui, sans-serif',
              letterSpacing: '-0.025em' }}>Signal</div>
            <div style={{ fontSize: 12.5, lineHeight: 1.55, color: 'rgba(236,237,240,0.7)',
              marginTop: 8 }}>
              Real-time first. Mantém continuidade visual. ~1.5–2 semanas de trabalho de
              design, paralelizável com F2–F4 do milestone v4.0.
            </div>
          </div>
          <div style={{ padding: 18, background: 'rgba(212,184,142,0.05)',
            border: '1px solid rgba(212,184,142,0.22)' }}>
            <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
              letterSpacing: '0.18em', textTransform: 'uppercase',
              color: '#d4b88e' }}>v4.x · next horizon</div>
            <div style={{ fontSize: 22, fontWeight: 600, marginTop: 6,
              fontFamily: '"Sora", system-ui, sans-serif', fontStyle: 'italic',
              letterSpacing: '-0.02em' }}>Casebook</div>
            <div style={{ fontSize: 12, lineHeight: 1.55, color: 'rgba(236,237,240,0.6)',
              marginTop: 6 }}>
              Quando o motor real-time estiver estável: introduzir como modo "Report" /
              "Dossier export". Vira a assinatura visual do PDF e do tier pago.
            </div>
          </div>
          <div style={{ padding: 18, background: 'rgba(255,255,255,0.02)',
            border: '1px dashed rgba(255,255,255,0.10)' }}>
            <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
              letterSpacing: '0.18em', textTransform: 'uppercase',
              color: 'rgba(236,237,240,0.45)' }}>future · enterprise</div>
            <div style={{ fontSize: 18, fontWeight: 500, marginTop: 6,
              fontFamily: '"Inter Tight", system-ui, sans-serif',
              color: 'rgba(236,237,240,0.75)' }}>Lumen</div>
            <div style={{ fontSize: 11.5, lineHeight: 1.55,
              color: 'rgba(236,237,240,0.5)', marginTop: 6 }}>
              Reservado para um pivot B2B. Tema "light premium" que abre o Nexus para
              clientes corporativos sem queimar a identidade core.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function NextSteps() {
  return (
    <div style={{ width: '100%', height: '100%', background: '#f5f3ed', color: '#14110d',
      fontFamily: 'Inter, system-ui, sans-serif', padding: 36, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div>
        <div style={{ fontFamily: 'Geist Mono, monospace', fontSize: 10,
          letterSpacing: '0.18em', textTransform: 'uppercase', color: '#5897ab' }}>
          Antes de qualquer código</div>
        <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.025em',
          marginTop: 6, fontFamily: '"Inter Tight", system-ui, sans-serif' }}>
          O que eu validaria com você primeiro.
        </div>
      </div>

      <ol style={{ margin: 0, padding: 0, listStyle: 'none',
        display: 'flex', flexDirection: 'column', gap: 14 }}>
        {[
          { n: '01', t: 'Confirmar o conceito vencedor',
            d: 'Concordamos com Signal? Ou Casebook fala mais ao público alvo real (jornalistas / fraude / due diligence)? Isso muda completamente a sequência de execução.' },
          { n: '02', t: 'Definir paleta extendida',
            d: 'Signal usa teal + sand como sinal. Antes de implementar, validar contraste em todos os pares (teal sobre slate, sand sobre slate, severidade sobre slate) — WCAG AA mínimo.' },
          { n: '03', t: 'Componentizar o status pill',
            d: '8 estados (pending/running/found/likely/uncertain/not_found/blocked/error) precisam de um componente único, testável, com testes de acessibilidade. Esse é o átomo da UI real-time.' },
          { n: '04', t: 'Decidir confidence vs. risk visual',
            d: 'Confirmar a separação proposta: confidence é contínua (dial/barra), risk é categórica (4 níveis discretos). É a única forma de evitar leitura ambígua quando ambos aparecem juntos.' },
          { n: '05', t: 'Prototipar Gantt de fontes com dados reais',
            d: 'O Gantt da tela de progresso é o experimento mais arriscado. Vale fazer um proof-of-concept clicável antes de comprometer o Meridian inteiro.' },
          { n: '06', t: 'Plano de migração tokens.css',
            d: 'Signal mantém a estrutura dos tokens atuais — adiciona variáveis sem remover. Isso permite ship gradual: novos componentes em Signal, antigos continuam em Meridian até serem revisados.' },
        ].map(s => (
          <li key={s.n} style={{ display: 'grid', gridTemplateColumns: '40px 1fr',
            gap: 14, alignItems: 'baseline' }}>
            <span style={{ fontFamily: 'Geist Mono, monospace', fontSize: 11,
              color: '#5897ab', letterSpacing: '0.1em', paddingTop: 3 }}>{s.n}</span>
            <div>
              <div style={{ fontSize: 14.5, fontWeight: 600, color: '#14110d' }}>{s.t}</div>
              <div style={{ fontSize: 12.5, color: 'rgba(20,17,13,0.65)',
                marginTop: 3, lineHeight: 1.5, maxWidth: 760 }}>{s.d}</div>
            </div>
          </li>
        ))}
      </ol>

      <div style={{ marginTop: 'auto', padding: 16,
        background: 'white', border: '1px solid rgba(0,0,0,0.06)',
        borderLeft: '3px solid #5897ab', fontSize: 12.5,
        color: 'rgba(20,17,13,0.7)', lineHeight: 1.55 }}>
        <span style={{ fontWeight: 600, color: '#14110d' }}>Nada disso virou commit.</span>{' '}
        Tudo o que você vê neste documento é exploração visual em HTML estático — zero arquivo
        do repositório foi tocado, zero PR aberto, zero token alterado. O próximo passo é{' '}
        <em>seu</em>: escolher o conceito, ou pedir variações antes de qualquer linha de código.
      </div>
    </div>
  );
}

function RecommendationBoards() {
  return (
    <React.Fragment>
      <DCArtboard id="rec-matrix" label="01 · Comparison matrix" width={1180} height={680}>
        <ComparisonMatrix />
      </DCArtboard>
      <DCArtboard id="rec-pick" label="02 · Final pick" width={1180} height={760}>
        <FinalPick />
      </DCArtboard>
      <DCArtboard id="rec-next" label="03 · Next steps" width={1180} height={760}>
        <NextSteps />
      </DCArtboard>
    </React.Fragment>
  );
}

Object.assign(window, { ComparisonMatrix, FinalPick, NextSteps, RecommendationBoards });
