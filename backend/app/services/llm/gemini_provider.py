"""Gemini LLM provider with bounded transient-error retries and model discovery."""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from backend.app.services.llm.provider import LLMProvider, LLMResponse

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 8.0


class GeminiProvider(LLMProvider):
    """Hosted Gemini REST provider. API credentials remain backend-only."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        # Treat empty or whitespace-only environment values as missing credentials.
        configured_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        self.api_key = configured_key.strip() or None
        configured_model = model_name or os.getenv("LLM_MODEL") or DEFAULT_GEMINI_MODEL
        # GET /api/llm/models returns resource names such as "models/foo";
        # the REST generateContent URL already supplies the /models/ segment.
        self.model_name = configured_model.removeprefix("models/").strip()
        if not self.model_name or "/" in self.model_name:
            raise ValueError("Gemini model must be a model ID, optionally prefixed with 'models/'.")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ValueError(
                "Gemini API key is not configured. Set GEMINI_API_KEY or GOOGLE_API_KEY in the environment or .env file."
            )
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            body = response.json()
            return str(body.get("error", {}).get("message", response.text[:300]))
        except Exception:
            return response.text[:300]

    @staticmethod
    def _retry_delay(response: httpx.Response, retry_index: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), MAX_RETRY_DELAY_SECONDS)
            except ValueError:
                pass
        return min(BASE_RETRY_DELAY_SECONDS * (2 ** retry_index), MAX_RETRY_DELAY_SECONDS)

    def _post_with_retries(
        self, client: httpx.Client, url: str, payload: dict[str, Any]
    ) -> httpx.Response:
        last_response: httpx.Response | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = client.post(url, headers=self._headers(), json=payload)
            except httpx.TimeoutException as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    raise TimeoutError(
                        f"Gemini API request timed out after {MAX_ATTEMPTS} attempts."
                    ) from exc
                time.sleep(min(BASE_RETRY_DELAY_SECONDS * (2 ** attempt), MAX_RETRY_DELAY_SECONDS))
                continue
            except httpx.RequestError as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    raise RuntimeError(
                        f"Network error communicating with Gemini API after {MAX_ATTEMPTS} attempts: {type(exc).__name__}"
                    ) from exc
                time.sleep(min(BASE_RETRY_DELAY_SECONDS * (2 ** attempt), MAX_RETRY_DELAY_SECONDS))
                continue

            if response.status_code == 200:
                return response

            last_response = response
            status = response.status_code
            if status in {401, 403}:
                raise PermissionError(
                    f"Gemini API authentication failed (HTTP {status}): {self._error_message(response)}"
                )
            if status not in TRANSIENT_STATUS_CODES or attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(self._retry_delay(response, attempt))

        assert last_response is not None
        status = last_response.status_code
        message = self._error_message(last_response)
        if status == 429:
            raise RuntimeError(
                f"Gemini API rate limit/quota response persisted after {MAX_ATTEMPTS} attempts (HTTP 429): {message}"
            )
        raise RuntimeError(
            f"Gemini API request failed after {MAX_ATTEMPTS} attempts (HTTP {status}): {message}"
        )

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model_name}:generateContent"
        )
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        try:
            with httpx.Client(timeout=45.0) as client:
                response = self._post_with_retries(client, url, payload)
        except (PermissionError, ValueError, RuntimeError, TimeoutError):
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Unexpected error communicating with Gemini API: {type(exc).__name__}"
            ) from exc

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini API returned no response candidates.")

        first_candidate = candidates[0]
        parts = first_candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if "text" in part)
        finish_reason = first_candidate.get("finishReason")
        if not text.strip():
            raise ValueError("Gemini returned an empty response.")
        if finish_reason not in (None, "STOP"):
            raise ValueError(
                f"Gemini response was not completed normally (finishReason={finish_reason})."
            )

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
            raw={"finish_reason": finish_reason},
        )

    def list_available_models(self) -> list[dict[str, Any]]:
        """Return models exposed to this API key that support generateContent."""
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    url,
                    headers=self._headers(),
                    params={"pageSize": 100},
                )
        except httpx.TimeoutException as exc:
            raise TimeoutError("Gemini model-list request timed out.") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Network error retrieving Gemini models: {type(exc).__name__}"
            ) from exc

        if response.status_code != 200:
            message = self._error_message(response)
            if response.status_code in {401, 403}:
                raise PermissionError(
                    f"Gemini model-list authentication failed (HTTP {response.status_code}): {message}"
                )
            raise RuntimeError(
                f"Gemini model-list request failed with HTTP {response.status_code}: {message}"
            )

        result: list[dict[str, Any]] = []
        page_token: str | None = None
        # Bounded pagination avoids silently missing models while preventing
        # unbounded discovery loops if the upstream API behaves unexpectedly.
        for _page in range(10):
            params = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token
            if _page:
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(url, headers=self._headers(), params=params)
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Gemini model-list pagination failed with HTTP {response.status_code}: {self._error_message(response)}"
                    )
            page = response.json()
            for model in page.get("models", []):
                methods = model.get("supportedGenerationMethods", [])
                if "generateContent" not in methods:
                    continue
                result.append({
                    "name": model.get("name"),
                    "display_name": model.get("displayName"),
                    "supported_generation_methods": methods,
                    "input_token_limit": model.get("inputTokenLimit"),
                    "output_token_limit": model.get("outputTokenLimit"),
                })
            page_token = page.get("nextPageToken")
            if not page_token:
                break
        return result
