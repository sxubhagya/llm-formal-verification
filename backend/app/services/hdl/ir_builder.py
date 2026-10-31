"""Convert Yosys JSON into a stable IR with conservative structural relationships."""
from __future__ import annotations
from collections import Counter
from typing import Any
from backend.app.models.design_ir import (
    DesignIR, ModuleIR, PortIR, NetIR, CellIR, RegisterIR, ModuleSummaryIR,
    MemoryAccessIR, FSMCandidateIR
)

SEQ_PREFIXES = ("$dff", "$adff", "$sdff", "$dffe", "$adffe", "$sdffe", "$aldff", "$dlatch", "$adlatch")
COMB_PREFIXES = ("$and", "$or", "$xor", "$not", "$logic", "$mux", "$pmux", "$add", "$sub", "$mul", "$div", "$mod", "$lt", "$le", "$eq", "$ne", "$ge", "$gt", "$shl", "$shr", "$sshl", "$sshr", "$reduce", "$concat", "$pos", "$neg", "$buf")

def _category(cell_type: str, module_names: set[str]) -> str:
    if cell_type.startswith(SEQ_PREFIXES): return "sequential"
    if cell_type.startswith(COMB_PREFIXES): return "combinational"
    if cell_type in module_names: return "module_instance"
    if cell_type.startswith(("$mem", "$memory")): return "memory"
    if cell_type.startswith("$"): return "internal"
    return "other"

def build_design_ir(raw: dict[str, Any], source_files: list[str], top_module: str) -> DesignIR:
    raw_modules = raw.get("modules", {})
    if top_module not in raw_modules:
        raise ValueError(f"Top module '{top_module}' was not found in Yosys JSON. Available modules: {', '.join(raw_modules)}")
    module_names = set(raw_modules)
    modules: list[ModuleIR] = []
    warnings: list[str] = []
    for module_name, module in raw_modules.items():
        ports = [PortIR(name=n, direction=p.get("direction", "unknown"), bit_width=len(p.get("bits", [])), bits=p.get("bits", [])) for n,p in module.get("ports", {}).items()]
        nets = [NetIR(name=n, bit_width=len(v.get("bits", [])), bits=v.get("bits", []), attributes=v.get("attributes", {})) for n,v in module.get("netnames", {}).items()]
        cells: list[CellIR] = []
        registers: list[RegisterIR] = []
        memory_accesses: list[MemoryAccessIR] = []
        fsm_candidates: list[FSMCandidateIR] = []
        clock_map: dict[str, dict[str, Any]] = {}
        reset_map: dict[str, dict[str, Any]] = {}
        producer_by_bit: dict[str, str] = {}
        cell_pending: list[tuple[CellIR, dict[str, Any]]] = []
        for cell_name, cell in module.get("cells", {}).items():
            ctype = cell.get("type", "unknown")
            conns = cell.get("connections", {})
            directions = cell.get("port_directions", {})
            params = cell.get("parameters", {})
            inputs = {k:v for k,v in conns.items() if directions.get(k) == "input"}
            outputs = {k:v for k,v in conns.items() if directions.get(k) == "output"}
            item = CellIR(name=cell_name, cell_type=ctype, connections=conns,
                          input_connections=inputs, output_connections=outputs,
                          parameters=params, category=_category(ctype, module_names))
            cells.append(item)
            cell_pending.append((item, cell))
            for bits in outputs.values():
                for bit in bits:
                    producer_by_bit[str(bit)] = cell_name
            if ctype.startswith(("$memrd", "$memwr")):
                operation = "read" if ctype.startswith("$memrd") else "write"
                clock_bits = conns.get("CLK", [])
                clk_enabled = str(params.get("CLK_ENABLE", "0")).strip("0") != "" and str(params.get("CLK_ENABLE", "0")) not in {"0", ""}
                valid_clock_bits = [b for b in clock_bits if str(b).lower() not in {"x", "z"}]
                memory_accesses.append(MemoryAccessIR(
                    cell_name=cell_name, cell_type=ctype, operation=operation,
                    address_bits=conns.get("ADDR", []),
                    data_bits=conns.get("DATA", []),
                    enable_bits=conns.get("EN", []),
                    clock_bits=clock_bits, clocked=bool(clk_enabled and valid_clock_bits),
                    parameters=params))
                if clk_enabled and valid_clock_bits:
                    key=str(valid_clock_bits)
                    clock_map[key]={"bits":valid_clock_bits,"source_cells":sorted(set(clock_map.get(key,{}).get("source_cells",[])+[cell_name])),"source_kind":"memory"}
            if ctype.startswith(SEQ_PREFIXES):
                clock_bits = conns.get("CLK", conns.get("G", []))
                reset_pin = next((pin for pin in ("ARST", "SRST", "ALOAD", "SET", "CLR") if pin in conns), None)
                reset_bits = conns.get(reset_pin, []) if reset_pin else []
                din = {k:v for k,v in inputs.items() if k not in ("CLK", "G", "ARST", "SRST", "ALOAD", "SET", "CLR")}
                registers.append(RegisterIR(cell_name=cell_name, cell_type=ctype, data_inputs=din,
                    data_outputs=outputs, clock_bits=clock_bits, reset_bits=reset_bits,
                    reset_kind=("asynchronous" if reset_pin == "ARST" else "synchronous" if reset_pin == "SRST" else "load/set/clear" if reset_pin else None), parameters=params))
                if clock_bits:
                    key=str(clock_bits); clock_map[key]={"bits":clock_bits,"source_cells":sorted(set(clock_map.get(key,{}).get("source_cells",[])+[cell_name])),"source_kind":"sequential"}
                if reset_bits:
                    key=str(reset_bits); reset_map[key]={"bits":reset_bits,"kind":"asynchronous" if reset_pin=="ARST" else "synchronous" if reset_pin=="SRST" else "load/set/clear","source_cells":sorted(set(reset_map.get(key,{}).get("source_cells",[])+[cell_name]))}
        for item, _ in cell_pending:
            drivers=set()
            for bits in item.input_connections.values():
                drivers.update(producer_by_bit[str(bit)] for bit in bits if str(bit) in producer_by_bit and producer_by_bit[str(bit)] != item.name)
            item.driven_by=sorted(drivers)
            for driver in drivers:
                driver_item=next((c for c in cells if c.name==driver),None)
                if driver_item and item.name not in driver_item.drives:
                    driver_item.drives.append(item.name)
        for net in nets:
            enum_values = {k: str(v).lstrip("\\\\") for k, v in net.attributes.items() if k.startswith("enum_value_")}
            if enum_values:
                fsm_candidates.append(FSMCandidateIR(
                    state_net=net.name, state_bits=net.bits, encoded_states=enum_values))
        counts=Counter(c.cell_type for c in cells)
        summary=ModuleSummaryIR(
            port_count=len(ports),
            input_port_count=sum(p.direction=="input" for p in ports),
            output_port_count=sum(p.direction=="output" for p in ports),
            net_count=len(nets), cell_count=len(cells),
            sequential_cell_count=sum(c.category=="sequential" for c in cells),
            combinational_cell_count=sum(c.category=="combinational" for c in cells),
            module_instance_count=sum(c.category=="module_instance" for c in cells),
            memory_cell_count=sum(c.category=="memory" for c in cells),
            cell_type_counts=dict(sorted(counts.items())))
        modules.append(ModuleIR(name=module_name, attributes=module.get("attributes",{}), ports=ports, nets=nets,
            cells=cells, registers=registers, memory_accesses=memory_accesses,
            fsm_candidates=fsm_candidates, clock_candidates=list(clock_map.values()),
            reset_candidates=list(reset_map.values()), summary=summary))
    if len(raw_modules)>1:
        warnings.append("The IR includes all modules emitted by Yosys. Module-instance cells are identified by matching cell types to module names; confirm hierarchy against the elaboration log.")
    warnings.append("Cell driven_by/drives relationships are inferred from bit-level producer/consumer connections. They are structural approximations and do not establish behavioural intent.")
    warnings.append("Clock/reset candidates are inferred from sequential-cell and clock-enabled memory connections. They are structural clues, not a substitute for a designer-reviewed clock/reset specification.")
    if any(m.fsm_candidates for m in modules):
        warnings.append("FSM candidates are inferred from enum-like net attributes. State transition tables and reachable-state semantics are not reconstructed.")
    return DesignIR(top_module=top_module, source_files=source_files, modules=modules, warnings=warnings,
        limitations=[
            "Initial frontend targets synthesizable Verilog/SystemVerilog accepted by the installed Yosys version.",
            "Procedural intent and source-level constructs may be transformed during Yosys elaboration/optimization.",
            "Clock domains, reset semantics, FSM meaning and signal roles may require additional analysis and designer confirmation.",
            "Cell connectivity is a structural approximation; it does not by itself prove functional dependencies or protocol semantics.",
            "Unsupported or non-synthesizable language constructs may be rejected by Yosys."
        ])
