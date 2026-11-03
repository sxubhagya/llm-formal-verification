# UpdateDoc15.2 — Yosys Conversion Diagnostics

**Date:** 2 November 2026  
**Base:** User-uploaded Build 15.1 project folder  
**Purpose:** Preserve the actual Yosys JSON-to-Verilog conversion failure so the FIFO issue can be diagnosed without guessing.

## Why this update exists

The Build 15.1 formal service caught per-property exceptions and displayed only `str(exc)`. Although `YosysExecutionError` already carried a return code and output, those details were discarded. As a result, all FIFO properties appeared INVALID with the same generic message, while the backend terminal showed only successful HTTP responses.

## Changes

1. **Conversion diagnostics in `yosys_probe_instrumenter.py`**
   - Captures the exact Yosys command.
   - Captures the working directory, generated Yosys script, instrumented JSON path and output Verilog target.
   - Preserves return code, stdout and stderr.
   - Handles conversion timeouts and preserves partial output.
   - Diagnostic context is assembled before the temporary directory is cleaned.

2. **Per-property error preservation in `verification_service.py`**
   - INVALID property results now include exception type.
   - `YosysExecutionError` return code and full diagnostic output are included in `log_snippet`.
   - This keeps each failure attached to its own property result and avoids confusion with unrelated design runs.

3. **Regression tests**
   - Synthetic Yosys conversion failure verifies that command/script/output details are retained.
   - Formal service diagnostic formatter verifies that the return code and tool output survive the service error boundary.

4. **Versioning**
   - Frontend footer: Build 15.2.
   - FastAPI version: 0.9.2.

## What this update does NOT claim

- It does not yet fix the root cause of the FIFO conversion failure.
- It does not change RTL, the independent FIFO specification, generated properties, SVA semantics, checker synthesis or proof interpretation.
- It does not add FIFO memory-array probing.
- It does not claim FIFO formal verification has passed.

## User validation required

After installing Build 15.2, rerun the exact same FIFO property batch against the same RTL and approved specification. If conversion fails, open the affected INVALID property's details and share the expanded diagnostic. The next correction will be based on the actual Yosys error. No property regeneration or RTL mutation is needed for this diagnostic run.

## Local validation

Pending execution of the complete backend test suite and Python compilation in the packaging environment. Real Yosys/SBY validation must be performed in the user's WSL environment.
