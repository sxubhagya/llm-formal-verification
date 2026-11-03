# UpdateDoc15 — Internal State Binding, Reset Environment & Auditability

**Build:** 15  
**Date:** 2 November 2026  
**Base:** User-provided `Program Folder(10).zip` (Build 14 working folder)

## 1. Purpose

Build 15 addresses the user's and Claude's outstanding concerns around internal DUT signal binding, arbitrary initial state, property-count behaviour, and experiment reproducibility. It preserves the Build 14 fail-closed design principles and does not claim that LLM-generated properties are correct merely because they pass schema validation.

## 2. Prior state (Build 14)

Build 14 rejected internal DUT nets because the checker wrapper connected only top-level ports. This avoided a serious false-result bug: a property could refer to a same-named but undriven wrapper-local net. The rejection was safe but prevented state-oriented FIFO properties such as occupancy and pointer invariants.

Sequential formal runs also began with unconstrained initial state unless the model itself constrained it. A synchronous reset in RTL does not mean the formal engine automatically assumes that reset was asserted before the first meaningful transaction. This can produce counterexamples from arbitrary initial states.

Build 14 stored RTL, DesignIR, specification, property batch, proof settings, results and VCD artifacts, but not the exact generation prompt/raw LLM response in the formal run record.

## 3. Changes made

### 3.1 Internal-net binding

Files:
- `backend/app/services/property_validation.py`
- `backend/app/services/formal/checker_synthesizer.py`
- `backend/app/services/llm/context_builder.py`
- `backend/app/services/llm/prompt_builder.py`
- `backend/tests/test_build14_integrity.py`

Changes:
- Property validation now resolves each signal against the selected module's top-level ports or exact named internal nets from DesignIR.
- Width and signedness checks apply to both.
- Internal signals are explicitly aliased in the wrapper, e.g. `assign count = dut.count;`.
- The old unsafe behaviour—implicitly creating a disconnected wrapper net—is not used.
- Clock/reset remain constrained to structurally validated top-level input ports.
- The LLM receives a separate list of exact named internal nets and is told not to invent absent names.
- Direct memory-array observation remains unsupported; the prompt explicitly says so.

**Critical qualification:** The implementation uses Verilog hierarchical references (`dut.<net>`). Automated unit tests verify the generated source, but the packaging environment does not contain Yosys/SBY/Z3. Therefore this integration has not yet been proven against the user's installed Yosys 0.33/SBY toolchain. A real WSL smoke test is supplied. Until it passes, internal-net support is a candidate implementation, not solver-validated functionality.

### 3.2 Initial reset environment contract

Files:
- `backend/app/models/formal_models.py`
- `backend/app/services/formal/checker_synthesizer.py`
- `backend/app/services/formal/verification_service.py`
- `backend/app/services/formal/run_store.py`
- `frontend/src/App.jsx`
- `backend/tests/test_build14_integrity.py`

Added `InitialResetContract`:
- reset signal
- active-high/active-low polarity
- reviewer identity
- rationale

When supplied, the checker:
- validates that the reset is a structurally identified top-level reset input;
- validates polarity against Yosys sequential-cell metadata;
- assumes reset is active on the first clock edge only;
- suppresses assertion evaluation on that first edge, allowing synchronous reset state updates to take effect;
- leaves reset unconstrained afterwards.

The contract is optional and disabled by default. The frontend exposes it under an optional advanced section. The exact contract is persisted in the run record.

Sequential runs without this contract now include a warning that initial state is unconstrained. This is not a blanket recommendation to assume reset: the user must enable it only when the actual integration environment guarantees it.

### 3.3 Property count and generation audit

Files:
- `backend/app/services/llm/prompt_builder.py`
- `backend/app/services/llm/property_generator.py`
- `backend/app/models/property_models.py`
- `backend/app/models/formal_models.py`
- `backend/app/services/formal/run_store.py`
- `frontend/src/App.jsx`
- `backend/tests/test_build13_1_regressions.py`

Changes:
- Removed quota-filling supplemental generation calls.
- The LLM chooses the number of properties; 20 remains only a defensive backend ceiling.
- The frontend no longer asks the user to choose a maximum count.
- Missing requirement references are reported as incomplete coverage; the system does not silently add more calls to fill a quota.
- Generation response includes the exact system prompt, user prompt, raw model response, model/provider metadata, prompt version, source/specification hashes and prompt hashes.
- When a formal run is executed, this generation audit is stored with the RTL, specification, DesignIR, property batch, proof configuration and traces.

Requirement IDs remain traceability metadata. They do not establish that an expression semantically formalises the referenced requirement; review and counterexample/mutation tests remain necessary.

### 3.4 Version and documentation

Files:
- `frontend/src/App.jsx`
- `backend/app/main.py`
- `docs/PROJECT_STATUS.md`
- `docs/BUILD15_WSL_VALIDATION.md`

- Frontend footer now identifies Build 15.
- API version updated to 0.9.0.
- Added a required WSL smoke-test guide.

## 4. Tests and evidence

| Check | Result |
|---|---|
| Backend automated tests | 109 passed |
| Parameterized subtests | 4 passed |
| Python compileall | Passed |
| Frontend JSX parse with Babel | Passed |
| Full Vite production build | Not completed: `vite` executable returned permission denied in packaging environment |
| Real Yosys/SBY/Z3 internal-probe smoke test | Not run: tools unavailable in packaging environment |
| Live Gemini generation | Not run |
| End-to-end FIFO baseline/mutation suite | Not run |

The new unit tests cover:
- exact internal-net lookup and width validation;
- generated explicit `dut.count` alias;
- initial reset contract syntax and first-cycle guard;
- removal of quota-filling generation calls;
- prompt safety-ceiling language and generation audit snapshot.

## 5. Known limitations / risks

1. **Hierarchical probe support is not yet confirmed on the user's toolchain.** Run `python backend/scripts/run_internal_probe_smoke.py` inside WSL before relying on internal signal properties.
2. **Memory arrays are not directly observable.** This build can expose named state nets such as count/pointers and externally observable outputs, but does not yet instrument memory contents or memory read/write ports.
3. **Only the first clock edge reset condition is assumed.** This contract models a specific environment guarantee, not a generic reset sequence or asynchronous abort semantics.
4. **SVA remains a restricted subset.** No full IEEE 1800 SVA support, vacuity checking, cover witness analysis, or general temporal sequence semantics.
5. **No live API call or real solver run was possible in the packaging environment.**
6. **The frontend production bundle was not rebuilt** because the packaged `vite` executable could not run in this Linux environment. JSX syntax was parsed successfully.
7. **Semantic correctness remains a separate concern.** A structurally valid property may still be weak, incorrectly mapped to a requirement, or vacuous. Mutation testing and manual review remain necessary.

## 6. Installation and preservation

1. Stop the backend and frontend.
2. Extract Build 15 over the existing project folder.
3. Preserve the existing `.env`, `.venv`, and `frontend/node_modules`; they are not included in the Build 15 archive.
4. Restart backend and frontend using the same commands as Build 14.
5. Run the WSL internal-probe smoke test in `docs/BUILD15_WSL_VALIDATION.md`.
6. Only after that test passes, rerun the FIFO experiment.

## 7. Security note

The uploaded Build 14 archive contained a populated `.env`. The Build 15 distribution excludes `.env` and `.env.*` secrets (while retaining `.env.example`). If the included credential was a real Gemini API key and has not already been rotated, rotate it in Google AI Studio. Do not copy a real key into source code or a ZIP shared with others.

## 8. Handoff / next steps

1. User installs Build 15 while preserving local environment files/dependencies.
2. Run the WSL smoke test and share its complete output.
3. If hierarchical references fail, replace this binding strategy with a Yosys-netlist-level probe/instrumentation pipeline before any FIFO claims.
4. If it passes, rerun FIFO baseline and controlled mutations (occupancy, full/empty, pointers, blocked operations, simultaneous read/write, reset).
5. Inspect every failed property’s VCD and SBY phase. A base-case/BMC counterexample is a reachable FAIL; induction-step-only failure remains UNKNOWN.
6. Add direct memory-port/content instrumentation in a later build if FIFO storage properties require it.
