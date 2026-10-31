"""Deterministic mock LLM provider for unit tests and token-free offline verification."""
from __future__ import annotations
import json
from typing import Any
from backend.app.services.llm.provider import LLMProvider, LLMResponse


COUNTER_MOCK_PROPERTIES = {
    "batch_id": "mock_counter_batch",
    "design_top": "counter",
    "properties": [
        {
            "property_id": "counter_holds_when_disabled",
            "design_top": "counter",
            "module": "counter",
            "name": "Counter holds when disabled",
            "description": "Counter retains count value when enable input is deasserted.",
            "category": "invariant",
            "assertion_language": "systemverilog_assertion",
            "expression": "enable == 1'b0 |-> count == $past(count)",
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
            "provenance": {"generator": "llm", "model_name": "mock-model", "prompt_version": "1.0"}
        },
        {
            "property_id": "counter_increments_when_enabled",
            "design_top": "counter",
            "module": "counter",
            "name": "Counter increments on enable",
            "description": "When enable is high and out of reset, count increments by 1.",
            "category": "safety",
            "assertion_language": "systemverilog_assertion",
            "expression": "enable == 1'b1 |=> count == $past(count) + 8'd1",
            "signals": [
                {"name": "enable", "role": "condition", "expected_width": 1},
                {"name": "count", "role": "state", "expected_width": 8}
            ],
            "clock": {"signal": "clk", "edge": "posedge"},
            "reset": {"signal": "rst_n", "polarity": "active_low", "asynchronous": True},
            "assumptions": [],
            "lifecycle": "generated",
            "provenance": {"generator": "llm", "model_name": "mock-model", "prompt_version": "1.0"}
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
            content = json.dumps(COUNTER_MOCK_PROPERTIES, indent=2)

        return LLMResponse(
            content=content,
            model_name=self.model_name,
            usage={"prompt_tokens": 150, "completion_tokens": 200, "total_tokens": 350},
            raw={"mock": True}
        )
