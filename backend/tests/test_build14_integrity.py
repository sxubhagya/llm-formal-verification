import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.design_ir import DesignIR, ModuleIR, PortIR, NetIR, RegisterIR, ModuleSummaryIR
from backend.app.models.property_models import (
    CandidateProperty, PropertyBatch, PropertyCategory, AssertionLanguage,
    SignalReference, ClockContext, ResetContext
)
from backend.app.models.specification_models import DesignSpecification, BehaviouralRequirement
from backend.app.services.property_validation import validate_property_batch
from backend.app.services.formal.checker_synthesizer import CheckerSynthesizer
from backend.app.services.formal.verification_service import FormalVerificationService
from backend.app.services.hdl.yosys_runner import YosysExecutionError
from backend.app.services.formal.sby_runner import parse_vcd_trace, SBYRunner
from backend.app.services.llm.property_generator import _canonicalize_property_categories
from backend.app.models.formal_models import VerificationStatus, ProofMode, InitialResetContract


class Build14IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.design = DesignIR(
            top_module="fifo", source_files=["fifo.sv"],
            modules=[ModuleIR(
                name="fifo",
                ports=[
                    PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                    PortIR(name="rst_n", direction="input", bit_width=1, bits=[2]),
                    PortIR(name="full", direction="output", bit_width=1, bits=[3]),
                ],
                nets=[NetIR(name="count", bit_width=3, bits=[4,5,6])],
                registers=[RegisterIR(cell_name="count_reg", cell_type="$adff", clock_bits=[1], parameters={"CLK_POLARITY":"1"})],
                clock_candidates=[{"name":"clk","signal":"clk","bits":[1]}],
                summary=ModuleSummaryIR(port_count=3),
            )]
        )

    def make_prop(self, expression="full == 1'b0", signals=None, lang=AssertionLanguage.BOOLEAN):
        return CandidateProperty(
            property_id="P1", design_top="fifo", module="fifo", name="test property",
            description="Integrity regression property", category=PropertyCategory.INVARIANT,
            assertion_language=lang, expression=expression,
            signals=signals or [SignalReference(name="full", expected_width=1)],
            clock=ClockContext(signal="clk", edge="posedge"),
        )

    def test_internal_net_is_validated_against_exact_design_ir_width(self):
        prop = self.make_prop("count <= 3'd4", [SignalReference(name="count", expected_width=3)])
        batch = PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
        result = validate_property_batch(self.design, batch).results[0]
        self.assertTrue(result.design_valid)
        self.assertFalse(result.issues)

    def test_internal_net_is_explicitly_aliased_to_dut_hierarchy(self):
        prop = self.make_prop("count <= 3'd4", [SignalReference(name="count", expected_width=3)])
        batch = PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
        with self.assertRaisesRegex(ValueError, "no Yosys-generated probe port"):
            CheckerSynthesizer().synthesize(self.design, batch)
        result = CheckerSynthesizer().synthesize(
            self.design, batch, internal_probe_ports={"count": "__formal_probe_count"}
        )
        self.assertIn("wire [2:0] count;", result.wrapper_source_code)
        self.assertIn(".__formal_probe_count(count)", result.wrapper_source_code)
        self.assertNotIn("dut.count", result.wrapper_source_code)
        self.assertIn("assert (count <= 3'd4)", result.wrapper_source_code)

    def test_reviewer_approved_initial_reset_contract_is_explicitly_assumed_once(self):
        design = self.design.model_copy(deep=True)
        design.modules[0].registers[0].reset_bits = [2]
        design.modules[0].registers[0].parameters["ARST_POLARITY"] = "0"
        design.modules[0].reset_candidates = [{
            "name": "rst_n", "signal": "rst_n", "bits": [2], "kind": "asynchronous"
        }]
        contract = InitialResetContract(
            signal="rst_n", polarity="active_low",
            reviewed_by="hardware designer",
            rationale="The integration environment asserts reset before releasing the design."
        )
        prop = self.make_prop("count <= 3'd4", [
            SignalReference(name="count", expected_width=3)
        ])
        result = CheckerSynthesizer().synthesize(
            design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop]),
            initial_reset_contract=contract,
            internal_probe_ports={"count": "__formal_probe_count"},
        )
        self.assertIn("assume (!rst_n)", result.wrapper_source_code)
        self.assertIn("formal_initial_reset_seen", result.wrapper_source_code)
        self.assertIn("if (formal_initial_reset_seen)", result.wrapper_source_code)

    def test_nonzero_port_index_range_is_preserved_in_wrapper(self):
        design = self.design.model_copy(deep=True)
        design.modules[0].ports[-1] = PortIR(name="full", direction="output", bit_width=4, bits=[3,4,5,6], offset=8)
        prop = self.make_prop("full[8] == 1'b0", [SignalReference(name="full", expected_width=4)])
        result = CheckerSynthesizer().synthesize(
            design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
        )
        self.assertIn("output wire [11:8] full", result.wrapper_source_code)

    def test_out_of_range_port_select_is_rejected(self):
        design = self.design.model_copy(deep=True)
        design.modules[0].ports[-1] = PortIR(name="full", direction="output", bit_width=4, bits=[3,4,5,6], offset=8)
        prop = self.make_prop("full[3] == 1'b0", [SignalReference(name="full", expected_width=4)])
        with self.assertRaisesRegex(ValueError, "outside the declared port index range"):
            CheckerSynthesizer().synthesize(
                design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
            )

    def test_reset_polarity_mismatch_is_rejected(self):
        design = self.design.model_copy(deep=True)
        design.modules[0].registers[0].reset_bits = [2]
        design.modules[0].registers[0].parameters["ARST_POLARITY"] = "0"
        design.modules[0].reset_candidates = [{"name": "rst_n", "signal": "rst_n", "bits": [2], "kind": "asynchronous"}]
        prop = self.make_prop("disable iff (rst_n) full == 1'b0", [
            SignalReference(name="full", expected_width=1),
            SignalReference(name="rst_n", expected_width=1),
        ], AssertionLanguage.SVA)
        prop.reset = ResetContext(
            signal="rst_n", polarity="active_high", asynchronous=True
        )
        with self.assertRaisesRegex(ValueError, "Reset polarity mismatch"):
            CheckerSynthesizer().synthesize(
                design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
            )

    def test_explicit_clock_edge_mismatch_is_rejected(self):
        prop = self.make_prop()
        prop.clock = ClockContext(signal="clk", edge="negedge")
        with self.assertRaisesRegex(ValueError, "Clock edge mismatch"):
            CheckerSynthesizer().synthesize(
                self.design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
            )

    def test_signal_names_containing_dollar_are_not_mistaken_for_system_tasks(self):
        design = self.design.model_copy(deep=True)
        design.modules[0].ports.append(PortIR(name="data$valid", direction="input", bit_width=1, bits=[7]))
        prop = self.make_prop(
            "data$valid == 1'b1",
            [SignalReference(name="data$valid", expected_width=1)],
        )
        result = CheckerSynthesizer().synthesize(
            design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
        )
        self.assertIn("assert (data$valid == 1'b1)", result.wrapper_source_code)

    def test_signed_port_is_rejected_by_design_validation(self):
        design = self.design.model_copy(deep=True)
        design.modules[0].ports[-1].is_signed = True
        prop = self.make_prop("full == 1'b0", [SignalReference(name="full", expected_width=1)])
        result = validate_property_batch(design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])).results[0]
        self.assertFalse(result.design_valid)
        self.assertIn("SIGNED_SIGNAL_UNSUPPORTED", {issue.code for issue in result.issues})

    def test_clock_edge_inference_uses_yosys_polarity(self):
        prop = self.make_prop()
        prop.clock = None
        design = self.design.model_copy(deep=True)
        result = CheckerSynthesizer().synthesize(
            design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
        )
        self.assertIn("always @(posedge clk)", result.wrapper_source_code)

    def test_temporal_nonblocking_implication_guard_includes_antecedent_history(self):
        prop = self.make_prop(
            "$past(full, 2) |=> full",
            [SignalReference(name="full", expected_width=1)],
            AssertionLanguage.SVA,
        )
        result = CheckerSynthesizer().synthesize(
            self.design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
        )
        self.assertIn("formal_past_count >= 3", result.wrapper_source_code)
        self.assertIn("$past($past(full, 2))", result.wrapper_source_code)

    def test_placeholder_substitution_is_token_safe_for_many_temporal_terms(self):
        expression = " && ".join([f"($past(full, {1 if i < 9 else 10}) == full)" for i in range(12)])
        prop = self.make_prop(expression, [SignalReference(name="full", expected_width=1)], AssertionLanguage.SVA)
        result = CheckerSynthesizer().synthesize(
            self.design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
        )
        self.assertNotIn("__TEMPORAL_SLOT_", result.wrapper_source_code)
        self.assertIn("$past(full, 10)", result.wrapper_source_code)

    def test_nested_temporal_sampling_is_rejected(self):
        prop = self.make_prop(
            "$past($past(full)) == full",
            [SignalReference(name="full", expected_width=1)],
            AssertionLanguage.SVA,
        )
        with self.assertRaisesRegex(ValueError, "Nested temporal"):
            CheckerSynthesizer().synthesize(
                self.design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
            )

    def test_maximum_temporal_history_guard_can_reach_eleven(self):
        prop = self.make_prop(
            "$past(full, 10) |=> full",
            [SignalReference(name="full", expected_width=1)],
            AssertionLanguage.SVA,
        )
        result = CheckerSynthesizer().synthesize(
            self.design, PropertyBatch(batch_id="b", design_top="fifo", properties=[prop])
        )
        self.assertIn("formal_past_count < 11", result.wrapper_source_code)
        self.assertIn("formal_past_count >= 11", result.wrapper_source_code)

    def test_unclassified_prove_failure_is_unknown_not_a_counterexample(self):
        status, phase, _, _ = SBYRunner().parse_sby_output(
            "DONE (FAIL, rc=2)", "", Path("/tmp"), ProofMode.PROVE
        )
        self.assertEqual(status, VerificationStatus.UNKNOWN)
        self.assertEqual(phase, "unknown")

    def test_base_case_counterexample_takes_precedence_over_induction_failure(self):
        stdout = (
            "engine_0.basecase: BMC failed!\n"
            "engine_0.induction: induction step failed!\n"
            "DONE (FAIL, rc=2)"
        )
        status, phase, _, _ = SBYRunner().parse_sby_output(stdout, "", Path("/tmp"), ProofMode.PROVE)
        self.assertEqual(status, VerificationStatus.FAIL)
        self.assertEqual(phase, "base")

    def test_vcd_parser_marks_signal_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.vcd"
            path.write_text(
                "$scope module top $end\n"
                "$var wire 1 ! a $end\n"
                "$var wire 1 % b $end\n"
                "$upscope $end\n$enddefinitions $end\n"
                "#0\n0!\n0%\n#1\n1!\n1%\n"
            )
            parsed = parse_vcd_trace(path, max_signals=1)
            self.assertTrue(parsed["truncated"])
            self.assertEqual(len(parsed["signals"]), 1)

    def test_induction_step_failure_is_fail_step(self):
        stdout = "engine_0.basecase: returned pass\nengine_0.induction: induction step failed!\nDONE (FAIL, rc=2)"
        status, phase, _, _ = SBYRunner().parse_sby_output(stdout, "", Path("/tmp"), ProofMode.PROVE)
        self.assertEqual(status, VerificationStatus.FAIL)
        self.assertEqual(phase, "step")

    def test_provider_functional_category_is_normalized_without_expression_change(self):
        payload = {"properties": [{
            "property_id": "P_FUNCTIONAL", "category": "functional",
            "assertion_language": "systemverilog_assertion",
            "expression": "full |=> empty", "clock": {"signal": "clk"}
        }]}
        warnings = _canonicalize_property_categories(payload)
        self.assertEqual(payload["properties"][0]["category"], "temporal")
        self.assertEqual(payload["properties"][0]["expression"], "full |=> empty")
        self.assertTrue(warnings)

    def test_spec_approval_is_bound_to_exact_content(self):
        draft = DesignSpecification(
            specification_id="fifo-spec", title="FIFO requirements", design_top="fifo",
            requirements=[BehaviouralRequirement(requirement_id="REQ-01", statement="A read is accepted only when the FIFO is not empty.")],
        )
        approved = draft.approve("reviewer")
        self.assertEqual(approved.approved_content_hash, approved.content_hash())
        tampered = approved.model_copy(update={"description":"Changed after approval"})
        with self.assertRaisesRegex(Exception, "exact current content hash"):
            DesignSpecification.model_validate(tampered.model_dump())

    def test_approval_endpoint_rejects_changed_content_hash(self):
        client = TestClient(app)
        draft = DesignSpecification(
            specification_id="fifo-spec", title="FIFO requirements", design_top="fifo",
            requirements=[BehaviouralRequirement(requirement_id="REQ-01", statement="A read is accepted only when the FIFO is not empty.")],
        )
        response = client.post("/api/specifications/approve", json={
            "specification": draft.model_dump(mode="json"),
            "reviewer":"reviewer",
            "reviewed_content_hash":"0"*64,
        })
        self.assertEqual(response.status_code, 409)

    def test_formal_service_preserves_yosys_conversion_diagnostics(self):
        error = YosysExecutionError(
            "Yosys failed while converting the instrumented JSON netlist to Verilog.",
            returncode=1,
            output="ERROR: synthetic conversion failure\nscript: read_json ...",
        )
        diagnostic = FormalVerificationService._diagnostic_for_exception(error)
        self.assertIn("YosysExecutionError", diagnostic)
        self.assertIn("Return code: 1", diagnostic)
        self.assertIn("synthetic conversion failure", diagnostic)
        self.assertIn("read_json", diagnostic)


if __name__ == "__main__":
    unittest.main()
