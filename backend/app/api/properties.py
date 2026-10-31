from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from backend.app.models.design_ir import DesignIR
from backend.app.models.property_models import (
    DesignPropertyValidationRequest,
    PropertyGenerationRequest,
    PropertyGenerationResponse
)
from backend.app.services.property_validation import validate_property_batch
from backend.app.services.llm.provider import get_llm_provider
from backend.app.services.llm.property_generator import PropertyGenerationService

router = APIRouter(prefix="/api/properties", tags=["property-management"])

@router.post("/validate")
def validate_properties(request: DesignPropertyValidationRequest):
    """Validate candidate-property schema and referenced signals against a DesignIR."""
    try:
        design = DesignIR.model_validate(request.design)
        return validate_property_batch(design, request.batch).model_dump()
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generate", response_model=PropertyGenerationResponse)
def generate_properties(request: PropertyGenerationRequest):
    """Generate candidate formal properties using an LLM and validate them against DesignIR."""
    try:
        provider = get_llm_provider(
            provider_name=request.provider,
            model=request.model
        )
        service = PropertyGenerationService(provider=provider)
        return service.generate_candidate_properties(
            design=request.design,
            target_module=request.target_module,
            max_properties=request.max_properties,
            focus_areas=request.focus_areas,
            source_code=request.source_code
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected property generation failure: {exc}") from exc

