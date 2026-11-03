"""Per-property formal orchestration with fail-closed result aggregation."""
from __future__ import annotations
import time
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from backend.app.models.property_models import PropertyBatch, VerificationStatus
from backend.app.models.formal_models import (
    ProofMode, VacuityStatus, PropertyVerificationResult,
    FormalVerificationRequest, FormalVerificationResponse
)
from backend.app.services.property_validation import validate_property_batch
from backend.app.services.formal.checker_synthesizer import CheckerSynthesizer
from backend.app.services.formal.sby_runner import SBYRunner, parse_vcd_trace
from backend.app.services.formal.run_store import FormalRunStore
from backend.app.services.hdl.yosys_probe_instrumenter import YosysProbeInstrumenter
from backend.app.services.hdl.yosys_runner import YosysExecutionError


class FormalVerificationService:
    @staticmethod
    def _diagnostic_for_exception(exc: Exception) -> str:
        """Keep actionable tool diagnostics in INVALID results without hiding the cause."""
        parts = [f"Exception type: {type(exc).__name__}", f"Message: {exc}"]
        if isinstance(exc, YosysExecutionError):
            if exc.returncode is not None:
                parts.append(f"Return code: {exc.returncode}")
            if exc.output:
                parts.append("Tool output / reproduction context:\n" + exc.output)
        return "\n".join(parts)[-24000:]

    def __init__(self, sby_runner: SBYRunner | None = None, check_vacuity: bool = False):
        self.checker_synthesizer = CheckerSynthesizer(check_vacuity=False)
        self.sby_runner = sby_runner or SBYRunner()
        self.check_vacuity = False  # Never claim cover-based non-vacuity until implemented.
        self.run_store = FormalRunStore()

    @staticmethod
    def _aggregate(results: list[PropertyVerificationResult]) -> VerificationStatus:
        statuses = {r.status for r in results}
        if not statuses:
            return VerificationStatus.INVALID
        if statuses == {VerificationStatus.PASS}:
            return VerificationStatus.PASS
        if VerificationStatus.FAIL in statuses:
            return VerificationStatus.FAIL
        if VerificationStatus.TIMEOUT in statuses:
            return VerificationStatus.TIMEOUT
        if VerificationStatus.INVALID in statuses:
            return VerificationStatus.INVALID
        return VerificationStatus.UNKNOWN

    def verify(self, request: FormalVerificationRequest) -> FormalVerificationResponse:
        start = time.time()
        design = request.design_ir
        batch = request.property_batch
        top = request.top_module or batch.design_top or design.top_module
        if top != design.top_module:
            raise ValueError("Formal verification currently requires the selected top module to match DesignIR.top_module.")
        if batch.design_top != design.top_module:
            raise ValueError("Property batch design_top does not match DesignIR.top_module.")
        specification_warnings: list[str] = []
        if request.specification is not None:
            if request.specification.approval_status != "approved":
                raise ValueError("The behavioural specification must be explicitly approved before formal verification.")
            if request.specification.design_top != design.top_module:
                raise ValueError("Behavioural specification design_top does not match the analysed RTL design.")
            valid_requirement_ids = {r.requirement_id for r in request.specification.requirements}
            for prop in batch.properties:
                unknown_ids = set(prop.requirement_ids) - valid_requirement_ids
                if unknown_ids:
                    raise ValueError(
                        f"Property {prop.property_id} references requirement IDs not present in the approved specification: {sorted(unknown_ids)}"
                    )
                if not prop.requirement_ids:
                    specification_warnings.append(
                        f"Property {prop.property_id} has no requirement traceability IDs; its proof does not establish coverage of a stated requirement."
                    )
        else:
            specification_warnings.append(
                "No approved behavioural specification was attached. Any PASS proves only the encoded property for the supplied RTL/model, not conformance to an independent design specification."
            )

        has_sequential_state = any(
            module.registers or any(access.clocked for access in module.memory_accesses)
            for module in design.modules if module.name == design.top_module
        )
        if has_sequential_state and request.initial_reset_contract is None:
            specification_warnings.append(
                "Initial sequential state is unconstrained. No reset-at-start environment assumption is applied; a counterexample may begin from an arbitrary state unless the property itself establishes a reset protocol."
            )
        if request.initial_reset_contract is not None:
            if not request.initial_reset_contract.reviewed_by.strip() or not request.initial_reset_contract.rationale.strip():
                raise ValueError("An initial reset contract requires a reviewer identity and rationale.")
        if request.check_vacuity:
            raise ValueError("Vacuity checking is not implemented yet. The request was rejected rather than silently ignoring check_vacuity=true.")
        if len(batch.properties) > 20:
            raise ValueError("A formal batch may contain at most 20 properties.")
        if len(request.verilog_sources) > 20:
            raise ValueError("A formal request may contain at most 20 RTL source files.")
        # Validate untrusted relative filenames before any filesystem operation.
        for name in request.verilog_sources:
            SBYRunner._validate_source_name(name)
        if not request.verilog_sources:
            raise ValueError("At least one RTL source file is required.")

        validation = validate_property_batch(design, batch)
        validation_by_id = {r.property_id: r for r in validation.results}
        if request.proof_mode == ProofMode.COVER:
            cover_results = [PropertyVerificationResult(
                property_id=prop.property_id,
                name=prop.name,
                status=VerificationStatus.INVALID,
                proof_mode=request.proof_mode,
                proof_scope="cover_reachability",
                depth=request.depth,
                vacuity_status=VacuityStatus.NOT_CHECKED,
                log_snippet="Cover-only execution is disabled until dedicated cover-property synthesis and witness parsing are implemented.",
            ) for prop in batch.properties]
            return FormalVerificationResponse(
                batch_id=batch.batch_id,
                design_top=top,
                overall_status=VerificationStatus.INVALID,
                results=cover_results,
                summary={"invalid": len(cover_results)},
                warnings=["Cover mode is not implemented; it is rejected rather than being misreported as assertion verification."],
                execution_time_seconds=time.time() - start,
            )
        # Use the request's bounded per-property timeout and run independent
        # properties concurrently in a small worker pool. This avoids the old
        # 10-property * 120-second serial worst case while keeping solver load
        # bounded on student laptops.
        self.sby_runner.timeout_seconds = request.timeout_seconds
        checker_warnings: list[str] = []

        def execute_one(index: int, prop):
            val = validation_by_id.get(prop.property_id)
            if val is None or not val.design_valid:
                issues = "; ".join(i.message for i in (val.issues if val else [])) or "Property failed design validation."
                return (PropertyVerificationResult(
                    property_id=prop.property_id, name=prop.name,
                    status=VerificationStatus.INVALID, proof_mode=request.proof_mode,
                    proof_scope=("bounded" if request.proof_mode == ProofMode.BMC else "inductive"),
                    depth=request.depth, vacuity_status=VacuityStatus.NOT_CHECKED,
                    log_snippet=issues,
                ), None, None, None, [], None)
            try:
                single = PropertyBatch(batch_id=f"{batch.batch_id}_{index}", design_top=batch.design_top, properties=[prop])
                module_ir = next(m for m in design.modules if m.name == top)
                port_names = {p.name for p in module_ir.ports}
                internal_names = [
                    signal.name for signal in prop.signals
                    if signal.name not in port_names
                ]
                probe_ports: dict[str, str] = {}
                sources: dict[str, str]
                instrumentation_warnings: list[str] = []
                if internal_names:
                    instrumented = YosysProbeInstrumenter().instrument(
                        request.verilog_sources, top, internal_names
                    )
                    probe_ports = instrumented.probe_ports
                    instrumentation_warnings.extend(instrumented.warnings)
                    sources = {"instrumented_design.v": instrumented.netlist_source}
                else:
                    sources = dict(request.verilog_sources)
                synthesized = self.checker_synthesizer.synthesize(
                    design, single, top,
                    initial_reset_contract=request.initial_reset_contract,
                    internal_probe_ports=probe_ports,
                )
                wrapper_file = f"{synthesized.wrapper_module_name}.sv"
                sources[wrapper_file] = synthesized.wrapper_source_code
                task_name = f"verify_prop_{index}_{hashlib.sha256(prop.property_id.encode()).hexdigest()[:8]}"
                run = self.sby_runner.run(
                    task_name=task_name, sources=sources,
                    top_module=synthesized.wrapper_module_name,
                    proof_mode=request.proof_mode, depth=request.depth,
                    solver=request.solver,
                )
                reported_status = run.status
                failure_scope = ("counterexample_bmc" if run.failure_phase in ("base", "bmc") else
                                 "induction_step_failure" if run.failure_phase == "step" else
                                 ("bounded" if request.proof_mode == ProofMode.BMC else "inductive"))
                trace = parse_vcd_trace(run.vcd_trace_path) if run.vcd_trace_path else None
                result = PropertyVerificationResult(
                    property_id=prop.property_id, name=prop.name,
                    status=reported_status, proof_mode=request.proof_mode,
                    proof_scope=failure_scope, depth=request.depth,
                    vacuity_status=VacuityStatus.NOT_CHECKED,
                    failure_phase=run.failure_phase,
                    counterexample_vcd=run.vcd_trace_path,
                    counterexample_trace=trace,
                    witness_vcd=run.witness_trace_path,
                    log_snippet=(run.stdout + "\n" + run.stderr)[-1500:],
                    execution_time_seconds=run.execution_time_seconds,
                )
                logs = [x for x in (run.stdout[-1500:] if run.stdout else "", run.stderr[-1000:] if run.stderr else "") if x]
                return (result, synthesized.wrapper_source_code, run.task_file_content, "\n".join(logs), synthesized.warnings + instrumentation_warnings, run.work_dir)
            except Exception as exc:
                return (PropertyVerificationResult(
                    property_id=prop.property_id, name=prop.name,
                    status=VerificationStatus.INVALID, proof_mode=request.proof_mode,
                    proof_scope=("bounded" if request.proof_mode == ProofMode.BMC else "inductive"),
                    depth=request.depth, vacuity_status=VacuityStatus.NOT_CHECKED,
                    log_snippet=(
                        "Property rejected before formal execution.\n"
                        + self._diagnostic_for_exception(exc)
                    ),
                ), None, None, None, [], None)

        indexed = list(enumerate(batch.properties))
        with ThreadPoolExecutor(max_workers=min(3, max(1, len(indexed)))) as pool:
            completed = list(pool.map(lambda pair: execute_one(pair[0], pair[1]), indexed))

        results: list[PropertyVerificationResult] = []
        checker_sources: list[str] = []
        task_configs: list[str] = []
        stdout_parts: list[str] = []
        work_dirs: list[Path] = []
        for result, checker_source, task_config, log_text, warnings_for_property, work_dir in completed:
            results.append(result)
            if checker_source: checker_sources.append(checker_source)
            if task_config: task_configs.append(task_config)
            if log_text: stdout_parts.append(log_text)
            checker_warnings.extend(warnings_for_property)
            if work_dir is not None:
                work_dirs.append(work_dir)

        summary = {
            "pass": sum(r.status == VerificationStatus.PASS for r in results),
            "fail": sum(r.status == VerificationStatus.FAIL for r in results),
            "unknown": sum(r.status == VerificationStatus.UNKNOWN for r in results),
            "timeout": sum(r.status == VerificationStatus.TIMEOUT for r in results),
            "invalid": sum(r.status == VerificationStatus.INVALID for r in results),
        }
        overall = self._aggregate(results)
        warnings = list(specification_warnings) + [
            "Properties were executed independently; a batch result is not copied across properties.",
            "Vacuity is NOT_CHECKED: an independent cover task and witness parser are not yet implemented.",
            "The checker supports same-sample Boolean properties and a restricted clocked SVA subset ($past/$stable/$rose/$fell, |->, |=>, synchronous disable iff). It is not a complete IEEE 1800 SVA implementation.",
            "A BMC PASS is bounded to the requested depth; it is not an unbounded inductive proof.",
            f"Independent properties ran with up to 3 concurrent workers and a {request.timeout_seconds}-second per-property timeout.",
            "A successful cover run is reported as UNKNOWN for assertion-verification status; its witness path is separate.",
        ]
        warnings.extend(dict.fromkeys(checker_warnings))
        response = FormalVerificationResponse(
            batch_id=batch.batch_id,
            design_top=top,
            overall_status=overall,
            results=results,
            summary=summary,
            sby_task_file="\n\n".join(task_configs) if task_configs else None,
            synthesized_checker="\n\n".join(checker_sources) if checker_sources else None,
            stdout="\n".join(stdout_parts) if stdout_parts else None,
            execution_time_seconds=time.time() - start,
            warnings=warnings,
        )
        try:
            response.run_metadata = self.run_store.save(request, response)
        except OSError as exc:
            response.warnings.append(f"Verification completed, but local run-artifact persistence failed: {exc}. Temporary solver work directories were retained for recovery.")
        else:
            # VCDs and logs have been copied into the durable run record. Remove
            # transient SBY work trees only after successful persistence.
            import shutil
            for work_dir in work_dirs:
                try:
                    shutil.rmtree(work_dir, ignore_errors=True)
                except OSError:
                    pass
        return response
