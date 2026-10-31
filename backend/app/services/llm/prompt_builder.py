"""Prompt construction for LLM candidate formal property generation."""
from __future__ import annotations
from backend.app.services.llm.context_builder import DesignContext

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """You are an expert formal verification engineer assistant specializing in digital RTL (Verilog/SystemVerilog).
Your role is to propose candidate formal verification properties (assertions, invariants, and environment assumptions) for hardware designs.

NON-NEGOTIABLE VERIFICATION PRINCIPLES:
1. You are an UNTRUSTED candidate proposer. Deterministic formal verification engines (Yosys, SymbiYosys, Z3, Boolector) determine mathematical proof outcomes.
2. NEVER claim a property has been proven or is mathematically verified.
3. NEVER invent or hallucinate signal names or bit widths. You must ONLY reference signals that exist in the provided design context.
4. Check declared bit widths carefully. Expected signal widths must match the design.
5. All environment assumptions must have status "proposed" and an explicit rationale explaining why the environment restriction is required.
6. Do not introduce circular or vacuous properties (e.g. asserting a signal equals itself, or preconditions that are never satisfiable).
7. Return ONLY a valid JSON object matching the requested schema. No surrounding explanatory text.
"""


def build_generation_prompts(
    context: DesignContext,
    max_properties: int = 5,
    model_name: str = "llm"
) -> tuple[str, str]:
    """Construct (system_prompt, user_prompt) for property candidate generation."""
    user_prompt = f"""Generate up to {max_properties} meaningful, mathematically checkable candidate formal properties for the following hardware design.

{context.to_prompt_text()}

### Required Output Format:
Return a single JSON object conforming exactly to this structure:
{{
  "batch_id": "{context.module_name}_candidate_batch",
  "design_top": "{context.design_top}",
  "properties": [
    {{
      "property_id": "{context.module_name}_prop_1",
      "design_top": "{context.design_top}",
      "module": "{context.module_name}",
      "name": "Concise descriptive title",
      "description": "Clear explanation of intended hardware behavior or invariant.",
      "category": "safety", // Choose from: safety, liveness, invariant, temporal, combinational
      "assertion_language": "systemverilog_assertion", // Choose from: systemverilog_assertion, boolean_expression
      "expression": "disable iff (!rst_n) enable |=> count == $past(count) + 8'd1", // Formal expression
      "signals": [
        {{"name": "signal_name", "role": "state", "expected_width": 8}}
      ],
      "clock": {{"signal": "{context.clock_context['signal'] if context.clock_context else 'clk'}", "edge": "posedge"}}, // Omit or null if pure combinational
      "reset": {{"signal": "{context.reset_context['signal'] if context.reset_context else 'rst_n'}", "polarity": "{context.reset_context['polarity'] if context.reset_context else 'active_low'}", "asynchronous": true}}, // Omit or null if none
      "assumptions": [
        {{
          "assumption_id": "asm_1",
          "statement": "Description of environment restriction",
          "rationale": "Justification for why this assumption is required",
          "status": "proposed",
          "source": "llm"
        }}
      ],
      "lifecycle": "generated",
      "provenance": {{
        "generator": "llm",
        "model_name": "{model_name}",
        "prompt_version": "{PROMPT_VERSION}"
      }}
    }}
  ]
}}

Ensure:
- Signal names in the `signals` list match the design ports and nets exactly.
- Widths in `expected_width` match the design port/net widths.
- Every assumption status is set to "proposed".
- Output ONLY valid JSON.
"""
    return SYSTEM_PROMPT, user_prompt
