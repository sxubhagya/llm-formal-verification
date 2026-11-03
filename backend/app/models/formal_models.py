"""Models for formal verification execution, tool configurations, and proof outcomes."""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

from backend.app.models.property_models import (
    VerificationStatus, PropertyBatch, CandidateProperty
)
from backend.app.models.design_ir import DesignIR
from backend.app.models.specification_models import DesignSpecification


class ProofMode(str, Enum):
    PROVE = "prove"       # Unbounded k-induction (base + induction step)
    BMC = "bmc"           # Bounded Model Checking up to depth N
    COVER = "cover"       # Reachability / vacuity cover check


class SolverEngine(str, Enum):
    Z3 = "z3"
    BOOLECTOR = "boolector"
    YICES = "yices"


class VacuityStatus(str, Enum):
    NON_VACUOUS = "non_vacuous"  # Antecedent was proven reachable via cover witness
    VACUOUS = "vacuous"          # Antecedent is unreachable; implication holds vacuously
    NOT_CHECKED = "not_checked"  # Vacuity check was not requested or not applicable


class PropertyVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: str
    name: str
    status: VerificationStatus
    proof_engine: str = "sby_smtbmc"
    proof_mode: ProofMode = ProofMode.PROVE
    proof_scope: str = "inductive"  # inductive, bounded, or cover_reachability
    depth: int = 20
    vacuity_status: VacuityStatus = VacuityStatus.NOT_CHECKED
    failure_phase: str | None = None  # "base", "step", "bmc", or None
    counterexample_vcd: str | None = None
    counterexample_trace: dict[str, Any] | None = None
    witness_vcd: str | None = None
    log_snippet: str | None = None
    execution_time_seconds: float = 0.0




class InitialResetContract(BaseModel):
    """Reviewer-approved environment condition: reset is active on the first clock edge."""
    model_config = ConfigDict(extra="forbid")
    signal: str
    polarity: str
    reviewed_by: str = Field(min_length=1, max_length=128)
    rationale: str = Field(min_length=8, max_length=1000)

    @field_validator("polarity")
    @classmethod
    def valid_polarity(cls, value):
        if value not in {"active_high", "active_low"}:
            raise ValueError("reset polarity must be active_high or active_low")
        return value

    @field_validator("reviewed_by", "rationale")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("reviewer and rationale must be non-empty")
        return value.strip()

class FormalVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design_ir: DesignIR
    verilog_sources: dict[str, str] = Field(
        description="Map of relative filename to Verilog/SystemVerilog source text"
    )
    property_batch: PropertyBatch
    top_module: str | None = None
    proof_mode: ProofMode = ProofMode.PROVE
    depth: int = Field(default=20, ge=1, le=200)
    solver: SolverEngine = SolverEngine.Z3
    timeout_seconds: int = Field(default=45, ge=5, le=180)
    check_vacuity: bool = Field(default=False, description="Vacuity analysis is not yet implemented; true requests are rejected.")
    specification: DesignSpecification | None = None
    generation_audit: dict[str, Any] | None = Field(
        default=None,
        description="Optional exact prompt/response snapshot from the property-generation step for experiment reproducibility."
    )
    initial_reset_contract: InitialResetContract | None = Field(
        default=None,
        description="Optional reviewer-approved assumption that the named reset is active on the first clock edge; it is not inferred automatically."
    )


class FormalVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: str
    design_top: str
    overall_status: VerificationStatus
    results: list[PropertyVerificationResult]
    summary: dict[str, int] = Field(default_factory=dict)
    sby_task_file: str | None = None
    synthesized_checker: str | None = None
    stdout: str | None = None
    execution_time_seconds: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    run_metadata: dict[str, Any] | None = None
