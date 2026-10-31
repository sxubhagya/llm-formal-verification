"""High-level formal verification orchestration service.

Validates properties against design IR, synthesizes procedural checkers,
executes SymbiYosys (SBY), and compiles verification verdicts.
"""
from __future__ import annotations
import time
from typing import Any
from pathlib import Path

from backend.app.models.design_ir import DesignIR
from backend.app.models.property_models import (
    PropertyBatch, CandidateProperty, VerificationStatus
)
from backend.app.models.formal_models import (
    ProofMode, SolverEngine, VacuityStatus,
    PropertyVerificationResult, FormalVerificationRequest, FormalVerificationResponse
)
from backend.app.services.property_validation import validate_property_batch
from backend.app.services.formal.checker_synthesizer import CheckerSynthesizer
from backend.app.services.formal.sby_runner import SBYRunner, SBYRunResult


class FormalVerificationService:
    """Coordinates property synthesis, formal tool execution, and verdict determination."""

    def __init__(self, sby_runner: SBYRunner | None = None, check_vacuity: bool = True):
        self.checker_synthesizer = CheckerSynthesizer(check_vacuity=check_vacuity)
        self.sby_runner = sby_runner or SBYRunner()
        self.check_vacuity = check_vacuity

    def verify(self, request: FormalVerificationRequest) -> FormalVerificationResponse:
        start_time = time.time()
        design_ir = request.design_ir
        batch = request.property_batch
        top_name = request.top_module or batch.design_top or design_ir.top_module

        # 1. First validate properties against Design IR
        val_result = validate_property_batch(design_ir, batch)
        val_by_id = {r.property_id: r for r in val_result.results}

        # Check if all properties are structurally valid
        invalid_props = {
            r.property_id: r for r in val_result.results if not r.design_valid
        }

        # 2. Synthesize procedural checker wrapper for the valid properties
        try:
            synth_res = self.checker_synthesizer.synthesize(
                design_ir=design_ir,
                property_batch=batch,
                target_module_name=top_name
            )
        except Exception as exc:
            # If synthesizer fails, mark all properties as INVALID
            results = [
                PropertyVerificationResult(
                    property_id=p.property_id,
                    name=p.name,
                    status=VerificationStatus.INVALID,
                    log_snippet=f"Checker synthesis error: {exc}",
                    execution_time_seconds=0.0
                )
                for p in batch.properties
            ]
            return FormalVerificationResponse(
                batch_id=batch.batch_id,
                design_top=top_name,
                overall_status=VerificationStatus.INVALID,
                results=results,
                summary={"invalid": len(results)},
                warnings=[f"Synthesis failed: {exc}"],
                execution_time_seconds=time.time() - start_time
            )

        # 3. Assemble source bundle
        wrapper_filename = f"{synth_res.wrapper_module_name}.sv"
        sources_bundle = dict(request.verilog_sources)
        sources_bundle[wrapper_filename] = synth_res.wrapper_source_code

        # 4. Execute SBY
        task_name = f"verify_{top_name}"
        run_res: SBYRunResult = self.sby_runner.run(
            task_name=task_name,
            sources=sources_bundle,
            top_module=synth_res.wrapper_module_name,
            proof_mode=request.proof_mode,
            depth=request.depth,
            solver=request.solver
        )

        # 5. Compile per-property outcomes
        prop_results: list[PropertyVerificationResult] = []
        overall_status = run_res.status

        for prop in batch.properties:
            p_id = prop.property_id
            # If property had fatal design validation issues
            if p_id in invalid_props:
                err_msgs = "; ".join(i.message for i in invalid_props[p_id].issues)
                prop_results.append(PropertyVerificationResult(
                    property_id=p_id,
                    name=prop.name,
                    status=VerificationStatus.INVALID,
                    proof_engine=f"sby_smtbmc_{request.solver.value}",
                    proof_mode=request.proof_mode,
                    depth=request.depth,
                    log_snippet=f"Design validation error: {err_msgs}",
                    execution_time_seconds=0.0
                ))
                continue

            # Otherwise, verdict derives from SBY execution
            vacuity = VacuityStatus.NOT_CHECKED
            if run_res.status == VerificationStatus.PASS:
                vacuity = VacuityStatus.NON_VACUOUS if self.check_vacuity else VacuityStatus.NOT_CHECKED

            prop_results.append(PropertyVerificationResult(
                property_id=p_id,
                name=prop.name,
                status=run_res.status,
                proof_engine=f"sby_smtbmc_{request.solver.value}",
                proof_mode=request.proof_mode,
                depth=request.depth,
                vacuity_status=vacuity,
                failure_phase=run_res.failure_phase,
                counterexample_vcd=run_res.vcd_trace_path,
                witness_vcd=run_res.witness_trace_path,
                log_snippet=run_res.stdout[-1000:] if run_res.stdout else None,
                execution_time_seconds=run_res.execution_time_seconds
            ))

        # Summary counts
        summary = {
            "pass": sum(1 for r in prop_results if r.status == VerificationStatus.PASS),
            "fail": sum(1 for r in prop_results if r.status == VerificationStatus.FAIL),
            "unknown": sum(1 for r in prop_results if r.status == VerificationStatus.UNKNOWN),
            "timeout": sum(1 for r in prop_results if r.status == VerificationStatus.TIMEOUT),
            "invalid": sum(1 for r in prop_results if r.status == VerificationStatus.INVALID),
        }

        # If any property failed, overall status is FAIL; if any invalid, INVALID; else PASS
        if summary["fail"] > 0:
            overall_status = VerificationStatus.FAIL
        elif summary["timeout"] > 0:
            overall_status = VerificationStatus.TIMEOUT
        elif summary["invalid"] > 0 and summary["pass"] == 0:
            overall_status = VerificationStatus.INVALID
        elif summary["pass"] > 0 and summary["fail"] == 0:
            overall_status = VerificationStatus.PASS

        elapsed = time.time() - start_time
        return FormalVerificationResponse(
            batch_id=batch.batch_id,
            design_top=top_name,
            overall_status=overall_status,
            results=prop_results,
            summary=summary,
            sby_task_file=run_res.task_file_content,
            synthesized_checker=synth_res.wrapper_source_code,
            stdout=run_res.stdout[-2000:] if run_res.stdout else None,
            execution_time_seconds=elapsed,
            warnings=[]
        )
