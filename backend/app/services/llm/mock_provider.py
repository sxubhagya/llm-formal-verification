"""Deterministic mock LLM provider for unit tests and token-free offline verification."""
from __future__ import annotations
import json
import copy
import re
from typing import Any
from backend.app.services.llm.provider import LLMProvider, LLMResponse


COMB_ALU_MOCK_PROPERTIES = {
    "batch_id": "mock_comb_alu_batch",
    "design_top": "comb_alu",
    "properties": [
        {
            "property_id": "comb_alu_matches_operation_table",
            "design_top": "comb_alu",
            "module": "comb_alu",
            "name": "ALU result matches selected operation",
            "description": "Checks the combinational ALU truth table for all operation codes: addition, subtraction, bitwise AND, and bitwise XOR.",
            "requirement_ids": ["REQ-01"],
            "category": "combinational",
            "assertion_language": "boolean_expression",
            "expression": "result == (op == 2'b00 ? a + b : op == 2'b01 ? a - b : op == 2'b10 ? a & b : a ^ b)",
            "signals": [
                {"name": "a", "role": "operand", "expected_width": 8},
                {"name": "b", "role": "operand", "expected_width": 8},
                {"name": "op", "role": "selector", "expected_width": 2},
                {"name": "result", "role": "result", "expected_width": 8}
            ],
            "clock": None,
            "reset": None,
            "assumptions": [],
            "lifecycle": "generated",
            "provenance": {"generator": "llm", "model_name": "mock-model", "prompt_version": "1.1"}
        }
    ]
}


COUNTER_MOCK_PROPERTIES = {
    "batch_id": "mock_counter_batch",
    "design_top": "counter",
    "properties": [
        {
            "property_id": "counter_holds_when_disabled",
            "design_top": "counter",
            "module": "counter",
            "name": "Counter holds when disabled",
            "description": "Illustrative width-bound invariant for the 8-bit counter; this is a trivial mock example, not a behavioural transition property.",
            "requirement_ids": ["REQ-01"],
            "category": "invariant",
            "assertion_language": "boolean_expression",
            "expression": "count <= 8'hff",
            "signals": [
                {"name": "enable", "role": "condition", "expected_width": 1},
                {"name": "count", "role": "state", "expected_width": 8}
            ],
            "clock": {"signal": "clk", "edge": "posedge"},
            "reset": {"signal": "rst_n", "polarity": "active_low", "asynchronous": True},
            "assumptions": [
                {
                    "assumption_id": "asm_clk_running",
                    "statement": "Clock clk is continuously toggling.",
                    "rationale": "Standard sequential clocked behavior",
                    "status": "proposed",
                    "source": "llm"
                }
            ],
            "lifecycle": "generated",
            "provenance": {"generator": "llm", "model_name": "mock-model", "prompt_version": "1.1"}
        },
        {
            "property_id": "counter_increments_when_enabled",
            "design_top": "counter",
            "module": "counter",
            "name": "Counter increments on enable",
            "description": "Illustrative unsigned lower-bound invariant; this is a trivial mock example, not a behavioural transition property.",
            "requirement_ids": ["REQ-01"],
            "category": "safety",
            "assertion_language": "boolean_expression",
            "expression": "count >= 8'h00",
            "signals": [
                {"name": "enable", "role": "condition", "expected_width": 1},
                {"name": "count", "role": "state", "expected_width": 8}
            ],
            "clock": {"signal": "clk", "edge": "posedge"},
            "reset": {"signal": "rst_n", "polarity": "active_low", "asynchronous": True},
            "assumptions": [],
            "lifecycle": "generated",
            "provenance": {"generator": "llm", "model_name": "mock-model", "prompt_version": "1.1"}
        }
    ]
}


class MockProvider(LLMProvider):
    """Deterministic mock provider."""

    def __init__(
        self,
        model_name: str = "mock-model",
        custom_content: str | None = None,
        raise_error: Exception | None = None
    ) -> None:
        self.model_name = model_name
        self.custom_content = custom_content
        self.raise_error = raise_error
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        if self.raise_error:
            raise self.raise_error

        if self.custom_content is not None:
            content = self.custom_content
        else:
            # Keep the offline provider deterministic, but select a fixture that
            # matches the analysed top module instead of always returning counter data.
            if "Top Module: `comb_alu`" in prompt or "Target Module: `comb_alu`" in prompt:
                fixture = copy.deepcopy(COMB_ALU_MOCK_PROPERTIES)
            else:
                fixture = copy.deepcopy(COUNTER_MOCK_PROPERTIES)
                top_match = re.search(r"Top Module: `([A-Za-z_][A-Za-z0-9_$]*)`", prompt)
                target = top_match.group(1) if top_match else "counter"
                fixture["design_top"] = target
                fixture["batch_id"] = f"mock_{target}_batch"
                for prop in fixture["properties"]:
                    prop["design_top"] = target
                    prop["module"] = target
                    prop["property_id"] = f"{target}_{prop['property_id'].split('_', 1)[-1]}"
            content = json.dumps(fixture, indent=2)

        return LLMResponse(
            content=content,
            model_name=self.model_name,
            usage={"prompt_tokens": 150, "completion_tokens": 200, "total_tokens": 350},
            raw={"mock": True}
        )
