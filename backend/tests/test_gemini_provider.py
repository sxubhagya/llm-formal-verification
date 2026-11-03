"""Offline tests for Gemini retries, model discovery, and credential handling."""
import unittest
from unittest.mock import Mock, patch

import httpx

from backend.app.services.llm.gemini_provider import GeminiProvider, DEFAULT_GEMINI_MODEL


def response(status: int, payload: dict, headers: dict | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://example.test")
    return httpx.Response(status, json=payload, headers=headers, request=request)


class GeminiProviderTests(unittest.TestCase):
    def test_default_model_is_current_configurable_default(self):
        # Isolate the default-value test from the developer's local .env model.
        # An explicit empty value makes the provider use DEFAULT_GEMINI_MODEL.
        with patch.dict("os.environ", {"LLM_MODEL": ""}):
            provider = GeminiProvider(api_key="test-key")
        self.assertEqual(provider.model_name, DEFAULT_GEMINI_MODEL)
        self.assertEqual(DEFAULT_GEMINI_MODEL, "gemini-3.5-flash-lite")

    def test_model_resource_prefix_is_normalized_before_url_construction(self):
        provider = GeminiProvider(api_key="test-key", model_name="models/gemini-3.5-flash-lite")
        self.assertEqual(provider.model_name, "gemini-3.5-flash-lite")

    @patch("backend.app.services.llm.gemini_provider.time.sleep")
    @patch("backend.app.services.llm.gemini_provider.httpx.Client")
    def test_generate_retries_503_then_succeeds(self, client_cls, sleep):
        ok = response(200, {
            "candidates": [{
                "content": {"parts": [{"text": '{"properties": []}'}]},
                "finishReason": "STOP"
            }],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4, "totalTokenCount": 14}
        })
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.post.side_effect = [
            response(503, {"error": {"message": "busy"}}),
            ok,
        ]
        client_cls.return_value = client

        result = GeminiProvider(api_key="test-key").generate("prompt")
        self.assertEqual(result.content, '{"properties": []}')
        self.assertEqual(result.usage["total_tokens"], 14)
        self.assertEqual(client.post.call_count, 2)
        sleep.assert_called_once_with(1.0)

    @patch("backend.app.services.llm.gemini_provider.time.sleep")
    @patch("backend.app.services.llm.gemini_provider.httpx.Client")
    def test_generate_stops_after_three_503_attempts(self, client_cls, sleep):
        busy = response(503, {"error": {"message": "high demand"}})
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.post.return_value = busy
        client_cls.return_value = client

        with self.assertRaisesRegex(RuntimeError, "after 3 attempts.*HTTP 503"):
            GeminiProvider(api_key="test-key").generate("prompt")
        self.assertEqual(client.post.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1.0, 2.0])

    @patch("backend.app.services.llm.gemini_provider.time.sleep")
    @patch("backend.app.services.llm.gemini_provider.httpx.Client")
    def test_authentication_error_is_not_retried(self, client_cls, sleep):
        denied = response(403, {"error": {"message": "forbidden"}})
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.post.return_value = denied
        client_cls.return_value = client

        with self.assertRaisesRegex(PermissionError, "HTTP 403"):
            GeminiProvider(api_key="test-key").generate("prompt")
        self.assertEqual(client.post.call_count, 1)
        sleep.assert_not_called()

    @patch("backend.app.services.llm.gemini_provider.httpx.Client")
    def test_model_discovery_filters_to_generate_content(self, client_cls):
        models_response = response(200, {
            "models": [
                {"name": "models/gemini-3.8-flash", "displayName": "Gemini Flash",
                 "supportedGenerationMethods": ["generateContent", "countTokens"]},
                {"name": "models/embedding-001", "displayName": "Embedding",
                 "supportedGenerationMethods": ["embedContent"]},
            ]
        })
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.get.return_value = models_response
        client_cls.return_value = client

        models = GeminiProvider(api_key="test-key").list_available_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["name"], "models/gemini-3.8-flash")
        self.assertEqual(client.get.call_count, 1)

    def test_missing_key_fails_before_network(self):
        provider = GeminiProvider(api_key="")
        provider.api_key = None
        with self.assertRaisesRegex(ValueError, "Gemini API key is not configured"):
            provider.list_available_models()



    @patch("backend.app.api.llm.GeminiProvider")
    def test_models_endpoint_returns_provider_model_metadata(self, provider_cls):
        from fastapi.testclient import TestClient
        from backend.app.main import app

        provider_cls.return_value.list_available_models.return_value = [
            {"name": "models/gemini-3.8-flash", "display_name": "Gemini Flash",
             "supported_generation_methods": ["generateContent"],
             "input_token_limit": 1000, "output_token_limit": 500}
        ]
        response = TestClient(app).get("/api/llm/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["models"][0]["name"], "models/gemini-3.8-flash")
        self.assertNotIn("api_key", data)

if __name__ == "__main__":
    unittest.main()
