// Entry point — composes all sections into the DesignCanvas.
const { DesignCanvas, DCSection, DCArtboard } = window;

function App() {
  return (
    <DesignCanvas>
      <DCSection id="intro" title="Nexus OSINT · Visual Direction Exploration"
        subtitle="Diagnostic of current Meridian + brief for three new concepts. No code, no commits — pure exploration.">
        {window.IntroBoards()}
      </DCSection>

      <DCSection id="lumen" title="Concept 1 · Lumen"
        subtitle="SaaS premium · light · Stripe/Linear-level polish · sage + ink on bone">
        {window.LumenBoards()}
      </DCSection>

      <DCSection id="casebook" title="Concept 2 · Casebook"
        subtitle="Investigation workspace · paper tones · serif display · the file folder as metaphor">
        {window.CasebookBoards()}
      </DCSection>

      <DCSection id="signal" title="Concept 3 · Signal"
        subtitle="Analyst console · evolved Meridian · slate not black · calm density, no cyberpunk">
        {window.SignalBoards()}
      </DCSection>

      <DCSection id="signal-v2" title="Signal v2 · Refined"
        subtitle="Five targeted refinements: dual-mode view, Gantt as hero, categorized findings, Casebook-styled exports.">
        {window.SignalV2Boards()}
      </DCSection>

      <DCSection id="recommendation" title="Comparison & Final Recommendation"
        subtitle="Where each concept wins, where each risks falling flat, and the one I'd ship.">
        {window.RecommendationBoards()}
      </DCSection>
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
