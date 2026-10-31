# LLM-Assisted Formal Verification Framework

**Current build:** Update 6 — RTL analysis enrichment and candidate-property schema.

## Objective
Generate candidate formal properties from Verilog/SystemVerilog RTL with an LLM, then validate and check them using classical formal verification. The LLM proposes; formal tools determine proof outcomes.

## Current pipeline status
RTL upload → **Yosys parsing/elaboration → Design IR v1.2** → candidate-property schema and design-reference validation → LLM candidate generation (not implemented) → formal execution (not integrated) → evidence and evaluation.

A PASS applies only to the checked property under the configured model, assumptions and proof mode. It does not prove the entire RTL design correct. Timeout/unknown is never PASS. Do not silently weaken assertions or alter RTL to obtain a pass. FIFO is only an initial smoke-test candidate, not the project scope. 1,000 examples is not a benchmark requirement. Hosted LLM APIs are the initial approach; fine-tuning is not core.

## Layout
- `backend/`: FastAPI service, Yosys integration, Design IR and tests
- `frontend/`: React/Vite workbench placeholder
- `formal/`: formal tool integration boundary, examples and manual property-schema fixtures
- `rtl/`: RTL examples
- `docs/`: status, handoff docs and HDL frontend notes

## Environment
Main development folder: `C:\Users\fateh\Desktop\Program Folder` (Windows). Use VS Code/PowerShell for app development and Ubuntu WSL2 for formal tools (`wsl -d Ubuntu`). WSL sees the Windows folder at `/mnt/c/Users/fateh/Desktop/Program Folder`. In PowerShell use `npm.cmd` to avoid the previously observed npm script execution-policy issue.

## Backend setup (PowerShell, repository root)
```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

## Frontend setup (PowerShell)
```powershell
cd frontend
npm.cmd install
npm.cmd run build
npm.cmd run dev
```

## Analyze RTL
Start the backend, then open `http://127.0.0.1:8000/docs`. Use `POST /api/designs/analyze`, supply a top module name and one or more `.v` / `.sv` files. On Windows, the backend defaults to Yosys through Ubuntu WSL. See `docs/HDL_FRONTEND.md` for configuration and limitations.

## Current implementation boundary
Implemented in this update: initial Yosys-based parse/elaboration workflow, JSON-to-DesignIR conversion, upload API, example counter/ALU RTL, and automated unit tests. Not implemented: full SystemVerilog support, source-accurate AST, complete FSM transition reconstruction, LLM property generation, assertion-language parsing/elaboration, formal-runner integration, counterexample parsing, and benchmarking.


## Latest update

Update 5 expands the RTL example suite and enriches the design IR (version 1.1). See `docs/UpdateDoc5.md` and `docs/PROJECT_STATUS.md`.


## Candidate-property schema (Update 6)

The provider-independent Pydantic schema is in `backend/app/models/property_models.py`. It represents property category, expression language, referenced signals, clock/reset context, assumptions and their review status, provenance, lifecycle and verification status.

`POST /api/properties/validate` accepts a `DesignIR` object and a `PropertyBatch`. It checks module/signal references and optional signal widths. This endpoint does **not** parse SystemVerilog Assertions, prove properties, establish assumption correctness, or mark properties as formally verified. A design-valid result means only that the referenced design objects were found.

Manual fixture batches are in `formal/examples/property_schema/`. They exercise the schema and are not claimed to be proven.
