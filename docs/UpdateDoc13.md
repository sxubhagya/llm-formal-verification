# UpdateDoc13 — Build 13

**Project:** LLM-Assisted RISC Formal Verification Framework  
**Base:** User-supplied `Program Folder(7).zip` (Build 12.0.1)  
**Build:** 13  
**Focus:** Custom RTL-first workflow, benchmark separation, sequential property clock handling, and complete frontend redesign.

## 1. Executive summary

Build 13 changes the default user journey from a preselected counter benchmark to a **Custom RTL** workspace. A user can paste Verilog/SystemVerilog RTL, specify the top module, and enter independent behavioural requirements. Built-in designs remain available as selectable examples and can be loaded into the same workflow.

The frontend has been redesigned around a blue, white and green palette, a scrollable single-column workflow with a compact live overview, collapsible advanced settings, and a separate Experiment History tab.

The FIFO investigation identified a concrete cause for the two INVALID properties in run `20261101T101152_ba9af0db`: both were Boolean expressions on a sequential design but contained no clock metadata. The checker rejected them before SBY execution with:

`Temporal/sequential properties require an explicit property-specific clock context.`

They were **not rejected because the benchmark preset configured an 8-bit counter**. The selected benchmark ID is not sent to the formal endpoint. The earlier interface could, however, leave the counter preset's example specification in place after a user manually replaced the RTL, which was confusing and unsafe as a workflow.

## 2. Main changes

### 2.1 Custom RTL is the default

- The application opens in the Custom RTL tab.
- RTL source and top-module fields start empty; no counter is silently preloaded.
- The behavioural specification starts empty and must be supplied by the user.
- A built-in example dropdown is available within the Custom RTL workflow.
- A separate Examples tab lists the reference designs and loads the selected design and its corresponding sample specification into the custom workflow.
- The FIFO has been added as a built-in reference design: 4 entries × 8 bits, synchronous active-low reset, read/write pointers, occupancy counter, and full/empty outputs.
- Changing the RTL or top module invalidates downstream analysis, generated properties, and verification results.

### 2.2 Benchmark selection is separated from formal configuration

The selected example is a convenience for loading RTL and sample requirements. It is not passed to the formal verification endpoint as a mode or engine configuration. The actual design top, elaborated DesignIR, RTL source, property batch, proof mode, depth, and solver determine the formal run.

A custom design therefore does not inherit a counter-specific width, clock, or reset merely because the application previously displayed a counter example. The application now starts without any selected example.

### 2.3 Sequential Boolean property clock handling

The run record for the earlier FIFO attempt showed:

- `sync_fifo_prop_02` and `sync_fifo_prop_03` were rejected before formal execution.
- Both used `boolean_expression`.
- Both omitted the `clock` field.
- The selected design contains sequential cells and has one structurally identified clock candidate (`clk`).
- The checker requires sequential properties to be sampled on a clock.

Build 13 updates `CheckerSynthesizer`:

- If a sequential design has exactly one structurally identified, named clock candidate, a Boolean property without explicit clock metadata is sampled on that clock's positive edge.
- The generated checker includes an explicit warning that the clock was inferred.
- If multiple clock candidates exist and the property does not specify one, the checker rejects the property rather than guessing.
- If no unique clock is identified, the checker rejects the property and asks for explicit clock metadata.
- Explicit property clock metadata continues to take precedence and is validated against the selected module's 1-bit input ports.

This addresses the precise pre-execution rejection seen in the FIFO run. It does not itself establish that every generated FIFO property is semantically correct or that the FIFO has been formally proven.

### 2.4 Property-generation guidance

- Prompt version advanced from 2.0 to 2.1.
- The LLM is instructed to attach clock metadata to properties on sequential designs, including Boolean invariants.
- The LLM is instructed to express invariants over their intended full scope; for example, an occupancy bound should not be restricted to reset cycles unless the specification explicitly requires that.
- The LLM is instructed to cover requirements with meaningful properties when the configured property limit permits.
- The LLM is explicitly warned that a requirement-ID mapping is only traceability metadata, not proof that the property semantically covers the requirement.
- The backend now reports requirement IDs that have no generated property.

### 2.5 Formal-result warnings

The formal verification response now describes the implemented checker accurately: same-sample Boolean properties plus the documented restricted SVA subset (`|->`, `|=>`, `$past`, `$stable`, `$rose`, `$fell`, and synchronous sampled `disable iff`). It no longer incorrectly states that only Boolean expressions are supported.

Checker warnings, including inferred-clock warnings, are propagated into the verification response.

### 2.6 Frontend redesign

The old two-column, information-dense workbench has been replaced with:

- Blue, white and green visual system.
- Clean header with explicit Custom RTL, Examples, and Experiment History tabs.
- Custom RTL as the default view.
- A clear vertical workflow: RTL input → behavioural specification → property review → formal verification.
- Scrollable code and specification editors.
- Dropdowns for built-in examples, provider, property limit, proof mode and solver.
- Optional generation settings behind a disclosure control.
- Experiment history hidden behind its own tab.
- Compact live overview and results panel.
- Responsive layout for narrower screens.
- No changes to the backend API-key handling; credentials remain backend-side.

## 3. Files changed

- `frontend/src/App.jsx`
- `frontend/src/styles.css`
- `backend/app/services/formal/checker_synthesizer.py`
- `backend/app/services/formal/verification_service.py`
- `backend/app/services/llm/prompt_builder.py`
- `backend/app/services/llm/property_generator.py`
- `backend/tests/test_temporal_validation_suite.py`
- `docs/UpdateDoc13.md`

## 4. Validation performed

- Backend test suite: **82 passed, 4 subtests passed**.
- Frontend JSX syntax parse: **passed**.
- Python changes were imported and exercised by the backend test suite.

### Validation not completed in this build environment

- A full Vite production build could not be completed because the uploaded `node_modules` tree did not contain the Linux Rollup native package (`@rollup/rollup-linux-x64-gnu`). This is an environment/package-platform mismatch, not a reported JSX syntax error. Run `npm install` in the user's normal Windows project environment if the installed dependency tree needs refreshing.
- Yosys/SymbiYosys were not installed in the build environment, so a fresh end-to-end FIFO proof could not be run here.
- A real Gemini API call was not run as part of this package validation.

## 5. Important FIFO follow-up test

After installing Build 13, use **Custom RTL** (or load the 4-entry FIFO from Examples), confirm the top module is `sync_fifo`, and analyse the RTL. Enter/review the independent FIFO requirements, then generate properties.

For the two earlier INVALID properties, the expected Build 13 behaviour is that a unique `clk` candidate is inferred and the generated checker samples the Boolean assertions at `posedge clk`. Check the generated checker preview and the warning that clock inference occurred.

Then run the properties. Do not interpret an overall PASS as proof of FIFO correctness unless the generated properties actually cover the FIFO requirements. In particular, inspect whether the generated properties cover accepted writes, accepted reads, simultaneous read/write, overflow/underflow protection, pointer updates, and data ordering. A requirement ID alone is not semantic coverage.

## 6. Known limitations retained

- The formal backend still supports a restricted SVA subset, not the complete IEEE 1800 assertion language.
- Vacuity analysis remains `NOT_CHECKED`.
- A property PASS proves only the encoded assertion under the recorded RTL, assumptions, and proof configuration.
- The correctness and completeness of the behavioural specification still require human review.
- LLM-generated properties remain candidates and require structural validation and formal verification.
- Generalization to all RISC designs remains a research objective; unsupported RTL constructs and multi-clock designs may require explicit handling.

## 7. Installation notes

1. Stop the running frontend and backend servers.
2. Back up the current project folder.
3. Extract the Build 13 ZIP over a clean project directory.
4. Preserve the user's local `.env` file separately; it is intentionally excluded from the ZIP.
5. Keep using the existing Python virtual environment if compatible, or reinstall backend dependencies from `backend/requirements.txt`.
6. In the frontend directory, run `npm install` if dependencies need to be restored, then start the Vite development server.
7. Start the backend as before. Formal tools continue to run in the configured WSL environment.

**Do not overwrite the user's `.env`, `.venv`, or existing local API credentials when installing the update.**
