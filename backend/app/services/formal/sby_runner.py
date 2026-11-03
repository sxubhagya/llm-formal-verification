"""Runner for SymbiYosys (SBY) formal verification execution.

Supports native execution on Linux/macOS, Windows-to-Ubuntu-WSL execution, and
isolated work directories. Provides structured result parsing for BMC and k-induction.
"""
from __future__ import annotations
import os
import platform
import shutil
import subprocess
import tempfile
import re
import secrets
from pathlib import Path
from dataclasses import dataclass, field

from backend.app.models.formal_models import (
    ProofMode, SolverEngine, VerificationStatus, VacuityStatus
)


class SBYExecutionError(RuntimeError):
    def __init__(self, message: str, *, returncode: int | None = None, output: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.output = output


@dataclass
class SBYRunResult:
    status: VerificationStatus
    returncode: int
    stdout: str
    stderr: str
    work_dir: Path
    task_file_content: str
    vcd_trace_path: str | None = None
    witness_trace_path: str | None = None
    failure_phase: str | None = None  # "base", "step", "bmc", or None
    vacuity_status: VacuityStatus = VacuityStatus.NOT_CHECKED
    properties_passed: list[str] = field(default_factory=list)
    properties_failed: list[str] = field(default_factory=list)
    covers_reached: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    simulated: bool = False


def parse_vcd_trace(path: str | Path, *, max_frames: int = 200, max_signals: int = 200) -> dict:
    """Parse a compact, bounded VCD view for UI diagnostics (not a simulator)."""
    vcd = Path(path)
    if not vcd.is_file():
        return {"signals": [], "frames": [], "truncated": False, "error": "VCD file not found"}
    scopes: list[str] = []
    signals: list[dict] = []
    id_to_signal: dict[str, dict] = {}
    frames: list[dict] = []
    current_time = "0"
    current_values: dict[str, str] = {}
    in_header = True
    truncated = False
    try:
        # Avoid loading arbitrarily large traces into API memory.
        max_bytes = 20 * 1024 * 1024
        raw_bytes = vcd.read_bytes()
        if len(raw_bytes) > max_bytes:
            raw_bytes = raw_bytes[:max_bytes]
            truncated = True
        for raw in raw_bytes.decode("utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            if in_header:
                if line.startswith("$scope"):
                    parts = line.split()
                    if len(parts) >= 3: scopes.append(parts[2])
                elif line.startswith("$upscope"):
                    if scopes: scopes.pop()
                elif line.startswith("$var"):
                    parts = line.split()
                    if len(parts) >= 6:
                        if len(signals) >= max_signals:
                            truncated = True
                        else:
                            width, ident, reference = int(parts[2]), parts[3], parts[4]
                            item = {"id": ident, "name": ".".join(scopes + [reference]), "width": width}
                            signals.append(item); id_to_signal[ident] = item
                elif line.startswith("$enddefinitions"):
                    in_header = False
                continue
            if line.startswith("#"):
                if current_values:
                    frames.append({"time": current_time, "values": dict(current_values)})
                current_time = line[1:]
                if len(frames) >= max_frames:
                    truncated = True
                    break
            elif line[0] in "bB":
                parts = line[1:].split()
                if len(parts) == 2 and parts[1] in id_to_signal:
                    current_values[parts[1]] = parts[0].lower()
            elif line[0] in "01xXzZ" and len(line) > 1:
                ident = line[1:].strip()
                if ident in id_to_signal: current_values[ident] = line[0].lower()
        if current_values and len(frames) < max_frames:
            frames.append({"time": current_time, "values": dict(current_values)})
        # Include only signals that actually appear in the trace.
        used = {key for frame in frames for key in frame["values"]}
        signals = [sig for sig in signals if sig["id"] in used]
        return {"signals": signals, "frames": frames[:max_frames], "truncated": truncated or len(frames) > max_frames}
    except (OSError, ValueError) as exc:
        return {"signals": [], "frames": [], "truncated": False, "error": str(exc)}


class SBYRunner:
    """Manages SBY configuration generation and invocation."""

    def __init__(
        self,
        mode: str | None = None,
        distro: str | None = None,
        timeout_seconds: int = 120,
        mock_mode: bool = False
    ):
        self.mode = (mode or os.getenv("FORMAL_RUNNER_MODE", "auto")).lower()
        self.distro = distro or os.getenv("WSL_DISTRO", "Ubuntu")
        self.timeout_seconds = timeout_seconds
        self.mock_mode = mock_mode
        self._availability_cache: dict[tuple[bool, str], bool] = {}

    def _use_wsl(self) -> bool:
        if self.mode == "wsl":
            return True
        if self.mode == "native":
            return False
        return platform.system() == "Windows"

    def _wsl_path(self, path: Path) -> str:
        windows_path = str(path.resolve()).replace("\\", "/")
        result = subprocess.run(
            ["wsl.exe", "-d", self.distro, "--", "wslpath", "-a", windows_path],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode != 0:
            raise SBYExecutionError(
                "Could not translate Windows path into WSL: " + result.stderr.strip(),
                returncode=result.returncode
            )
        return result.stdout.strip()

    @staticmethod
    def _validate_identifier(value: str, label: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value or ""):
            raise ValueError(f"Invalid {label}: {value!r}")
        return value

    @staticmethod
    def _validate_source_name(value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or not value or any(c in value for c in "\\\x00\r\n;`$%"):
            raise ValueError(f"Unsafe source filename: {value!r}")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", value):
            raise ValueError(f"Unsafe source filename: {value!r}")
        return value

    def _wsl_has_sby(self, solver_name: str) -> bool:
        cache_key = (True, solver_name)
        if cache_key in self._availability_cache:
            return self._availability_cache[cache_key]
        result = subprocess.run(
            ["wsl.exe", "-d", self.distro, "--", "bash", "-lc", f"command -v sby && command -v yosys && command -v {solver_name}"],
            capture_output=True, text=True, timeout=15
        )
        available = result.returncode == 0 and "sby" in result.stdout and "yosys" in result.stdout
        self._availability_cache[cache_key] = available
        return available

    def generate_sby_config(
        self,
        top_module: str,
        source_filenames: list[str],
        proof_mode: ProofMode = ProofMode.PROVE,
        depth: int = 20,
        solver: SolverEngine = SolverEngine.Z3
    ) -> str:
        """Generates the text for an .sby project configuration file."""
        self._validate_identifier(top_module, "top module")
        for src in source_filenames:
            self._validate_source_name(src)
        if not 1 <= depth <= 200:
            raise ValueError("SBY depth must be between 1 and 200.")
        lines = [
            "[options]",
            f"mode {proof_mode.value}",
            f"depth {depth}",
            "",
            "[engines]",
            f"smtbmc {solver.value}",
            "",
            "[script]",
        ]

        for src in source_filenames:
            lines.append(f"read -formal -sv {src}")

        lines.append(f"prep -top {top_module}")
        lines.append("")
        lines.append("[files]")
        for src in source_filenames:
            lines.append(src)
        lines.append("")

        return "\n".join(lines)

    def parse_sby_output(self, stdout: str, stderr: str, work_dir: Path, proof_mode: ProofMode) -> tuple[VerificationStatus, str | None, str | None, str | None]:
        """Parses SBY stdout/stderr to determine proof status, failure phase, and trace paths."""
        combined = stdout + "\n" + stderr

        # Require an explicit SBY terminal marker. Incidental log words must not
        # be interpreted as a proof result.
        status = VerificationStatus.UNKNOWN
        failure_phase = None
        done = re.findall(r"DONE \((PASS|FAIL|TIMEOUT)(?:,|\))", combined)
        if done:
            terminal = done[-1]
            status = {
                "PASS": VerificationStatus.PASS,
                "FAIL": VerificationStatus.FAIL,
                "TIMEOUT": VerificationStatus.TIMEOUT,
            }[terminal]
        elif "syntax error" in combined.lower() or "unknown command" in combined.lower() or "could not find" in combined.lower():
            status = VerificationStatus.INVALID

        # Analyze failure phase for k-induction or BMC
        if status == VerificationStatus.FAIL:
            # Determine the phase from an explicit failure event. Merely seeing
            # an induction process in the log is not evidence that induction failed.
            if re.search(r"basecase:.*(?:BMC failed|Status: failed)|BMC failed!|returned FAIL for basecase", combined, re.IGNORECASE):
                # A reachable base-case counterexample is decisive even if the
                # induction engine also reports a failed step.
                failure_phase = "base"
            elif re.search(r"induction(?: step)? failed|engine_\d+\.induction:.*(?:failed|Status: failed)", combined, re.IGNORECASE):
                failure_phase = "step"
            elif proof_mode == ProofMode.BMC:
                failure_phase = "bmc"
            else:
                failure_phase = "unknown"
            if failure_phase == "unknown":
                # In prove mode, an unclassified failure without basecase or induction
                # diagnostics is treated as unknown.
                status = VerificationStatus.UNKNOWN

        # Locate counterexample trace
        vcd_path = None
        witness_path = None
        # SBY standard trace locations: <work_dir>/<task>/engine_0/trace.vcd
        for trace_file in work_dir.glob("**/engine_0/trace*.vcd"):
            if status == VerificationStatus.FAIL:
                vcd_path = str(trace_file.resolve())
            elif status == VerificationStatus.PASS and proof_mode == ProofMode.COVER:
                witness_path = str(trace_file.resolve())
            break

        return status, failure_phase, vcd_path, witness_path

    def run(
        self,
        task_name: str,
        sources: dict[str, str],
        top_module: str,
        proof_mode: ProofMode = ProofMode.PROVE,
        depth: int = 20,
        solver: SolverEngine = SolverEngine.Z3,
        work_dir: Path | None = None
    ) -> SBYRunResult:
        """Executes SBY in an isolated work directory."""
        import time
        start_time = time.time()
        self._validate_identifier(task_name, "task name")
        self._validate_identifier(top_module, "top module")
        for source_name in sources:
            self._validate_source_name(source_name)

        # Create isolated working directory
        cleanup_dir = False
        if work_dir is None:
            work_dir = Path(tempfile.mkdtemp(prefix=f"sby_{task_name}_"))
            cleanup_dir = False  # Retain for trace inspection
        else:
            work_dir.mkdir(parents=True, exist_ok=True)

        # Write all source files into working directory
        total_source_bytes = 0
        for fname, content in sources.items():
            if not isinstance(content, str) or "\x00" in content:
                raise ValueError(f"Invalid source content for {fname!r}.")
            total_source_bytes += len(content.encode("utf-8"))
            if total_source_bytes > 5_000_000:
                raise ValueError("Combined formal source bundle exceeds 5 MB limit.")
            fpath = work_dir / fname
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")

        # Generate SBY config
        source_names = list(sources.keys())
        sby_config = self.generate_sby_config(
            top_module=top_module,
            source_filenames=source_names,
            proof_mode=proof_mode,
            depth=depth,
            solver=solver
        )
        task_file = work_dir / f"{task_name}.sby"
        task_file.write_text(sby_config, encoding="utf-8")

        # Mock mode is test-only and can never produce a mathematical PASS.
        use_wsl = self._use_wsl()
        if self.mock_mode:
            elapsed = time.time() - start_time
            return SBYRunResult(
                status=VerificationStatus.UNKNOWN,
                returncode=0,
                stdout="MOCK EXECUTION ONLY: no solver was invoked; no proof result is available.",
                stderr="",
                work_dir=work_dir,
                task_file_content=sby_config,
                vacuity_status=VacuityStatus.NOT_CHECKED,
                execution_time_seconds=elapsed,
                simulated=True,
            )

        cache_key = (False, solver.value)
        if cache_key not in self._availability_cache:
            self._availability_cache[cache_key] = bool(shutil.which("sby") and shutil.which("yosys") and shutil.which(solver.value))
        solver_available = self._wsl_has_sby(solver.value) if use_wsl else self._availability_cache[cache_key]
        is_tool_available = solver_available
        if not is_tool_available:
            elapsed = time.time() - start_time
            return SBYRunResult(
                status=VerificationStatus.INVALID,
                returncode=127,
                stdout="",
                stderr="Formal tools unavailable: both sby and yosys must be installed in the selected execution environment.",
                work_dir=work_dir,
                task_file_content=sby_config,
                vacuity_status=VacuityStatus.NOT_CHECKED,
                execution_time_seconds=elapsed,
            )

        # Real execution via native SBY or WSL
        try:
            if use_wsl:
                self._validate_identifier(task_name, "task name")
                wsl_work = self._wsl_path(work_dir)
                cmd = ["wsl.exe", "-d", self.distro, "--cd", wsl_work, "--", "sby", "-f", f"{task_name}.sby"]
            else:
                cmd = ["sby", "-f", f"{task_name}.sby"]

            popen_kwargs = {
                "cwd": str(work_dir),
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
            except subprocess.TimeoutExpired:
                # Kill the process tree/group, not just the Python parent. This
                # prevents orphaned solver processes consuming resources.
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
                stdout, stderr = proc.communicate()
                raise subprocess.TimeoutExpired(cmd, self.timeout_seconds, output=stdout, stderr=stderr)
            elapsed = time.time() - start_time
            retcode = proc.returncode

            status, failure_phase, vcd_path, witness_path = self.parse_sby_output(
                stdout, stderr, work_dir, proof_mode
            )
            if retcode != 0 and status == VerificationStatus.PASS:
                status = VerificationStatus.UNKNOWN
            if retcode == 0 and status == VerificationStatus.UNKNOWN and "DONE (PASS" not in (stdout + stderr):
                status = VerificationStatus.UNKNOWN

            # Assertion proof and cover reachability are separate tasks. This runner
            # does not claim non-vacuity until an independent cover task is implemented.
            vacuity = VacuityStatus.NOT_CHECKED

            return SBYRunResult(
                status=status,
                returncode=retcode,
                stdout=stdout,
                stderr=stderr,
                work_dir=work_dir,
                task_file_content=sby_config,
                vcd_trace_path=vcd_path,
                witness_trace_path=witness_path,
                failure_phase=failure_phase,
                vacuity_status=vacuity,
                execution_time_seconds=elapsed
            )

        except subprocess.TimeoutExpired as exc:
            elapsed = time.time() - start_time
            partial_stdout = exc.stdout or ""
            partial_stderr = exc.stderr or ""
            if isinstance(partial_stdout, bytes):
                partial_stdout = partial_stdout.decode("utf-8", errors="replace")
            if isinstance(partial_stderr, bytes):
                partial_stderr = partial_stderr.decode("utf-8", errors="replace")
            return SBYRunResult(
                status=VerificationStatus.TIMEOUT,
                returncode=124,
                stdout=partial_stdout,
                stderr=(partial_stderr + "\nSBY execution exceeded the configured per-property timeout limit.").strip(),
                work_dir=work_dir,
                task_file_content=sby_config,
                failure_phase="timeout",
                vacuity_status=VacuityStatus.NOT_CHECKED,
                execution_time_seconds=elapsed
            )
        except Exception as exc:
            elapsed = time.time() - start_time
            return SBYRunResult(
                status=VerificationStatus.INVALID,
                returncode=1,
                stdout="",
                stderr=f"Execution error: {exc}",
                work_dir=work_dir,
                task_file_content=sby_config,
                failure_phase="execution_error",
                vacuity_status=VacuityStatus.NOT_CHECKED,
                execution_time_seconds=elapsed
            )
