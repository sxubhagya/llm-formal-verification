import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from backend.app.models.formal_models import ProofMode, VacuityStatus, FormalVerificationRequest
from backend.app.services.formal.verification_service import FormalVerificationService
from backend.app.models.property_models import VerificationStatus, AssumptionReviewStatus
from backend.app.services.formal.sby_runner import SBYRunner, SBYRunResult
from backend.app.services.formal.checker_synthesizer import CheckerSynthesizer
from backend.app.services.llm.provider import get_llm_provider
from backend.app.core import config
from backend.app.models.design_ir import DesignIR, ModuleIR, PortIR
from backend.app.models.property_models import (
    PropertyBatch, CandidateProperty, PropertyCategory, AssertionLanguage,
    SignalReference, ClockContext, PropertyAssumption
)


class StabilizationHardeningTests(unittest.TestCase):
    def test_mock_runner_never_reports_pass(self):
        runner = SBYRunner(mode="native", mock_mode=True)
        result = runner.run("mock_task", {"simple.sv": "module simple; endmodule"}, "simple")
        self.assertEqual(result.status, VerificationStatus.UNKNOWN)
        self.assertTrue(result.simulated)

    def test_missing_tools_never_reports_pass(self):
        runner = SBYRunner(mode="native", mock_mode=False)
        with patch("backend.app.services.formal.sby_runner.shutil.which", return_value=None):
            result = runner.run("no_tools", {"simple.sv": "module simple; endmodule"}, "simple")
        self.assertNotEqual(result.status, VerificationStatus.PASS)
        self.assertEqual(result.status, VerificationStatus.INVALID)

    def test_rejects_path_traversal_and_absolute_source_names(self):
        for name in ("../outside.sv", "/tmp/outside.sv", "a;touch-b.sv"):
            with self.assertRaises(ValueError):
                SBYRunner._validate_source_name(name)

    def test_rejects_expression_injection_and_temporal_sva(self):
        design = DesignIR(
            top_module="m",
            source_files=["m.sv"],
            modules=[ModuleIR(name="m", ports=[
                PortIR(name="a", direction="input", bit_width=1),
                PortIR(name="clk", direction="input", bit_width=1),
            ])],
        )
        for expression in ("a); endmodule module injected;", "a |=> a", "a; $display(1)"):
            prop = CandidateProperty(
                property_id="p", design_top="m", module="m", name="p", description="p",
                category=PropertyCategory.SAFETY,
                assertion_language=AssertionLanguage.BOOLEAN,
                expression=expression,
                signals=[SignalReference(name="a")],
                clock=ClockContext(signal="clk"),
            )
            with self.assertRaises(ValueError):
                CheckerSynthesizer().synthesize(
                    design, PropertyBatch(batch_id="b", design_top="m", properties=[prop])
                )

    def test_only_accepted_assumptions_are_injected(self):
        design = DesignIR(
            top_module="m",
            source_files=["m.sv"],
            modules=[ModuleIR(name="m", ports=[
                PortIR(name="a", direction="input", bit_width=1),
                PortIR(name="clk", direction="input", bit_width=1),
            ])],
        )
        assumptions = [
            PropertyAssumption(
                assumption_id="p", statement="a == 1'b1", rationale="proposed",
                status=AssumptionReviewStatus.PROPOSED,
            ),
            PropertyAssumption(
                assumption_id="r", statement="a == 1'b0", rationale="rejected",
                status=AssumptionReviewStatus.REJECTED, reviewed_by="reviewer",
            ),
            PropertyAssumption(
                assumption_id="a", statement="a == 1'b1", rationale="accepted",
                status=AssumptionReviewStatus.ACCEPTED, reviewed_by="reviewer",
            ),
        ]
        prop = CandidateProperty(
            property_id="p", design_top="m", module="m", name="p", description="p",
            category=PropertyCategory.SAFETY,
            assertion_language=AssertionLanguage.BOOLEAN,
            expression="a == 1'b1",
            signals=[SignalReference(name="a")],
            clock=ClockContext(signal="clk"),
            assumptions=assumptions,
        )
        result = CheckerSynthesizer().synthesize(
            design, PropertyBatch(batch_id="b", design_top="m", properties=[prop])
        )
        self.assertEqual(result.wrapper_source_code.count("assume ("), 1)
        self.assertIn("assume (a == 1'b1);", result.wrapper_source_code)

    def test_property_batch_ids_must_be_unique(self):
        from backend.app.models.property_models import PropertyBatch

        with self.assertRaises(ValueError):
            PropertyBatch.model_validate({
                "batch_id": "b",
                "design_top": "m",
                "properties": [
                    {
                        "property_id": "same", "design_top": "m", "module": "m",
                        "name": "a", "description": "a", "category": "invariant",
                        "assertion_language": "boolean_expression",
                        "expression": "a == 1'b0", "signals": [{"name": "a"}],
                    },
                    {
                        "property_id": "same", "design_top": "m", "module": "m",
                        "name": "b", "description": "b", "category": "invariant",
                        "assertion_language": "boolean_expression",
                        "expression": "a == 1'b1", "signals": [{"name": "a"}],
                    },
                ],
            })

    def test_provider_keys_are_not_cross_wired(self):
        """A missing Gemini setting must not fall back to a real developer env key."""
        fake_settings = SimpleNamespace(
            llm_provider="gemini",
            gemini_api_key=None,
            openai_api_key="openai-secret",
            generic_llm_api_key=None,
            llm_model=None,
        )

        # GeminiProvider has an environment fallback. Clear both supported
        # environment variables so this test checks only the supplied settings.
        with (
            patch("backend.app.services.llm.provider.settings", fake_settings),
            patch.dict("os.environ", {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}),
        ):
            provider = get_llm_provider("gemini")
            self.assertIsNone(provider.api_key)


if __name__ == "__main__":
    unittest.main()
