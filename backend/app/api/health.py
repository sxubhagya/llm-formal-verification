from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}
