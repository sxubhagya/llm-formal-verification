# UpdateDoc3 — HDL Parsing and Design Analysis (Initial Implementation)

**Project:** LLM-Assisted Formal Verification Framework for Verilog RTL  
**Update:** 3  
**Scope:** Yosys-first HDL frontend, initial Design IR, upload API, examples and tests  
**Implementation status:** Created in this build; local Windows/WSL verification is pending

---

## 1. Objective

Implement the first actual RTL ingestion and analysis path. The backend should accept Verilog/SystemVerilog source files, invoke an HDL frontend, elaborate the design, normalize the resulting structural information into a stable intermediate representation, and return that representation through an API.

The implementation deliberately separates the Yosys-specific process runner from the framework's own Design IR. This means downstream LLM/property-generation components need not consume raw Yosys JSON directly.

## 2. Architectural decision

The selected initial architecture is **Yosys-first with a modular frontend boundary**.

Reasons:
- Yosys is already installed and command-checked in the project's Ubuntu WSL environment.
- Yosys can parse/elaborate synthesizable Verilog and a useful subset of SystemVerilog.
- Its JSON netlist output is machine-readable and provides module, port, net, cell, connection and parameter information.
- The backend can normalize this output into our own schema, reducing coupling to Yosys internals.
- A future Slang/pyslang frontend can be added behind the same service boundary if language coverage requires it.

This is a pragmatic first frontend, not a claim of complete SystemVerilog-standard coverage.

## 3. Implemented files and responsibilities

### Backend models
- `backend/app/models/design_ir.py`
  - Pydantic models for `DesignIR`, `ModuleIR`, `PortIR`, `NetIR`, `CellIR`, and `RegisterIR`.
  - Includes structural fields and explicit warnings/limitations.

### HDL services
- `backend/app/services/hdl/yosys_runner.py`
  - Invokes Yosys natively or through WSL.
  - `HDL_FRONTEND_MODE=auto` selects WSL on Windows and native Yosys on Linux/WSL.
  - `HDL_FRONTEND_MODE=wsl` forces WSL; `native` forces a local executable.
  - `WSL_DISTRO` defaults to `Ubuntu`.
  - Uses argument-list subprocess execution (not `shell=True`), a generated Yosys script, a configurable timeout, and explicit failure diagnostics.
- `backend/app/services/hdl/ir_builder.py`
  - Converts Yosys JSON to the framework IR.
  - Classifies cells into sequential, combinational, internal and module-instance categories.
  - Summarizes common sequential cells and infers clock/reset candidates from common pin names.
- `backend/app/services/hdl/parser.py`
  - Coordinates Yosys execution, JSON loading and IR construction.

### API
- `backend/app/api/designs.py`
  - Adds `POST /api/designs/analyze`.
  - Accepts multipart form fields `top_module` and one or more `.v`/`.sv` files.
  - Per-file upload limit: 2 MiB.
  - Returns an `ANALYZED` status, serialized Design IR and a short frontend log tail.
  - Invalid RTL/elaboration errors are reported as HTTP 422; missing Yosys as HTTP 503.
- `backend/app/main.py`
  - Registers the new router and updates the API version to 0.2.0.

### Examples and tests
- `rtl/examples/counter/counter.sv`: parameterized counter with active-low asynchronous reset and enable.
- `rtl/examples/comb_alu/comb_alu.v`: small combinational ALU.
- `backend/tests/test_ir_builder.py`: checks ports, register extraction and clock/reset candidate extraction, plus missing top-module handling.
- `backend/tests/test_yosys_runner.py`: checks missing source handling and a mocked native runner invocation.
- `backend/requirements.txt`: adds `python-multipart`, required for FastAPI multipart uploads.

## 4. Yosys workflow

The current runner generates a script containing the equivalent of:

```text
read_verilog -sv <source files>
hierarchy -check -top <top module>
proc
opt
write_json <output file>
```

The `-sv` option enables Yosys' supported SystemVerilog subset. `hierarchy -check` validates that the requested top exists and that hierarchy can be resolved. `proc` lowers procedural blocks; `opt` performs basic optimization; `write_json` exports the elaborated structure.

The output is an optimized structural representation, not a lossless source AST. This distinction matters when later generating properties: source-level intent and some procedural structure may have been transformed.

## 5. Initial Design IR contents

The initial schema captures:
- Design-level top-module name, source file list, frontend name, warnings and limitations.
- Module names and attributes.
- Port names, directions, widths and bit identifiers.
- Named nets, widths, bit identifiers and attributes.
- Cell names, cell types, connections, parameters and coarse categories.
- Register-like sequential cells, data inputs/outputs, clock bits, reset bits and inferred reset kind.
- Clock and reset candidates with the sequential cells that reference them.

Clock/reset inference is explicitly labelled as candidate information. It is not a replacement for a timing specification or designer review.

## 6. API use

1. Start the backend from the repository root using the existing virtual environment.
2. Open `http://127.0.0.1:8000/docs`.
3. Expand `POST /api/designs/analyze`.
4. Enter the top module name (for example, `counter`).
5. Upload `rtl/examples/counter/counter.sv`.
6. Execute and inspect the returned `design` object.

For a second example, upload `rtl/examples/comb_alu/comb_alu.v` and set the top module to `comb_alu`.

## 7. Tests and verification status

Automated unit tests have been added for the IR builder and Yosys runner. In the build environment, all six backend unit tests passed and the FastAPI app imported successfully with `/api/designs/analyze` present in OpenAPI. These are assistant-side checks; the tests and WSL-backed Yosys execution have **not yet been run on the user's Windows/WSL machine in this update**. Do not treat this implementation as user-verified until the user runs the commands in Section 10 and tests both example RTL files through the API.

The previous elementary SBY proof/counterexample smoke tests remain separate evidence about the installed formal tools; they do not verify this HDL analysis service.

## 8. Known limitations and risks

1. **SystemVerilog subset:** Yosys does not implement every SystemVerilog language feature. Designs outside the supported subset may fail parsing/elaboration.
2. **Synthesis orientation:** The current flow targets synthesizable RTL. Testbench constructs and many verification-only language features are not supported by this frontend path.
3. **Optimization effects:** `proc` and `opt` can transform the representation. The IR is structural, not a source-faithful syntax tree.
4. **Clock/reset semantics:** Current identification is based on common sequential-cell pins. Polarity and detailed reset behaviour are not yet normalized into a complete semantic model.
5. **Clock domains:** No clock-domain crossing analysis is implemented.
6. **FSM analysis:** No robust state-machine recognition, state encoding extraction or transition graph is implemented yet.
7. **Hierarchy:** All modules in the Yosys JSON are included, but explicit instance graph normalization is not yet implemented.
8. **Security and scale:** The endpoint validates extensions and imposes a 2 MiB per-file limit, but authentication, aggregate upload limits, sandboxing and production hardening remain future work.
9. **Persistence:** Uploaded RTL and generated JSON are temporary; designs are not persisted.
10. **No LLM or formal proof:** This update does not generate properties, call an LLM, or run formal proofs.

## 9. Acceptance criteria

| Criterion | Build 3 status |
|---|---|
| Accept `.v` / `.sv` source uploads | Implemented; test pending |
| Invoke Yosys via WSL on Windows | Implemented; user test pending |
| Parse and elaborate top module | Implemented; user test pending |
| Extract modules, ports, nets and cells | Implemented in IR builder; unit test pending |
| Identify common sequential cells | Implemented; unit test pending |
| Infer clock/reset candidates | Basic structural inference implemented; semantic validation pending |
| Produce structured JSON IR | Implemented; user test pending |
| Handle invalid RTL with diagnostics | Implemented; user test pending |
| Report unsupported constructs | Via Yosys failure diagnostics; richer classification pending |
| Multi-module hierarchy | Yosys hierarchy check and module list; explicit instance graph pending |

## 10. User-side verification instructions

### A. Update dependencies

From PowerShell at the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

This installs `python-multipart`, newly required by the file-upload endpoint. Keep the existing `.venv`.

### B. Run backend tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
```

Expected: all six tests (health, IR-builder, and Yosys-runner tests) pass. The mocked runner test does not require Yosys execution.

### C. Start/restart the backend

Stop the old backend process with Ctrl+C in its terminal, then from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

The backend must be restarted so it loads the new router and code.

### D. Test the API

Open `http://127.0.0.1:8000/docs` and use `POST /api/designs/analyze`.

Test 1:
- `top_module`: `counter`
- file: `rtl/examples/counter/counter.sv`

Inspect the returned IR for the `counter` module, ports, sequential cells/registers, and clock/reset candidate information.

Test 2:
- `top_module`: `comb_alu`
- file: `rtl/examples/comb_alu/comb_alu.v`

Inspect the ports, combinational cells and net information.

Test 3 (invalid RTL): upload a deliberately malformed `.v` file with a valid `.v` extension and confirm that the endpoint returns HTTP 422 with Yosys diagnostics. Do not use a real project design for this destructive test; the API does not modify the source file.

### E. Frontend

No frontend changes are included in this update. If the frontend dev server is already running, it may continue running, but the new analysis API is currently tested through FastAPI's `/docs` interface.

## 11. Next step

After user-side verification, refine the IR based on observed Yosys JSON and add explicit module-instance/hierarchy relationships plus more robust clock/reset metadata. Then move into formal backend integration and the property representation work. Keep the LLM layer downstream of the validated design representation.

---

**Handoff rule:** This document records what this build adds and separates implementation from user-side verification. UpdateDoc4 will accompany the next meaningful code generation/build.
