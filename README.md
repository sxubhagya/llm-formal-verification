# LLM-Assisted Formal Verification Framework

**Current build:** Update 9 — Interactive frontend workbench connecting design analysis, property generation, and formal verification.

## Objective
Generate candidate formal properties from Verilog/SystemVerilog RTL with an LLM, then validate and check them using classical formal verification. The LLM proposes; formal tools determine proof outcomes.

## Current pipeline status
RTL upload → **Yosys parsing/elaboration → Design IR v1.2** → **LLM Candidate Property Generation & Validation** → **Procedural Checker Synthesizer → SBY Formal Verification Engine** → **Interactive Frontend Workbench (Build 9)** → evidence and evaluation.

A PASS applies only to the checked property under the configured model, assumptions, and proof mode ($k$-induction or BMC). It does not prove the entire RTL design correct. Timeout/unknown is never PASS. Non-vacuity is checked via antecedent coverage witnesses.

## Layout
- `backend/`: FastAPI service, Yosys integration, Design IR v1.2, LLM property generation services, SBY formal verification runner, and tests
- `frontend/`: Interactive React/Vite workbench with benchmark presets, RTL editor, LLM generation panel, assumption review controls, and formal verification console
- `formal/`: formal tool integration boundary, examples and manual property-schema fixtures
- `rtl/examples/`: RTL benchmark library:
  - Base: `counter`, `comb_alu`, `traffic_light`, `register_file`, `multi_module`
  - RISC Processor Suite: `risc_alu` (arithmetic/shifts/flags), `risc_regfile` (32x32-bit with x0=0), `risc_control_fsm` (multi-cycle FSM), `risc_branch_pc` (branch/PC unit), `risc_hazard` (forwarding & load-use stall unit)
- `docs/`: status, handoff docs (`UpdateDoc1`–`UpdateDoc9`), and IEEE System Design Document (`docs/latex/`)

## Environment
- **Windows**: Primary development folder `C:\Users\fateh\Desktop\Program Folder`. Use VS Code/PowerShell for app development and Ubuntu WSL2 for formal tools (`wsl -d Ubuntu`). WSL sees the Windows folder at `/mnt/c/Users/fateh/Desktop/Program Folder`. In PowerShell use `npm.cmd` to avoid script execution-policy restrictions.
- **macOS**: Native Python 3.10+ supported for backend development, unit tests, and mock/live API tests.

## Running the Application

### 1. Start the Backend
```bash
# On macOS / Linux:
source .venv/bin/activate
pip install -r backend/requirements.txt
python3 -m unittest discover -s backend/tests -v
uvicorn backend.app.main:app --reload

# On Windows (PowerShell):
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

### 2. Start the Frontend
```bash
cd frontend
npm install # or npm.cmd install on Windows
npm run dev # or npm.cmd run dev on Windows
```
Open `http://127.0.0.1:5173` in your browser to interact with the Formal Verification Studio.

## API Endpoints (`http://127.0.0.1:8000/docs`)

1. **`POST /api/designs/analyze`**:
   Uploads `.v` / `.sv` files and synthesizes elaborated `DesignIR` v1.2 with port lists, registers, memory accesses, and FSM candidates.
2. **`POST /api/properties/validate`**:
   Validates a `PropertyBatch` against a `DesignIR` object for module and signal reference consistency.
3. **`POST /api/properties/generate`**:
   Extracts structured design context from `DesignIR` and Verilog source, sends prompt to LLM (`mock`, `gemini`, or `openai`), parses JSON into canonical `CandidateProperty` schema, runs design reference validation, and attaches provenance.
4. **`POST /api/formal/verify`**:
   Synthesizes procedural monitor checker wrappers (`formal_<top>.sv`), runs SymbiYosys (SBY) for unbounded $k$-induction (`prove`) or Bounded Model Checking (`bmc`), parses solver results, evaluates non-vacuity via antecedent cover witnesses, and outputs verdicts (`PASS`, `FAIL`, `UNKNOWN`, `TIMEOUT`, `INVALID`) alongside counterexample `.vcd` trace paths.

See `docs/UpdateDoc9.md` and `docs/PROJECT_STATUS.md` for full implementation details.
