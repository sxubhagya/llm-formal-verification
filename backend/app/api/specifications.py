from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from backend.app.models.specification_models import DesignSpecification

router = APIRouter(prefix="/api/specifications", tags=["behavioural-specifications"])

class SpecificationApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    specification: DesignSpecification
    reviewer: str = Field(min_length=1, max_length=200)
    reviewed_content_hash: str = Field(min_length=64, max_length=64)

@router.post("/approve")
def approve_specification(request: SpecificationApprovalRequest):
    """Approve only the exact specification content the reviewer inspected."""
    spec = request.specification
    if spec.approval_status != "draft":
        raise HTTPException(status_code=422, detail="Only a draft specification can be approved.")
    actual_hash = spec.content_hash()
    if request.reviewed_content_hash != actual_hash:
        raise HTTPException(status_code=409, detail="Specification content changed after review. Review the current version and approve again.")
    approved = spec.approve(request.reviewer)
    return {
        "approved": True,
        "specification": approved.model_dump(mode="json"),
        "sha256": actual_hash,
        "warning": "Approval records reviewer attestation to this exact specification content; it does not prove the requirements are complete or correct."
    }

@router.post("/validate")
def validate_specification(specification: DesignSpecification):
    """Validate structure and ensure approval is bound to exact specification content."""
    try:
        parsed = DesignSpecification.model_validate(specification.model_dump())
        return {
            "valid": True,
            "approved": parsed.approval_status == "approved",
            "specification": parsed.model_dump(mode="json"),
            "sha256": parsed.content_hash(),
            "requirement_count": len(parsed.requirements),
            "warning": "Formal verification can establish RTL conformance to these encoded requirements; it cannot independently establish that the requirements capture the intended product behaviour."
        }
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
