"""API endpoints for formal verification execution."""
from fastapi import APIRouter, HTTPException, status

from backend.app.models.formal_models import (
    FormalVerificationRequest, FormalVerificationResponse
)
from backend.app.services.formal.verification_service import FormalVerificationService

router = APIRouter(prefix="/api/formal", tags=["formal"])


@router.post(
    "/verify",
    response_model=FormalVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute formal verification on candidate properties using SymbiYosys"
)
def verify_properties(request: FormalVerificationRequest) -> FormalVerificationResponse:
    try:
        service = FormalVerificationService()
        return service.verify(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Formal verification failed to execute: {str(e)}"
        )
