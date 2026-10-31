# Project Status

## Current checkpoint — Update 8

| Area | Status | Evidence / notes |
|---|---|---|
| Repository skeleton and environments | Verified | Windows + Ubuntu WSL2 and macOS Python environments operational |
| Windows-to-WSL Yosys path | Verified | Live counter/ALU/FSM/register-file/multi-module analysis |
| Counter and ALU RTL analysis | Verified | API returned ANALYZED |
| FSM/register-file/multi-module analysis | Verified | User supplied successful Build 5 API outputs |
| Design IR v1.2 summaries/connectivity | Verified | Memory access records and enum-derived FSM candidate extraction |
| Candidate-property schema | Implemented | Pydantic models, assumptions guard, provenance |
| Design-reference validation API | Implemented | `POST /api/properties/validate`; signal names and widths |
| Provider abstraction layer | Implemented | `LLMProvider` interface; Gemini, OpenAI, and deterministic Mock |
| Design context preparation | Implemented | Extracts ports, registers, clocks, resets, memories, FSMs, source snippets |
| Prompt construction | Implemented | Untrusted generator role, zero proof claims, explicit assumption rationale |
| Structured property output parsing | Implemented | Markdown fence stripping, schema validation, assumption guard |
| LLM candidate generation API | Implemented | `POST /api/properties/generate`; 28 backend tests pass |
| Procedural checker synthesizer | Implemented | Synthesizes `formal_<top>` wrapper with `$past()`, `assert`, `assume`, and `cover` |
| SymbiYosys (SBY) execution runner | Implemented | Cross-platform (native & WSL) SBY runner for BMC and unbounded $k$-induction |
| Non-vacuity cover guard | Implemented | Automatically generates `cover(antecedent)` witness checks |
| Formal proof execution API | Implemented | `POST /api/formal/verify`; returns PASS/FAIL/UNKNOWN/TIMEOUT/INVALID + VCD traces |
| RISC benchmark suite | Implemented | 5 core processor blocks: ALU flags, RegFile, Control FSM, Branch PC, Hazard Unit |
| Frontend workflow integration | Not started (Build 9) | React/Vite workbench placeholder |

## Update 8 scope

- Added `backend/app/models/formal_models.py` defining proof modes (`prove`, `bmc`, `cover`), solver engines (`z3`, `boolector`, `yices`), vacuity statuses, and detailed verification result models.
- Implemented `CheckerSynthesizer` in `backend/app/services/formal/checker_synthesizer.py` translating candidate properties and SVA implications into procedural Verilog monitors without modifying source RTL.
- Implemented `SBYRunner` in `backend/app/services/formal/sby_runner.py` with cross-platform WSL/native execution, isolated scratch directories, and robust log parsing (distinguishing base vs. inductive step failure).
- Implemented `FormalVerificationService` in `backend/app/services/formal/verification_service.py` orchestrating validation -> synthesis -> formal execution.
- Added `POST /api/formal/verify` endpoint in `backend/app/api/formal.py`.
- Added 5 new RISC processor RTL benchmarks in `rtl/examples/`: `risc_alu`, `risc_regfile`, `risc_control_fsm`, `risc_branch_pc`, `risc_hazard`.
- Added 11 automated unit/integration tests in `backend/tests/test_formal_verification.py` (total 39 tests passing).

## Verification Boundary

`PASS` indicates that the property was mathematically proven by the underlying formal solver (e.g. Z3 / Boolector via SBY) under the specified assumptions and proof mode ($k$-induction or BMC depth $N$). Non-vacuity is checked via antecedent coverage witnesses. Any counterexample produces a `.vcd` trace for inspection.

See `UpdateDoc1` through `UpdateDoc8` for build handoffs.
