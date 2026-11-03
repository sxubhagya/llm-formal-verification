# UpdateDoc15.1 — Yosys-Netlist Internal Probe Correction

**Date:** 2 November 2026  
**Base:** Build 15, extracted from the user's Build 14 archive and corrected through Build 15  
**Release:** Build 15.1

## 1. Why this correction was necessary

The first Build 15 implementation generated wrapper aliases of the form `assign state = dut.state;`. The user's WSL test exposed that Yosys 0.33 parsed the hierarchy but the resulting formal model did not preserve the intended connection. The VCD showed the DUT's `state` and `out_value` equal while the wrapper-level `state` alias was zero. The true relation therefore failed at the base case.

This was a real instrumentation defect, not an installation problem. The user's Yosys 0.33, SBY 0.70 and Z3 4.8.12 were installed and callable.

## 2. Architectural correction

Build 15.1 removes hierarchical internal-net aliases.

New flow for a property that references internal nets:

1. Write the supplied RTL source bundle to an isolated temporary directory.
2. Elaborate it once with Yosys into JSON using the configured Yosys runner.
3. Resolve each requested internal signal in the selected top module's `netnames` table.
4. Require a concrete, non-empty list of integer Yosys bit IDs. Missing names, constants/unknown bits and unsupported mappings fail closed.
5. Add uniquely named output ports (for example `__formal_probe_state`) to the top module's JSON `ports` object. Each added port receives a copy of the original net's exact `bits`, offset, `upto` and signedness metadata.
6. Read the instrumented JSON back into Yosys and convert it to a Verilog netlist.
7. Generate a formal wrapper that connects the DUT's explicit probe output port to the assertion signal.
8. Run SBY on the instrumented netlist and wrapper. The original RTL is not separately re-elaborated by SBY for that property.

This uses netlist bit identity rather than `dut.internal_signal` hierarchical references.

## 3. Files changed

- `backend/app/services/hdl/yosys_probe_instrumenter.py` — new Yosys JSON probe-port instrumentation and conversion service.
- `backend/app/services/formal/checker_synthesizer.py` — requires explicit probe-port mappings for internal signals; removes hierarchical aliases; fixes actual newline joining in generated module port declarations.
- `backend/app/services/formal/verification_service.py` — instruments internal signal references before checker synthesis and runs SBY against the generated netlist.
- `backend/scripts/run_internal_probe_smoke.py` — real WSL smoke test with one expected PASS and one expected reachable FAIL.
- `backend/tests/test_yosys_probe_instrumenter.py` — synthetic JSON bit-identity and fail-closed tests.
- `backend/tests/test_build14_integrity.py` — updated tests to require explicit probe mapping and reject the old alias route.
- `backend/app/main.py` — API version 0.9.1.
- `frontend/src/App.jsx` — footer build label.
- `docs/PROJECT_STATUS.md` — current status and limitations.

## 4. Tests and evidence

Executed in the assistant build environment:

- `pytest -q`: **111 passed, 4 parameterized subtests passed**.
- New unit tests confirm the instrumented JSON probe port uses exactly the original Yosys bit IDs and rejects constant/unknown mappings.
- Checker unit tests confirm internal references fail closed without a probe map and use explicit probe output connections when a map is supplied.

Not executed in the assistant environment:

- Actual Yosys 0.33 + SBY 0.70 + Z3 4.8.12 run (these binaries are not installed in the assistant environment).
- Full Vite production build.

## 5. Mandatory user-side test

In Ubuntu WSL, from the project root, with `.venv-wsl` active:

```bash
python backend/scripts/run_internal_probe_smoke.py
```

The script must report:
- true relation `out_value == state`: `pass`
- false relation `out_value != state`: `fail`, with a reachable base-case VCD
- final line: `PASS: Yosys bit-level probe proves the true relation and rejects the false relation with a trace.`

If either condition differs, stop and share the full output. Do not run FIFO verification until this smoke test passes.

## 6. Known limitations / not claimed

- Arbitrary memory-array contents are not exposed by this patch. The instrumenter currently supports named top-module nets with concrete Yosys bit IDs. Memory read/write port probes require a dedicated extension and regression tests.
- The new instrumentation path has not yet passed the user's real WSL smoke test. It is code-implemented and unit-tested, but not solver-validated at release time.
- FIFO baseline and mutation verification are still pending.
- This is not full IEEE SystemVerilog assertion support and does not establish complete RTL correctness.
- Probe outputs are observational aliases to existing Yosys bit IDs; however, the real toolchain smoke test is required to verify the Yosys JSON read/write round-trip and SBY model preserve this relation.

## 7. Installation notes

Extract the Build 15.1 ZIP over the project folder while preserving the user's `.env`, Windows `.venv`, WSL `.venv-wsl`, and `frontend/node_modules`. The ZIP deliberately excludes these environment-specific directories/files. Do not copy the ZIP's `.env.example` over the user's `.env`.
