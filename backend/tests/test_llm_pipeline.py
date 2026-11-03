"""Unit and integration tests for Build 7 LLM property generation pipeline."""
import unittest
import json
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.specification_models import DesignSpecification, BehaviouralRequirement
from backend.app.models.design_ir import (
    DesignIR, ModuleIR, PortIR, NetIR, ModuleSummaryIR,
    FSMCandidateIR, MemoryAccessIR, RegisterIR
)
from backend.app.services.llm.provider import get_llm_provider
from backend.app.services.llm.mock_provider import MockProvider
from backend.app.services.llm.context_builder import build_design_context
from backend.app.services.llm.prompt_builder import build_generation_prompts
from backend.app.services.llm.property_generator import PropertyGenerationService, _canonicalize_clock_reset_fields


class LLMPipelineTests(unittest.TestCase):
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
                    nets=[
                        NetIR(name="clk", bit_width=1, bits=[1]),
                        NetIR(name="rst_n", bit_width=1, bits=[2]),
                        NetIR(name="enable", bit_width=1, bits=[3]),
                        NetIR(name="count", bit_width=8, bits=list(range(4, 12))),
                    ],
                    registers=[RegisterIR(
                        cell_name="$adffe_0", cell_type="$adffe",
                        clock_bits=[1], reset_bits=[2],
                        parameters={"CLK_POLARITY": "00000000000000000000000000000001", "ARST_POLARITY": "00000000000000000000000000000000"}
                    )],
                    clock_candidates=[{"name": "clk", "signal": "clk", "bits": [1], "source_cells": ["$adffe_0"], "source_kind": "sequential"}],
                    reset_candidates=[{"bits": [2], "kind": "asynchronous", "source_cells": ["$adffe_0"]}],
                    summary=ModuleSummaryIR(port_count=4, input_port_count=3, output_port_count=1)
                )
            ]
        )

        self.counter_spec = DesignSpecification(specification_id="counter-spec", title="Counter behaviour", design_top="counter", requirements=[BehaviouralRequirement(requirement_id="REQ-01", statement="The count output is an unsigned 8-bit value and never exceeds 255.")]).approve("test-reviewer")
        self.alu_spec = DesignSpecification(specification_id="alu-spec", title="ALU behaviour", design_top="comb_alu", requirements=[BehaviouralRequirement(requirement_id="REQ-01", statement="For op 00 result is a plus b, for 01 it is a minus b, for 10 it is bitwise AND, and for 11 it is bitwise XOR.")]).approve("test-reviewer")

        self.alu_design = DesignIR(
            top_module="comb_alu",
            source_files=["comb_alu.v"],
            modules=[
                ModuleIR(
                    name="comb_alu",
                    ports=[
                        PortIR(name="a", direction="input", bit_width=8, bits=list(range(8))),
                        PortIR(name="b", direction="input", bit_width=8, bits=list(range(8, 16))),
                        PortIR(name="op", direction="input", bit_width=2, bits=[16, 17]),
                        PortIR(name="result", direction="output", bit_width=8, bits=list(range(18, 26))),
                    ],
                    summary=ModuleSummaryIR(port_count=4, input_port_count=3, output_port_count=1)
                )
            ]
        )

    def test_context_builder_extracts_clock_and_reset(self):
        ctx = build_design_context(self.counter_design)
        self.assertEqual(ctx.design_top, "counter")
        self.assertEqual(ctx.module_name, "counter")
        self.assertIsNotNone(ctx.clock_context)
        self.assertEqual(ctx.clock_context["signal"], "clk")
        self.assertEqual(ctx.clock_context["edge"], "posedge")
        self.assertIsNotNone(ctx.reset_context)
        self.assertEqual(ctx.reset_context["signal"], "rst_n")
        self.assertEqual(ctx.reset_context["polarity"], "active_low")
        self.assertTrue(ctx.reset_context["asynchronous"])

        prompt_text = ctx.to_prompt_text()
        self.assertIn("Top Module: `counter`", prompt_text)
        self.assertIn("`count`: output [7:0] (8 bits, unsigned)", prompt_text)
        self.assertIn("Inferred Clock Context", prompt_text)

    def test_context_builder_combinational_design(self):
        ctx = build_design_context(self.alu_design)
        self.assertIsNone(ctx.clock_context)
        self.assertIsNone(ctx.reset_context)
        prompt_text = ctx.to_prompt_text()
        self.assertIn("No clocked elements structurally identified", prompt_text)

    def test_context_builder_invalid_target_module_raises(self):
        with self.assertRaises(ValueError):
            build_design_context(self.counter_design, target_module="nonexistent")

    def test_prompt_builder_enforces_principles(self):
        ctx = build_design_context(self.counter_design)
        sys_prompt, user_prompt = build_generation_prompts(ctx, max_properties=3, specification_text="REQ-01: count stays within 8-bit range")
        self.assertIn("UNTRUSTED candidate proposer", sys_prompt)
        self.assertIn("NEVER claim a property has been proven", sys_prompt)
        self.assertIn("NEVER invent or hallucinate signal names", sys_prompt)
        self.assertIn("proposed", user_prompt)
        self.assertIn("INDEPENDENT BEHAVIOURAL SPECIFICATION", user_prompt)
        self.assertIn("sole authority", sys_prompt)
        self.assertIn("systemverilog_assertion", sys_prompt)
        self.assertIn("|=>", sys_prompt)
        self.assertIn('"signal": "clk"', user_prompt)
        self.assertIn('"signal": "rst_n"', user_prompt)


    def test_clock_reset_name_alias_is_normalized_to_signal(self):
        payload = {"properties": [{"property_id": "p1", "clock": {"name": "clk", "edge": "posedge"}, "reset": {"name": "rst_n", "polarity": "active_low", "asynchronous": False}}]}
        warnings = _canonicalize_clock_reset_fields(payload)
        self.assertEqual(payload["properties"][0]["clock"]["signal"], "clk")
        self.assertEqual(payload["properties"][0]["reset"]["signal"], "rst_n")
        self.assertNotIn("name", payload["properties"][0]["clock"])
        self.assertNotIn("name", payload["properties"][0]["reset"])
        self.assertEqual(len(warnings), 2)

    def test_clock_reset_conflicting_aliases_are_rejected(self):
        payload = {"properties": [{"property_id": "p1", "clock": {"name": "clk_a", "signal": "clk_b"}}]}
        with self.assertRaisesRegex(ValueError, "conflicting clock.name and clock.signal"):
            _canonicalize_clock_reset_fields(payload)

    def test_mock_provider_generation_end_to_end(self):
        provider = MockProvider(model_name="test-mock")
        service = PropertyGenerationService(provider=provider)
        response = service.generate_candidate_properties(design=self.counter_design, max_properties=2, specification=self.counter_spec)

        self.assertEqual(response.batch.design_top, "counter")
        self.assertEqual(len(response.batch.properties), 2)
        # Validation checks
        self.assertEqual(response.validation.summary["design_valid"], 2)
        self.assertEqual(response.validation.summary["rejected"], 0)
        self.assertEqual(response.validation.results[0].verification_status.value, "not_run")
        # Provenance check
        self.assertEqual(response.provenance.generator, "llm")
        self.assertEqual(response.provenance.model_name, "test-mock")
        # Assumptions must be proposed
        for prop in response.batch.properties:
            for asm in prop.assumptions:
                self.assertEqual(asm.status.value, "proposed")

    def test_mock_provider_generation_matches_comb_alu_design(self):
        provider = MockProvider(model_name="test-mock-alu")
        service = PropertyGenerationService(provider=provider)
        response = service.generate_candidate_properties(design=self.alu_design, max_properties=5, specification=self.alu_spec)

        self.assertEqual(response.batch.design_top, "comb_alu")
        self.assertEqual(len(response.batch.properties), 1)
        prop = response.batch.properties[0]
        self.assertEqual(prop.module, "comb_alu")
        self.assertEqual(prop.property_id, "comb_alu_matches_operation_table")
        self.assertIn("result ==", prop.expression)
        self.assertEqual(response.validation.summary["design_valid"], 1)
        self.assertEqual(response.validation.summary["rejected"], 0)

    def test_api_generate_endpoint_success_for_comb_alu_mock(self):
        client = TestClient(app)
        payload = {
            "design": self.alu_design.model_dump(),
            "target_module": "comb_alu",
            "max_properties": 5,
            "provider": "mock",
            "specification": self.alu_spec.model_dump(mode="json")
        }
        res = client.post("/api/properties/generate", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["batch"]["design_top"], "comb_alu")
        self.assertEqual(data["validation"]["summary"]["design_valid"], 1)

    def test_generation_strips_markdown_code_fences(self):
        provider = MockProvider(model_name="fenced-mock")
        service = PropertyGenerationService(provider=provider)
        # Wrap mock output in markdown fences
        fenced_json = f"```json\n{json.dumps(provider.generate('test').content)}\n```"
        fenced_provider = MockProvider(custom_content=fenced_json.replace('\\"', '"').replace('"\n```', '\n```').strip('\"'))
        service = PropertyGenerationService(provider=fenced_provider)

        # Standard provider default response inside markdown fence
        raw_default = MockProvider().generate("").content
        fenced = f"Here is the result:\n```json\n{raw_default}\n```\nHope this helps!"
        service_fenced = PropertyGenerationService(provider=MockProvider(custom_content=fenced))
        resp = service_fenced.generate_candidate_properties(design=self.counter_design, specification=self.counter_spec)
        self.assertEqual(len(resp.batch.properties), 2)

    def test_generation_rejects_malformed_json(self):
        service = PropertyGenerationService(provider=MockProvider(custom_content="Not valid JSON at all"))
        with self.assertRaises(ValueError) as ctx:
            service.generate_candidate_properties(design=self.counter_design, specification=self.counter_spec)
        self.assertIn("could not be parsed as valid JSON", str(ctx.exception))

    def test_api_generate_endpoint_success(self):
        client = TestClient(app)
        payload = {
            "design": self.counter_design.model_dump(),
            "target_module": "counter",
            "max_properties": 2,
            "provider": "mock",
            "specification": self.counter_spec.model_dump(mode="json")
        }
        res = client.post("/api/properties/generate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("batch", data)
        self.assertIn("validation", data)
        self.assertIn("provenance", data)
        self.assertEqual(data["batch"]["design_top"], "counter")
        self.assertEqual(data["validation"]["summary"]["design_valid"], 2)

    def test_context_builder_fsm_and_memory(self):
        fsm_design = DesignIR(
            top_module="traffic_light",
            source_files=["traffic_light.sv"],
            modules=[
                ModuleIR(
                    name="traffic_light",
                    ports=[
                        PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                        PortIR(name="rst_n", direction="input", bit_width=1, bits=[2]),
                        PortIR(name="red", direction="output", bit_width=1, bits=[3]),
                        PortIR(name="yellow", direction="output", bit_width=1, bits=[4]),
                        PortIR(name="green", direction="output", bit_width=1, bits=[5]),
                    ],
                    fsm_candidates=[
                        FSMCandidateIR(state_net="state", state_bits=[6, 7], encoded_states={"RED": "2'b00", "GREEN": "2'b01", "YELLOW": "2'b10"})
                    ],
                    summary=ModuleSummaryIR(port_count=5, input_port_count=2, output_port_count=3)
                )
            ]
        )
        ctx = build_design_context(fsm_design)
        self.assertEqual(len(ctx.fsm_candidates), 1)
        self.assertIn("RED=2'b00", ctx.to_prompt_text())

        mem_design = DesignIR(
            top_module="register_file",
            source_files=["register_file.sv"],
            modules=[
                ModuleIR(
                    name="register_file",
                    ports=[
                        PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                        PortIR(name="we", direction="input", bit_width=1, bits=[2]),
                        PortIR(name="waddr", direction="input", bit_width=3, bits=[3, 4, 5]),
                        PortIR(name="wdata", direction="input", bit_width=8, bits=list(range(6, 14))),
                    ],
                    memory_accesses=[
                        MemoryAccessIR(cell_name="$mem_rf", cell_type="$memwr", operation="write", clocked=True)
                    ],
                    summary=ModuleSummaryIR(port_count=4, memory_cell_count=1)
                )
            ]
        )
        mctx = build_design_context(mem_design)
        self.assertEqual(len(mctx.memory_accesses), 1)
        self.assertIn("Memory Accesses", mctx.to_prompt_text())

    def test_provider_missing_api_key_raises_error(self):
        from backend.app.services.llm.gemini_provider import GeminiProvider
        provider = GeminiProvider(api_key="")
        # Remove any ambient env key for this check
        orig_key = provider.api_key
        provider.api_key = None
        with self.assertRaises(ValueError) as ctx:
            provider.generate("test")
        self.assertIn("Gemini API key is not configured", str(ctx.exception))

    def test_api_generate_endpoint_error_handling(self):
        client = TestClient(app)
        # 1. Unknown provider
        payload_bad_prov = {
            "design": self.counter_design.model_dump(),
            "provider": "unknown_provider"
        }
        res = client.post("/api/properties/generate", json=payload_bad_prov)
        self.assertEqual(res.status_code, 422)

        # 2. Mock provider raising PermissionError -> HTTP 401
        err_provider = MockProvider(raise_error=PermissionError("Invalid API Key"))
        service = PropertyGenerationService(provider=err_provider)
        with self.assertRaises(PermissionError):
            service.generate_candidate_properties(self.counter_design, specification=self.counter_spec)


if __name__ == "__main__":
    unittest.main()

