# UpdateDoc13.1 — Property Coverage, Formal Execution, and Evidence Recovery

**Project:** LLM-Assisted RISC Formal Verification Framework  
**Release:** Build 13.1  
**Base:** User-provided Build 13 project folder  
**Date:** 1 November 2026

## 1. Purpose

Build 13.1 addresses three issues observed during the FIFO and 32-bit RISC ALU demonstrations:

1. The LLM could return a small subset of properties even when the approved specification contained many requirements, and the application did not make missing requirement coverage sufficiently visible.
2. Formal properties were executed serially, with a 120-second per-property timeout that was not passed through from the request. A batch of ten properties could therefore appear frozen for a long time.
3. Saved experiment history did not restore the RTL workspace, and counterexample VCD files were not retained in the run archive or exposed through a download endpoint.

This release improves these paths without treating LLM-generated requirement IDs as proof of semantic coverage.

## 2. LLM property generation and requirement coverage

### 2.1 Stronger generation instructions

- Prompt version advanced from 2.1 to 2.2.
- The prompt now makes requirement coverage a hard objective when the configured maximum allows it.
- It explicitly prohibits using a merely related signal-definition check as a substitute for a behavioural requirement.
- It asks the model to reason about guards, state transitions, outputs, and temporal relationships for each requirement.
- It distinguishes protocol requirements (accepted/rejected transactions) from simple output-definition requirements.

### 2.2 Bounded coverage-repair pass

After the initial LLM response, the backend computes which specification requirement IDs have no candidate reference. For non-mock providers, it can make up to two additional targeted requests for the missing requirements, subject to the configured maximum property count. Duplicate property IDs and invalid requirement references are not merged.

No assertion is fabricated locally. If requirements remain uncovered, the response contains an explicit warning and the UI shows the uncovered requirement IDs.

**Important limitation:** requirement-ID mapping is traceability metadata. Neither the mapping nor the retry mechanism proves that an expression fully captures a requirement. Human review and formal verification remain necessary. The framework reports reference coverage, not semantic coverage.

### 2.3 Default generation limit

The backend default maximum increased from 5 to 12, matching the existing frontend default. The UI continues to permit an explicit maximum up to 20.

## 3. Formal verification execution

### 3.1 Bounded concurrency

Independent property jobs now execute in a thread pool with at most three concurrent SBY workers. Results are returned in the original property order. Each job retains its own wrapper, task name, work directory, solver result, and trace.

### 3.2 Per-property timeout

- The formal request default is now 45 seconds per property (configurable between 5 and 180 seconds by the API).
- The frontend exposes a timeout selector: 15, 30, 45, 60, 90, or 120 seconds.
- The configured timeout is passed to the SBY runner.
- Timeout results remain `TIMEOUT`; they are never converted to PASS.
- Partial process output is decoded safely when a subprocess timeout occurs.

The frontend displays the property count, worker limit, and timeout while a run is active. This is a bounded synchronous request, not a live per-property progress stream. Ten properties can still take multiple timeout windows if several are difficult; the UI no longer implies that an unlimited run is progressing normally.

## 4. Experiment history and counterexample evidence

### 4.1 Workspace restoration

Completed run records now include the RTL source text in addition to the source hashes and saved RTL copies. Selecting a history entry restores:

- RTL source and top-module name;
- analysed DesignIR;
- approved behavioural specification and reviewer;
- generated property batch;
- formal results.

The application returns to the Custom RTL workspace with the saved inputs populated rather than navigating to an empty workspace.

### 4.2 VCD persistence and download

When a failed property has a VCD trace, the run store copies it into that experiment's `traces/` directory. The saved verification result points to a download endpoint:

`GET /api/formal/runs/{run_id}/traces/{property_id}`

The UI exposes a **Download counterexample trace** link and displays the parsed signal/frame values when available. Existing records without saved trace artifacts remain readable; they simply have no trace download.

## 5. Frontend changes

- Added a requirement-reference coverage summary above the generated candidate list.
- Displays requirement IDs with no generated candidate reference.
- Displays generation warnings so incomplete coverage is visible before verification.
- Added configurable per-property formal timeout.
- Added counterexample trace download and compact signal-value table.
- History selection now restores the RTL and specification fields.
- Updated application footer version to Build 13.1.

## 6. Files changed

### Backend

- `backend/app/services/llm/prompt_builder.py`
- `backend/app/services/llm/property_generator.py`
- `backend/app/models/property_models.py`
- `backend/app/models/formal_models.py`
- `backend/app/services/formal/verification_service.py`
- `backend/app/services/formal/sby_runner.py`
- `backend/app/services/formal/run_store.py`
- `backend/app/api/formal.py`

### Frontend

- `frontend/src/App.jsx`
- `frontend/src/styles.css`

### Tests and documentation

- `backend/tests/test_build13_1_regressions.py`
- `UpdateDoc13_1.md`
- `docs/UpdateDoc13_1.md`

## 7. Validation performed

| Check | Result |
|---|---|
| Python compilation | Passed |
| Existing backend test suite | 82 passed, 4 subtests passed |
| New Build 13.1 regression tests | 4 passed |
| Combined backend test suite | 86 passed, 4 subtests passed |
| JSX parsing (`App.jsx`, `main.jsx`) | Passed |
| Automated regression: VCD copy, trace URL, RTL source restoration | Passed |
| Full Vite production build | Not completed in this environment |
| Real SBY/Yosys/Z3 end-to-end execution | Not available in this build environment; must be tested in the user's WSL installation |

The uploaded `node_modules` directory contains Windows-native optional binaries, so the Linux Vite build could not run here (`@rollup/rollup-linux-x64-gnu` and Linux esbuild binary are absent). Do not treat JSX parsing as a substitute for a production build. On the user's Windows environment, run `npm.cmd install` if dependencies need refreshing, then `npm.cmd run build`.

## 8. Installation

1. Stop the existing backend and frontend processes.
2. Back up the current project folder.
3. Extract the Build 13.1 ZIP over a clean copy of the project.
4. Preserve the user's `.env` file and API keys; `.env` is intentionally excluded from the ZIP.
5. Preserve `.venv` and `frontend/node_modules` if desired, but if frontend dependency errors occur, reinstall dependencies using `npm.cmd install` from the `frontend` directory.
6. Start the backend and frontend using the existing project instructions.
7. Test property generation on the FIFO and inspect the requirement coverage panel. If some requirements remain uncovered, the application should explicitly identify them.
8. Run the FIFO and 32-bit ALU formal batches. Confirm that the result completes or returns individual TIMEOUT statuses rather than remaining indefinitely in the running state.
9. Open a failed property, download its counterexample trace, and verify that selecting its history entry restores the original RTL and specification.

## 9. Known limitations and interpretation

- LLM generation is nondeterministic. The two targeted supplements improve requirement coverage but cannot guarantee that every requirement is representable or correctly formalised. The UI explicitly reports uncovered requirement IDs.
- A requirement reference does not establish semantic coverage. Human review remains essential.
- Formal execution remains a synchronous API request with bounded concurrency and per-property timeouts; it is not yet a background job with live per-property progress/cancellation.
- The checker still supports only its documented restricted Boolean/SVA subset, not full IEEE 1800 SVA.
- Vacuity remains `NOT_CHECKED`.
- BMC PASS is bounded to the selected depth; it is not an unbounded proof.
- No real SBY/Yosys end-to-end run was possible in this build environment. The FIFO and 32-bit ALU must be rerun under the user's WSL formal-tool installation before the release is described as end-to-end verified.

## 10. Research integrity

The framework continues to separate the approved behavioural specification from the RTL implementation. The LLM proposes candidate properties; structural validation checks signal references and widths; SBY and the selected solver determine formal outcomes. The system must not convert missing coverage, timeout, unsupported syntax, or an unverified property into PASS.
