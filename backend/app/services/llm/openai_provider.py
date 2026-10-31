"""OpenAI LLM provider implementation."""
from __future__ import annotations
import os
import httpx
from typing import Any
from backend.app.services.llm.provider import LLMProvider, LLMResponse

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    """Hosted OpenAI LLM provider using chat completions API."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        self.model_name = model_name or os.getenv("LLM_MODEL") or DEFAULT_OPENAI_MODEL

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is not configured. Set OPENAI_API_KEY or LLM_API_KEY in the environment or .env file."
            )

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"OpenAI API request timed out after 45 seconds: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Network error communicating with OpenAI API: {type(exc).__name__}") from exc

        if response.status_code != 200:
            status = response.status_code
            try:
                err_body = response.json()
                msg = err_body.get("error", {}).get("message", response.text[:200])
            except Exception:
                msg = response.text[:200]
            if status in {401, 403}:
                raise PermissionError(f"OpenAI API authentication failed (HTTP {status}): {msg}")
            if status == 429:
                raise RuntimeError(f"OpenAI API rate limit or quota exceeded (HTTP 429): {msg}")
            raise RuntimeError(f"OpenAI API request failed with HTTP {status}: {msg}")

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenAI API returned no completion choices.")

        choice = choices[0]
        text = choice.get("message", {}).get("content", "")

        usage_raw = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens", 0),
            "completion_tokens": usage_raw.get("completion_tokens", 0),
            "total_tokens": usage_raw.get("total_tokens", 0),
        }

        return LLMResponse(
            content=text,
            model_name=self.model_name,
            usage=usage,
            raw={"finish_reason": choice.get("finish_reason")}
        )
