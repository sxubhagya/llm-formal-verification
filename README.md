# LLM-Assisted Formal Verification Framework

**Current build:** Update 7 — LLM candidate property generation and design validation.

## Objective
Generate candidate formal properties from Verilog/SystemVerilog RTL with an LLM, then validate and check them using classical formal verification. The LLM proposes; formal tools determine proof outcomes.

## Current pipeline status
RTL upload → **Yosys parsing/elaboration → Design IR v1.2** → **LLM Candidate Property Generation & Design Validation** → formal execution (Build 8) → evidence and evaluation.

A PASS applies only to the checked property under the configured model, assumptions, and proof mode. It does not prove the entire RTL design correct. Timeout/unknown is never PASS. Do not silently weaken assertions or alter RTL to obtain a pass. FIFO is only an initial smoke-test candidate, not the project scope. 1,000 examples is not a benchmark requirement. Hosted LLM APIs (Gemini, OpenAI) and offline Mock providers are supported.

## Layout
- `backend/`: FastAPI service, Yosys integration, Design IR v1.2, LLM property generation services, and tests
- `frontend/`: React/Vite workbench placeholder
- `formal/`: formal tool integration boundary, examples and manual property-schema fixtures
- `rtl/`: RTL examples (counter, ALU, traffic light FSM, register file, RAM)
- `docs/`: status, handoff docs (`UpdateDoc1`–`UpdateDoc7`), and IEEE System Design Document (`docs/latex/`)

## Environment
- **Windows**: Primary development folder `C:\Users\fateh\Desktop\Program Folder`. Use VS Code/PowerShell for app development and Ubuntu WSL2 for formal tools (`wsl -d Ubuntu`). WSL sees the Windows folder at `/mnt/c/Users/fateh/Desktop/Program Folder`. In PowerShell use `npm.cmd` to avoid script execution-policy restrictions.
- **macOS**: Native Python 3.10+ supported for backend development and mock/live API tests.

## Backend Setup

### Windows (PowerShell, repository root)
```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python3 -m unittest discover -s backend/tests -v
uvicorn backend.app.main:app --reload
```

## Frontend Setup (PowerShell / Bash)
```bash
cd frontend
npm install # or npm.cmd install on Windows PowerShell
npm run build
npm run dev
```

## API Endpoints (`http://127.0.0.1:8000/docs`)

1. **`POST /api/designs/analyze`**:
   Uploads `.v` / `.sv` files and synthesizes elaborated `DesignIR` v1.2 with port lists, registers, memory accesses, and FSM candidates.
2. **`POST /api/properties/validate`**:
   Validates a `PropertyBatch` against a `DesignIR` object for module and signal reference consistency.
3. **`POST /api/properties/generate` (New in Build 7)**:
   Extracts structured design context from `DesignIR` and Verilog source, sends prompt to LLM (`mock`, `gemini`, or `openai`), extracts JSON, parses into `CandidateProperty` schema, runs design reference validation, and attaches provenance.
   - Example request payload:
   ```json
   {
     "design_ir": { ... },
     "top_module": "counter",
     "provider": "mock"
   }
   ```
   To use Gemini or OpenAI, set environment variables (`GEMINI_API_KEY` or `OPENAI_API_KEY`) or pass `provider` and `api_key` in the request body.

## Important Validation Boundary

`design_valid: true` indicates that referenced module/signal names and declared widths match the supplied `DesignIR`. It does **not** prove that the property is syntactically valid SVA, non-vacuous, or mathematically proven. All candidate properties maintain `verification_status: "not_run"` until formal backends execute them in Build 8.

See `docs/UpdateDoc7.md` and `docs/PROJECT_STATUS.md` for full implementation details.
