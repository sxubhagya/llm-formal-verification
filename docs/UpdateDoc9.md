# UpdateDoc9 — Frontend Workbench for RTL Ingestion, Property Generation, and Formal Verification

## Purpose

Implement Build 9 according to the roadmap in `Soubhagya_Important.md`:
- Replace the static frontend placeholder with an interactive React/Vite research workbench.
- Connect the frontend to the entire backend pipeline:
  1. RTL design ingestion and Design IR v1.2 elaboration (`POST /api/designs/analyze`).
  2. Structured LLM candidate property generation and validation (`POST /api/properties/generate`).
  3. Human-in-the-loop assumption review controls.
  4. SymbiYosys formal verification execution with $k$-induction and non-vacuity checking (`POST /api/formal/verify`).
  5. Evidence display: verdicts, proof metrics, non-vacuity witness status, and synthesized Verilog monitor code.

---

## Changes Implemented

### 1. Interactive Research Workbench (`frontend/src/App.jsx`)
- **Benchmark Suite Presets**: Quick-load selector for standard benchmarks (`counter`, `comb_alu`, `traffic_light`) and the expanded RISC processor suite (`risc_alu`, `risc_regfile`).
- **RTL Code Editor**: Allows viewing, editing, or pasting custom Verilog/SystemVerilog RTL.
- **Design Analysis Trigger & Inspector**:
  - Triggers `POST /api/designs/analyze`.
  - Visualizes elaborated Design IR metrics: port count, direction tags (`IN` / `OUT` with bit widths), inferred clock/reset candidates, and sequential registers.
- **LLM Candidate Property Generation Panel**:
  - Provider selector (`mock`, `gemini`, `openai`).
  - Optional API key input (masked; falls back to backend environment variable).
  - Focus guidance prompt text field.
  - Triggers `POST /api/properties/generate`.
  - Displays generated candidate properties with category, language, expression, and referenced signals.
- **Interactive Assumption Review Gate**:
  - In-browser review controls allowing researchers to inspect proposed assumptions and their rationales.
  - Enforces the project rule that accepted/rejected assumptions require a reviewer name attribution.
- **Formal Verification Execution Panel**:
  - Proof mode selection: unbounded $k$-induction (`prove`), Bounded Model Checking (`bmc`), or reachability (`cover`).
  - Solver selection: `z3`, `boolector`, `yices`.
  - Cycle bound depth input (1–100).
  - Triggers `POST /api/formal/verify`.
  - Displays high-visibility verdict badges (`PASS`, `FAIL`, `TIMEOUT`, `INVALID`), solver execution time, and non-vacuity status (`NON_VACUOUS`).
  - Embedded viewer for the synthesized procedural Verilog monitor (`formal_<top>.sv`).

### 2. Dark Mode UI Styling (`frontend/src/styles.css`)
- Clean research-grade visual design with high-contrast typography, metrics cards, syntax-highlighted code blocks, and status indicators.
- Responsive two-column workbench layout.

### 3. Full-Stack Connectivity & CORS (`frontend/vite.config.js` & `backend/app/main.py`)
- Configured Vite development proxy: routes `/api/*` requests to the FastAPI backend at `http://127.0.0.1:8000`.
- Added FastAPI `CORSMiddleware` to allow direct requests from development servers.

---

## Test Results

### 1. Frontend Build Verification
```bash
$ npm run build
vite v6.4.5 building for production...
✓ 27 modules transformed.
dist/index.html                   0.43 kB │ gzip:  0.30 kB
dist/assets/index-Y4ticPau.css    7.86 kB │ gzip:  2.15 kB
dist/assets/index-_v34A4Nj.js   160.35 kB │ gzip: 50.92 kB
✓ built in 1.23s
```

### 2. Backend Automated Test Suite
All 39 backend tests pass in 0.067s:
```bash
$ python3 -m unittest discover -s backend/tests -v
...
Ran 39 tests in 0.067s

OK
```

---

## Deviations from Soubhagya_Important

**No material deviations.**

All workstream items were implemented according to the agreed plan:
- Frontend provides full visibility into all five pipeline stages.
- Untrusted AI role is clearly maintained: formal verification results are strictly driven by SBY and SMT solvers.
- Human review is enforced for assumption status changes.
- All 39 automated unit and integration tests remain passing.

---

## How to Run the Complete Stack

### 1. Start the Backend (Terminal 1)
```bash
# On macOS / Linux:
source .venv/bin/activate
uvicorn backend.app.main:app --reload

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload
```
The backend API and interactive Swagger docs are accessible at `http://127.0.0.1:8000/docs`.

### 2. Start the Frontend (Terminal 2)
```bash
cd frontend
npm run dev # or npm.cmd run dev on Windows
```
Open `http://127.0.0.1:5173` in your browser to interact with the Formal Verification Studio.

---

## Next Step: Build 10 (Counterexample Analysis & Bounded Candidate Refinement)

In Build 10, when a candidate property receives a `FAIL` verdict:
- Parse the generated VCD counterexample trace (`engine_0/trace.vcd`).
- Reconstruct the cycle-by-cycle signal waveform leading up to the violation.
- Provide structured failure explanation and bounded candidate refinement prompts back to the LLM for iterative correction.
