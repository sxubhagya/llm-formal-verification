# UpdateDoc14 — Verification Integrity and Reliability

**Build:** 14  
**Base:** `Program Folder(8).zip` (Build 13.1 working folder)  
**Date:** 2 November 2026  
**Purpose:** Correct high-risk soundness and reliability defects before adding more verification features.

## 1. Most important finding and correction

### Internal DUT signal binding

The previous checker wrapper declared and connected top-level DUT ports, but accepted internal net names during validation. An assertion such as `count <= 3'd4` could therefore refer to a separate, undriven wrapper-local `count` instead of `dut.count`. This can produce misleading formal results, including a false PASS.

Build 14 changes this to fail closed:

- Structural property validation rejects internal DUT nets with `INTERNAL_SIGNAL_UNSUPPORTED`.
- Checker synthesis independently rejects them as defence in depth.
- The LLM prompt explicitly says only top-level input/output ports are currently bindable.
- The design context explains the boundary so the LLM is less likely to propose unsupported internal-state assertions.

**Important limitation:** Build 14 does not yet instrument internal DUT signals. FIFO properties requiring internal `count`, pointers, or memory state will be rejected. This is a deliberate safety restriction, not a completed FIFO verification solution. The next engineering task is to implement and test a Yosys-backed internal-signal instrumentation mechanism that proves signal identity, width, signedness, and hierarchy before allowing those assertions.

## 2. Checker and HDL/IR correctness

- DesignIR now retains signedness and packed-vector index metadata (`offset`, `upto`) for ports and nets.
- The checker preserves non-zero port index ranges in its wrapper declarations.
- Constant bit/part-selects are checked against the original port index range; dynamic selects and unsupported part-select forms are rejected.
- Signed ports are rejected until signed arithmetic/comparison semantics are supported end to end.
- `inout` and unsupported port directions are rejected instead of being emitted as ordinary output wires.
- Clock inference requires one unambiguous candidate and consistent, decodable Yosys `CLK_POLARITY` metadata. Unknown or mixed edge polarity is not silently treated as `posedge`.
- Reset context no longer infers active-low polarity from names such as `rst_n`. The selected reset must match a structurally identified reset input, and timing/polarity metadata is checked against Yosys reset-cell parameters.
- Sequential memory state also triggers clocked-property handling; a memory-only design without enough edge metadata requires explicit designer confirmation.
- The LLM context now states when a clock edge or reset polarity cannot be established.

## 3. Temporal checker and proof-result integrity

- Corrected non-overlapped implication (`|=>`) history accounting when the antecedent itself contains `$past`.
- Increased the helper history counter saturation point to 11 so the supported maximum `$past(expr, 10)` can also be used in a `|=>` antecedent without making the property permanently disabled.
- Temporal placeholder replacement is token-safe; placeholder 1 cannot corrupt placeholder 10.
- Nested temporal sampling is explicitly rejected.
- Signal identifiers containing `$` are no longer mistaken automatically for system functions.
- Induction-step failure is now `UNKNOWN`, not `FAIL`, because a failed induction step is not itself a reachable counterexample.
- In prove mode, an unclassified `DONE (FAIL)` is `UNKNOWN` unless a base-case counterexample is identified. A base-case failure takes precedence if both base and induction diagnostics appear.
- BMC failure remains `FAIL`; BMC PASS remains bounded to the configured depth.
- `check_vacuity=true` is rejected because cover-based vacuity analysis is not implemented. The system does not silently ignore the request or claim non-vacuity.
- VCD parsing now reports truncation when signal, frame, or byte limits are reached and caps trace input size.

## 4. Formal-run lifecycle and persistence

- SBY and Yosys execution use process-group termination on timeout where supported by the host OS.
- SBY tool availability is cached per runner rather than checked for every property.
- Temporary SBY work directories are deleted only after trace and run artifacts have been saved successfully.
- Run artifacts are written to a staging directory and become visible in history only after an atomic rename.
- New trace URLs use safe hashed filenames; the API resolves them through the run's trace-artifact map.
- A run-history record continues to preserve the exact RTL source bundle, DesignIR, property batch, behavioural specification, hashes, results, and trace artifacts.

## 5. Specification approval and LLM generation

- Specification approval is now a separate backend operation.
- The UI requires a reviewer identity and an explicit confirmation that the requirements describe intended behaviour independently of the RTL.
- Approval is bound to the canonical specification content hash. Any content change invalidates the approval and requires re-approval.
- Restoring a historical experiment with a legacy specification lacking a content-bound approval does not invent a reviewer or silently treat it as newly approved.
- Formal verification warns when no independent specification is attached; a PASS in that case proves only the encoded property, not design-specification conformance.
- Provider-specific `functional` property categories are normalized to the canonical category based on assertion context; the assertion expression is not modified.
- Clock/reset alias-normalization warnings are retained instead of being lost after parsing.
- A failed or malformed supplemental LLM request no longer discards an otherwise valid initial generation response.
- Null assumptions are normalized to an empty list; malformed non-list assumptions are rejected clearly.
- LLM output with invalid requirement IDs is rejected from the supplement merge.
- Gemini model IDs returned as `models/<id>` are normalized before constructing the `generateContent` URL; model discovery follows bounded pagination.
- The default Gemini model now matches `.env.example`.

## 6. Frontend and application workflow

- Added optional multi-file RTL upload and restoration from saved experiment history.
- The combined source bundle is passed to property generation; the full named source map is passed to formal verification.
- Yosys analysis is dispatched to a worker thread so the async API handler does not block the event loop during elaboration.
- The UI requires explicit specification confirmation before approval and generation.
- The API version was updated to `0.8.0`.
- `.gitignore` now excludes `formal/runs/`; `.env.example` documents `HDL_FRONTEND_MODE` and `FORMAL_RUNS_DIR`.

## 7. Validation performed

| Check | Result |
|---|---|
| Backend pytest suite | **107 passed** |
| Python source compilation | **Passed** |
| Babel JSX parse (`App.jsx`, `main.jsx`) | **Passed** |
| Full Vite production build in this Linux environment | **Not completed** — uploaded `node_modules` contains Windows-native optional dependencies; Linux Rollup binary is absent and offline npm cache cannot supply it |
| Real Yosys/SBY proof run in this environment | **Not run** — Yosys, SBY, Z3, and Boolector are not installed in this build environment |
| Real WSL2 formal regression | **Required after installation** |

The 105 passing tests include the new regressions for internal-net rejection, clock-edge handling, temporal history, temporal placeholder safety, induction-step classification, VCD truncation, content-bound specification approval, category normalization, signed-port rejection, and non-zero vector indices. Passing unit tests do not substitute for a real Yosys/SBY proof run.

## 8. Known limitations deliberately retained

1. Internal DUT nets are not yet supported. This is the main remaining blocker for deep FIFO state assertions.
2. Signed arithmetic/comparison, `inout`, dynamic bit-selects, and unsupported part-select forms are rejected.
3. The checker supports only its documented restricted SVA subset; it is not a full IEEE 1800 implementation.
4. Asynchronous `disable iff` abort semantics are not approximated.
5. Vacuity/cover checking is not implemented.
6. No universal initial-reset assumption is added. The DUT initial state remains unconstrained unless a reviewed property/environment contract constrains it.
7. Requirement-ID traceability is not semantic proof that a property fully captures a requirement.
8. A PASS proves only the encoded property under the exact recorded RTL, specification (if attached), assumptions, and proof configuration.

## 9. Security note

The uploaded Build 13.1 archive contained a populated Gemini credential in its local `.env` file. Build 14 packages **do not include `.env`**, `.git`, `.venv`, `node_modules`, formal run history, or the bundled research PDF. Because the credential was present in a shared archive, rotate it in Google AI Studio before continuing to use that key. Keep the replacement only in the local, unshared `.env` file.

## 10. Installation

1. Stop the running frontend and backend.
2. Extract the Build 14 ZIP over the existing `Program Folder`.
3. Preserve the existing local `.venv`, `frontend/node_modules`, and `.env`; they are intentionally not included in the ZIP.
4. Run the backend test suite from the project root:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```
5. Start the backend and frontend using the same commands as the previous build.
6. Run the real formal regression in WSL2 after startup. Start with a simple combinational ALU case, then a counter with an explicit independent specification. Confirm a reachable mutation produces a base-case FAIL and that an induction-step-only failure is reported UNKNOWN.
7. Do not treat the previous FIFO `count` PASS/FAIL results as valid evidence; they were generated before the internal-net binding issue was fixed.

**Build 14 is an integrity hardening milestone, not the final research release.** Internal-state instrumentation and a real WSL2 FIFO regression remain necessary before claiming broad FIFO verification.
