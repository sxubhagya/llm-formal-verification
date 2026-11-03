"""Independent behavioural specifications used as the authority for property generation."""
from __future__ import annotations
import hashlib
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, model_validator

class RequirementSource(str, Enum):
    USER = "user"
    DOCUMENT = "document"
    REVIEWED_INTERPRETATION = "reviewed_interpretation"

class BehaviouralRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_id: str = Field(min_length=1, max_length=64)
    statement: str = Field(min_length=8, max_length=3000)
    source: RequirementSource = RequirementSource.USER
    notes: str | None = Field(default=None, max_length=1000)

class DesignSpecification(BaseModel):
    """User-approved behavioural intent, kept separate from implementation RTL."""
    model_config = ConfigDict(extra="forbid")
    specification_id: str = Field(min_length=1, max_length=100)
    version: str = "1.0"
    title: str = Field(min_length=2, max_length=200)
    design_top: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=3000)
    requirements: list[BehaviouralRequirement] = Field(min_length=1, max_length=100)
    approved_by: str | None = None
    approval_status: str = "draft"
    approved_content_hash: str | None = None

    @model_validator(mode="after")
    def validate_requirements(self):
        ids = [r.requirement_id for r in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("requirement_id values must be unique")
        if self.approval_status not in {"draft", "approved"}:
            raise ValueError("approval_status must be draft or approved")
        if self.approval_status == "approved":
            if not (self.approved_by or "").strip():
                raise ValueError("approved specifications require approved_by")
            if not self.approved_content_hash or self.approved_content_hash != self.content_hash():
                raise ValueError("approved specifications must be bound to the exact current content hash; re-approve after any edit")
        elif self.approved_content_hash is not None:
            raise ValueError("draft specifications cannot carry an approval content hash")
        return self

    def content_hash(self) -> str:
        import json
        payload = self.model_dump(mode="json", exclude={"approved_by", "approval_status", "approved_content_hash"})
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def approve(self, reviewer: str) -> "DesignSpecification":
        reviewer = reviewer.strip()
        if not reviewer:
            raise ValueError("A non-empty reviewer identity is required.")
        if self.approval_status != "draft":
            raise ValueError("Only a draft specification can be approved.")
        approved = self.model_copy(update={
            "approved_by": reviewer,
            "approval_status": "approved",
            "approved_content_hash": self.content_hash(),
        })
        return DesignSpecification.model_validate(approved.model_dump())
