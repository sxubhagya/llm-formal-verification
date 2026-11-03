from pathlib import Path
import json
from tempfile import TemporaryDirectory
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from backend.app.services.hdl.parser import HDLAnalysisService
from backend.app.services.hdl.yosys_runner import YosysExecutionError

router = APIRouter(prefix="/api/designs", tags=["design-analysis"])
ALLOWED_SUFFIXES = {".v", ".sv"}
MAX_FILE_BYTES = 2 * 1024 * 1024

@router.post("/analyze")
async def analyze_design(top_module: str = Form(...), files: list[UploadFile] = File(...)):
    if not top_module.strip(): raise HTTPException(status_code=422, detail="top_module must not be empty")
    if not files: raise HTTPException(status_code=422, detail="At least one RTL file is required")
    with TemporaryDirectory(prefix="uploaded_rtl_") as temp_dir:
        paths = []
        for index, upload in enumerate(files):
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise HTTPException(status_code=415, detail=f"Unsupported file extension for '{upload.filename}'. Use .v or .sv.")
            data = await upload.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES: raise HTTPException(status_code=413, detail=f"'{upload.filename}' exceeds the 2 MiB per-file limit.")
            safe_name = f"source_{index}{suffix}"
            path = Path(temp_dir) / safe_name; path.write_bytes(data); paths.append(path)
        try:
            ir, log = await run_in_threadpool(HDLAnalysisService().analyze, paths, top_module.strip())
        except YosysExecutionError as exc:
            detail = {"message": str(exc), "returncode": exc.returncode, "diagnostics": exc.output[-8000:]}
            status_code = 503 if "was not found" in str(exc) or "Could not translate" in str(exc) else 422
            raise HTTPException(status_code=status_code, detail=detail) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"status": "ANALYZED", "design": ir.model_dump(), "frontend_log_tail": log[-4000:]}
