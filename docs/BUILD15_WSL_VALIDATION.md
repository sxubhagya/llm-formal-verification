# Build 15 — Required WSL formal smoke test

This test checks the most important Build 15 integration risk: whether the installed Yosys/SBY versions accept the generated hierarchical alias to a real internal DUT net.

## Run

Open Ubuntu WSL, navigate to the extracted project directory (the Windows Desktop path is usually available under `/mnt/c/Users/<WindowsUser>/Desktop/...`), activate the project's Python environment if used, then run:

```bash
python backend/scripts/run_internal_probe_smoke.py
```

The script requires `yosys`, `sby`, and `z3` on the Ubuntu PATH. It creates a tiny sequential RTL module with an internal register `state`, generates the checker using the same DesignIR and checker pipeline as the app, and asks SBY to prove `out_value == state`.

## Expected result

The final lines should include:

```text
Internal-net probe smoke result: pass
PASS: hierarchical internal-net probe elaborated and proved.
```

If the result is `invalid`, `unknown`, `fail`, or `timeout`, **do not rely on Build 15 internal-net properties yet**. Send the full terminal output. In particular, a parser/elaboration error involving `dut.state` means the hierarchical alias strategy is not supported by the installed toolchain and must be replaced with Yosys-netlist-level instrumentation.

## Then validate the FIFO

After the smoke test passes:

1. Load the FIFO RTL and its independent behavioural specification.
2. Analyse the RTL and confirm that the relevant named internal nets (for example `count`, `read_ptr`, and `write_ptr`) appear in the elaborated DesignIR.
3. Generate properties. Review each expression and requirement mapping; do not treat a requirement ID as proof of semantic correctness.
4. Run formal verification first with the initial-reset contract disabled. This is the unconstrained-initial-state model.
5. If the real integration environment guarantees reset active on the first clock edge, run again with the initial-reset contract enabled, selecting the structurally detected reset and entering a reviewer and rationale.
6. Compare the results and inspect counterexample traces. Do not add assumptions merely to make a property pass.

## Scope limitation

The smoke test validates named scalar/vector internal-net aliases. It does not validate direct observation of Verilog memory arrays. Build 15 reports that limitation explicitly; FIFO storage correctness must be checked through supported observable interfaces/state or deferred until memory-port instrumentation is implemented.
