# UpdateDoc9 — Frontend Workbench and Stabilisation Release

**Build status:** Frontend inherited from the partner's Build 9 workbench and corrected where source inspection identified integration defects. Backend stabilisation tests pass. A production frontend build could not be rerun because npm registry packages were unavailable in the packaging environment.

## Objective
Provide a React/Vite workbench for RTL analysis, LLM candidate generation, assumption review, formal execution configuration, and per-property result display.

## Inherited Build 9 functionality
- Benchmark selection and RTL editor.
- Design analysis and IR display.
- Mock/Gemini/OpenAI provider selection.
- Candidate property generation.
- Assumption review controls.
- Formal proof mode, solver, and depth selection.
- Result summary and synthesized checker display.

## Changes made in this stabilisation update

### Backend and formal safety
- Replaced unsafe implication string splitting with a conservative Boolean-expression checker.
- Rejected temporal SVA and system functions until a semantics-preserving compiler exists.
- Required property-specific clock context for sequential modules; no guessed `clk` fallback.
- Injected only accepted assumptions with reviewer identity.
- Ran properties independently.
- Prevented mock or missing-tool paths from returning PASS.
- Disabled cover-only mode until independent cover generation and witness parsing are implemented.
- Set vacuity status to NOT_CHECKED.
- Added explicit proof-scope metadata for bounded and inductive runs.
- Added safe path, identifier, source-size, and batch-size checks.
- Added provider-specific credential selection and Gemini header authentication.
- Added `httpx` to backend requirements.
- Added health route compatibility at both `/health` and `/api/health`.
- Restricted CORS to local Vite origins and disabled credentialed wildcard CORS.

### Frontend
- Removed browser-side API-key entry. Provider credentials are read by the backend from `.env`.
- Removed fake fallback DesignIR generation when RTL analysis fails.
- Made the analysis handler return the actual analysed IR and use it directly in the generation request, avoiding stale React state.
- Changed generation messaging to show rejected-property counts and clarify that generation is not proof.
- Added explicit reviewer identity entry before assumption acceptance/rejection.
- Replaced the hardcoded DESIGN VALID badge with actual validation counts.
- Updated result display to show proof scope and NOT_CHECKED vacuity state.
- Disabled the cover option in the UI because cover execution is not implemented.

## Verification evidence

Command:
```powershell
python -m unittest discover -s backend/tests -v
```

Result: **46 tests passed**.

Additional smoke checks:
- `python -m compileall -q backend` completed successfully.
- `GET /api/health` returned HTTP 200.
- `GET /health` returned HTTP 200.
- `GET /openapi.json` returned HTTP 200.
- A direct runner check with formal tools unavailable returned `INVALID`, not PASS.
- Mock runner returns `UNKNOWN`, not PASS.
- Unsafe source paths and expression-injection attempts were rejected.

## Not verified in this environment
- Real Yosys/SBY/Z3 execution and proof outcomes.
- Real Windows-to-WSL invocation after the new SBY runner changes.
- Live Gemini/OpenAI API calls.
- Production frontend build. `npm ci --offline` failed because the required `yallist` package was not present in the local npm cache and network access to the npm registry was unavailable.

## Known limitations retained deliberately
- Temporal SVA compilation and correct implication/delay semantics are not implemented.
- Asynchronous reset-edge assertions are not supported by the current checker subset.
- Independent cover task generation/witness parsing and vacuity analysis are not implemented.
- Formal source text is not yet cryptographically bound to the DesignIR using a persistent source manifest/hash.
- Formal job concurrency/resource quotas and artifact retention policy need further work.
- Full COI extraction and VCD counterexample parsing are future work.
- BMC PASS is bounded and must not be described as unbounded proof.

## Deviations from the original Build 7–9 plan
- The checker has been deliberately narrowed to a safe same-sample Boolean subset. This reduces functionality compared with the inherited temporal-SVA ambition, but avoids unsound translation of `|->` and `|=>`.
- Cover mode and vacuity claims have been disabled rather than left in a misleading partially implemented state.
- Mock formal execution is now explicitly non-proof (`UNKNOWN`).
- Formal properties are run independently instead of sharing one batch-level result.

## Release conclusion
This is a **hardened Build 9 candidate** with 46 passing backend tests and fail-closed safeguards. It is not yet a fully cross-platform, real-solver-verified release because real WSL/SBY execution and the frontend production build could not be run in the packaging environment. Complete the manual Windows/WSL verification steps before pushing it as a fully validated stable release.
