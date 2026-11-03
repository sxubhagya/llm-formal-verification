"""Prepare structured design context from DesignIR for LLM prompt construction."""
from __future__ import annotations
from typing import Any
from backend.app.models.design_ir import DesignIR, ModuleIR


def _decode_bit_parameter(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if value in (0, 1) else None
    raw = str(value).strip().replace("_", "")
    if raw in {"0", "1"}:
        return int(raw)
    import re
    match = re.fullmatch(r"[0-9]+'[sS]?[bB]([01]+)", raw)
    if match:
        number = int(match.group(1), 2)
        return number if number in (0, 1) else None
    if re.fullmatch(r"[01]+", raw):
        number = int(raw, 2)
        return number if number in (0, 1) else None
    return None


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
            if p['bit_width'] > 1 or p.get("offset", 0) != 0 or p.get("upto", False):
                left = p["offset"] if p.get("upto", False) else p["offset"] + p["bit_width"] - 1
                right = p["offset"] + p["bit_width"] - 1 if p.get("upto", False) else p["offset"]
                width_str = f"[{left}:{right}]"
            else:
                width_str = "[0:0]"
            signed = " signed" if p.get("is_signed") else " unsigned"
            port_lines.append(f"  - `{p['name']}`: {p['direction']} {width_str} ({p['bit_width']} bits, {signed.strip()})")
        sections.append("## Ports\n" + ("\n".join(port_lines) if port_lines else "  None"))
        # Named internal nets from the elaborated target module are candidate
        # observation points. They are not inferred from raw RTL text.
        net_lines = []
        port_names = {p["name"] for p in self.ports}
        for name, width in sorted(self.signal_map.items()):
            if name in port_names:
                continue
            net_lines.append(f"  - `{name}`: internal net ({width} bit(s)); hierarchical probe required")
        sections.append(
            "## Signal Observation Boundary\n"
            "Top-level ports bind directly. Named internal nets listed below may be referenced; "
            "the formal wrapper binds them explicitly through the instantiated DUT hierarchy. "
            "Never invent names, widths, or signals. If a required internal net is absent from this list, omit the property. "
            "Memory arrays themselves are not directly observable in this build; reason from exposed memory interface/state signals.\n"
            + ("## Named Internal Nets\n" + "\\n".join(net_lines) if net_lines else "## Named Internal Nets\\n  None")
        )

        # Clock Context
        if self.clock_context:
            sections.append(
                f"## Inferred Clock Context\n"
                f"  - Signal: `{self.clock_context['signal']}`\n"
                f"  - Edge: {self.clock_context['edge']}\n"
                f"  - Source Cells: {', '.join(self.clock_context.get('source_cells', []))}"
            )
        else:
            if self.summary.get("sequential_cell_count", 0) == 0 and self.summary.get("memory_cell_count", 0) == 0:
                sections.append("## Clock Context\n  No clocked elements structurally identified (combinational design).")
            else:
                sections.append("## Clock Context\n  Clocked state was identified, but no unambiguous clock edge was established. Do not assume posedge; omit temporal candidates or request explicit designer confirmation.")

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
    context_warnings = list(design.warnings)
    clock_ctx: dict[str, Any] | None = None
    if module.clock_candidates:
        cand = module.clock_candidates[0]
        clk_bits = [str(b) for b in cand.get("bits", [])]
        clk_port = next((bit_to_port[b] for b in clk_bits if b in bit_to_port), None)
        if clk_port:
            polarities = {
                _decode_bit_parameter((r.parameters or {}).get("CLK_POLARITY"))
                for r in module.registers
                if [str(bit) for bit in r.clock_bits] == clk_bits
            }
            polarities.update({
                _decode_bit_parameter((access.parameters or {}).get("CLK_POLARITY"))
                for access in module.memory_accesses
                if access.clocked and [str(bit) for bit in access.clock_bits] == clk_bits
            })
            if len(polarities) == 1 and None not in polarities:
                edge = "posedge" if next(iter(polarities)) == 1 else "negedge"
                clock_ctx = {
                    "signal": clk_port,
                    "edge": edge,
                    "source_cells": cand.get("source_cells", [])
                }
            else:
                context_warnings.append(
                    f"Clock candidate '{clk_port}' was found, but its active edge could not be established unambiguously from sequential-cell metadata. Explicit clock-edge review is required."
                )

    # Inferred reset context. Signal names such as rst_n are not reliable
    # evidence of polarity; use the elaborated sequential-cell polarity.
    reset_ctx: dict[str, Any] | None = None
    if module.reset_candidates:
        rcand = module.reset_candidates[0]
        rst_bits = [str(b) for b in rcand.get("bits", [])]
        rst_port = next((bit_to_port[b] for b in rst_bits if b in bit_to_port), None)
        if rst_port:
            reset_kind = rcand.get("kind", "unknown")
            polarity_parameter = "ARST_POLARITY" if reset_kind == "asynchronous" else "SRST_POLARITY" if reset_kind == "synchronous" else None
            polarities = {
                _decode_bit_parameter((r.parameters or {}).get(polarity_parameter))
                for r in module.registers
                if polarity_parameter and [str(bit) for bit in r.reset_bits] == rst_bits
            }
            if len(polarities) == 1 and None not in polarities:
                polarity = "active_high" if next(iter(polarities)) == 1 else "active_low"
                reset_ctx = {
                    "signal": rst_port,
                    "polarity": polarity,
                    "asynchronous": (reset_kind == "asynchronous"),
                    "kind": reset_kind,
                    "source_cells": rcand.get("source_cells", [])
                }
            else:
                context_warnings.append(
                    f"Reset candidate '{rst_port}' was found, but its active polarity could not be established unambiguously from sequential-cell metadata. Do not infer polarity from the signal name."
                )

    ports_data = [
        {"name": p.name, "direction": p.direction, "bit_width": p.bit_width, "is_signed": p.is_signed, "offset": p.offset, "upto": p.upto}
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
        warnings=context_warnings,
        limitations=design.limitations,
        source_code=source_code,
        focus_areas=focus_areas
    )
