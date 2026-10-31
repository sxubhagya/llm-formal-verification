"""Canonical, provider-independent representation of candidate formal properties."""
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

class PropertyCategory(str, Enum):
    SAFETY = "safety"
    LIVENESS = "liveness"
    INVARIANT = "invariant"
    TEMPORAL = "temporal"
    COMBINATIONAL = "combinational"

class AssertionLanguage(str, Enum):
    SVA = "systemverilog_assertion"
    BOOLEAN = "boolean_expression"
    PSL = "psl"
    OTHER = "other"

class PropertyLifecycle(str, Enum):
    GENERATED = "generated"
    SCHEMA_VALID = "schema_valid"
    DESIGN_VALID = "design_valid"
    READY_FOR_FORMAL = "ready_for_formal"
    REJECTED = "rejected"

class AssumptionReviewStatus(str, Enum):
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class VerificationStatus(str, Enum):
    NOT_RUN = "not_run"
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    INVALID = "invalid"

class SignalReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    role: str = "referenced"
    expected_width: int | None = Field(default=None, ge=1)
    rationale: str | None = None

class ClockContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal: str
    edge: str = "posedge"
    domain: str | None = None

    @model_validator(mode="after")
    def valid_edge(self):
        if self.edge not in {"posedge", "negedge"}:
            raise ValueError("clock edge must be posedge or negedge")
        return self

class ResetContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal: str
    polarity: str
    asynchronous: bool | None = None
    active_during_disable: bool = True

    @model_validator(mode="after")
    def valid_polarity(self):
        if self.polarity not in {"active_high", "active_low"}:
            raise ValueError("reset polarity must be active_high or active_low")
        return self

class PropertyAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assumption_id: str
    statement: str
    rationale: str
    status: AssumptionReviewStatus = AssumptionReviewStatus.PROPOSED
    reviewed_by: str | None = None
    source: str = "llm"

    @model_validator(mode="after")
    def accepted_requires_review(self):
        if self.status in {AssumptionReviewStatus.ACCEPTED, AssumptionReviewStatus.REJECTED} and not self.reviewed_by:
            raise ValueError("accepted/rejected assumptions require reviewed_by")
        return self

class PropertyProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generator: str = "manual"
    model_name: str | None = None
    prompt_version: str | None = None
    source_design_hash: str | None = None
    generation_notes: str | None = None
    timestamp: str | None = None
    tokens_used: int | None = None


class CandidateProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: str
    design_top: str
    module: str
    name: str
    description: str
    category: PropertyCategory
    assertion_language: AssertionLanguage
    expression: str
    signals: list[SignalReference] = Field(min_length=1)
    clock: ClockContext | None = None
    reset: ResetContext | None = None
    assumptions: list[PropertyAssumption] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    lifecycle: PropertyLifecycle = PropertyLifecycle.GENERATED
    provenance: PropertyProvenance = Field(default_factory=PropertyProvenance)

    @model_validator(mode="after")
    def basic_semantic_checks(self):
        if not self.expression.strip():
            raise ValueError("property expression must not be empty")
        if not self.name.strip() or not self.description.strip():
            raise ValueError("property name and description must not be empty")
        if len({s.name for s in self.signals}) != len(self.signals):
            raise ValueError("signal references must have unique names")
        return self

class PropertyBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: str
    design_top: str
    properties: list[CandidateProperty] = Field(min_length=1)

class PropertyValidationIssue(BaseModel):
    property_id: str
    code: str
    message: str
    severity: str = "error"

class PropertyValidationResult(BaseModel):
    property_id: str
    schema_valid: bool = True
    design_valid: bool = False
    lifecycle: PropertyLifecycle
    issues: list[PropertyValidationIssue] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.NOT_RUN
    note: str = "Design validation checks referenced signal names and widths only; they do not parse or prove the assertion expression."

class PropertyValidationBatchResult(BaseModel):
    design_top: str
    results: list[PropertyValidationResult]
    summary: dict[str, int] = Field(default_factory=dict)


class DesignPropertyValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design: Any
    batch: PropertyBatch


class PropertyGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design: Any
    target_module: str | None = None
    max_properties: int = Field(default=5, ge=1, le=20)
    focus_areas: list[str] | None = None
    source_code: str | None = None
    provider: str | None = None
    model: str | None = None


class PropertyGenerationResponse(BaseModel):
    batch: PropertyBatch
    validation: PropertyValidationBatchResult
    provenance: PropertyProvenance
    raw_response: str | None = None
    usage: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)

