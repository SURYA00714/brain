import unittest
from unittest.mock import patch, MagicMock
import requests
import os

from models.gateway import (
    ModelResponse,
    GroqProvider,
    GeminiProvider,
    ModelGateway
)


class TestModelGateway(unittest.TestCase):
    """Test suite for Phase 10 Multi-Model Gateway and Provider Abstractions."""

    def test_model_response_contract(self):
        resp = ModelResponse(
            text='{"type": "final", "answer": "Hello"}',
            model="llama-3.1-8b-instant",
            provider="groq",
            duration_ms=45.2,
            success=True,
            error=None,
            fallback_used=False
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "groq")
        self.assertEqual(resp.model, "llama-3.1-8b-instant")
        d = resp.to_dict()
        self.assertIn("text", d)
        self.assertIn("duration_ms", d)
        self.assertIn("fallback_used", d)



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
    def test_gateway_returns_error_when_cloud_fails(self, mock_post):
        """When Groq fails with error, gateway must return failure (no fallback)."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            gateway = ModelGateway()
            gateway.providers["groq"].api_key = "gsk_test123"

            def mock_post_dispatch(url, *args, **kwargs):
                m = MagicMock()
                if "groq.com" in url:
                    m.status_code = 500
                    m.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
                    return m
                m.status_code = 404
                m.raise_for_status.side_effect = requests.exceptions.HTTPError("Not Found")
                return m

            mock_post.side_effect = mock_post_dispatch

            res = gateway.generate("test prompt", tier="CLOUD")
            self.assertFalse(res.success)
            self.assertFalse(res.fallback_used)



if __name__ == "__main__":
    unittest.main()
