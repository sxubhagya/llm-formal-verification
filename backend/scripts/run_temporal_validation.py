"""Run the Build 11.1 temporal-operator validation suite against real Yosys/SBY.

Run from the project root:
    python backend/scripts/run_temporal_validation.py

The suite uses hand-authored properties. It does not call Gemini.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models.formal_models import FormalVerificationRequest, ProofMode, SolverEngine
from backend.app.models.property_models import (
    AssertionLanguage,
    CandidateProperty,
    ClockContext,
    PropertyBatch,
    PropertyCategory,
    PropertyProvenance,
    ResetContext,
    SignalReference,
)
from backend.app.services.formal.verification_service import FormalVerificationService
from backend.app.services.hdl.parser import HDLAnalysisService


RTL_PATH = PROJECT_ROOT / "rtl" / "examples" / "counter_sync" / "counter_sync.sv"
TOP = "counter_sync"


def build_property(property_id: str, name: str, expression: str) -> CandidateProperty:
    return CandidateProperty(
        property_id=property_id,
        design_top=TOP,
        module=TOP,
        name=name,
        description=f"Build 11.1 manually authored temporal validation: {name}",
        category=PropertyCategory.TEMPORAL,
        assertion_language=AssertionLanguage.SVA,
        expression=expression,
        signals=[
            SignalReference(name="clk", expected_width=1),
            SignalReference(name="rst_n", expected_width=1),
            SignalReference(name="enable", expected_width=1),
            SignalReference(name="count", expected_width=8),
        ],
        clock=ClockContext(signal="clk", edge="posedge"),
        reset=ResetContext(
            signal="rst_n",
            polarity="active_low",
            asynchronous=False,
        ),
        provenance=PropertyProvenance(
            generator="manual_validation_suite",
            generation_notes="Authored independently of the RTL implementation for temporal-engine validation.",
        ),
    )


CASES = [
    (
        "past_depth_2",
        "$past(expr, 2): count is unchanged across two cycles of disable",
        "((rst_n && $past(rst_n) && $past(rst_n, 2)) && "
        "(!enable && $past(!enable) && $past(!enable, 2))) "
        "|-> (count == $past(count, 2))",
    ),
    (
        "stable_next_cycle",
        "$stable(expr): count remains stable after a disabled cycle",
        "disable iff (!rst_n) (rst_n && !enable) |=> ($stable(count))",
    ),
    (
        "rose_enable",
        "$rose(signal): a rising enable edge follows a disabled sample",
        "(rst_n && $past(rst_n) && $rose(enable)) "
        "|-> (count == $past(count))",
    ),
    (
        "fell_enable",
        "$fell(signal): a falling enable edge follows an enabled sample",
        "(rst_n && $past(rst_n) && $fell(enable)) "
        "|-> (count == ($past(count) + 8'd1))",
    ),
    (
        "overlapped_implication",
        "|->: same-sample consequent after two disabled samples",
        "(rst_n && $past(rst_n) && !enable && $past(!enable)) "
        "|-> (count == $past(count))",
    ),
    (
        "non_overlapped_implication",
        "|=>: count reflects the increment on the preceding enabled sample",
        "disable iff (!rst_n) (rst_n && enable) "
        "|=> (count == ($past(count) + 8'd1))",
    ),
    (
        "reset_enable_priority",
        "Reset dominates enable when both are asserted on the same sampled edge",
        "(!rst_n && enable) |=> (count == 8'd0)",
    ),
    (
        "disable_iff_mask",
        "disable iff: reset samples are masked; deasserted samples satisfy rst_n",
        "disable iff (!rst_n) (rst_n)",
    ),
]


def main() -> int:
    if not RTL_PATH.is_file():
        print(f"ERROR: benchmark RTL not found: {RTL_PATH}")
        return 2

    print("Build 11.1 — Temporal Validation Harness")
    print(f"RTL: {RTL_PATH.relative_to(PROJECT_ROOT)}")
    print("LLM: not used (all properties are manually authored)")
    print("Formal backend: Yosys + SymbiYosys + Z3")
    print()

    try:
        design_ir, _yosys_log = HDLAnalysisService().analyze([RTL_PATH], TOP)
    except Exception as exc:
        print(f"DESIGN ANALYSIS ERROR: {exc}")
        return 2

    failures = []
    for index, (case_id, description, expression) in enumerate(CASES, start=1):
        prop = build_property(f"TEMPORAL_{case_id.upper()}", case_id, expression)
        batch = PropertyBatch(
            batch_id=f"build11_1_{case_id}",
            design_top=TOP,
            properties=[prop],
        )
        request = FormalVerificationRequest(
            design_ir=design_ir,
            verilog_sources={"counter_sync.sv": RTL_PATH.read_text(encoding="utf-8")},
            property_batch=batch,
            top_module=TOP,
            proof_mode=ProofMode.PROVE,
            depth=20,
            solver=SolverEngine.Z3,
            timeout_seconds=120,
        )
        try:
            response = FormalVerificationService().verify(request)
            result = response.results[0]
            passed = result.status.value == "pass"
            print(f"[{index}/{len(CASES)}] {case_id}: {result.status.value.upper()} "
                  f"({result.proof_scope}, {result.execution_time_seconds:.2f}s)")
            print(f"    {description}")
            if not passed:
                failures.append((case_id, result.status.value, result.log_snippet or "No log detail"))
                print(f"    DETAILS: {(result.log_snippet or '')[-700:]}")
        except Exception as exc:
            failures.append((case_id, "error", str(exc)))
            print(f"[{index}/{len(CASES)}] {case_id}: ERROR — {exc}")

    print()
    print(f"RESULT: {len(CASES) - len(failures)}/{len(CASES)} expected PASS")
    if failures:
        print("Cases requiring investigation:")
        for case_id, status, detail in failures:
            print(f"- {case_id}: {status}: {detail}")
        return 1
    print("All temporal validation cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
