import unittest
from unittest.mock import patch, MagicMock
import requests
import os

from models.gateway import (
    ModelResponse,
    OllamaProvider,
    GroqProvider,
    GeminiProvider,
    ModelGateway
)


class TestModelGateway(unittest.TestCase):
    """Test suite for Phase 10 Multi-Model Gateway and Provider Abstractions."""

    def test_model_response_contract(self):
        resp = ModelResponse(
            text='{"type": "final", "answer": "Hello"}',
            model="qwen2.5:3b",
            provider="ollama",
            duration_ms=45.2,
            success=True,
            error=None,
            fallback_used=False
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "ollama")
        self.assertEqual(resp.model, "qwen2.5:3b")
        d = resp.to_dict()
        self.assertIn("text", d)
        self.assertIn("duration_ms", d)
        self.assertIn("fallback_used", d)

    @patch("requests.post")
    def test_ollama_provider_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Processed answer"}
        mock_post.return_value = mock_resp

        provider = OllamaProvider()
        res = provider.generate("test prompt")
        self.assertTrue(res.success)
        self.assertEqual(res.text, "Processed answer")
        self.assertEqual(res.provider, "ollama")
        self.assertFalse(res.fallback_used)

    @patch("requests.post")
    def test_ollama_provider_connection_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Failed to connect")

        provider = OllamaProvider()
        res = provider.generate("test prompt")
        self.assertFalse(res.success)
        self.assertIn("Could not connect to Ollama", res.error)

    def test_groq_provider_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            provider = GroqProvider(api_key="")
            res = provider.generate("hello")
            self.assertFalse(res.success)
            self.assertIn("GROQ_API_KEY", res.error)

    @patch("requests.post")
    def test_groq_provider_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Groq response"}}]
        }
        mock_post.return_value = mock_resp

        provider = GroqProvider(api_key="gsk_test123")
        res = provider.generate("hello")
        self.assertTrue(res.success)
        self.assertEqual(res.text, "Groq response")
        self.assertEqual(res.provider, "groq")

    @patch("requests.post")
    def test_groq_provider_auth_failure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        provider = GroqProvider(api_key="invalid_key")
        res = provider.generate("hello")
        self.assertFalse(res.success)
        self.assertIn("authentication failed", res.error)

    def test_gemini_provider_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            provider = GeminiProvider(api_key="")
            res = provider.generate("hello")
            self.assertFalse(res.success)
            self.assertIn("GEMINI_API_KEY", res.error)

    @patch("requests.post")
    def test_gemini_provider_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Gemini response"}]
                }
            }]
        }
        mock_post.return_value = mock_resp

        provider = GeminiProvider(api_key="AIzaSyTestKey")
        res = provider.generate("hello")
        self.assertTrue(res.success)
        self.assertEqual(res.text, "Gemini response")
        self.assertEqual(res.provider, "gemini")

    @patch("requests.post")
    def test_gateway_fallback_when_cloud_fails(self, mock_post):
        """When Groq fails with error, gateway must seamlessly fall back to local Ollama."""
        gateway = ModelGateway()
        gateway.providers["groq"].api_key = "gsk_test123"

        def mock_post_dispatch(url, *args, **kwargs):
            m = MagicMock()
            if "groq.com" in url:
                m.status_code = 500
                m.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
                return m
            elif "11434" in url:
                m.status_code = 200
                m.json.return_value = {"response": "Local Qwen fallback answer"}
                return m
            m.status_code = 404
            return m

        mock_post.side_effect = mock_post_dispatch

        res = gateway.generate("test prompt", tier="CLOUD")
        self.assertTrue(res.success)
        self.assertEqual(res.text, "Local Qwen fallback answer")
        self.assertEqual(res.provider, "ollama")
        self.assertTrue(res.fallback_used)

    @patch("requests.post")
    def test_gateway_local_tier_ignores_cloud(self, mock_post):
        """LOCAL tier must directly invoke Ollama without attempting cloud."""
        gateway = ModelGateway()
        gateway.providers["groq"].api_key = "gsk_test123"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Direct local answer"}
        mock_post.return_value = mock_resp

        res = gateway.generate("test prompt", tier="LOCAL")
        self.assertTrue(res.success)
        self.assertEqual(res.provider, "ollama")
        self.assertFalse(res.fallback_used)
        # Verify the endpoint called was 11434
        called_url = mock_post.call_args[0][0]
        self.assertIn("11434", called_url)


if __name__ == "__main__":
    unittest.main()
