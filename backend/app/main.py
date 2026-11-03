from fastapi import FastAPI
from backend.app.api.health import router as health_router
from backend.app.api.designs import router as designs_router
from backend.app.api.properties import router as properties_router
from backend.app.api.formal import router as formal_router
from backend.app.api.llm import router as llm_router
from backend.app.api.specifications import router as specifications_router
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings

app = FastAPI(title="LLM-Assisted Formal Verification API", version="0.9.3", description="RTL analysis, LLM candidate generation, and formal verification.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(designs_router)
app.include_router(properties_router)
app.include_router(formal_router)
app.include_router(llm_router)
app.include_router(specifications_router)

@app.get("/")
def root() -> dict[str, str]:
    return {"service": "llm-assisted-formal-verification", "status": "running", "environment": settings.app_env}
