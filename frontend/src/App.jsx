import React, { useEffect, useState } from "react";

const BENCHMARKS = [
  {
    id: "counter",
    name: "8-bit Up-Counter with Enable & Reset",
    top: "counter",
    source: `module counter(
    input wire clk,
    input wire rst_n,
    input wire enable,
    output reg [7:0] count
);
    always @(posedge clk) begin
        if (!rst_n) begin
            count <= 8'h00;
        end else if (enable) begin
            count <= count + 1'b1;
        end
    end
endmodule`
  },
  {
    id: "counter_sync",
    name: "8-bit Counter with Synchronous Reset (Temporal SVA)",
    top: "counter_sync",
    source: `module counter_sync #(parameter WIDTH = 8) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             enable,
    output logic [WIDTH-1:0] count
);
    always_ff @(posedge clk) begin
        if (!rst_n)
            count <= '0;
        else if (enable)
            count <= count + 1'b1;
    end
endmodule`
  },
  {
    id: "comb_alu",
    name: "8-bit Combinational ALU",
    top: "comb_alu",
    source: `module comb_alu(
    input wire [7:0] a,
    input wire [7:0] b,
    input wire [1:0] op,
    output reg [7:0] result
);
    always @(*) begin
        case (op)
            2'b00: result = a + b;
            2'b01: result = a - b;
            2'b10: result = a & b;
            default: result = a ^ b;
        endcase
    end
endmodule`
  },
  {
    id: "risc_alu",
    name: "32-bit RISC ALU with Status Flags",
    top: "risc_alu",
    source: `module risc_alu(
    input wire [31:0] a,
    input wire [31:0] b,
    input wire [3:0]  alu_op,
    output reg [31:0] out,
    output wire       zero,
    output wire       negative,
    output reg        overflow,
    output reg        carry
);
    always @(*) begin
        carry = 1'b0;
        overflow = 1'b0;
        case (alu_op)
            4'b0000: {carry, out} = {1'b0, a} + {1'b0, b};
            4'b0001: {carry, out} = {1'b0, a} - {1'b0, b};
            4'b0010: out = a & b;
            4'b0011: out = a | b;
            4'b0100: out = a ^ b;
            4'b0101: out = a << b[4:0];
            4'b0110: out = a >> b[4:0];
            4'b1000: out = ($signed(a) < $signed(b)) ? 32'b1 : 32'b0;
            default: out = 32'b0;
        endcase
    end
    assign zero = (out == 32'b0);
    assign negative = out[31];
endmodule`
  },
  {
    id: "risc_regfile",
    name: "32x32-bit RISC Register File (x0=0)",
    top: "risc_regfile",
    source: `module risc_regfile(
    input wire        clk,
    input wire        rst_n,
    input wire        we,
    input wire [4:0]  waddr,
    input wire [31:0] wdata,
    input wire [4:0]  raddr1,
    output wire [31:0] rdata1,
    input wire [4:0]  raddr2,
    output wire [31:0] rdata2
);
    reg [31:0] rf [31:1];
    always @(posedge clk) begin
        if (we && (waddr != 5'b00000))
            rf[waddr] <= wdata;
    end
    assign rdata1 = (raddr1 == 5'b00000) ? 32'b0 : rf[raddr1];
    assign rdata2 = (raddr2 == 5'b00000) ? 32'b0 : rf[raddr2];
endmodule`
  },
  {
    id: "traffic_light",
    name: "Traffic Light Controller FSM",
    top: "traffic_light",
    source: `module traffic_light(
    input wire clk,
    input wire rst_n,
    output reg red,
    output reg yellow,
    output reg green
);
    localparam S_RED = 2'b00, S_GREEN = 2'b01, S_YELLOW = 2'b10;
    reg [1:0] state;
    always @(posedge clk) begin
        if (!rst_n) state <= S_RED;
        else case (state)
            S_RED: state <= S_GREEN;
            S_GREEN: state <= S_YELLOW;
            S_YELLOW: state <= S_RED;
            default: state <= S_RED;
        endcase
    end
    always @(*) begin
        red = (state == S_RED);
        green = (state == S_GREEN);
        yellow = (state == S_YELLOW);
    end
endmodule`
  },
  {
    id: "sync_fifo",
    name: "4-entry Synchronous FIFO",
    top: "sync_fifo",
    source: `module sync_fifo (
    input wire clk, rst_n, write_en, read_en,
    input wire [7:0] data_in,
    output reg [7:0] data_out,
    output wire full, empty
);
    reg [7:0] mem [0:3];
    reg [1:0] write_ptr, read_ptr;
    reg [2:0] count;
    assign full = (count == 3'd4);
    assign empty = (count == 3'd0);
    always @(posedge clk) begin
        if (!rst_n) begin
            write_ptr <= 0; read_ptr <= 0; count <= 0; data_out <= 0;
        end else begin
            if (write_en && !full) begin
                mem[write_ptr] <= data_in;
                write_ptr <= write_ptr + 1'b1;
            end
            if (read_en && !empty) begin
                data_out <= mem[read_ptr];
                read_ptr <= read_ptr + 1'b1;
            end
            case ({write_en && !full, read_en && !empty})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
        end
    end
endmodule`
  },
]; ;
const DEFAULT_SPECIFICATIONS = {
  counter: `On each rising edge of clk, if rst_n is low, count is set to zero.
When rst_n is high and enable is high, count increments by one modulo 256.
When rst_n is high and enable is low, count retains its previous value.
Reset has priority over enable.`,
  counter_sync: `On each rising edge of clk, if rst_n is low, count is set to zero.
When rst_n is high and enable is high, count increments by one modulo 2^WIDTH.
When rst_n is high and enable is low, count retains its previous value.
Reset has priority over enable.`,
  comb_alu: `When op is 2'b00, result equals a plus b, truncated to 8 bits.
When op is 2'b01, result equals a minus b, truncated to 8 bits.
When op is 2'b10, result equals the bitwise AND of a and b.
When op is 2'b11, result equals the bitwise XOR of a and b.`,
  risc_alu: `For alu_op 0000, out is the 32-bit sum of a and b.
For alu_op 0001, out is the 32-bit difference a minus b.
For alu_op 0010, out is bitwise AND; 0011 is bitwise OR; 0100 is bitwise XOR.
For alu_op 0101, out is a logical left shift by the low five bits of b; 0110 is a logical right shift.
For alu_op 1000, out is one when signed a is less than signed b, otherwise zero.
zero is asserted exactly when out is zero; negative equals out[31].`,
  risc_regfile: `Register x0 always reads as zero.
On a rising edge of clk, when we is high and waddr is not zero, the register selected by waddr is written with wdata.
Reads return the value stored at the selected address, except address zero which returns zero.`,
  traffic_light: `On a rising edge of clk, if rst_n is low, the controller enters RED.
After RED, the next state is GREEN; after GREEN, the next state is YELLOW; after YELLOW, the next state is RED.
The red, green and yellow outputs are one-hot indicators of the current state.`,
  sync_fifo: `When rst_n is low at a rising edge of clk, write_ptr, read_ptr, count and data_out are reset to zero.
A write is accepted only when write_en is high and the FIFO is not full.
An accepted write stores data_in at the current write pointer and advances write_ptr modulo four.
A read is accepted only when read_en is high and the FIFO is not empty.
An accepted read places the oldest unread entry on data_out and advances read_ptr modulo four.
When only a write is accepted, count increases by one.
When only a read is accepted, count decreases by one.
When a read and write are both accepted in the same cycle, count remains unchanged.
When neither operation is accepted, count remains unchanged.
The occupancy count always remains between zero and four inclusive.
The full output is high exactly when count equals four; otherwise it is low.
The empty output is high exactly when count equals zero; otherwise it is low.
A write attempted while full must not change FIFO contents or write_ptr.
A read attempted while empty must not change read_ptr or data_out.`

};

const resetWorkflow = () => ({
  designIR: null, propertyBatch: null, propertyValidation: null,
  verificationResult: null, activeSpecification: null, generationWarnings: [], generationAudit: null
});

export default function App() {
  const [activeTab, setActiveTab] = useState("custom");
  const [selectedExample, setSelectedExample] = useState("custom");
  const [sourceCode, setSourceCode] = useState("");
  const [additionalSources, setAdditionalSources] = useState([]);
  const [topModule, setTopModule] = useState("");
  const [specificationText, setSpecificationText] = useState("");
  const [specificationReviewer, setSpecificationReviewer] = useState("");
  const [specificationConfirmed, setSpecificationConfirmed] = useState(false);
  const [provider, setProvider] = useState("gemini");
  const [userInstructions, setUserInstructions] = useState("");
  const [proofMode, setProofMode] = useState("prove");
  const [solver, setSolver] = useState("z3");
  const [depth, setDepth] = useState(20);
  const [formalTimeout, setFormalTimeout] = useState(45);
  const [reviewerName, setReviewerName] = useState("");
  const [assumeInitialReset, setAssumeInitialReset] = useState(false);
  const [initialResetSignal, setInitialResetSignal] = useState("");
  const [initialResetPolarity, setInitialResetPolarity] = useState("active_low");
  const [initialResetRationale, setInitialResetRationale] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [workflow, setWorkflow] = useState(resetWorkflow);
  const [savedRuns, setSavedRuns] = useState([]);
  const [backendAlive, setBackendAlive] = useState(false);
  const [busy, setBusy] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  const { designIR, propertyBatch, propertyValidation, verificationResult, activeSpecification } = workflow;
  const updateWorkflow = (patch) => setWorkflow((old) => ({ ...old, ...patch }));
  const clearDownstream = () => setWorkflow(resetWorkflow());

  useEffect(() => {
    fetch("/api/health").then(r => r.json()).then(d => setBackendAlive(d.status === "ok")).catch(() => setBackendAlive(false));
    refreshSavedRuns();
  }, []);

  async function refreshSavedRuns() {
    try {
      const r = await fetch("/api/formal/runs?limit=50");
      if (r.ok) { const d = await r.json(); setSavedRuns(d.runs || []); }
    } catch { /* history is supplementary */ }
  }

  function loadExample(id) {
    if (id === "custom") {
      setSelectedExample("custom");
      setSourceCode("");
      setTopModule("");
      setSpecificationText("");
    } else {
      const item = BENCHMARKS.find(x => x.id === id);
      if (!item) return;
      setSelectedExample(id);
      setSourceCode(item.source);
      setTopModule(item.top);
      setSpecificationText(DEFAULT_SPECIFICATIONS[id] || "");
    }
    setSpecificationReviewer("");
    setSpecificationConfirmed(false);
    setUserInstructions("");
    clearDownstream();
    setStatusMessage(id === "custom" ? "Custom RTL workspace ready." : `${BENCHMARKS.find(x => x.id === id)?.name || "Example"} loaded.`);
  }

  async function addAdditionalSources(event) {
    const files = Array.from(event.target.files || []);
    const loaded = await Promise.all(files.map(async (file, index) => ({
      name: `additional_${index + 1}_${file.name.replace(/[^A-Za-z0-9_.-]/g, "_")}`,
      content: await file.text()
    })));
    setAdditionalSources(previous => {
      const byName = new Map(previous.map(item => [item.name, item]));
      loaded.forEach(item => byName.set(item.name, item));
      return Array.from(byName.values());
    });
    updateWorkflow({ designIR: null, propertyBatch: null, propertyValidation: null, verificationResult: null, activeSpecification: null });
    event.target.value = "";
  }

  async function analyzeDesign() {
    if (!sourceCode.trim() || !topModule.trim()) throw new Error("Provide RTL source and a top-module name first.");
    setBusy("analyze");
    setStatusMessage("Elaborating RTL and extracting design structure…");
    try {
      const fd = new FormData();
      fd.append("top_module", topModule.trim());
      fd.append("files", new Blob([sourceCode], { type: "text/plain" }), `${topModule.trim()}.sv`);
      additionalSources.forEach(item => fd.append("files", new Blob([item.content], { type: "text/plain" }), item.name));
      const r = await fetch("/api/designs/analyze", { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.text()).slice(0, 900));
      const d = await r.json();
      const ir = d.design || d.design_ir || d;
      updateWorkflow({ designIR: ir, propertyBatch: null, propertyValidation: null, verificationResult: null, activeSpecification: null });
      setStatusMessage(`RTL analysed successfully · ${ir.top_module}`);
      return ir;
    } finally { setBusy(""); }
  }

  async function generateProperties() {
    setBusy("generate");
    try {
      const ir = designIR || await analyzeDesign();
      const lines = specificationText.split("\n").map(x => x.trim().replace(/^[-*•]\s*/, "")).filter(Boolean);
      if (!lines.length) throw new Error("Add at least one independent behavioural requirement.");
      if (!specificationReviewer.trim()) throw new Error("Enter the specification reviewer before generation.");
      if (!specificationConfirmed) throw new Error("Confirm that the requirements are the intended independent behavioural specification before approval.");
      const draft = {
        specification_id: `${topModule}-spec-v1`, version: "1.0",
        title: `${topModule} behavioural specification`, design_top: topModule,
        description: "User-reviewed requirements define intended behaviour independently of the RTL implementation.",
        requirements: lines.map((statement, i) => ({ requirement_id: `REQ-${String(i + 1).padStart(2, "0")}`, statement, source: "user" })),
        approval_status: "draft"
      };
      const check = await fetch("/api/specifications/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) });
      if (!check.ok) throw new Error(`Specification validation failed: ${(await check.text()).slice(0, 700)}`);
      const validated = await check.json();
      const approval = await fetch("/api/specifications/approve", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specification: validated.specification, reviewer: specificationReviewer.trim(), reviewed_content_hash: validated.sha256 })
      });
      if (!approval.ok) throw new Error(`Specification approval failed: ${(await approval.text()).slice(0, 700)}`);
      const spec = (await approval.json()).specification;
      const r = await fetch("/api/properties/generate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ design: ir, specification: spec, target_module: topModule, source_code: [sourceCode, ...additionalSources.map(item => `// Additional source: ${item.name}\n${item.content}`)].join("\n"), provider, max_properties: 20, focus_areas: userInstructions ? [userInstructions] : [] })
      });
      if (!r.ok) {
        let detail = await r.text();
        try { const j = JSON.parse(detail); detail = j.detail || detail; } catch {}
        throw new Error(`Property generation failed (${r.status}): ${String(detail).slice(0, 900)}`);
      }
      const data = await r.json();
      updateWorkflow({ activeSpecification: spec, propertyBatch: data.batch, propertyValidation: data.validation || null, verificationResult: null, generationWarnings: data.warnings || [], generationAudit: data.generation_audit || null });
      setStatusMessage(`${data.batch.properties.length} candidate properties generated. Review them before formal verification.`);
    } catch (e) { setStatusMessage(e.message); }
    finally { setBusy(""); }
  }

  async function runFormal() {
    if (!propertyBatch || !activeSpecification || !designIR) return;
    setBusy("verify");
    setStatusMessage(`Verifying ${propertyBatch.properties.length} properties with up to 3 parallel workers · ${formalTimeout}s per property maximum.`);
    try {
      const resetContract = assumeInitialReset ? {
        signal: initialResetSignal,
        polarity: initialResetPolarity,
        reviewed_by: reviewerName.trim(),
        rationale: initialResetRationale.trim()
      } : null;
      if (assumeInitialReset && (!resetContract.signal || !resetContract.reviewed_by || resetContract.rationale.length < 8)) {
        throw new Error("To apply an initial-reset assumption, select a reset signal and provide reviewer identity plus a rationale of at least 8 characters.");
      }
      const r = await fetch("/api/formal/verify", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          design_ir: designIR, verilog_sources: Object.fromEntries([
            [`${topModule}.sv`, sourceCode],
            ...additionalSources.map(item => [item.name, item.content])
          ]),
          property_batch: propertyBatch, specification: activeSpecification, generation_audit: workflow.generationAudit || null, top_module: topModule,
          proof_mode: proofMode, depth: Number(depth) || 20, solver, timeout_seconds: Number(formalTimeout), check_vacuity: false,
          initial_reset_contract: resetContract
        })
      });
      if (!r.ok) throw new Error(`Formal verification failed (${r.status}): ${(await r.text()).slice(0, 900)}`);
      const data = await r.json();
      updateWorkflow({ verificationResult: data });
      await refreshSavedRuns();
      setStatusMessage(`Verification finished · ${data.overall_status.toUpperCase()}`);
    } catch (e) { setStatusMessage(e.message); }
    finally { setBusy(""); }
  }

  async function loadRun(id) {
    try {
      const r = await fetch(`/api/formal/runs/${encodeURIComponent(id)}`);
      if (!r.ok) throw new Error("Could not load this experiment.");
      const d = await r.json();
      const savedSources = d.verilog_sources || {};
      const sourceEntries = Object.entries(savedSources);
      const firstSource = sourceEntries[0]?.[1] || "";
      setSourceCode(firstSource);
      setAdditionalSources(sourceEntries.slice(1).map(([name, content]) => ({ name, content })));
      setTopModule(d.design_top || d.design_ir?.top_module || "");
      setSelectedExample("custom");
      const savedRequirements = d.behavioural_specification?.requirements || [];
      setSpecificationText(savedRequirements.map(x => x.statement).join("\n"));
      setSpecificationReviewer(d.behavioural_specification?.approved_by || "");
      setSpecificationConfirmed(false);
      const restoredSpec = d.behavioural_specification;
      const specIsHashBound = !!restoredSpec?.approved_content_hash && restoredSpec.approved_content_hash === d.specification_sha256;
      updateWorkflow({ designIR: d.design_ir || null, verificationResult: d.verification, propertyBatch: d.property_batch || null, activeSpecification: specIsHashBound ? restoredSpec : null, propertyValidation: null, generationAudit: d.generation_audit || null });
      setActiveTab("custom");
      setStatusMessage(restoredSpec && !specIsHashBound
        ? `Loaded historical experiment ${id}. Its specification predates content-bound approval; review and approve the requirements again before starting a new formal run.`
        : `Loaded experiment ${id}.`);
    } catch (e) { setStatusMessage(e.message); }
  }

  function changeSource(value) { setSourceCode(value); if (selectedExample !== "custom") setSelectedExample("custom"); clearDownstream(); }
  function changeTop(value) { setTopModule(value); clearDownstream(); }
  function changeSpec(value) { setSpecificationText(value); setSpecificationConfirmed(false); updateWorkflow({ activeSpecification: null, propertyBatch: null, propertyValidation: null, verificationResult: null, generationAudit: null }); }

  const moduleIR = designIR?.modules?.find(m => m.name === topModule) || designIR?.modules?.[0];
  const results = verificationResult?.results || [];
  const coveredRequirementIds = new Set((propertyBatch?.properties || []).flatMap(p => p.requirement_ids || []));
  const uncoveredRequirementIds = (activeSpecification?.requirements || []).map(r => r.requirement_id).filter(id => !coveredRequirementIds.has(id));
  const statusClass = (s) => String(s || "unknown").toLowerCase();
  const historyCount = savedRuns.length;

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#" onClick={e => e.preventDefault()}>
          <span className="brand-symbol">F</span><span>FORMAL<span className="brand-light">LAB</span></span>
        </a>
        <nav className="main-nav" aria-label="Main navigation">
          <button className={activeTab === "custom" ? "nav-link active" : "nav-link"} onClick={() => setActiveTab("custom")}>Custom RTL</button>
          <button className={activeTab === "examples" ? "nav-link active" : "nav-link"} onClick={() => setActiveTab("examples")}>Examples</button>
          <button className={activeTab === "history" ? "nav-link active" : "nav-link"} onClick={() => setActiveTab("history")}>Experiment history <span className="nav-count">{historyCount}</span></button>
        </nav>
        <div className="connection"><span className={backendAlive ? "connection-dot online" : "connection-dot"} />{backendAlive ? "Backend connected" : "Backend offline"}</div>
      </header>

      <main className="page-content">
        {activeTab === "custom" ? <>
          <section className="hero">
            <div className="eyebrow">RTL · SPECIFICATION · FORMAL PROOF</div>
            <h1>Verify what your hardware<br/><span>is supposed to do.</span></h1>
            <p>Generate candidate properties from an independent behavioural specification, then validate them against your RTL using classical formal verification.</p>
          </section>

          <div className="workspace-layout">
            <section className="workflow">
              <div className="section-heading"><div><span className="section-kicker">01 / DESIGN INPUT</span><h2>Start with your RTL</h2></div><span className="quiet-tag">Custom by default</span></div>
              <div className="panel">
                <div className="field-row preset-row">
                  <label className="field grow"><span>Design source</span>
                    <select value={selectedExample} onChange={e => loadExample(e.target.value)}>
                      <option value="custom">Custom RTL · enter your own design</option>
                      <optgroup label="Built-in examples">{BENCHMARKS.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</optgroup>
                    </select>
                  </label>
                </div>
                <div className="field-row">
                  <label className="field grow"><span>Top module</span><input value={topModule} onChange={e => changeTop(e.target.value)} placeholder="e.g. sync_fifo" /></label>
                  <label className="field"><span>RTL language</span><input value="Verilog / SystemVerilog" readOnly /></label>
                </div>
                <label className="field"><span>RTL source code</span><textarea className="code-input" rows={12} value={sourceCode} onChange={e => changeSource(e.target.value)} placeholder={"Paste your Verilog/SystemVerilog RTL here…"} spellCheck="false" /></label>
                <div className="additional-sources">
                  <label className="field"><span>Additional RTL files <small>Optional · for multi-module designs</small></span><input type="file" accept=".v,.sv" multiple onChange={addAdditionalSources} /></label>
                  {additionalSources.length > 0 && <p className="note-line">{additionalSources.length} additional source file(s): {additionalSources.map(x => x.name).join(", ")}</p>}
                </div>
                <div className="action-row"><button className="button primary" onClick={() => analyzeDesign().catch(e => setStatusMessage(e.message))} disabled={!!busy || !sourceCode.trim() || !topModule.trim()}>{busy === "analyze" ? "Analysing…" : "Analyse RTL"} <span>→</span></button>{designIR && <span className="success-note">Design structure extracted</span>}</div>
                {designIR && <div className="design-facts"><div><strong>{moduleIR?.ports?.length || 0}</strong><span>Ports</span></div><div><strong>{moduleIR?.summary?.sequential_cell_count || 0}</strong><span>Sequential cells</span></div><div><strong>{moduleIR?.summary?.memory_cell_count || 0}</strong><span>Memory cells</span></div><div><strong>{moduleIR?.clock_candidates?.map(c => c.name || c.signal).filter(Boolean).join(", ") || "—"}</strong><span>Clock candidate(s)</span></div></div>}
              </div>

              <div className="section-heading second"><div><span className="section-kicker">02 / INTENDED BEHAVIOUR</span><h2>Define the specification</h2></div></div>
              <div className="panel">
                <p className="panel-intro">Describe the behaviour the hardware must satisfy. These requirements are the source of truth; the RTL is the implementation being checked.</p>
                <label className="field"><span>Functional requirements <small>One requirement per line</small></span><textarea className="spec-input" rows={8} value={specificationText} onChange={e => changeSpec(e.target.value)} placeholder={"When reset is asserted, all pointers and occupancy return to zero.\nA write is accepted only when the FIFO is not full.\n…"} /></label>
                <div className="field-row">
                  <label className="field grow"><span>Specification reviewed by</span><input value={specificationReviewer} onChange={e => setSpecificationReviewer(e.target.value)} placeholder="Reviewer name / ID" /></label>
                </div>
                <label className="review-confirm"><input type="checkbox" checked={specificationConfirmed} onChange={e => setSpecificationConfirmed(e.target.checked)} /><span>I have reviewed these requirements and confirm they independently describe the intended behaviour, rather than merely restating the current RTL.</span></label>
                <details className="advanced">
                  <summary>Generation settings <span>Optional</span></summary>
                  <div className="advanced-content">
                    <div className="field-row">
                      <label className="field grow"><span>LLM provider</span><select value={provider} onChange={e => setProvider(e.target.value)}><option value="gemini">Google Gemini</option><option value="openai">OpenAI</option><option value="mock">Mock · testing only</option></select></label>
                    </div>
                    <label className="field"><span>Generation focus <small>Optional</small></span><input value={userInstructions} onChange={e => setUserInstructions(e.target.value)} placeholder="e.g. focus on FIFO overflow and underflow behaviour" /></label>
                  </div>
                </details>
                <div className="action-row"><button className="button primary" onClick={generateProperties} disabled={!!busy || !sourceCode.trim() || !specificationText.trim() || !specificationReviewer.trim() || !specificationConfirmed}>{busy === "generate" ? "Generating…" : "Approve specification & generate properties"} <span>→</span></button></div>
              </div>

              {propertyBatch && <><div className="section-heading second"><div><span className="section-kicker">03 / CANDIDATE REVIEW</span><h2>Review generated properties</h2></div><span className="quiet-tag">{propertyBatch.properties.length} candidates</span></div>
                <div className="panel">
                  <div className="coverage-summary"><strong>Requirement coverage: {coveredRequirementIds.size} / {activeSpecification?.requirements?.length || 0}</strong>{uncoveredRequirementIds.length > 0 && <p className="note-line">No candidate references: {uncoveredRequirementIds.join(", ")}. A reference is traceability metadata, not proof of semantic coverage.</p>}{(workflow.generationWarnings || []).map((w, i) => <p className="note-line" key={i}>{w}</p>)}</div>
                  <div className="property-stack">{propertyBatch.properties.map((p, i) => <article className="property-card" key={p.property_id}>
                    <div className="property-head"><div><h3>{p.name}</h3><p>{p.description}</p></div><span className="mini-tag">{p.category}</span></div>
                    <pre>{p.expression}</pre>
                    <div className="property-meta"><span>Requirements: {(p.requirement_ids || []).join(", ") || "Unmapped"}</span><span>{propertyValidation?.results?.find(x => x.property_id === p.property_id)?.design_valid ? "Design-valid" : "Review validation"}</span></div>
                  </article>)}</div>
                  {propertyValidation?.results?.some(x => x.issues?.length) && <details className="advanced"><summary>Structural validation notes</summary>{propertyValidation.results.filter(x => x.issues?.length).map(x => <p key={x.property_id} className="note-line"><strong>{x.property_id}:</strong> {x.issues.map(i => i.message).join("; ")}</p>)}</details>}
                </div>
              </>}

              {propertyBatch && <><div className="section-heading second"><div><span className="section-kicker">04 / FORMAL ENGINE</span><h2>Run formal verification</h2></div></div>
                <div className="panel">
                  <div className="field-row">
                    <label className="field grow"><span>Proof strategy</span><select value={proofMode} onChange={e => setProofMode(e.target.value)}><option value="prove">k-Induction · unbounded proof</option><option value="bmc">Bounded model checking</option></select></label>
                    <label className="field grow"><span>SMT solver</span><select value={solver} onChange={e => setSolver(e.target.value)}><option value="z3">Z3</option><option value="boolector">Boolector</option><option value="yices">Yices</option></select></label>
                    <label className="field"><span>Timeout / property</span><select value={formalTimeout} onChange={e => setFormalTimeout(Number(e.target.value))}>{[15,30,45,60,90,120].map(n => <option key={n} value={n}>{n}s</option>)}</select></label>
                  </div>
                  {proofMode === "bmc" && <label className="field short-field"><span>Bound depth (cycles)</span><input type="number" min="1" max="200" value={depth} onChange={e => setDepth(e.target.value)} /></label>}
                  <details className="advanced"><summary>Initial reset environment <span>Optional · reviewer-approved</span></summary><div className="advanced-content">
                    <label className="review-confirm"><input type="checkbox" checked={assumeInitialReset} onChange={e => setAssumeInitialReset(e.target.checked)} /><span>Assume the selected reset is active on the first clock edge, then allow it to change freely.</span></label>
                    {assumeInitialReset && <><label className="field"><span>Reset signal</span><select value={initialResetSignal} onChange={e => setInitialResetSignal(e.target.value)}><option value="">Select structurally detected reset</option>{(designIR?.modules?.find(m => m.name === topModule)?.reset_candidates || []).map((r,i) => <option key={`${r.signal || r.name}-${i}`} value={r.signal || r.name}>{r.signal || r.name}</option>)}</select></label>
                    <label className="field"><span>Active polarity</span><select value={initialResetPolarity} onChange={e => setInitialResetPolarity(e.target.value)}><option value="active_low">Active low</option><option value="active_high">Active high</option></select></label>
                    <label className="field"><span>Reviewed by</span><input value={reviewerName} onChange={e => setReviewerName(e.target.value)} placeholder="Reviewer name / ID" /></label>
                    <label className="field"><span>Why is this environment condition valid?</span><textarea value={initialResetRationale} onChange={e => setInitialResetRationale(e.target.value)} placeholder="Describe the system-level reset guarantee (minimum 8 characters)." /></label></>}
                    <p className="note-line">This is an explicit assumption about the environment, not a property of the RTL. It affects every property in this verification run and is saved in the experiment record.</p>
                  </div></details>
                  <div className="action-row"><button className="button green" onClick={runFormal} disabled={!!busy || !propertyBatch}>{busy === "verify" ? "Running formal engine…" : "Verify properties"} <span>→</span></button></div>
                </div>
              </>}
            </section>

            <aside className="insights">
              <div className="aside-sticky">
                <div className="aside-title"><span className="section-kicker">LIVE WORKSPACE</span><h2>Run overview</h2></div>
                <div className="overview-card">
                  <div className="overview-row"><span>Design</span><strong>{topModule || "Not provided"}</strong></div>
                  <div className="overview-row"><span>RTL analysis</span><strong className={designIR ? "text-green" : ""}>{designIR ? "Complete" : "Pending"}</strong></div>
                  <div className="overview-row"><span>Specification</span><strong className={activeSpecification ? "text-green" : ""}>{activeSpecification ? "Approved" : "Not submitted"}</strong></div>
                  <div className="overview-row"><span>Properties</span><strong>{propertyBatch?.properties?.length || "—"}</strong></div>
                  <div className="overview-row"><span>Formal run</span><strong>{verificationResult?.overall_status?.toUpperCase() || "Pending"}</strong></div>
                </div>
                {statusMessage && <div className="status-message"><span className="status-pulse" />{statusMessage}</div>}
                {verificationResult && <div className="result-card">
                  <div className="result-top"><span className="section-kicker">FORMAL RESULT</span><span className={`verdict ${statusClass(verificationResult.overall_status)}`}>{verificationResult.overall_status?.toUpperCase()}</span></div>
                  <div className="result-counts"><div><strong>{verificationResult.summary?.pass || 0}</strong><span>Pass</span></div><div><strong>{verificationResult.summary?.fail || 0}</strong><span>Fail</span></div><div><strong>{verificationResult.summary?.invalid || 0}</strong><span>Invalid</span></div><div><strong>{verificationResult.summary?.unknown || 0}</strong><span>Unknown</span></div></div>
                  {results.map(r => <div className="result-item" key={r.property_id}><span>{r.name}</span><span className={`result-status ${statusClass(r.status)}`}>{r.status.toUpperCase()}</span>{r.counterexample_vcd && <a className="trace-link" href={r.counterexample_vcd} target="_blank" rel="noreferrer">Download counterexample trace</a>}{r.counterexample_trace?.signals?.length > 0 && <details><summary>Counterexample signal values</summary><div className="trace-table-wrap"><table className="trace-table"><thead><tr><th>Step</th>{r.counterexample_trace.signals.map(sig => <th key={sig.id}>{sig.name}</th>)}</tr></thead><tbody>{r.counterexample_trace.frames.map((frame, i) => <tr key={`${frame.time}-${i}`}><td>{frame.time}</td>{r.counterexample_trace.signals.map(sig => <td key={sig.id}>{frame.values[sig.id] ?? "—"}</td>)}</tr>)}</tbody></table></div></details>}{r.log_snippet && <details><summary>Details</summary><pre>{r.log_snippet}</pre></details>}</div>)}
                  <details className="advanced"><summary>Verification notes and evidence</summary><p className="note-line">Engine: {results[0]?.proof_engine || "sby_smtbmc"} · Mode: {proofMode} · Runtime: {Number(verificationResult.execution_time_seconds || 0).toFixed(2)}s</p>{(verificationResult.warnings || []).map((w,i) => <p className="note-line" key={i}>{w}</p>)}</details>
                </div>}
                <div className="integrity-note"><strong>Proof integrity</strong><p>PASS means the encoded property was proven for this RTL snapshot and formal environment. It does not establish that the specification is complete or correct.</p></div>
              </div>
            </aside>
          </div>
        </> : activeTab === "examples" ? <section className="history-page examples-page">
          <div className="section-kicker">START FROM A REFERENCE DESIGN</div><h1>Built-in examples</h1><p>Load a known RTL example and its independent behavioural requirements into the custom workspace. You can edit both before analysis.</p>
          <div className="example-grid">{BENCHMARKS.map(example => <article className="example-card" key={example.id}><span className="mini-tag">REFERENCE DESIGN</span><h2>{example.name}</h2><p>Top module: <code>{example.top}</code></p><button className="button primary" onClick={() => { loadExample(example.id); setActiveTab("custom"); }}>Load example <span>→</span></button></article>)}</div>
        </section> : <section className="history-page">
          <div className="section-kicker">WORKSPACE ARCHIVE</div><h1>Experiment history</h1><p>Saved formal runs, kept out of the main workflow until you need them. Selecting a run restores its RTL, specification, properties and results.</p>
          {savedRuns.length ? <div className="history-list">{savedRuns.map((run, i) => <button className="history-item" key={run.run_id || run.id || i} onClick={() => loadRun(run.run_id || run.id)}>
            <div><strong>{run.design_top || run.top_module || "RTL design"}</strong><span>{run.run_id || run.id || "Saved experiment"}</span></div><span className={`verdict ${statusClass(run.overall_status || run.status)}`}>{(run.overall_status || run.status || "saved").toUpperCase()}</span><span className="history-arrow">→</span>
          </button>)}</div> : <div className="empty-history"><strong>No saved experiments yet</strong><p>Completed formal runs will appear here.</p></div>}
        </section>}
      </main>
      <footer className="site-footer"><span>FORMALLAB · BUILD 15.3</span><span>LLM-assisted property generation · Classical formal verification</span></footer>
    </div>
  );
}
