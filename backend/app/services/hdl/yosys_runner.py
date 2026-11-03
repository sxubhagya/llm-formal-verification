"""Run Yosys natively or through WSL without passing RTL through a shell."""
from __future__ import annotations
import os, platform, shutil, subprocess, re
from pathlib import Path

class YosysExecutionError(RuntimeError):
    def __init__(self, message: str, *, returncode: int | None = None, output: str = ""):
        super().__init__(message); self.returncode = returncode; self.output = output

class YosysRunner:
    def __init__(self, mode: str | None = None, distro: str | None = None, timeout_seconds: int = 90):
        self.mode = (mode or os.getenv("HDL_FRONTEND_MODE", "auto")).lower()
        self.distro = distro or os.getenv("WSL_DISTRO", "Ubuntu")
        self.timeout_seconds = timeout_seconds

    def _use_wsl(self) -> bool:
        if self.mode == "wsl": return True
        if self.mode == "native": return False
        return platform.system() == "Windows"

    def _wsl_path(self, path: Path) -> str:
        # WSL interop can strip backslashes from a Windows path passed as an argv
        # value (for example C:\\Users\\... becomes C:Users...). Use forward
        # slashes so the drive-qualified path survives argument translation.
        windows_path = str(path.resolve()).replace("\\", "/")
        result = subprocess.run(["wsl.exe", "-d", self.distro, "--", "wslpath", "-a", windows_path], capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise YosysExecutionError("Could not translate a Windows path into WSL: " + result.stderr.strip(), returncode=result.returncode)
        return result.stdout.strip()

    def run(self, source_files: list[Path], top_module: str, output_json: Path) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", top_module):
            raise ValueError("top_module must be a valid Verilog identifier.")
        if not source_files: raise ValueError("At least one RTL source file is required.")
        for source in source_files:
            if not source.is_file(): raise FileNotFoundError(f"RTL source file not found: {source}")
        output_json.parent.mkdir(parents=True, exist_ok=True)
        use_wsl = self._use_wsl()
        if not use_wsl and not shutil.which("yosys"):
            raise YosysExecutionError("Yosys was not found. Install it in Ubuntu WSL or set HDL_FRONTEND_MODE=wsl.")
        # Script paths are quoted for Yosys' command language; subprocess is always invoked with argv, never shell=True.
        if use_wsl:
            source_paths = [self._wsl_path(p) for p in source_files]
            output_path = self._wsl_path(output_json)
        else:
            source_paths = [str(p.resolve()) for p in source_files]
            output_path = str(output_json.resolve())
        def q(value: str) -> str:
            escaped = value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))
            return chr(34) + escaped + chr(34)
        commands = [f"read_verilog -sv {q(p)}" for p in source_paths]
        commands += [f"hierarchy -check -top {top_module}", "proc", "opt", f"write_json {q(output_path)}"]
        script = output_json.with_suffix('.ys')
        script.write_text("\n".join(commands) + "\n", encoding="utf-8")
        try:
            if use_wsl:
                script_path = self._wsl_path(script)
                cmd = ["wsl.exe", "-d", self.distro, "--", "yosys", "-s", script_path]
            else:
                cmd = ["yosys", "-s", str(script.resolve())]
            popen_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
            }
            if os.name == "nt":
                popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                popen_kwargs["start_new_session"] = True
            proc = subprocess.Popen(cmd, **popen_kwargs)
            try:
                stdout, stderr = proc.communicate(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                        capture_output=True, text=True, timeout=10
                    )
                else:
                    import signal
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                partial_out, partial_err = proc.communicate()
                raise YosysExecutionError(
                    f"Yosys exceeded the {self.timeout_seconds}-second timeout.",
                    output=((partial_out or "") + "\\n" + (partial_err or ""))[-12000:]
                ) from exc
            returncode = proc.returncode
            output = (stdout or "") + (stderr or "")
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            raise YosysExecutionError(f"Yosys exceeded the {self.timeout_seconds}-second timeout.", output=partial) from exc
        finally:
            script.unlink(missing_ok=True)
        if returncode != 0:
            raise YosysExecutionError("Yosys failed to parse or elaborate the supplied RTL.", returncode=returncode, output=output[-12000:])
        if not output_json.is_file():
            raise YosysExecutionError("Yosys completed without producing the expected JSON output.", returncode=returncode, output=output[-12000:])
        return output
