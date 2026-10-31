# RTL Examples

These designs are controlled test inputs, not hardcoded verification solutions.

- `counter/counter.sv`: enabled counter with active-low asynchronous reset.
- `comb_alu/comb_alu.v`: combinational arithmetic/logic unit.
- `traffic_light/traffic_light.sv`: three-state traffic-light controller.
- `register_file/register_file.sv`: 8 x 8-bit register file with synchronous write and asynchronous read.
- `multi_module/alu_core.sv` + `multi_module/top_system.sv`: a hierarchical top-level design instantiating an ALU and output register.

The examples are intended to exercise parsing and structural IR extraction. They are not yet a formal benchmark with independently proven reference properties. Yosys may represent memories, FSMs, and procedural logic using internal cells; the IR reports those structures conservatively and does not claim to infer complete behavioural specifications.
