"""Prepare structured design context from DesignIR for LLM prompt construction."""
from __future__ import annotations
from typing import Any
from backend.app.models.design_ir import DesignIR, ModuleIR


class DesignContext:
    """Encapsulates prepared context for a target module."""

    def __init__(
        self,
        design_top: str,
        module_name: str,
        ports: list[dict[str, Any]],
        registers: list[dict[str, Any]],
        clock_context: dict[str, Any] | None,
        reset_context: dict[str, Any] | None,
        memory_accesses: list[dict[str, Any]],
        fsm_candidates: list[dict[str, Any]],
        summary: dict[str, Any],
        signal_map: dict[str, int],
        warnings: list[str],
        limitations: list[str],
        source_code: str | None = None,
        focus_areas: list[str] | None = None
    ) -> None:
        self.design_top = design_top
        self.module_name = module_name
        self.ports = ports
        self.registers = registers
        self.clock_context = clock_context
        self.reset_context = reset_context
        self.memory_accesses = memory_accesses
        self.fsm_candidates = fsm_candidates
        self.summary = summary
        self.signal_map = signal_map
        self.warnings = warnings
        self.limitations = limitations
        self.source_code = source_code
        self.focus_areas = focus_areas or []

    def to_prompt_text(self) -> str:
        """Format the structured context into a clear text prompt for the LLM."""
        sections: list[str] = []

        sections.append(f"## Design Overview\n- Top Module: `{self.design_top}`\n- Target Module: `{self.module_name}`")

        # Ports
        port_lines = []
        for p in self.ports:
            width_str = f"[{p['bit_width']-1}:0]" if p['bit_width'] > 1 else "[0:0]"
            port_lines.append(f"  - `{p['name']}`: {p['direction']} {width_str} ({p['bit_width']} bits)")
        sections.append("## Ports\n" + ("\n".join(port_lines) if port_lines else "  None"))

        # Clock Context
        if self.clock_context:
            sections.append(
                f"## Inferred Clock Context\n"
                f"  - Signal: `{self.clock_context['signal']}`\n"
                f"  - Edge: {self.clock_context['edge']}\n"
                f"  - Source Cells: {', '.join(self.clock_context.get('source_cells', []))}"
            )
        else:
            sections.append("## Clock Context\n  No clocked elements structurally identified (combinational design).")

        # Reset Context
        if self.reset_context:
            sections.append(
                f"## Inferred Reset Context\n"
                f"  - Signal: `{self.reset_context['signal']}`\n"
                f"  - Polarity: {self.reset_context['polarity']}\n"
                f"  - Asynchronous: {self.reset_context.get('asynchronous', False)}\n"
                f"  - Reset Kind: {self.reset_context.get('kind', 'unknown')}"
            )
        else:
            sections.append("## Reset Context\n  No structural reset detected.")

        # Registers
        if self.registers:
            reg_lines = []
            for r in self.registers:
                reg_lines.append(f"  - Register `{r['cell_name']}` ({r['cell_type']}): kind={r.get('reset_kind')}")
            sections.append(f"## Sequential State Elements ({len(self.registers)})\n" + "\n".join(reg_lines[:15]))

        # Memory Accesses
        if self.memory_accesses:
            mem_lines = []
            for m in self.memory_accesses:
                mem_lines.append(f"  - `{m['cell_name']}`: op={m['operation']}, clocked={m['clocked']}")
            sections.append(f"## Memory Accesses ({len(self.memory_accesses)})\n" + "\n".join(mem_lines))

        # FSM Candidates
        if self.fsm_candidates:
            fsm_lines = []
            for f in self.fsm_candidates:
                states_str = ", ".join(f"{k}={v}" for k, v in f.get('encoded_states', {}).items())
                fsm_lines.append(f"  - State Net `{f['state_net']}`: {states_str}")
            sections.append(f"## Inferred FSM State Candidates\n" + "\n".join(fsm_lines))

        # Warnings / Limitations
        if self.warnings or self.limitations:
            note_lines = [f"  - {w}" for w in (self.warnings + self.limitations)]
            sections.append("## Elaboration Notes & Boundary Limitations\n" + "\n".join(note_lines[:5]))

        # Source Code Snippet
        if self.source_code:
            code_snippet = self.source_code.strip()
            if len(code_snippet) > 2000:
                code_snippet = code_snippet[:2000] + "\n... [source truncated]"
            sections.append(f"## Relevant RTL Source Code\n```verilog\n{code_snippet}\n```")

        if self.focus_areas:
            sections.append(f"## Priority Focus Areas Requested\n" + "\n".join(f"  - {f}" for f in self.focus_areas))

        return "\n\n".join(sections)


def build_design_context(
    design: DesignIR | dict[str, Any],
    target_module: str | None = None,
    source_code: str | None = None,
    focus_areas: list[str] | None = None
) -> DesignContext:
    """Extract and synthesize context from DesignIR for LLM property generation."""
    if isinstance(design, dict):
        design = DesignIR.model_validate(design)

    target_name = target_module or design.top_module
    module: ModuleIR | None = next((m for m in design.modules if m.name == target_name), None)
    if module is None:
        raise ValueError(
            f"Target module '{target_name}' not found in DesignIR. Available: {[m.name for m in design.modules]}"
        )

    # Signal map: name -> bit_width
    signal_map: dict[str, int] = {p.name: p.bit_width for p in module.ports}
    signal_map.update({n.name: n.bit_width for n in module.nets})

    # Bit map for identifying clock/reset ports
    bit_to_port: dict[str, str] = {}
    for p in module.ports:
        for bit in p.bits:
            bit_to_port[str(bit)] = p.name

    # Inferred clock context
    clock_ctx: dict[str, Any] | None = None
    if module.clock_candidates:
        cand = module.clock_candidates[0]
        clk_bits = [str(b) for b in cand.get("bits", [])]
        clk_port = next((bit_to_port[b] for b in clk_bits if b in bit_to_port), None)
        if clk_port:
            edge = "posedge"
            # check register cell parameters for CLK_POLARITY if available
            for r in module.registers:
                params = r.parameters or {}
                if "CLK_POLARITY" in params and str(params["CLK_POLARITY"]) in {"0", "0'b0"}:
                    edge = "negedge"
                    break
            clock_ctx = {
                "signal": clk_port,
                "edge": edge,
                "source_cells": cand.get("source_cells", [])
            }

    # Inferred reset context
    reset_ctx: dict[str, Any] | None = None
    if module.reset_candidates:
        rcand = module.reset_candidates[0]
        rst_bits = [str(b) for b in rcand.get("bits", [])]
        rst_port = next((bit_to_port[b] for b in rst_bits if b in bit_to_port), None)
        if rst_port:
            polarity = "active_high"
            if "rst_n" in rst_port.lower() or "resetn" in rst_port.lower() or "reset_n" in rst_port.lower():
                polarity = "active_low"
            # check register parameters
            for r in module.registers:
                params = r.parameters or {}
                if "ARST_POLARITY" in params and str(params["ARST_POLARITY"]) in {"0", "0'b0"}:
                    polarity = "active_low"
                    break
            reset_ctx = {
                "signal": rst_port,
                "polarity": polarity,
                "asynchronous": (rcand.get("kind") == "asynchronous"),
                "kind": rcand.get("kind", "unknown"),
                "source_cells": rcand.get("source_cells", [])
            }

    ports_data = [
        {"name": p.name, "direction": p.direction, "bit_width": p.bit_width}
        for p in module.ports
    ]

    regs_data = [
        {"cell_name": r.cell_name, "cell_type": r.cell_type, "reset_kind": r.reset_kind}
        for r in module.registers
    ]

    mem_data = [
        {"cell_name": m.cell_name, "operation": m.operation, "clocked": m.clocked}
        for m in module.memory_accesses
    ]

    fsm_data = [
        {"state_net": f.state_net, "encoded_states": f.encoded_states}
        for f in module.fsm_candidates
    ]

    summary_data = module.summary.model_dump()

    return DesignContext(
        design_top=design.top_module,
        module_name=target_name,
        ports=ports_data,
        registers=regs_data,
        clock_context=clock_ctx,
        reset_context=reset_ctx,
        memory_accesses=mem_data,
        fsm_candidates=fsm_data,
        summary=summary_data,
        signal_map=signal_map,
        warnings=design.warnings,
        limitations=design.limitations,
        source_code=source_code,
        focus_areas=focus_areas
    )
