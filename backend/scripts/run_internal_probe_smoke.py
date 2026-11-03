"""Native WSL formal smoke test for Yosys-netlist internal signal probes.

Run from the repository root with the WSL project virtualenv active:
    python backend/scripts/run_internal_probe_smoke.py

The test requires a real Yosys, SymbiYosys and Z3 installation. It checks both
that a true internal-state relation proves and that a deliberately false
relation produces a reachable counterexample.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.models.design_ir import DesignIR
from backend.app.models.property_models import (
    CandidateProperty, PropertyBatch, PropertyCategory, AssertionLanguage,
    SignalReference, ClockContext,
)
from backend.app.models.formal_models import ProofMode, SolverEngine
from backend.app.services.hdl.yosys_runner import YosysRunner
from backend.app.services.hdl.ir_builder import build_design_ir
from backend.app.services.hdl.yosys_probe_instrumenter import YosysProbeInstrumenter
from backend.app.services.formal.checker_synthesizer import CheckerSynthesizer
from backend.app.services.formal.sby_runner import SBYRunner


def main() -> int:
    missing = [tool for tool in ("yosys", "sby", "z3") if shutil.which(tool) is None]
    if missing:
        print("Missing required tools: " + ", ".join(missing))
        print("Run this script inside Ubuntu WSL, not Windows PowerShell.")
        return 2

    rtl = """module probe_demo(input wire clk, input wire [1:0] in_value, output wire [1:0] out_value);
    reg [1:0] state;
    always @(posedge clk) state <= in_value;
    assign out_value = state;
endmodule
"""
    with tempfile.TemporaryDirectory(prefix="formal_internal_probe_") as tmp:
        work = Path(tmp)
        rtl_path = work / "probe_demo.sv"
        json_path = work / "design.json"
        rtl_path.write_text(rtl, encoding="utf-8")
        YosysRunner(mode="native").run([rtl_path], "probe_demo", json_path)
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        design = build_design_ir(raw, ["probe_demo.sv"], "probe_demo")

        instrumented = YosysProbeInstrumenter(mode="native").instrument(
            {"probe_demo.sv": rtl}, "probe_demo", ["state"]
        )
        if "state" not in instrumented.probe_ports:
            print("FAIL: Instrumenter did not return a probe port for state.")
            return 1
        if "dut.state" in instrumented.netlist_source:
            print("FAIL: Instrumented netlist unexpectedly relies on hierarchical references.")
            return 1

        def run_property(task: str, expression: str):
            prop = CandidateProperty(
                property_id=f"P_{task.upper()}",
                design_top="probe_demo",
                module="probe_demo",
                name=f"Internal state relation {task}",
                description="Checks an explicitly instrumented internal state signal.",
                category=PropertyCategory.INVARIANT,
                assertion_language=AssertionLanguage.BOOLEAN,
                expression=expression,
                signals=[
                    SignalReference(name="out_value", expected_width=2),
                    SignalReference(name="state", expected_width=2),
                ],
                clock=ClockContext(signal="clk", edge="posedge"),
            )
            batch = PropertyBatch(
                batch_id=f"internal_probe_{task}",
                design_top="probe_demo",
                properties=[prop],
            )
            checker = CheckerSynthesizer().synthesize(
                design, batch, internal_probe_ports=instrumented.probe_ports
            )
            if "dut.state" in checker.wrapper_source_code:
                raise AssertionError("Checker still uses a hierarchical internal reference.")
            if f".{instrumented.probe_ports['state']}(state)" not in checker.wrapper_source_code:
                raise AssertionError("Checker does not connect the explicit probe output.")
            return SBYRunner(mode="native", timeout_seconds=60).run(
                task_name=f"internal_probe_{task}",
                sources={
                    "instrumented_design.v": instrumented.netlist_source,
                    f"{checker.wrapper_module_name}.sv": checker.wrapper_source_code,
                },
                top_module=checker.wrapper_module_name,
                proof_mode=ProofMode.PROVE,
                depth=10,
                solver=SolverEngine.Z3,
                work_dir=work / f"sby_{task}",
            )

        true_run = run_property("true", "out_value == state")
        false_run = run_property("false", "out_value != state")
        print(f"True relation result: {true_run.status.value}")
        print((true_run.stdout + "\n" + true_run.stderr)[-1800:])
        print(f"False relation result: {false_run.status.value}")
        print((false_run.stdout + "\n" + false_run.stderr)[-1800:])

        if true_run.status.value != "pass":
            print("FAIL: True internal-state relation was not proven.")
            return 1
        if false_run.status.value != "fail" or not false_run.vcd_trace_path:
            print("FAIL: Deliberately false relation did not produce a reachable counterexample.")
            return 1
        print("PASS: Yosys bit-level probe proves the true relation and rejects the false relation with a trace.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
