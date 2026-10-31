from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from backend.app.models.design_ir import DesignIR
from backend.app.models.property_models import DesignPropertyValidationRequest
from backend.app.services.property_validation import validate_property_batch

router = APIRouter(prefix="/api/properties", tags=["property-management"])

@router.post("/validate")
def validate_properties(request: DesignPropertyValidationRequest):
    """Validate candidate-property schema and referenced signals against a DesignIR."""
    try:
        design = DesignIR.model_validate(request.design)
        return validate_property_batch(design, request.batch).model_dump()
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
