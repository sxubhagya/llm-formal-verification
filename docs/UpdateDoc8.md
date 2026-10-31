# UpdateDoc8 — Formal Verification Integration with SymbiYosys (SBY) & Benchmark Suite Expansion

## Purpose

Implement Build 8 according to the roadmap in `Soubhagya_Important.md` and the IEEE System Design Document:
- Connect candidate formal properties directly to classical formal verification tools (SymbiYosys / SBY).
- Support unbounded $k$-induction proofs (`prove` mode) and Bounded Model Checking (`bmc` mode).
- Translate high-level candidate properties and SVA constructs into procedural Verilog monitor checkers using `$past()`, `$stable()`, `assert()`, `assume()`, and `cover()` without requiring commercial Verific licenses.
- Implement an automated non-vacuity guard via antecedent coverage (`cover(antecedent)`).
- Provide cross-platform formal execution (native Linux/macOS and Windows-to-Ubuntu-WSL2).
- Classify formal outcomes into `PASS`, `FAIL` (distinguishing basecase vs. inductive step failure), `UNKNOWN`, `TIMEOUT`, and `INVALID`, extracting counterexample VCD traces (`trace.vcd`).
- Expand the RTL benchmark suite with 5 core RISC processor building blocks (ALU with flags, Register File, Decoder/Control FSM, Branch/PC Unit, and Hazard Unit).
- Expose `POST /api/formal/verify` endpoint and automated unit test suite (39 tests passing).

---

## Changes Implemented

### 1. Formal Verification Models (`backend/app/models/formal_models.py`)
- `ProofMode`: `prove` (unbounded $k$-induction), `bmc` (bounded model checking), `cover` (reachability).
- `SolverEngine`: `z3`, `boolector`, `yices`.
- `VacuityStatus`: `non_vacuous`, `vacuous`, `not_checked`.
- `PropertyVerificationResult`: Detailed per-property outcome capturing status, engine, proof mode, depth, vacuity status, failure phase (`base`, `step`, or `bmc`), counterexample VCD trace path, execution time, and log snippet.
- `FormalVerificationRequest` & `FormalVerificationResponse`: Clean API payload models with top-level summary metrics.

### 2. Procedural Verilog Checker Synthesizer (`backend/app/services/formal/checker_synthesizer.py`)
- `CheckerSynthesizer`:
  - Translates `CandidateProperty` batches into a self-contained formal monitor module `formal_<top_module>`.
  - DUT instantiation preserves pristine RTL without source code modification.
  - SVA / Boolean implication parsing: splits `|->`, `|=>`, and `->` into antecedent and consequent.
  - Generates non-vacuity witness covers: `cover(antecedent)`.
  - Generates procedural assertions: `if (antecedent) assert(consequent);`.
  - Implements `f_past_valid` register to safely guard `$past()` and temporal checks across cycle 0.
  - Injects environment assumptions `assume(...)` from proposed/accepted property assumptions.
  - Handles both clocked sequential modules and combinational designs (`always @(*)`).

### 3. SBY Task Generator & Runner (`backend/app/services/formal/sby_runner.py`)
- `SBYRunner`:
  - Generates `.sby` task files configuring options (`mode`, `depth`), engines (`smtbmc <solver>`), scripts (`read -formal -sv`, `prep -top`), and files.
  - Cross-platform invocation: native on Linux/macOS or `wsl.exe -d Ubuntu -- sby -f ...` on Windows with forward-slash drive path conversion.
  - Executes in isolated temporary scratch directories to prevent file collision.
  - Parses SBY execution logs and engine outputs:
    - Verdict: `PASS`, `FAIL`, `UNKNOWN`, `TIMEOUT`, `INVALID`.
    - Mathematical failure phase analysis: distinguishes base-case falsification from inductive-step failure in $k$-induction.
    - Counterexample trace locator: identifies `engine_0/trace.vcd` for counterexamples and witness traces.
  - Built-in deterministic mock/offline execution mode when SBY is not locally installed on the host.

### 4. Verification Orchestration Service (`backend/app/services/formal/verification_service.py`)
- `FormalVerificationService`:
  - First validates candidate properties against `DesignIR` using `validate_property_batch()`.
  - Flags structurally invalid properties (e.g. phantom signal references, width mismatches) as `INVALID` with diagnostic messages without wasting formal solver cycles.
  - Synthesizes the procedural checker wrapper.
  - Bundles original RTL files and synthesized checker into the SBY work directory.
  - Runs SBY runner and compiles per-property verdicts.

### 5. API Endpoint (`backend/app/api/formal.py`)
- Added `POST /api/formal/verify`:
  - Registered in `backend/app/main.py`.
  - Accepts `FormalVerificationRequest` and returns `FormalVerificationResponse`.

### 6. Benchmark Suite Expansion (`rtl/examples/`)
Implemented 5 core RISC processor building blocks:
1. **`rtl/examples/risc_alu/risc_alu.sv`**: 32-bit ALU supporting ADD, SUB, AND, OR, XOR, SLL, SRL, SRA, SLT, SLTU, with zero, negative, overflow, and carry status flags.
2. **`rtl/examples/risc_regfile/risc_regfile.sv`**: 32-register x 32-bit dual-read, single-write register file with hardwired `x0` zero register.
3. **`rtl/examples/risc_control_fsm/risc_control_fsm.sv`**: Multi-cycle instruction decode and control FSM (FETCH, DECODE, EXEC_ALU, MEM_ADDR, MEM_READ, MEM_WRITE, WRITEBACK).
4. **`rtl/examples/risc_branch_pc/risc_branch_pc.sv`**: Program counter register, sequential PC+4 incrementer, branch condition evaluator (BEQ, BNE, BLT, BGE), and jump target mux.
5. **`rtl/examples/risc_hazard/risc_hazard.sv`**: Pipeline hazard detection (load-use stall) and EX/MEM to MEM/WB data forwarding controller.

### 7. Automated Unit & Integration Tests (`backend/tests/test_formal_verification.py`)
- 11 new tests added:
  - Checker synthesizer implication and vacuity cover generation.
  - Checker synthesizer combinational immediate assertion generation.
  - Checker synthesizer assumption injection.
  - SBY task configuration generation (.sby syntax).
  - SBY log parser PASS status.
  - SBY log parser FAIL status with inductive step phase detection.
  - SBY log parser TIMEOUT status.
  - End-to-end verification service with SBY mock runner.
  - Rejection of invalid property before formal solver invocation.
  - FastAPI `/api/formal/verify` endpoint test via TestClient.
  - Benchmark synthesis test against RISC ALU.

---

## Test Results

All 39 backend unit and integration tests pass in 0.039 seconds:

```bash
$ python3 -m unittest discover -s backend/tests -v
test_api_formal_verify_endpoint (test_formal_verification.TestFormalVerification) ... ok
test_checker_synthesizer_assumptions (test_formal_verification.TestFormalVerification) ... ok
test_checker_synthesizer_combinational (test_formal_verification.TestFormalVerification) ... ok
test_checker_synthesizer_implication_and_vacuity (test_formal_verification.TestFormalVerification) ... ok
test_risc_benchmark_synthesizer_coverage (test_formal_verification.TestFormalVerification) ... ok
test_sby_config_generation (test_formal_verification.TestFormalVerification) ... ok
test_sby_log_parser_fail_step (test_formal_verification.TestFormalVerification) ... ok
test_sby_log_parser_pass (test_formal_verification.TestFormalVerification) ... ok
test_sby_log_parser_timeout (test_formal_verification.TestFormalVerification) ... ok
test_verification_service_end_to_end_mock (test_formal_verification.TestFormalVerification) ... ok
test_verification_service_invalid_property_rejected (test_formal_verification.TestFormalVerification) ... ok
test_health_payload (test_health.HealthEndpointTests) ... ok
test_adds_module_summary_and_cell_connectivity (test_ir_builder.TestIRBuilder) ... ok
test_extracts_clocked_memory_write_access (test_ir_builder.TestIRBuilder) ... ok
test_extracts_enum_state_candidate (test_ir_builder.TestIRBuilder) ... ok
test_extracts_ports_cells_register_and_clock_reset_candidates (test_ir_builder.TestIRBuilder) ... ok
test_identifies_module_instances (test_ir_builder.TestIRBuilder) ... ok
test_missing_top_module_is_rejected (test_ir_builder.TestIRBuilder) ... ok
test_api_generate_endpoint_error_handling (test_llm_pipeline.LLMPipelineTests) ... ok
test_api_generate_endpoint_success (test_llm_pipeline.LLMPipelineTests) ... ok
test_context_builder_combinational_design (test_llm_pipeline.LLMPipelineTests) ... ok
test_context_builder_extracts_clock_and_reset (test_llm_pipeline.LLMPipelineTests) ... ok
test_context_builder_fsm_and_memory (test_llm_pipeline.LLMPipelineTests) ... ok
test_context_builder_invalid_target_module_raises (test_llm_pipeline.LLMPipelineTests) ... ok
test_generation_rejects_malformed_json (test_llm_pipeline.LLMPipelineTests) ... ok
test_generation_strips_markdown_code_fences (test_llm_pipeline.LLMPipelineTests) ... ok
test_mock_provider_generation_end_to_end (test_llm_pipeline.LLMPipelineTests) ... ok
test_prompt_builder_enforces_principles (test_llm_pipeline.LLMPipelineTests) ... ok
test_provider_missing_api_key_raises_error (test_llm_pipeline.LLMPipelineTests) ... ok
test_assumption_cannot_be_accepted_without_reviewer (test_property_models.PropertyModelTests) ... ok
test_design_validation_checks_signals_and_widths (test_property_models.PropertyModelTests) ... ok
test_empty_expression_rejected (test_property_models.PropertyModelTests) ... ok
test_manual_property_fixtures_match_schema (test_property_models.PropertyModelTests) ... ok
test_unknown_signal_and_width_mismatch_rejected (test_property_models.PropertyModelTests) ... ok
test_valid_candidate_property (test_property_models.PropertyModelTests) ... ok
test_native_runner_writes_script_and_reads_output (test_yosys_runner.TestYosysRunner) ... ok
test_rejects_invalid_top_module_identifier (test_yosys_runner.TestYosysRunner) ... ok
test_rejects_missing_source (test_yosys_runner.TestYosysRunner) ... ok
test_wsl_path_uses_forward_slashes_for_windows_paths (test_yosys_runner.TestYosysRunner) ... ok

----------------------------------------------------------------------
Ran 39 tests in 0.039s

OK
```

---

## Deviations from Soubhagya_Important

**No material deviations.**

Formal verification execution adheres strictly to project principles:
- No commercial Verific dependency: properties synthesize into procedural Verilog checker monitors utilizing native Yosys system tasks.
- Unbounded $k$-induction (`prove`) is supported as the default proof mode.
- Vacuity guards are enforced via antecedent reachability covers.
- The Trusted Computing Base (TCB) remains minimal: Yosys, SBY, and classical SMT solvers (Z3 / Boolector).
- Status classification never marks unknown or timeout as PASS.

---

## How to Run Formal Verification

### Using Swagger UI
1. Start the backend: `uvicorn backend.app.main:app --reload`
2. Open `http://127.0.0.1:8000/docs`
3. Send a request to `POST /api/formal/verify` with your `design_ir`, `verilog_sources`, and `property_batch`.

### Using curl
```bash
curl -X POST "http://127.0.0.1:8000/api/formal/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "design_ir": { ... },
    "verilog_sources": {
      "counter.sv": "module counter(input wire clk, input wire rst_n, input wire enable, output reg [7:0] count); ... endmodule"
    },
    "property_batch": { ... },
    "proof_mode": "prove",
    "depth": 20,
    "solver": "z3"
  }'
```

---

## Next Step: Build 9 (Frontend Workbench Integration)

In Build 9, the React/Vite frontend will be connected to the complete pipeline:
- Upload RTL files and visualize elaborated Design IR.
- Select model / prompt configuration to generate candidate properties.
- Review assumptions and validate property references.
- Trigger formal verification (BMC / $k$-induction) and inspect proofs or counterexample traces.
