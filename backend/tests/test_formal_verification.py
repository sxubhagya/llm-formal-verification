"""Automated unit and integration tests for Build 8 formal verification pipeline."""
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.design_ir import (
    DesignIR, ModuleIR, PortIR, NetIR, ModuleSummaryIR
)
from backend.app.models.property_models import (
    PropertyBatch, CandidateProperty, PropertyCategory,
    AssertionLanguage, SignalReference, ClockContext, ResetContext,
    PropertyAssumption, AssumptionReviewStatus, VerificationStatus
)
from backend.app.models.formal_models import (
    ProofMode, SolverEngine, VacuityStatus,
    FormalVerificationRequest, FormalVerificationResponse
)
from backend.app.services.formal.checker_synthesizer import CheckerSynthesizer
from backend.app.services.formal.sby_runner import SBYRunner
from backend.app.services.formal.verification_service import FormalVerificationService


class TestFormalVerification(unittest.TestCase):
    def setUp(self):
        self.counter_design = DesignIR(
            top_module="counter",
            source_files=["counter.sv"],
            modules=[
                ModuleIR(
                    name="counter",
                    ports=[
                        PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                        PortIR(name="rst_n", direction="input", bit_width=1, bits=[2]),
                        PortIR(name="enable", direction="input", bit_width=1, bits=[3]),
                        PortIR(name="count", direction="output", bit_width=8, bits=list(range(4, 12))),
                    ],
                    clock_candidates=[{"name": "clk", "polarity": "posedge"}],
                    reset_candidates=[{"name": "rst_n", "polarity": "active_low"}],
                    summary=ModuleSummaryIR(port_count=4)
                )
            ]
        )

        self.counter_batch = PropertyBatch(
            batch_id="batch_counter_001",
            design_top="counter",
            properties=[
                CandidateProperty(
                    property_id="PROP_COUNT_RESET",
                    design_top="counter",
                    module="counter",
                    name="count_reset_zero",
                    description="When reset is active, count must be 0",
                    category=PropertyCategory.SAFETY,
                    assertion_language=AssertionLanguage.BOOLEAN,
                    expression="rst_n == 0 |-> count == 0",
                    signals=[
                        SignalReference(name="rst_n", expected_width=1),
                        SignalReference(name="count", expected_width=8)
                    ],
                    clock=ClockContext(signal="clk", edge="posedge"),
                    reset=ResetContext(signal="rst_n", polarity="active_low")
                ),
                CandidateProperty(
                    property_id="PROP_COUNT_INC",
                    design_top="counter",
                    module="counter",
                    name="count_increments_when_enabled",
                    description="When enabled, count increments by 1",
                    category=PropertyCategory.SAFETY,
                    assertion_language=AssertionLanguage.BOOLEAN,
                    expression="(enable && rst_n) |-> (count == $past(count) + 1'b1)",
                    signals=[
                        SignalReference(name="clk", expected_width=1),
                        SignalReference(name="rst_n", expected_width=1),
                        SignalReference(name="enable", expected_width=1),
                        SignalReference(name="count", expected_width=8)
                    ],
                    clock=ClockContext(signal="clk", edge="posedge"),
                    reset=ResetContext(signal="rst_n", polarity="active_low")
                )
            ]
        )

    def test_checker_synthesizer_implication_and_vacuity(self):
        synth = CheckerSynthesizer(check_vacuity=True)
        res = synth.synthesize(self.counter_design, self.counter_batch)

        self.assertEqual(res.wrapper_module_name, "formal_counter")
        self.assertTrue(res.has_clock)
        self.assertEqual(res.clock_signal, "clk")
        self.assertEqual(res.reset_signal, "rst_n")
        self.assertEqual(len(res.properties), 2)

        code = res.wrapper_source_code
        self.assertIn("module formal_counter", code)
        self.assertIn("counter dut (", code)
        self.assertIn("`ifdef FORMAL", code)
        self.assertIn("reg f_past_valid = 1'b0;", code)
        self.assertIn("cover(", code)
        self.assertIn("assert(", code)
        self.assertIn("if (!rst_n)", code)

    def test_checker_synthesizer_combinational(self):
        alu_design = DesignIR(
            top_module="comb_alu",
            source_files=["comb_alu.v"],
            modules=[
                ModuleIR(
                    name="comb_alu",
                    ports=[
                        PortIR(name="a", direction="input", bit_width=8),
                        PortIR(name="b", direction="input", bit_width=8),
                        PortIR(name="op", direction="input", bit_width=3),
                        PortIR(name="out", direction="output", bit_width=8),
                    ],
                    summary=ModuleSummaryIR(port_count=4)
                )
            ]
        )
        alu_batch = PropertyBatch(
            batch_id="batch_alu_001",
            design_top="comb_alu",
            properties=[
                CandidateProperty(
                    property_id="PROP_ALU_ADD",
                    design_top="comb_alu",
                    module="comb_alu",
                    name="alu_addition",
                    description="Addition operation",
                    category=PropertyCategory.COMBINATIONAL,
                    assertion_language=AssertionLanguage.BOOLEAN,
                    expression="op == 3'b000 |-> out == a + b",
                    signals=[
                        SignalReference(name="a", expected_width=8),
                        SignalReference(name="b", expected_width=8),
                        SignalReference(name="op", expected_width=3),
                        SignalReference(name="out", expected_width=8),
                    ]
                )
            ]
        )
        synth = CheckerSynthesizer(check_vacuity=True)
        res = synth.synthesize(alu_design, alu_batch)
        self.assertFalse(res.has_clock)
        self.assertIn("always @(*)", res.wrapper_source_code)
        self.assertIn("assert(out == a + b)", res.wrapper_source_code)

    def test_checker_synthesizer_assumptions(self):
        batch = PropertyBatch(
            batch_id="batch_asm",
            design_top="counter",
            properties=[
                CandidateProperty(
                    property_id="PROP_WITH_ASM",
                    design_top="counter",
                    module="counter",
                    name="test_with_assumption",
                    description="Counter bounded input test",
                    category=PropertyCategory.SAFETY,
                    assertion_language=AssertionLanguage.BOOLEAN,
                    expression="count < 8'hff",
                    signals=[SignalReference(name="count", expected_width=8)],
                    assumptions=[
                        PropertyAssumption(
                            assumption_id="ASM_STABLE",
                            statement="enable == 1'b1",
                            rationale="Constrain enable high for test",
                            status=AssumptionReviewStatus.PROPOSED
                        )
                    ]
                )
            ]
        )
        synth = CheckerSynthesizer()
        res = synth.synthesize(self.counter_design, batch)
        self.assertIn("assume(enable == 1'b1);", res.wrapper_source_code)

    def test_sby_config_generation(self):
        runner = SBYRunner()
        cfg = runner.generate_sby_config(
            top_module="formal_counter",
            source_filenames=["counter.sv", "formal_counter.sv"],
            proof_mode=ProofMode.PROVE,
            depth=25,
            solver=SolverEngine.Z3
        )
        self.assertIn("mode prove", cfg)
        self.assertIn("depth 25", cfg)
        self.assertIn("smtbmc z3", cfg)
        self.assertIn("read -formal -sv counter.sv", cfg)
        self.assertIn("prep -top formal_counter", cfg)

    def test_sby_log_parser_pass(self):
        runner = SBYRunner()
        stdout = (
            "SBY 12:00:00 [task] engine_0 (smtbmc z3) starting...\n"
            "SBY 12:00:01 [task] summary: engine_0 (smtbmc z3) returned pass\n"
            "DONE (PASS, rc=0)\n"
        )
        status, failure_phase, vcd, witness = runner.parse_sby_output(
            stdout, "", Path("/tmp"), ProofMode.PROVE
        )
        self.assertEqual(status, VerificationStatus.PASS)
        self.assertIsNone(failure_phase)

    def test_sby_log_parser_fail_step(self):
        runner = SBYRunner()
        stdout = (
            "SBY [task] engine_0.basecase: returned pass\n"
            "SBY [task] engine_0.induction: induction step failed!\n"
            "DONE (FAIL, rc=2)\n"
        )
        status, failure_phase, vcd, witness = runner.parse_sby_output(
            stdout, "", Path("/tmp"), ProofMode.PROVE
        )
        self.assertEqual(status, VerificationStatus.FAIL)
        self.assertEqual(failure_phase, "step")

    def test_sby_log_parser_timeout(self):
        runner = SBYRunner()
        stdout = "DONE (TIMEOUT)\n"
        status, failure_phase, vcd, witness = runner.parse_sby_output(
            stdout, "", Path("/tmp"), ProofMode.PROVE
        )
        self.assertEqual(status, VerificationStatus.TIMEOUT)

    def test_verification_service_end_to_end_mock(self):
        service = FormalVerificationService(
            sby_runner=SBYRunner(mock_mode=True),
            check_vacuity=True
        )
        req = FormalVerificationRequest(
            design_ir=self.counter_design,
            verilog_sources={"counter.sv": "// dummy counter RTL"},
            property_batch=self.counter_batch,
            proof_mode=ProofMode.PROVE,
            depth=20,
            solver=SolverEngine.Z3
        )
        res = service.verify(req)
        self.assertEqual(res.overall_status, VerificationStatus.PASS)
        self.assertEqual(len(res.results), 2)
        self.assertEqual(res.results[0].status, VerificationStatus.PASS)
        self.assertEqual(res.results[0].vacuity_status, VacuityStatus.NON_VACUOUS)
        self.assertIn("formal_counter", res.synthesized_checker)

    def test_verification_service_invalid_property_rejected(self):
        invalid_batch = PropertyBatch(
            batch_id="batch_inv",
            design_top="counter",
            properties=[
                CandidateProperty(
                    property_id="PROP_BAD_SIG",
                    design_top="counter",
                    module="counter",
                    name="bad_signal_test",
                    description="References nonexistent signal",
                    category=PropertyCategory.SAFETY,
                    assertion_language=AssertionLanguage.BOOLEAN,
                    expression="phantom_signal == 1",
                    signals=[SignalReference(name="phantom_signal", expected_width=1)]
                )
            ]
        )
        service = FormalVerificationService(sby_runner=SBYRunner(mock_mode=True))
        req = FormalVerificationRequest(
            design_ir=self.counter_design,
            verilog_sources={"counter.sv": "// dummy"},
            property_batch=invalid_batch
        )
        res = service.verify(req)
        self.assertEqual(res.results[0].status, VerificationStatus.INVALID)
        self.assertIn("Design validation error", res.results[0].log_snippet)

    def test_api_formal_verify_endpoint(self):
        client = TestClient(app)
        payload = {
            "design_ir": self.counter_design.model_dump(),
            "verilog_sources": {"counter.sv": "module counter(input clk); endmodule"},
            "property_batch": self.counter_batch.model_dump(),
            "proof_mode": "prove",
            "depth": 15,
            "solver": "z3"
        }
        response = client.post("/api/formal/verify", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["batch_id"], "batch_counter_001")
        self.assertIn(data["overall_status"], ["pass", "fail", "unknown", "invalid"])
        self.assertEqual(len(data["results"]), 2)

    def test_risc_benchmark_synthesizer_coverage(self):
        # Test synthesis against RISC ALU
        alu_design = DesignIR(
            top_module="risc_alu",
            source_files=["risc_alu.sv"],
            modules=[
                ModuleIR(
                    name="risc_alu",
                    ports=[
                        PortIR(name="a", direction="input", bit_width=32),
                        PortIR(name="b", direction="input", bit_width=32),
                        PortIR(name="alu_op", direction="input", bit_width=4),
                        PortIR(name="out", direction="output", bit_width=32),
                        PortIR(name="zero", direction="output", bit_width=1),
                        PortIR(name="negative", direction="output", bit_width=1),
                        PortIR(name="overflow", direction="output", bit_width=1),
                        PortIR(name="carry", direction="output", bit_width=1),
                    ]
                )
            ]
        )
        alu_batch = PropertyBatch(
            batch_id="batch_risc_alu",
            design_top="risc_alu",
            properties=[
                CandidateProperty(
                    property_id="PROP_ZERO_FLAG",
                    design_top="risc_alu",
                    module="risc_alu",
                    name="zero_flag_invariant",
                    description="zero flag must equal (out == 0)",
                    category=PropertyCategory.INVARIANT,
                    assertion_language=AssertionLanguage.BOOLEAN,
                    expression="zero == (out == 32'b0)",
                    signals=[
                        SignalReference(name="out", expected_width=32),
                        SignalReference(name="zero", expected_width=1)
                    ]
                )
            ]
        )
        synth = CheckerSynthesizer()
        res = synth.synthesize(alu_design, alu_batch)
        self.assertEqual(res.wrapper_module_name, "formal_risc_alu")
        self.assertIn("assert(zero == (out == 32'b0));", res.wrapper_source_code)


if __name__ == "__main__":
    unittest.main()
