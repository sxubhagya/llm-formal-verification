"""LLM provider diagnostics endpoints."""
from fastapi import APIRouter, HTTPException

from backend.app.services.llm.gemini_provider import GeminiProvider

router = APIRouter(prefix="/api/llm", tags=["llm-provider"])


@router.get("/models")
def list_gemini_models():
    """List Gemini models visible to the configured API key and supporting generateContent."""
    try:
        provider = GeminiProvider()
        models = provider.list_available_models()
        return {
            "provider": "gemini",
            "count": len(models),
            "models": models,
        }
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
