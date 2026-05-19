// Shared helpers used across all concept boards.

// Striped placeholder for any image / avatar / map area.
// Renders a diagonally-striped block with a monospace explainer.
function Placeholder({ label, w, h, tone = 'light', radius = 6, style }) {
  const bg = tone === 'dark' ? '#1a1f2a' : tone === 'paper' ? '#e9e0cf' : '#e6e3dc';
  const stripe = tone === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.05)';
  const fg = tone === 'dark' ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.40)';
  return (
    <div style={{
      width: w, height: h, borderRadius: radius,
      background: `repeating-linear-gradient(135deg, ${bg} 0 8px, ${stripe} 8px 16px)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: fg, fontFamily: 'Geist Mono, JetBrains Mono, monospace',
      fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase',
      ...style
    }}>{label}</div>
  );
}

// Inline color swatch for palette displays.
function Swatch({ hex, name, role, dark }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{
        width: '100%', height: 64, borderRadius: 4,
        background: hex,
        border: dark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.06)',
      }} />
      <div style={{ fontSize: 10, fontFamily: 'Geist Mono, monospace',
        textTransform: 'uppercase', letterSpacing: '0.06em',
        color: dark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)' }}>{role}</div>
      <div style={{ fontSize: 12, fontWeight: 600,
        color: dark ? 'rgba(255,255,255,0.92)' : 'rgba(0,0,0,0.85)' }}>{name}</div>
      <div style={{ fontSize: 10, fontFamily: 'Geist Mono, monospace',
        color: dark ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.35)' }}>{hex}</div>
    </div>
  );
}

// Pros / Cons / Risks card for each concept.
function ProsConsCard({ title, accent, pros, cons, riskGeneric, riskImpl, recommendation, dark }) {
  const fg = dark ? '#e8e8eb' : '#181612';
  const fgMute = dark ? 'rgba(232,232,235,0.55)' : 'rgba(24,22,18,0.55)';
  const fgDim = dark ? 'rgba(232,232,235,0.35)' : 'rgba(24,22,18,0.35)';
  const bg = dark ? '#14181f' : '#fbfaf6';
  const line = dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
  return (
    <div style={{ width: '100%', height: '100%', background: bg, color: fg,
      fontFamily: 'Inter, system-ui, sans-serif', padding: 40, boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <div style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase',
          color: accent, fontFamily: 'Geist Mono, monospace', marginBottom: 8 }}>Trade-offs</div>
        <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em' }}>{title}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div>
          <div style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase',
            color: fgDim, fontFamily: 'Geist Mono, monospace', marginBottom: 10 }}>Pros</div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {pros.map((p, i) => (
              <li key={i} style={{ fontSize: 13, lineHeight: 1.45, color: fg,
                paddingLeft: 14, position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 6, width: 6, height: 6,
                  borderRadius: 99, background: accent }} />{p}</li>
            ))}
          </ul>
        </div>
        <div>
          <div style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase',
            color: fgDim, fontFamily: 'Geist Mono, monospace', marginBottom: 10 }}>Cons</div>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {cons.map((p, i) => (
              <li key={i} style={{ fontSize: 13, lineHeight: 1.45, color: fgMute,
                paddingLeft: 14, position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 6, width: 6, height: 6,
                  borderRadius: 99, background: fgDim }} />{p}</li>
            ))}
          </ul>
        </div>
      </div>

      <div style={{ borderTop: `1px solid ${line}`, paddingTop: 18, display: 'grid',
        gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div>
          <div style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase',
            color: fgDim, fontFamily: 'Geist Mono, monospace', marginBottom: 6 }}>Risco · "parece genérico"</div>
          <div style={{ fontSize: 13, color: fg, lineHeight: 1.45 }}>{riskGeneric}</div>
        </div>
        <div>
          <div style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase',
            color: fgDim, fontFamily: 'Geist Mono, monospace', marginBottom: 6 }}>Risco · implementação</div>
          <div style={{ fontSize: 13, color: fg, lineHeight: 1.45 }}>{riskImpl}</div>
        </div>
      </div>

      <div style={{ marginTop: 'auto', padding: 16, borderRadius: 8,
        background: dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)',
        borderLeft: `3px solid ${accent}` }}>
        <div style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase',
          color: accent, fontFamily: 'Geist Mono, monospace', marginBottom: 6 }}>Recomendação</div>
        <div style={{ fontSize: 13, color: fg, lineHeight: 1.5 }}>{recommendation}</div>
      </div>
    </div>
  );
}

Object.assign(window, { Placeholder, Swatch, ProsConsCard });
