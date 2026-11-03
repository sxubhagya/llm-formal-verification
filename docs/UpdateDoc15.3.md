# UpdateDoc15.3 — Windows-to-WSL Probe Conversion Path Fix

**Date:** 2 November 2026  
**Base:** Build 15.2 project package  
**Purpose:** Fix the confirmed Windows-path leakage into the Yosys conversion script when Yosys is launched through WSL.

## Confirmed root cause

The user's Build 15.2 diagnostic showed that the conversion command launched Yosys inside Ubuntu WSL, but the generated `convert.ys` contained Windows paths:

```text
read_json "C:/Users/fateh/AppData/Local/Temp/.../instrumented.json"
hierarchy -check -top sync_fifo
write_verilog -noattr "C:/Users/fateh/AppData/Local/Temp/.../instrumented_design.v"
```

Yosys 0.33 returned code 1 because it could not open the Windows-style JSON path from inside Linux. The same path issue affected the output target. All properties failed before formal execution because each property went through this common instrumentation/conversion path.

## Code changes

### `backend/app/services/hdl/yosys_probe_instrumenter.py`

- When the configured runner uses WSL, translate `instrumented.json` and `instrumented_design.v` with `YosysRunner._wsl_path()`.
- Embed the translated `/mnt/<drive>/...` paths in the `read_json` and `write_verilog` commands in `convert.ys`.
- Retain resolved host paths for native execution.
- Quote/escape the translated paths for Yosys script syntax.
- Keep the existing WSL script invocation and detailed failure diagnostics.

### Regression coverage

Added a WSL-mode test that verifies:
- `read_json` references the translated Linux path;
- `write_verilog` references the translated Linux output path;
- Windows drive paths do not appear in the conversion script;
- the instrumented netlist is returned through the host-side temporary file in the test harness.

### Versioning

- Frontend footer: Build 15.3.
- FastAPI version: 0.9.3.

## Validation completed

- Focused Yosys runner and probe instrumenter tests: **8 passed**.
- Complete backend test suite: **114 passed, 4 parameterized subtests passed**.
- Python compilation: passed.
- Actual Yosys 0.33 / SBY / Z3 execution through the user's Windows-to-WSL application path: **not yet run after this patch**.

## What this update does not claim

- It does not claim that the FIFO formal batch has passed.
- It does not implement memory-array probing or prove FIFO data ordering/storage.
- It does not change the FIFO RTL, independent specification, generated property batch, or formal semantics.
- It does not change the initial-reset assumption policy.

## Installation and test instructions

1. Stop frontend and backend servers.
2. Extract the Build 15.3 ZIP over the existing project folder.
3. Preserve `.env`, `.venv`, `.venv-wsl`, and `frontend/node_modules`; these are not included in the ZIP.
4. Restart backend and frontend.
5. In Ubuntu WSL, run:

```bash
python backend/scripts/run_internal_probe_smoke.py
```

6. Return to the application and rerun the same FIFO property batch against the unchanged FIFO RTL and approved specification. Do not regenerate the candidates.
7. Share the results. If conversion now succeeds, we will evaluate actual property outcomes and separately address memory/data-path coverage.
