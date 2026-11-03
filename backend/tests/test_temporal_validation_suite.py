import unittest

from backend.app.models.design_ir import DesignIR, ModuleIR, PortIR, RegisterIR
from backend.app.models.property_models import (
    AssertionLanguage, CandidateProperty, ClockContext, PropertyBatch,
    PropertyCategory, ResetContext, SignalReference,
)
from backend.app.services.formal.checker_synthesizer import CheckerSynthesizer


class TemporalValidationSuiteTests(unittest.TestCase):
    def setUp(self):
        self.design = DesignIR(
            top_module="counter_sync",
            source_files=["counter_sync.sv"],
            modules=[ModuleIR(
                name="counter_sync",
                ports=[
                    PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                    PortIR(name="rst_n", direction="input", bit_width=1, bits=[2]),
                    PortIR(name="enable", direction="input", bit_width=1, bits=[3]),
                    PortIR(name="count", direction="output", bit_width=8, bits=list(range(4, 12))),
                ],
                registers=[RegisterIR(cell_name="count_reg", cell_type="$sdffe", clock_bits=[1], reset_bits=[2], parameters={"CLK_POLARITY": "1", "SRST_POLARITY": "0"})],
                clock_candidates=[{"name": "clk", "signal": "clk", "bits": [1]}],
                reset_candidates=[{"name": "rst_n", "signal": "rst_n", "bits": [2], "kind": "synchronous"}],
            )],
        )
        self.signals = [
            SignalReference(name="clk", expected_width=1),
            SignalReference(name="rst_n", expected_width=1),
            SignalReference(name="enable", expected_width=1),
            SignalReference(name="count", expected_width=8),
        ]

    def synthesize(self, expression, *, reset=False):
        prop = CandidateProperty(
            property_id="TEMPORAL_TEST",
            design_top="counter_sync",
            module="counter_sync",
            name="temporal_test",
            description="Temporal operator translation regression",
            category=PropertyCategory.TEMPORAL,
            assertion_language=AssertionLanguage.SVA,
            expression=expression,
            signals=self.signals,
            clock=ClockContext(signal="clk"),
            reset=(
                ResetContext(
                    signal="rst_n", polarity="active_low",
                    asynchronous=(None if reset == "unspecified" else False)
                )
                if reset else None
            ),
        )
        batch = PropertyBatch(
            batch_id="temporal_test_batch",
            design_top="counter_sync",
            properties=[prop],
        )
        return CheckerSynthesizer().synthesize(self.design, batch)

    def test_past_depth_two_is_preserved(self):
        result = self.synthesize("rst_n |-> (count == $past(count, 2))")
        self.assertIn("$past(count, 2)", result.wrapper_source_code)
        self.assertIn("formal_past_count >= 2", result.wrapper_source_code)

    def test_stable_lowers_to_current_equals_previous(self):
        result = self.synthesize("rst_n |-> $stable(count)")
        self.assertIn("((count) == $past(count))", result.wrapper_source_code)

    def test_rose_lowers_to_current_high_and_previous_low(self):
        result = self.synthesize("rst_n |-> $rose(enable)")
        self.assertIn("((enable) && !$past(enable))", result.wrapper_source_code)

    def test_fell_lowers_to_current_low_and_previous_high(self):
        result = self.synthesize("rst_n |-> $fell(enable)")
        self.assertIn("(!(enable) && $past(enable))", result.wrapper_source_code)

    def test_overlapped_implication_uses_current_antecedent(self):
        result = self.synthesize("enable |-> enable")
        self.assertIn("if (1'b1 && (enable))", result.wrapper_source_code)

    def test_non_overlapped_implication_uses_past_antecedent(self):
        result = self.synthesize("enable |=> enable")
        self.assertIn("$past(enable)", result.wrapper_source_code)
        self.assertIn("formal_past_count >= 1", result.wrapper_source_code)

    def test_disable_iff_requires_and_uses_synchronous_reset_context(self):
        result = self.synthesize(
            "disable iff (!rst_n) rst_n",
            reset=True,
        )
        self.assertIn("if (!rst_n) formal_past_count <= 0;", result.wrapper_source_code)
        self.assertIn("if (!(!rst_n)) begin", result.wrapper_source_code)

    def test_disable_iff_rejects_unspecified_reset_timing(self):
        with self.assertRaisesRegex(ValueError, "asynchronous=false"):
            self.synthesize("disable iff (!rst_n) rst_n", reset="unspecified")

    def test_sequential_boolean_invariant_infers_unique_clock(self):
        from backend.app.models.property_models import PropertyLifecycle
        design = self.design.model_copy(deep=True)
        design.modules[0].clock_candidates = [{"name": "clk", "signal": "clk", "bits": [1]}]
        prop = CandidateProperty(
            property_id="BOOL_INV", design_top="counter_sync", module="counter_sync",
            name="range_invariant", description="Counter stays in range",
            category=PropertyCategory.INVARIANT,
            assertion_language=AssertionLanguage.BOOLEAN,
            expression="count <= 8'd255", signals=self.signals,
        )
        batch = PropertyBatch(batch_id="bool_batch", design_top="counter_sync", properties=[prop])
        result = CheckerSynthesizer().synthesize(design, batch)
        self.assertIn("always @(posedge clk)", result.wrapper_source_code)
        self.assertIn("assert (count <= 8'd255)", result.wrapper_source_code)
        self.assertTrue(any("inferred clock" in w for w in result.warnings))

    def test_sequential_boolean_invariant_rejects_ambiguous_clocks(self):
        design = self.design.model_copy(deep=True)
        design.modules[0].clock_candidates = [
            {"name": "clk_a", "signal": "clk_a", "bits": [1]},
            {"name": "clk_b", "signal": "clk_b", "bits": [2]},
        ]
        prop = CandidateProperty(
            property_id="BOOL_MULTI", design_top="counter_sync", module="counter_sync",
            name="range_invariant", description="Counter stays in range",
            category=PropertyCategory.INVARIANT,
            assertion_language=AssertionLanguage.BOOLEAN,
            expression="count <= 8'd255", signals=self.signals,
        )
        batch = PropertyBatch(batch_id="bool_batch", design_top="counter_sync", properties=[prop])
        with self.assertRaisesRegex(ValueError, "multiple clock candidates"):
            CheckerSynthesizer().synthesize(design, batch)


if __name__ == "__main__":
    unittest.main()
