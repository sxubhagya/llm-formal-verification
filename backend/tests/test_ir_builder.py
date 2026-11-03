import unittest
from backend.app.services.hdl.ir_builder import build_design_ir

class TestIRBuilder(unittest.TestCase):
    def test_extracts_ports_cells_register_and_clock_reset_candidates(self):
        raw = {"modules": {"counter": {"ports": {"clk": {"direction":"input", "bits":[2]}, "q": {"direction":"output", "bits":[3,4]}}, "netnames": {"q": {"bits":[3,4], "attributes":{}}}, "cells": {"$procdff$1": {"type":"$adff", "parameters":{"WIDTH":"00000000000000000000000000000010"}, "connections":{"CLK":[2], "ARST":[5], "D":[6,7], "Q":[3,4]}, "port_directions":{"CLK":"input", "ARST":"input", "D":"input", "Q":"output"}}}}}}
        ir = build_design_ir(raw, ["counter.sv"], "counter")
        module = ir.modules[0]
        self.assertEqual(module.ports[0].direction, "input")
        self.assertEqual(len(module.registers), 1)
        self.assertEqual(module.registers[0].clock_bits, [2])
        self.assertEqual(module.registers[0].reset_bits, [5])
        self.assertEqual(module.registers[0].reset_kind, "asynchronous")

    def test_resolves_clock_and_sync_reset_candidates_to_port_names(self):
        raw = {"modules": {"counter_sync": {
            "ports": {
                "clk": {"direction": "input", "bits": [2]},
                "rst_n": {"direction": "input", "bits": [3]},
                "enable": {"direction": "input", "bits": [4]},
                "count": {"direction": "output", "bits": list(range(5, 13))}
            },
            "netnames": {},
            "cells": {
                "$auto$ff$1": {
                    "type": "$sdffe",
                    "parameters": {"CLK_POLARITY": "1", "SRST_POLARITY": "0", "SRST_VALUE": "00000000"},
                    "connections": {"CLK": [2], "SRST": [3], "EN": [4], "D": list(range(13, 21)), "Q": list(range(5, 13))},
                    "port_directions": {"CLK": "input", "SRST": "input", "EN": "input", "D": "input", "Q": "output"}
                }
            }
        }}}
        module = build_design_ir(raw, ["counter_sync.sv"], "counter_sync").modules[0]
        self.assertEqual(module.clock_candidates[0]["name"], "clk")
        self.assertEqual(module.clock_candidates[0]["signal"], "clk")
        self.assertEqual(module.reset_candidates[0]["name"], "rst_n")
        self.assertEqual(module.reset_candidates[0]["kind"], "synchronous")
        self.assertEqual(module.registers[0].clock_bits, [2])
        self.assertEqual(module.registers[0].reset_bits, [3])

    def test_missing_top_module_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Top module"):
            build_design_ir({"modules": {"other": {}}}, [], "missing")

    def test_adds_module_summary_and_cell_connectivity(self):
        raw = {"modules": {"top": {
            "ports": {"a": {"direction":"input","bits":[1]}, "y": {"direction":"output","bits":[3]}},
            "netnames": {},
            "cells": {
                "gate_a": {"type":"$not", "connections":{"A":[1],"Y":[2]}, "port_directions":{"A":"input","Y":"output"}},
                "gate_b": {"type":"$not", "connections":{"A":[2],"Y":[3]}, "port_directions":{"A":"input","Y":"output"}}
            }
        }}}
        ir = build_design_ir(raw, ["top.v"], "top")
        module = ir.modules[0]
        self.assertEqual(ir.ir_version, "1.3")
        self.assertEqual(module.summary.cell_count, 2)
        self.assertEqual(module.summary.input_port_count, 1)
        self.assertEqual(module.cells[1].driven_by, ["gate_a"])
        self.assertIn("gate_b", module.cells[0].drives)

    def test_identifies_module_instances(self):
        raw = {"modules": {
            "child": {"ports": {}, "netnames": {}, "cells": {}},
            "top": {"ports": {}, "netnames": {}, "cells": {
                "u_child": {"type":"child", "connections":{}, "port_directions":{}}
            }}
        }}
        ir = build_design_ir(raw, [], "top")
        top = next(m for m in ir.modules if m.name == "top")
        self.assertEqual(top.summary.module_instance_count, 1)
        self.assertEqual(top.cells[0].category, "module_instance")


    def test_extracts_clocked_memory_write_access(self):
        raw = {"modules": {"rf": {"ports": {}, "netnames": {}, "cells": {
            "mem_write": {"type":"$memwr_v2", "parameters":{"CLK_ENABLE":"1","WIDTH":"00001000"},
                "connections":{"ADDR":[1,2,3],"DATA":[4,5],"EN":[6,6],"CLK":[7]},
                "port_directions":{"ADDR":"input","DATA":"input","EN":"input","CLK":"input"}}
        }}}}
        module = build_design_ir(raw, [], "rf").modules[0]
        self.assertEqual(len(module.memory_accesses), 1)
        self.assertEqual(module.memory_accesses[0].operation, "write")
        self.assertTrue(module.memory_accesses[0].clocked)
        self.assertEqual(module.clock_candidates[0]["bits"], [7])

    def test_extracts_enum_state_candidate(self):
        raw = {"modules": {"fsm": {"ports": {}, "netnames": {
            "state": {"bits":[1,2], "attributes":{"enum_value_00":"\\\\IDLE","enum_value_01":"\\\\BUSY"}}
        }, "cells": {}}}}
        module = build_design_ir(raw, [], "fsm").modules[0]
        self.assertEqual(len(module.fsm_candidates), 1)
        self.assertEqual(module.fsm_candidates[0].state_net, "state")

if __name__ == "__main__": unittest.main()
