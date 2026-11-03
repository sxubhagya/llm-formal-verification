"""Stable, tool-independent representation of an elaborated RTL design."""
from typing import Any
from pydantic import BaseModel, Field

class PortIR(BaseModel):
    name: str
    direction: str
    bit_width: int
    bits: list[int | str] = Field(default_factory=list)
    is_signed: bool = False
    offset: int = 0
    upto: bool = False

class NetIR(BaseModel):
    name: str
    bit_width: int
    bits: list[int | str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    is_signed: bool = False
    offset: int = 0
    upto: bool = False

class CellIR(BaseModel):
    name: str
    cell_type: str
    connections: dict[str, list[int | str]] = Field(default_factory=dict)
    input_connections: dict[str, list[int | str]] = Field(default_factory=dict)
    output_connections: dict[str, list[int | str]] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    category: str = "other"
    driven_by: list[str] = Field(default_factory=list)
    drives: list[str] = Field(default_factory=list)

class RegisterIR(BaseModel):
    cell_name: str
    cell_type: str
    data_inputs: dict[str, list[int | str]] = Field(default_factory=dict)
    data_outputs: dict[str, list[int | str]] = Field(default_factory=dict)
    clock_bits: list[int | str] = Field(default_factory=list)
    reset_bits: list[int | str] = Field(default_factory=list)
    reset_kind: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

class MemoryAccessIR(BaseModel):
    cell_name: str
    cell_type: str
    operation: str
    address_bits: list[int | str] = Field(default_factory=list)
    data_bits: list[int | str] = Field(default_factory=list)
    enable_bits: list[int | str] = Field(default_factory=list)
    clock_bits: list[int | str] = Field(default_factory=list)
    clocked: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)

class FSMCandidateIR(BaseModel):
    state_net: str
    state_bits: list[int | str] = Field(default_factory=list)
    encoded_states: dict[str, str] = Field(default_factory=dict)
    confidence: str = "candidate"
    note: str = "Inferred from enum-like net attributes; transition behaviour has not been reconstructed."

class ModuleSummaryIR(BaseModel):
    port_count: int = 0
    input_port_count: int = 0
    output_port_count: int = 0
    net_count: int = 0
    cell_count: int = 0
    sequential_cell_count: int = 0
    combinational_cell_count: int = 0
    module_instance_count: int = 0
    memory_cell_count: int = 0
    cell_type_counts: dict[str, int] = Field(default_factory=dict)

class ModuleIR(BaseModel):
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    ports: list[PortIR] = Field(default_factory=list)
    nets: list[NetIR] = Field(default_factory=list)
    cells: list[CellIR] = Field(default_factory=list)
    registers: list[RegisterIR] = Field(default_factory=list)
    memory_accesses: list[MemoryAccessIR] = Field(default_factory=list)
    fsm_candidates: list[FSMCandidateIR] = Field(default_factory=list)
    clock_candidates: list[dict[str, Any]] = Field(default_factory=list)
    reset_candidates: list[dict[str, Any]] = Field(default_factory=list)
    summary: ModuleSummaryIR = Field(default_factory=ModuleSummaryIR)

class DesignIR(BaseModel):
    ir_version: str = "1.3"
    frontend: str = "yosys"
    top_module: str
    source_files: list[str]
    modules: list[ModuleIR]
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
