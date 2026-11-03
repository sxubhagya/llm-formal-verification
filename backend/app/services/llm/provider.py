"""Provider-independent LLM interface and factory."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from backend.app.core.config import settings


@dataclass
class LLMResponse:
    content: str
    model_name: str
    usage: dict[str, int] | None = None
    raw: Any = None


class LLMProvider(ABC):
    """Abstract interface for hosted LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Submit a prompt and return a structured LLMResponse."""
        pass


def get_llm_provider(
    provider_name: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> LLMProvider:
    """Factory to retrieve a configured LLM provider instance."""
    name = (provider_name or settings.llm_provider or "gemini").lower().strip()
    if name == "mock":
        from backend.app.services.llm.mock_provider import MockProvider
        return MockProvider(model_name=model or "mock-model")

    if name in {"gemini", "google"}:
        from backend.app.services.llm.gemini_provider import GeminiProvider
        key = api_key or settings.gemini_api_key or settings.generic_llm_api_key
        return GeminiProvider(api_key=key, model_name=model or settings.llm_model)

    if name == "openai":
        from backend.app.services.llm.openai_provider import OpenAIProvider
        key = api_key or settings.openai_api_key or settings.generic_llm_api_key
        return OpenAIProvider(api_key=key, model_name=model or settings.llm_model)

    raise ValueError(f"Unsupported LLM provider '{name}'. Supported: 'gemini', 'openai', 'mock'.")
