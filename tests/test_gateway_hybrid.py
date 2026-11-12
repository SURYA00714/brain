import os
import unittest
from unittest.mock import patch, MagicMock
from models.gateway import ModelGateway, GroqProvider, ModelResponse


class TestHybridRouting(unittest.TestCase):
    def test_auto_falls_back_to_local_when_no_cloud_keys(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            gw = ModelGateway()
            gw.providers["ollama"].generate = MagicMock(
                return_value=ModelResponse(text="local ok", provider="ollama", model="qwen3.5:2b-q4_K_M", success=True)
            )
            resp = gw.route_task("complex_reasoning", "hello")
            self.assertTrue(resp.success)
            self.assertEqual(resp.provider, "ollama")
            self.assertTrue(resp.fallback_used)

    def test_sensitive_data_never_sent_to_cloud(self):
        gw = ModelGateway()
        gw.providers["groq"].api_key = "gsk_testkey123456789012345"
        gw.providers["groq"].generate = MagicMock()
        gw.providers["ollama"].generate = MagicMock(
            return_value=ModelResponse(text="kept local", provider="ollama", model="qwen3.5:2b-q4_K_M", success=True)
        )
        resp = gw.route_task("complex_reasoning", "My password=supersecret123, please help")
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "ollama")
        gw.providers["groq"].generate.assert_not_called()

    @patch("requests.post")
    def test_auth_failure_circuit_breaker_avoids_duplicate_calls(self, mock_post):
        m = MagicMock()
        m.status_code = 401
        m.text = "Invalid API key"
        mock_post.return_value = m

        p = GroqProvider(api_key="gsk_bad_key")
        self.assertTrue(p.is_available())
        r1 = p.generate("hi")
        self.assertFalse(r1.success)
        self.assertFalse(p.is_available())  # Circuit breaker tripped

    def test_task_based_routing_local_first(self):
        gw = ModelGateway()
        gw.providers["groq"].api_key = "gsk_testkey123456789012345"
        gw.providers["groq"].generate = MagicMock(
            return_value=ModelResponse(text="cloud ok", provider="groq", model="llama-3.1-8b-instant", success=True)
        )
        gw.providers["ollama"].generate = MagicMock(
            return_value=ModelResponse(text="local ok", provider="ollama", model="qwen3.5:2b-q4_K_M", success=True)
        )
        r_local = gw.route_task("conversation", "hi there")
        self.assertEqual(r_local.provider, "ollama")
        gw.providers["groq"].generate.assert_not_called()

        r_complex = gw.route_task("complex_reasoning", "analyze this architecture")
        self.assertEqual(r_complex.provider, "groq")


if __name__ == "__main__":
    unittest.main()
