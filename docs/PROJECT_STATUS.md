# Project Status — Build 15.3

**Current package:** Build 15.3, correction to the Windows-to-WSL Yosys JSON conversion path, 2 November 2026.

Build 15.1 introduced explicit Yosys JSON netlist instrumentation for internal named-net probes. Build 15.2 added detailed conversion diagnostics. The user's Build 15.2 FIFO run exposed the exact defect: the conversion Yosys script was executed inside WSL but embedded Windows paths (`C:/Users/...`) in `read_json` and `write_verilog` commands. Yosys therefore could not open the JSON file. Build 15.3 translates both paths through `wslpath` before writing the conversion script.

| Area | Status | Evidence / qualification |
|---|---|---|
| Independent behavioural specification | Retained | Approval remains bound to exact specification content hash |
| Internal named-net observation | Implemented | Yosys JSON bit IDs are exposed through explicit top-level output ports |
| Windows-to-WSL conversion paths | Fixed in code | JSON input and Verilog output paths embedded in `convert.ys` are translated to WSL paths |
| Conversion diagnostics | Retained | Stage, command, working directory, script, return code, stdout and stderr remain available |
| WSL path regression test | Added | Confirms `read_json` and `write_verilog` use `/mnt/...` paths, not Windows drive paths |
| Internal memory-array observation | Not implemented | Memory read/write port and array-state instrumentation remain a separate task |
| Initial reset environment | Retained | Optional reviewer + rationale required; active reset assumed on first clock edge only; disabled by default |
| Arbitrary initial state warning | Retained | Sequential verification without a reset contract warns that initial state is unconstrained |
| Property count | LLM-selected | Backend ceiling is a safety limit, not a target |
| VCD trace persistence | Retained | Existing run-store behaviour |
| Frontend | Updated | Build label 15.3 |
| API | Updated | FastAPI version 0.9.3 |

## Root cause confirmed from user's Build 15.2 diagnostic

The failing script contained:

```text
read_json "C:/Users/fateh/AppData/Local/Temp/.../instrumented.json"
hierarchy -check -top sync_fifo
write_verilog -noattr "C:/Users/fateh/AppData/Local/Temp/.../instrumented_design.v"
```

Yosys 0.33 ran inside WSL and returned:

```text
ERROR: Can't open input file `C:/Users/.../instrumented.json' for reading: No such file or directory
```

The conversion stage now calls the existing `YosysRunner._wsl_path()` for both files and writes the resulting Linux paths into the Yosys script. Native execution continues to use resolved host paths.

## Local validation in the assistant environment

- Backend tests: **114 passed, 4 parameterized subtests passed**.
- Focused Yosys runner/instrumenter tests: **8 passed**.
- Python compilation: completed for backend source tree.
- Real Windows + WSL Yosys execution: not available in the assistant environment; must be confirmed by the user's WSL smoke test and FIFO run.
- Full frontend production build: not independently completed in this correction.

## Required user validation

1. Install Build 15.3 while preserving `.env`, `.venv`, `.venv-wsl`, and `frontend/node_modules`.
2. Run `python backend/scripts/run_internal_probe_smoke.py` in Ubuntu WSL. This confirms native-in-WSL register probing remains intact.
3. Run the same FIFO verification using the existing 12 properties, unchanged RTL, and unchanged approved specification. Do not regenerate properties.
4. If conversion succeeds, inspect individual property statuses. This only validates the register/control properties; it does not prove FIFO memory ordering or storage.

## Known limitations

- Internal probes are limited to named nets in the selected top module's Yosys JSON `netnames` with concrete bit IDs.
- Memory array contents are not directly probed. FIFO data storage, oldest-entry ordering and memory preservation need dedicated memory instrumentation or an equivalent formal reference model.
- A successful conversion does not guarantee every candidate property is semantically adequate. Property coverage and vacuity still require separate review.
- This release is not yet considered FIFO-validated.
