const stages = [
  "RTL ingestion", "Design analysis and IR", "Candidate property generation",
  "Property validation", "Formal verification", "Evidence and report"
];

export default function App() {
  return <main className="shell">
    <header className="topbar">
      <div className="brand-mark">FV</div>
      <div><p className="eyebrow">RESEARCH WORKBENCH</p><h1>Formal Verification Studio</h1></div>
      <span className="status">FOUNDATION BUILD</span>
    </header>
    <section className="intro">
      <p className="eyebrow">LLM-ASSISTED RTL VERIFICATION</p>
      <h2>From RTL to checkable properties.</h2>
      <p className="lead">A research framework in which an LLM proposes candidate properties and classical formal methods determine whether they hold.</p>
    </section>
    <section className="panel">
      <div className="panel-heading"><div><p className="eyebrow">PIPELINE OVERVIEW</p><h3>Verification workflow</h3></div><span className="muted">Planned stages</span></div>
      <ol className="pipeline">{stages.map((stage, i) => <li key={stage}>
        <span className="stage-number">{String(i + 1).padStart(2, "0")}</span>
        <span>{stage}</span><span className="stage-state">NOT IMPLEMENTED</span>
      </li>)}</ol>
    </section>
    <footer><span>Build 0.1.0 · Project skeleton</span><span>The formal engine remains the authority for proof results.</span></footer>
  </main>;
}
