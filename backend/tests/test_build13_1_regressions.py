import json
import threading
import time
import tempfile
import unittest
from pathlib import Path

from backend.app.models.design_ir import DesignIR, ModuleIR, PortIR, NetIR, ModuleSummaryIR
from backend.app.models.formal_models import FormalVerificationRequest, FormalVerificationResponse, PropertyVerificationResult, ProofMode, SolverEngine
from backend.app.models.property_models import (
    PropertyBatch, CandidateProperty, PropertyCategory, AssertionLanguage,
    SignalReference, VerificationStatus
)
from backend.app.models.specification_models import DesignSpecification, BehaviouralRequirement
from backend.app.services.llm.provider import LLMProvider, LLMResponse
from backend.app.services.llm.property_generator import PropertyGenerationService
from backend.app.services.llm.prompt_builder import build_generation_prompts
from backend.app.services.llm.context_builder import build_design_context
from backend.app.services.formal.sby_runner import SBYRunResult
from backend.app.services.formal.verification_service import FormalVerificationService
from backend.app.services.formal.run_store import FormalRunStore


class SequenceProvider(LLMProvider):
    model_name = "sequence-test"
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []
    def generate(self, prompt, system_prompt=None):
        self.calls.append(prompt)
        return LLMResponse(content=json.dumps(self.outputs[min(len(self.calls)-1, len(self.outputs)-1)]), model_name=self.model_name,
                           usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20})


def property_payload(pid, req_id, expression="count <= 8'hff"):
    return {
        "property_id": pid, "design_top": "counter", "module": "counter",
        "name": pid, "description": f"Formalises {req_id}", "requirement_ids": [req_id],
        "category": "invariant", "assertion_language": "boolean_expression",
        "expression": expression,
        "signals": [{"name": "count", "role": "state", "expected_width": 8}],
        "clock": {"signal": "clk", "edge": "posedge"}, "reset": None,
        "assumptions": [], "lifecycle": "generated",
        "provenance": {"generator": "llm", "model_name": "sequence-test", "prompt_version": "test"}
    }


class Build131RegressionTests(unittest.TestCase):
    def setUp(self):
        self.design = DesignIR(top_module="counter", source_files=["counter.sv"], modules=[
            ModuleIR(name="counter", ports=[
                PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                PortIR(name="count", direction="output", bit_width=8, bits=list(range(2, 10)))
            ], nets=[
                NetIR(name="clk", bit_width=1, bits=[1]),
                NetIR(name="count", bit_width=8, bits=list(range(2, 10)))
            ], clock_candidates=[{"bits": [1], "source_cells": ["$dff"]}], summary=ModuleSummaryIR(port_count=2))
        ])
        self.spec = DesignSpecification(
            specification_id="counter-spec", title="Counter requirements", design_top="counter",
            requirements=[
                BehaviouralRequirement(requirement_id="REQ-01", statement="The count output must never exceed 255."),
                BehaviouralRequirement(requirement_id="REQ-02", statement="When enable is low, the count value must remain unchanged."),
            ]
        ).approve("reviewer")

    def test_prompt_treats_property_count_as_a_safety_ceiling_not_a_target(self):
        context = build_design_context(self.design)
        system, user = build_generation_prompts(context, max_properties=12, specification_text="REQ-01 ...")
        self.assertIn("hard safety ceiling, NOT a target or minimum", user)
        self.assertIn("Do not pad the batch", user)
        self.assertIn("exact named internal nets", system)

    def test_missing_requirement_is_reported_without_quota_filling_supplement(self):
        first = {"batch_id": "b", "design_top": "counter", "properties": [property_payload("p1", "REQ-01")]}
        second = {"batch_id": "b2", "design_top": "counter", "properties": [property_payload("p2", "REQ-02", "$past(count) == count")]}
        provider = SequenceProvider([first, second])
        response = PropertyGenerationService(provider).generate_candidate_properties(
            design=self.design, source_code="module counter; endmodule", specification=self.spec, max_properties=12)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(response.batch.properties), 1)
        self.assertTrue(any("REQ-02" in w for w in response.warnings))
        self.assertEqual(response.generation_audit["raw_responses"], [response.raw_response])

    def test_run_store_persists_vcd_and_rtl_for_history_restore(self):
        temp = Path(tempfile.mkdtemp())
        trace_file = temp / "counterexample.vcd"
        trace_file.write_text("$enddefinitions $end\n#0\n0!\n", encoding="utf-8")
        prop = CandidateProperty(property_id="p-trace", design_top="counter", module="counter", name="trace test",
                                 description="trace persistence", category=PropertyCategory.INVARIANT,
                                 assertion_language=AssertionLanguage.BOOLEAN, expression="count <= 8'hff",
                                 signals=[SignalReference(name="count", expected_width=8)])
        batch = PropertyBatch(batch_id="trace-batch", design_top="counter", properties=[prop])
        request = FormalVerificationRequest(design_ir=self.design, verilog_sources={"counter.sv": "module counter; endmodule"},
                                            property_batch=batch, top_module="counter", proof_mode=ProofMode.BMC,
                                            depth=5, solver=SolverEngine.Z3)
        result = PropertyVerificationResult(property_id="p-trace", name="trace test", status=VerificationStatus.FAIL,
                                             proof_mode=ProofMode.BMC, counterexample_vcd=str(trace_file))
        response = FormalVerificationResponse(batch_id="trace-batch", design_top="counter", overall_status=VerificationStatus.FAIL,
                                              results=[result], summary={"fail": 1})
        store = FormalRunStore(temp / "runs")
        metadata = store.save(request, response)
        saved = store.get_run(metadata["run_id"])
        trace_name = saved["trace_artifacts"]["p-trace"]
        self.assertTrue((store.root / metadata["run_id"] / "traces" / trace_name).is_file())
        self.assertFalse(any(path.name.startswith(".tmp_") for path in store.root.iterdir()))
        self.assertEqual(saved["verilog_sources"]["counter.sv"], "module counter; endmodule")
        self.assertTrue(saved["verification"]["results"][0]["counterexample_vcd"].endswith(".vcd"))
        self.assertRegex(saved["verification"]["results"][0]["counterexample_vcd"], r"/[0-9a-f]{16}\.vcd$")

    def test_formal_properties_execute_with_bounded_parallelism(self):
        active = 0
        maximum = 0
        lock = threading.Lock()
        class FakeRunner:
            timeout_seconds = 45
            def run(self, **kwargs):
                nonlocal active, maximum
                with lock:
                    active += 1
                    maximum = max(maximum, active)
                time.sleep(0.04)
                with lock:
                    active -= 1
                return SBYRunResult(status=VerificationStatus.PASS, returncode=0, stdout="DONE (PASS, rc=0)", stderr="",
                                    work_dir=Path(tempfile.mkdtemp()), task_file_content="[options]")
        batch = PropertyBatch(batch_id="parallel", design_top="alu", properties=[
            CandidateProperty(property_id=f"p{i}", design_top="alu", module="alu", name=f"p{i}", description="test",
                              category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                              expression="a == a", signals=[SignalReference(name="a", expected_width=1)])
            for i in range(5)
        ])
        design = DesignIR(top_module="alu", source_files=["alu.sv"], modules=[
            ModuleIR(name="alu", ports=[PortIR(name="a", direction="input", bit_width=1)], summary=ModuleSummaryIR(port_count=1))
        ])
        request = FormalVerificationRequest(design_ir=design, verilog_sources={"alu.sv": "module alu(input wire a); endmodule"},
                                            property_batch=batch, top_module="alu", proof_mode=ProofMode.BMC,
                                            depth=5, solver=SolverEngine.Z3)
        service = FormalVerificationService(sby_runner=FakeRunner())
        service.run_store = FormalRunStore(Path(tempfile.mkdtemp()) / "runs")
        response = service.verify(request)
        self.assertEqual(response.summary["pass"], 5)
        self.assertEqual(maximum, 3)


if __name__ == "__main__":
    unittest.main()
