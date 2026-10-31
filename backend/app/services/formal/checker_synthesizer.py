"""Synthesizes procedural Verilog checker monitors from CandidateProperty models.

Open-source Yosys (without proprietary Verific) compiles procedural assertions
(assert, assume, cover within always blocks) and formal system tasks ($past,
$stable, $rose, $fell) under `read_verilog -formal`. This synthesizer converts
high-level candidate properties into a self-contained formal verification wrapper
that preserves pristine RTL without source modification.
"""
from __future__ import annotations
import re
from typing import Any
from dataclasses import dataclass, field

from backend.app.models.design_ir import DesignIR, ModuleIR, PortIR
from backend.app.models.property_models import (
    CandidateProperty, PropertyBatch, PropertyCategory, AssertionLanguage
)


@dataclass
class SynthesizedPropertyMeta:
    property_id: str
    name: str
    assertion_label: str
    cover_label: str | None = None
    is_implication: bool = False
    antecedent: str | None = None
    consequent: str | None = None


@dataclass
class SynthesizedCheckerResult:
    wrapper_module_name: str
    wrapper_source_code: str
    top_module: str
    properties: list[SynthesizedPropertyMeta] = field(default_factory=list)
    has_clock: bool = True
    clock_signal: str = "clk"
    reset_signal: str | None = None
    reset_polarity: str = "active_low"


class CheckerSynthesizer:
    """Translates CandidateProperty specifications into synthesizable procedural Verilog checkers."""

    def __init__(self, check_vacuity: bool = True):
        self.check_vacuity = check_vacuity

    def _split_implication(self, expr: str) -> tuple[str, str] | None:
        """Splits an expression on SVA or Boolean implication operators (|->, |=>, ->)."""
        clean_expr = expr.strip()
        # Remove outer assert property (...) if present
        m = re.match(r"^assert\s+property\s*\(\s*(?:@\([^)]+\)\s*)?(.*)\)\s*;?$", clean_expr, re.DOTALL)
        if m:
            clean_expr = m.group(1).strip()

        # Check for overlapping implication operators
        for op in ["|->", "|=>", "->"]:
            if op in clean_expr:
                parts = clean_expr.split(op, 1)
                antecedent = parts[0].strip()
                consequent = parts[1].strip()
                # Strip leading/trailing parens if matching
                if antecedent.startswith("(") and antecedent.endswith(")"):
                    antecedent = antecedent[1:-1].strip()
                if consequent.startswith("(") and consequent.endswith(")"):
                    consequent = consequent[1:-1].strip()
                return antecedent, consequent
        return None

    def _clean_expression(self, expr: str) -> str:
        """Cleans syntax wrappers like assert(...) or ending semicolons."""
        clean = expr.strip()
        m = re.match(r"^assert\s*\(\s*(.*)\)\s*;?$", clean, re.DOTALL)
        if m:
            clean = m.group(1).strip()
        if clean.endswith(";"):
            clean = clean[:-1].strip()
        return clean

    def synthesize(
        self,
        design_ir: DesignIR,
        property_batch: PropertyBatch,
        target_module_name: str | None = None
    ) -> SynthesizedCheckerResult:
        top_name = target_module_name or property_batch.design_top or design_ir.top_module
        target_mod: ModuleIR | None = next((m for m in design_ir.modules if m.name == top_name), None)
        if not target_mod:
            raise ValueError(f"Target module '{top_name}' not found in DesignIR.")

        # Determine clock & reset from target_mod ports/candidates or properties
        clock_sig = "clk"
        reset_sig = None
        reset_polarity = "active_low"

        # Check clock candidates
        if target_mod.clock_candidates:
            clock_sig = target_mod.clock_candidates[0].get("name", "clk")
        elif any(p.name in {"clk", "clock"} for p in target_mod.ports):
            clock_sig = next(p.name for p in target_mod.ports if p.name in {"clk", "clock"})
        else:
            # Check if any property declares a clock
            for prop in property_batch.properties:
                if prop.clock:
                    clock_sig = prop.clock.signal
                    break

        # Check reset candidates
        if target_mod.reset_candidates:
            reset_sig = target_mod.reset_candidates[0].get("name")
            reset_polarity = target_mod.reset_candidates[0].get("polarity", "active_low")
        elif any(p.name in {"rst", "rst_n", "reset", "reset_n"} for p in target_mod.ports):
            r_port = next(p.name for p in target_mod.ports if p.name in {"rst", "rst_n", "reset", "reset_n"})
            reset_sig = r_port
            reset_polarity = "active_low" if "n" in r_port.lower() else "active_high"
        else:
            for prop in property_batch.properties:
                if prop.reset:
                    reset_sig = prop.reset.signal
                    reset_polarity = prop.reset.polarity
                    break

        has_clock = any(p.name == clock_sig for p in target_mod.ports)
        wrapper_name = f"formal_{top_name}"

        # Build port list for wrapper
        port_decls = []
        port_conns = []
        for port in target_mod.ports:
            width_spec = f"[{port.bit_width - 1}:0] " if port.bit_width > 1 else ""
            if port.direction == "input":
                port_decls.append(f"    input wire {width_spec}{port.name}")
            else:
                port_decls.append(f"    output wire {width_spec}{port.name}")
            port_conns.append(f"        .{port.name}({port.name})")

        ports_str = ",\n".join(port_decls)
        conns_str = ",\n".join(port_conns)

        # Build procedural formal blocks
        assumptions_code = []
        properties_meta = []
        checks_code = []

        # Collect global assumptions from properties
        seen_assumptions = set()
        for prop in property_batch.properties:
            for asm in prop.assumptions:
                stmt = self._clean_expression(asm.statement)
                if stmt not in seen_assumptions:
                    seen_assumptions.add(stmt)
                    assumptions_code.append(f"        // Assumption {asm.assumption_id}: {asm.rationale}")
                    assumptions_code.append(f"        assume({stmt});")

        # Synthesize each candidate property
        for idx, prop in enumerate(property_batch.properties):
            p_id = prop.property_id
            safe_name = re.sub(r"[^A-Za-z0-9_]", "_", prop.name)
            assert_lbl = f"assert_{safe_name}_{idx}"
            cover_lbl = f"cover_antecedent_{safe_name}_{idx}"

            imp = self._split_implication(prop.expression)
            if imp:
                antecedent, consequent = imp
                properties_meta.append(SynthesizedPropertyMeta(
                    property_id=p_id,
                    name=prop.name,
                    assertion_label=assert_lbl,
                    cover_label=cover_lbl if self.check_vacuity else None,
                    is_implication=True,
                    antecedent=antecedent,
                    consequent=consequent
                ))
                checks_code.append(f"        // Property {p_id}: {prop.name}")
                checks_code.append(f"        // Description: {prop.description}")
                if self.check_vacuity:
                    checks_code.append(f"        // Vacuity cover check (witness reachability):")
                    checks_code.append(f"        {cover_lbl}: cover({antecedent});")
                checks_code.append(f"        if ({antecedent}) begin")
                checks_code.append(f"            {assert_lbl}: assert({consequent});")
                checks_code.append(f"        end")
            else:
                clean_expr = self._clean_expression(prop.expression)
                properties_meta.append(SynthesizedPropertyMeta(
                    property_id=p_id,
                    name=prop.name,
                    assertion_label=assert_lbl,
                    is_implication=False
                ))
                checks_code.append(f"        // Property {p_id}: {prop.name}")
                checks_code.append(f"        // Description: {prop.description}")
                checks_code.append(f"        {assert_lbl}: assert({clean_expr});")

        # Construct full wrapper module
        wrapper_lines = [
            f"// Self-contained formal verification wrapper for module '{top_name}'",
            f"// Synthesized for open-source Yosys / SBY verification",
            f"`default_nettype none",
            f"",
            f"module {wrapper_name} (",
            ports_str,
            f");",
            f"",
            f"    // Instantiate Device Under Test (DUT)",
            f"    {top_name} dut (",
            conns_str,
            f"    );",
            f"",
            f"`ifdef FORMAL",
        ]

        if has_clock:
            wrapper_lines += [
                f"    // Past-valid register to guard $past() across cycle 0",
                f"    reg f_past_valid = 1'b0;",
                f"    always @(posedge {clock_sig}) begin",
                f"        f_past_valid <= 1'b1;",
            ]
            if reset_sig:
                rst_cond = f"!{reset_sig}" if reset_polarity == "active_low" else f"{reset_sig}"
                wrapper_lines += [
                    f"",
                    f"        // Environment Assumptions",
                    *assumptions_code,
                    f"",
                    f"        // Reset guard",
                    f"        if ({rst_cond}) begin",
                    f"            // Reset state holds",
                    f"        end else if (f_past_valid) begin",
                    f"            // Sequentially verified candidate properties",
                    *checks_code,
                    f"        end",
                    f"    end",
                ]
            else:
                wrapper_lines += [
                    f"",
                    f"        // Environment Assumptions",
                    *assumptions_code,
                    f"",
                    f"        if (f_past_valid) begin",
                    *checks_code,
                    f"        end",
                    f"    end",
                ]
        else:
            # Combinational design: procedural check on all signal inputs
            wrapper_lines += [
                f"    always @(*) begin",
                f"        // Environment Assumptions",
                *assumptions_code,
                f"",
                f"        // Combinational candidate properties",
                *checks_code,
                f"    end",
            ]

        wrapper_lines += [
            f"`endif // FORMAL",
            f"",
            f"endmodule",
            f"`default_nettype wire",
            f""
        ]

        source_code = "\n".join(wrapper_lines)

        return SynthesizedCheckerResult(
            wrapper_module_name=wrapper_name,
            wrapper_source_code=source_code,
            top_module=top_name,
            properties=properties_meta,
            has_clock=has_clock,
            clock_signal=clock_sig,
            reset_signal=reset_sig,
            reset_polarity=reset_polarity
        )
