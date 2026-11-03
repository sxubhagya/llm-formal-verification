"""Expose selected internal Yosys net bits as explicit top-level output ports.

The instrumented netlist is generated from a single Yosys JSON elaboration. This
avoids unsupported/ambiguous hierarchical references in formal wrapper RTL.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.app.services.hdl.yosys_runner import YosysRunner, YosysExecutionError


@dataclass
class ProbeInstrumentationResult:
    netlist_source: str
    probe_ports: dict[str, str]
    elaborated_json: dict
    warnings: list[str]


class YosysProbeInstrumenter:
    def __init__(self, mode: str | None = None, timeout_seconds: int = 90):
        self.runner = YosysRunner(mode=mode, timeout_seconds=timeout_seconds)
        self.mode = mode or "auto"
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _identifier(value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value or ""))

    def instrument(
        self,
        sources: dict[str, str],
        top_module: str,
        internal_signal_names: list[str],
    ) -> ProbeInstrumentationResult:
        if not sources:
            raise ValueError("At least one RTL source is required for probe instrumentation.")
        if not self._identifier(top_module):
            raise ValueError("Invalid top module identifier.")
        names = list(dict.fromkeys(internal_signal_names))
        if not names:
            raise ValueError("At least one internal signal must be selected for probe instrumentation.")
        if any(not self._identifier(name) for name in names):
            raise ValueError("Internal signal names must be simple Verilog identifiers.")

        with tempfile.TemporaryDirectory(prefix="yosys_probe_instrument_") as tmp:
            work = Path(tmp)
            source_paths = []
            for index, (name, content) in enumerate(sources.items()):
                # Caller already validates names at the API boundary; retain only
                # a safe local basename for the temporary elaboration.
                suffix = Path(name).suffix if Path(name).suffix.lower() in {".v", ".sv"} else ".sv"
                path = work / f"source_{index}{suffix}"
                path.write_text(content, encoding="utf-8")
                source_paths.append(path)
            json_path = work / "design.json"
            self.runner.run(source_paths, top_module, json_path)
            design_json = json.loads(json_path.read_text(encoding="utf-8"))
            modules = design_json.get("modules", {})
            if top_module not in modules:
                raise ValueError(f"Yosys JSON does not contain selected top module {top_module!r}.")
            module = modules[top_module]
            ports = module.setdefault("ports", {})
            netnames = module.get("netnames", {})
            existing_names = set(ports) | set(netnames)
            next_port_id = max(
                [int(p.get("port_id", 0)) for p in ports.values()] + [0]
            ) + 1
            probe_ports: dict[str, str] = {}
            for name in names:
                if name in ports:
                    raise ValueError(f"Signal {name!r} is already a top-level port, not an internal net.")
                net = netnames.get(name)
                if net is None:
                    raise ValueError(f"Internal signal {name!r} is absent from the elaborated Yosys netnames.")
                bits = net.get("bits")
                if not isinstance(bits, list) or not bits or any(not isinstance(bit, int) for bit in bits):
                    raise ValueError(
                        f"Internal signal {name!r} does not have a fully materialized Yosys bit mapping; constants/unknown bits are rejected."
                    )
                probe_name = f"__formal_probe_{name}"
                suffix = 0
                while probe_name in existing_names:
                    suffix += 1
                    probe_name = f"__formal_probe_{name}_{suffix}"
                existing_names.add(probe_name)
                ports[probe_name] = {
                    "direction": "output",
                    "bits": list(bits),
                    "offset": int(net.get("offset", 0)),
                    "upto": int(net.get("upto", 0)),
                    "signed": int(net.get("signed", 0)),
                    "port_id": next_port_id,
                }
                next_port_id += 1
                probe_ports[name] = probe_name

            instrumented_json = work / "instrumented.json"
            instrumented_json.write_text(json.dumps(design_json), encoding="utf-8")
            netlist_path = work / "instrumented_design.v"
            ys_path = work / "convert.ys"
            # The conversion script is executed by the Yosys process. When that
            # process runs through WSL, every path embedded INSIDE the script must
            # be a WSL path too. Translating only the script path is insufficient:
            # Windows paths such as C:/Users/... are not valid Linux paths in
            # read_json/write_verilog commands.
            if self.runner._use_wsl():
                json_script_path = self.runner._wsl_path(instrumented_json)
                netlist_script_path = self.runner._wsl_path(netlist_path)
            else:
                json_script_path = str(instrumented_json.resolve())
                netlist_script_path = str(netlist_path.resolve())

            def quote_yosys_path(value: str) -> str:
                escaped = value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))
                return chr(34) + escaped + chr(34)

            # read_json consumes the exact bit IDs used above; write_verilog emits
            # an ordinary netlist with explicit probe output ports.
            ys_path.write_text(
                f'read_json {quote_yosys_path(json_script_path)}\n'
                f'hierarchy -check -top {top_module}\n'
                f'write_verilog -noattr {quote_yosys_path(netlist_script_path)}\n',
                encoding="utf-8",
            )
            # Conversion uses the same configured execution mode as the initial
            # elaboration (native in WSL; WSL interop on Windows).
            if self.runner._use_wsl():
                script_path = self.runner._wsl_path(ys_path)
                cmd = ["wsl.exe", "-d", self.runner.distro, "--", "yosys", "-s", script_path]
            else:
                cmd = ["yosys", "-s", str(ys_path)]
            try:
                completed = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=self.timeout_seconds
                )
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or ""
                stderr = exc.stderr or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")
                diagnostic = (
                    f"Stage: JSON-to-Verilog conversion\nCommand: {cmd!r}\n"
                    f"Yosys script ({ys_path}):\n{ys_path.read_text(encoding='utf-8')}\n"
                    f"Partial stdout:\n{stdout}\nPartial stderr:\n{stderr}"
                )
                raise YosysExecutionError(
                    f"Yosys conversion exceeded the {self.timeout_seconds}-second timeout.",
                    output=diagnostic[-20000:],
                ) from exc
            if completed.returncode:
                diagnostic = (
                    f"Stage: JSON-to-Verilog conversion\n"
                    f"Command: {cmd!r}\n"
                    f"Working directory: {work}\n"
                    f"Yosys script ({ys_path}):\n{ys_path.read_text(encoding='utf-8')}\n"
                    f"Instrumented JSON: {instrumented_json}\n"
                    f"Output Verilog target: {netlist_path}\n"
                    f"Return code: {completed.returncode}\n"
                    f"stdout:\n{completed.stdout or ''}\n"
                    f"stderr:\n{completed.stderr or ''}"
                )
                raise YosysExecutionError(
                    "Yosys failed while converting the instrumented JSON netlist to Verilog.",
                    returncode=completed.returncode,
                    output=diagnostic[-20000:],
                )
            if not netlist_path.is_file():
                raise YosysExecutionError("Yosys did not produce the instrumented Verilog netlist.")
            return ProbeInstrumentationResult(
                netlist_source=netlist_path.read_text(encoding="utf-8"),
                probe_ports=probe_ports,
                elaborated_json=design_json,
                warnings=[
                    "Internal probes are explicit top-level output ports added to the elaborated Yosys JSON netlist.",
                    "The formal run uses the instrumented netlist, not a second elaboration of the original RTL.",
                    "Memory-array contents are not exposed as scalar probes; memory read/write ports require dedicated instrumentation.",
                ],
            )
