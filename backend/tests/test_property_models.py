import unittest
import json
from pathlib import Path
from pydantic import ValidationError
from backend.app.models.property_models import (
    CandidateProperty, PropertyAssumption, AssumptionReviewStatus,
    PropertyBatch, PropertyCategory, AssertionLanguage, SignalReference,
    ClockContext, ResetContext, PropertyProvenance
)
from backend.app.models.design_ir import DesignIR, ModuleIR, PortIR, NetIR
from backend.app.services.property_validation import validate_property_batch

class PropertyModelTests(unittest.TestCase):
    def make_property(self, **overrides):
        payload = dict(
            property_id="counter_increment",
            design_top="counter",
            module="counter",
            name="Counter increments when enabled",
            description="On an enabled clock edge, count advances by one.",
            category=PropertyCategory.SAFETY,
            assertion_language=AssertionLanguage.SVA,
            expression="disable iff (!rst_n) enable |=> count == $past(count) + 1'b1",
            signals=[
                SignalReference(name="count", role="state", expected_width=8),
                SignalReference(name="enable", role="condition", expected_width=1),
                SignalReference(name="rst_n", role="reset", expected_width=1),
            ],
            clock=ClockContext(signal="clk", edge="posedge"),
            reset=ResetContext(signal="rst_n", polarity="active_low", asynchronous=True),
            provenance=PropertyProvenance(generator="manual"),
        )
        payload.update(overrides)
        return CandidateProperty.model_validate(payload)

    def test_valid_candidate_property(self):
        prop = self.make_property()
        self.assertEqual(prop.lifecycle.value, "generated")
        self.assertEqual(prop.category.value, "safety")

    def test_manual_property_fixtures_match_schema(self):
        fixture_dir = Path(__file__).resolve().parents[2] / "formal" / "examples" / "property_schema"
        for fixture in fixture_dir.glob("*_property_batch.json"):
            with self.subTest(fixture=fixture.name):
                PropertyBatch.model_validate(json.loads(fixture.read_text(encoding="utf-8")))

    def test_empty_expression_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_property(expression="   ")

    def test_assumption_cannot_be_accepted_without_reviewer(self):
        with self.assertRaises(ValidationError):
            PropertyAssumption(
                assumption_id="a1", statement="reset is asserted at startup",
                rationale="test", status=AssumptionReviewStatus.ACCEPTED
            )

    def test_design_validation_checks_signals_and_widths(self):
        design = DesignIR(
            top_module="counter", source_files=["counter.sv"],
            modules=[ModuleIR(name="counter", ports=[
                PortIR(name="clk", direction="input", bit_width=1, bits=[2]),
                PortIR(name="rst_n", direction="input", bit_width=1, bits=[3]),
                PortIR(name="enable", direction="input", bit_width=1, bits=[4]),
                PortIR(name="count", direction="output", bit_width=8, bits=list(range(5,13))),
            ])]
        )
        batch = PropertyBatch(batch_id="batch1", design_top="counter", properties=[self.make_property()])
        result = validate_property_batch(design, batch)
        self.assertEqual(result.summary["design_valid"], 1)
        self.assertTrue(result.results[0].design_valid)
        self.assertEqual(result.results[0].verification_status.value, "not_run")

    def test_unknown_signal_and_width_mismatch_rejected(self):
        design = DesignIR(top_module="counter", source_files=[], modules=[
            ModuleIR(name="counter", ports=[PortIR(name="count", direction="output", bit_width=8, bits=list(range(8)))])
        ])
        prop = self.make_property(signals=[
            SignalReference(name="count", expected_width=4),
            SignalReference(name="not_a_signal")
        ], clock=None, reset=None)
        result = validate_property_batch(design, PropertyBatch(batch_id="b", design_top="counter", properties=[prop]))
        self.assertFalse(result.results[0].design_valid)
        self.assertEqual({i.code for i in result.results[0].issues}, {"SIGNAL_WIDTH_MISMATCH", "UNKNOWN_SIGNAL"})

if __name__ == "__main__":
    unittest.main()
