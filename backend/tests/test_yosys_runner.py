import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.app.services.hdl.yosys_runner import YosysRunner


class TestYosysRunner(unittest.TestCase):
    def test_rejects_invalid_top_module_identifier(self):
        with self.assertRaisesRegex(ValueError, "valid Verilog identifier"):
            YosysRunner(mode="native").run([], "top; write_json hacked.json", Path("unused.json"))

    def test_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                YosysRunner(mode="native").run([Path(tmp) / "missing.v"], "top", Path(tmp) / "out.json")

    @patch("backend.app.services.hdl.yosys_runner.subprocess.run")
    @patch("backend.app.services.hdl.yosys_runner.shutil.which", return_value="/usr/bin/yosys")
    def test_native_runner_writes_script_and_reads_output(self, _which, run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "top.v"
            src.write_text("module top; endmodule")
            out = Path(tmp) / "out.json"

            def fake_run(*args, **kwargs):
                out.write_text('{"modules":{"top":{}}}')
                result = MagicMock()
                result.returncode = 0
                result.stdout = "Yosys done"
                result.stderr = ""
                return result

            run_mock.side_effect = fake_run
            log = YosysRunner(mode="native").run([src], "top", out)
            self.assertIn("Yosys done", log)
            self.assertTrue(out.exists())
            self.assertEqual(run_mock.call_args.args[0][0], "yosys")

    @patch("backend.app.services.hdl.yosys_runner.subprocess.run")
    def test_wsl_path_uses_forward_slashes_for_windows_paths(self, run_mock):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "/mnt/c/Users/example/source_0.sv\n"
        result.stderr = ""
        run_mock.return_value = result

        fake_path = MagicMock()
        fake_path.resolve.return_value = r"C:\Users\example\source_0.sv"
        translated = YosysRunner(mode="wsl")._wsl_path(fake_path)

        self.assertEqual(translated, "/mnt/c/Users/example/source_0.sv")
        passed_path = run_mock.call_args.args[0][-1]
        self.assertEqual(passed_path, "C:/Users/example/source_0.sv")
        self.assertNotIn("\\", passed_path)


if __name__ == "__main__":
    unittest.main()
