"""Gemini LLM provider implementation."""
from __future__ import annotations
import os
import json
import httpx
from typing import Any
from backend.app.services.llm.provider import LLMProvider, LLMResponse

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiProvider(LLMProvider):
    """Hosted Gemini LLM provider using REST API with httpx."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or os.getenv("LLM_MODEL") or DEFAULT_GEMINI_MODEL

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        if not self.api_key:
            raise ValueError(
                "Gemini API key is not configured. Set GEMINI_API_KEY or GOOGLE_API_KEY in the environment or .env file."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        params = {"key": self.api_key}

        contents = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nPlease acknowledge and follow these instructions."}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will strictly act as an untrusted property proposer, output JSON conforming to the candidate-property schema, and make no claims of formal proof."}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(url, params=params, json=payload)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Gemini API request timed out after 45 seconds: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Network error communicating with Gemini API: {type(exc).__name__}") from exc

        if response.status_code != 200:
            status = response.status_code
            try:
                err_body = response.json()
                msg = err_body.get("error", {}).get("message", response.text[:200])
            except Exception:
                msg = response.text[:200]
            if status in {401, 403}:
                raise PermissionError(f"Gemini API authentication failed (HTTP {status}): {msg}")
            if status == 429:
                raise RuntimeError(f"Gemini API rate limit or quota exceeded (HTTP 429): {msg}")
            raise RuntimeError(f"Gemini API request failed with HTTP {status}: {msg}")

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini API returned no response candidates.")

        first_cand = candidates[0]
        parts = first_cand.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if "text" in p)

        usage_meta = data.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        }

        return LLMResponse(
            content=text,
            model_name=self.model_name,
            usage=usage,
            raw={"finish_reason": first_cand.get("finishReason")}
        )
