import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.services.hdl.yosys_probe_instrumenter import YosysProbeInstrumenter


class YosysProbeInstrumenterTests(unittest.TestCase):
    def test_probe_port_uses_exact_yosys_bit_ids(self):
        instrumenter = YosysProbeInstrumenter(mode="native")
        fixture = {
            "modules": {
                "demo": {
                    "ports": {
                        "clk": {"direction": "input", "bits": [1], "port_id": 1}
                    },
                    "netnames": {
                        "state": {
                            "bits": [10, 11, 12, 13],
                            "offset": 0,
                            "upto": 0,
                            "signed": 0,
                        }
                    },
                }
            }
        }

        def fake_elaboration(source_paths, top, output_json):
            Path(output_json).write_text(json.dumps(fixture), encoding="utf-8")

        instrumenter.runner.run = fake_elaboration

        def fake_yosys(command, **kwargs):
            script = Path(command[-1]).read_text(encoding="utf-8")
            match = re.search(r'write_verilog -noattr "([^"]+)"', script)
            self.assertIsNotNone(match)
            Path(match.group(1)).write_text(
                "module demo(input clk, output [3:0] __formal_probe_state); endmodule\n",
                encoding="utf-8",
            )

            # Ensure the JSON passed to read_json contains the exact original bit IDs.
            json_match = re.search(r'read_json "([^"]+)"', script)
            transformed = json.loads(Path(json_match.group(1)).read_text())
            port = transformed["modules"]["demo"]["ports"]["__formal_probe_state"]
            self.assertEqual(port["bits"], [10, 11, 12, 13])
            self.assertEqual(port["direction"], "output")
            return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch("backend.app.services.hdl.yosys_probe_instrumenter.subprocess.run", side_effect=fake_yosys):
            result = instrumenter.instrument({"demo.sv": "module demo; endmodule"}, "demo", ["state"])

        self.assertEqual(result.probe_ports, {"state": "__formal_probe_state"})
        self.assertIn("__formal_probe_state", result.netlist_source)

    def test_wsl_conversion_script_uses_linux_paths_for_json_and_verilog(self):
        instrumenter = YosysProbeInstrumenter(mode="wsl")
        fixture = {
            "modules": {
                "demo": {
                    "ports": {"clk": {"direction": "input", "bits": [1], "port_id": 1}},
                    "netnames": {"state": {"bits": [10], "offset": 0, "upto": 0, "signed": 0}},
                }
            }
        }

        def fake_elaboration(source_paths, top, output_json):
            Path(output_json).write_text(json.dumps(fixture), encoding="utf-8")

        instrumenter.runner.run = fake_elaboration
        translated = {}
        host_paths = {}

        def fake_wsl_path(path):
            path = Path(path)
            value = f"/mnt/c/Users/test/AppData/Local/Temp/{path.name}"
            translated[path.name] = value
            host_paths[path.name] = path
            return value

        instrumenter.runner._wsl_path = fake_wsl_path

        def fake_yosys(command, **kwargs):
            script = host_paths["convert.ys"].read_text(encoding="utf-8")
            self.assertIn(f'read_json "{translated["instrumented.json"]}"', script)
            self.assertIn(f'write_verilog -noattr "{translated["instrumented_design.v"]}"', script)
            self.assertNotIn('C:/Users/', script)
            # The fake WSL process writes to the host-side temp file, standing in
            # for Yosys writing to its equivalent /mnt/c path.
            host_output = host_paths["instrumented_design.v"]
            host_output.write_text("module demo(input clk, output __formal_probe_state); endmodule\n", encoding="utf-8")
            return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch("backend.app.services.hdl.yosys_probe_instrumenter.subprocess.run", side_effect=fake_yosys):
            result = instrumenter.instrument({"demo.sv": "module demo; endmodule"}, "demo", ["state"])

        self.assertEqual(result.probe_ports, {"state": "__formal_probe_state"})

    def test_missing_or_constant_internal_net_fails_closed(self):
        instrumenter = YosysProbeInstrumenter(mode="native")
        fixture = {
            "modules": {
                "demo": {
                    "ports": {},
                    "netnames": {"state": {"bits": ["0", 10]}},
                }
            }
        }

        def fake_elaboration(source_paths, top, output_json):
            Path(output_json).write_text(json.dumps(fixture), encoding="utf-8")

        instrumenter.runner.run = fake_elaboration
        with self.assertRaisesRegex(ValueError, "constants/unknown bits"):
            instrumenter.instrument({"demo.sv": "module demo; endmodule"}, "demo", ["state"])

    def test_conversion_failure_preserves_command_script_and_yosys_output(self):
        instrumenter = YosysProbeInstrumenter(mode="native")
        fixture = {
            "modules": {
                "demo": {
                    "ports": {"clk": {"direction": "input", "bits": [1], "port_id": 1}},
                    "netnames": {"state": {"bits": [10], "offset": 0, "upto": 0, "signed": 0}},
                }
            }
        }

        def fake_elaboration(source_paths, top, output_json):
            Path(output_json).write_text(json.dumps(fixture), encoding="utf-8")

        instrumenter.runner.run = fake_elaboration

        def fake_yosys(command, **kwargs):
            return type("Completed", (), {
                "returncode": 1,
                "stdout": "Yosys stdout diagnostic",
                "stderr": "ERROR: synthetic JSON conversion failure",
            })()

        with patch("backend.app.services.hdl.yosys_probe_instrumenter.subprocess.run", side_effect=fake_yosys):
            with self.assertRaisesRegex(Exception, "failed while converting") as caught:
                instrumenter.instrument({"demo.sv": "module demo; endmodule"}, "demo", ["state"])

        error = caught.exception
        self.assertEqual(error.returncode, 1)
        self.assertIn("read_json", error.output)
        self.assertIn("write_verilog", error.output)
        self.assertIn("synthetic JSON conversion failure", error.output)
        self.assertIn("Working directory:", error.output)


if __name__ == "__main__":
    unittest.main()
