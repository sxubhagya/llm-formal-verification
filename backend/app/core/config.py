import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load local backend credentials without ever requiring them in frontend code.
load_dotenv()

@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    llm_model: str | None = os.getenv("LLM_MODEL")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    generic_llm_api_key: str | None = os.getenv("LLM_API_KEY")

settings = Settings()
