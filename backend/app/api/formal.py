"""API endpoints for formal verification execution."""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pathlib import Path
import hashlib
import re

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


@router.get("/runs", summary="List saved formal-verification experiments")
def list_formal_runs(limit: int = 50) -> dict:
    from backend.app.services.formal.run_store import FormalRunStore
    return {"runs": FormalRunStore().list_runs(limit=limit)}


@router.get("/runs/{run_id}", summary="Retrieve a saved formal-verification experiment")
def get_formal_run(run_id: str) -> dict:
    from backend.app.services.formal.run_store import FormalRunStore
    record = FormalRunStore().get_run(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formal run not found.")
    return record


@router.get("/runs/{run_id}/traces/{trace_ref}", summary="Download a saved counterexample VCD trace")
def download_counterexample_trace(run_id: str, trace_ref: str):
    from backend.app.services.formal.run_store import FormalRunStore
    store = FormalRunStore()
    record = store.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Formal run not found.")
    artifacts = record.get("trace_artifacts") or {}
    # New records link by the safe hashed filename. Accept historical property
    # IDs as a compatibility path, but resolve them only through the saved map.
    filename = trace_ref if trace_ref in artifacts.values() else artifacts.get(trace_ref)
    if not filename or not re.fullmatch(r"[0-9a-f]{16}\.vcd", filename):
        raise HTTPException(status_code=404, detail="No saved counterexample trace exists for this property.")
    path = store.root / run_id / "traces" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Saved counterexample trace is missing.")
    return FileResponse(path, media_type="text/vcd", filename=filename)
