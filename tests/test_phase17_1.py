import os
import unittest
from unittest.mock import patch, MagicMock

from models.gateway import ModelGateway, ModelResponse, GroqProvider, GeminiProvider
from core.cognition import CognitiveEngine, default_cognition
from core.telemetry import default_telemetry, RequestTelemetry
from brain import run_planner_task


class TestPhase17_1CloudIntelligence(unittest.TestCase):
    """
    Test suite for Phase 17.1: Cloud Intelligence Integration & Verification.
    All tests use mocks to ensure no real API keys are required and tests never flake.
    """

    def setUp(self):
        # Save original environ
        self._orig_groq = os.environ.get("GROQ_API_KEY")
        self._orig_gemini = os.environ.get("GEMINI_API_KEY")
        self._orig_google = os.environ.get("GOOGLE_API_KEY")

        # Clear them by default for test isolation
        for k in ["GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"]:
            if k in os.environ:
                del os.environ[k]

    def tearDown(self):
        # Restore environ
        if self._orig_groq is not None:
            os.environ["GROQ_API_KEY"] = self._orig_groq
        elif "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]

        if self._orig_gemini is not None:
            os.environ["GEMINI_API_KEY"] = self._orig_gemini
        elif "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

        if self._orig_google is not None:
            os.environ["GOOGLE_API_KEY"] = self._orig_google
        elif "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]

    # 1. No cloud keys -> Cloud failure (No local fallback)
    def test_01_no_cloud_keys_fails(self):
        gateway = ModelGateway()
        resp = gateway.generate("Explain polymorphism", tier="AUTO")
        self.assertFalse(resp.success)
        err_msg = (resp.error or "").lower()
        self.assertTrue("error" in err_msg or "no cloud models" in err_msg)

    # 2. Groq configured -> Groq selected
    def test_02_groq_configured_selected(self):
        os.environ["GROQ_API_KEY"] = "mock_groq_secret_key"
        gateway = ModelGateway()
        with patch.object(gateway.providers["groq"], "generate", return_value=ModelResponse(
            text="Groq low-latency reasoning output",
            model="llama-3.3-70b-versatile",
            provider="groq",
            duration_ms=250.0,
            success=True
        )) as mock_groq:
            resp = gateway.generate("Compare Rust and Go", tier="AUTO")
            self.assertTrue(resp.success)
            self.assertEqual(resp.provider, "groq")
            self.assertTrue(resp.cloud_attempted)
            self.assertFalse(resp.fallback_used)
            mock_groq.assert_called_once()

    # 3. Gemini configured -> Gemini selected when appropriate
    def test_03_gemini_configured_selected(self):
        os.environ["GEMINI_API_KEY"] = "mock_gemini_secret_key"
        gateway = ModelGateway()
        with patch.object(gateway.providers["gemini"], "generate", return_value=ModelResponse(
            text="Gemini deep reasoning output",
            model="gemini-2.5-flash",
            provider="gemini",
            duration_ms=400.0,
            success=True
        )) as mock_gemini:
            resp = gateway.generate("Deep architectural comparison", tier="DEEP")
            self.assertTrue(resp.success)
            self.assertEqual(resp.provider, "gemini")
            self.assertTrue(resp.cloud_attempted)
            mock_gemini.assert_called_once()

    # 4. Cloud success -> no fallback call
    def test_04_cloud_success_no_fallback_call(self):
        os.environ["GROQ_API_KEY"] = "mock_key"
        gateway = ModelGateway()
        with patch.object(gateway.providers["groq"], "generate", return_value=ModelResponse(
            text="Fast response",
            model="llama-3.3-70b",
            provider="groq",
            duration_ms=180.0,
            success=True
        )):
            resp = gateway.generate("Explain Python GIL", tier="CLOUD")
            self.assertEqual(resp.provider, "groq")

    # 5. Cloud failure -> Returns explicit failure
    def test_05_cloud_failure_explicit_failure(self):
        os.environ["GROQ_API_KEY"] = "mock_key"
        gateway = ModelGateway()
        with patch.object(gateway.providers["groq"], "generate", return_value=ModelResponse(
            text="",
            model="llama-3.3-70b",
            provider="groq",
            duration_ms=50.0,
            success=False,
            error="Groq 503 service unavailable"
        )):
            resp = gateway.generate("Explain recursion", tier="CLOUD")
            self.assertFalse(resp.success)
            self.assertIn("Groq 503", resp.error)
            self.assertTrue(resp.cloud_attempted)

    # 6. Telemetry records provider and latency
    def test_06_telemetry_records_provider_and_latency(self):
        os.environ["GROQ_API_KEY"] = "mock_key"
        with patch("models.gateway.default_gateway.providers") as mock_providers:
            mock_groq = MagicMock()
            mock_groq.is_available.return_value = True
            mock_groq.generate.return_value = ModelResponse(
                text="Python is readable and clean",
                model="llama-3.3-70b-versatile",
                provider="groq",
                duration_ms=215.0,
                success=True,
                cloud_attempted=True
            )
            mock_gemini = MagicMock()
            mock_gemini.is_available.return_value = False

            mock_providers.__getitem__.side_effect = lambda k: {
                "groq": mock_groq,
                "gemini": mock_gemini
            }[k]

            with patch("core.cognition.default_cognition.process_reasoning_query") as mock_proc:
                mock_proc.return_value = "Python is readable and clean"
                default_cognition.last_reasoning_response = ModelResponse(
                    text="Python is readable and clean",
                    model="llama-3.3-70b-versatile",
                    provider="groq",
                    duration_ms=215.0,
                    success=True,
                    cloud_attempted=True
                )
                ans = run_planner_task("explain why Python is popular")
                self.assertIn("Python is readable", ans)

                last_tel = default_telemetry.get_last()
                self.assertIsNotNone(last_tel)
                self.assertTrue(last_tel.reasoning_required)
                self.assertEqual(last_tel.llm_provider, "groq")
                self.assertEqual(last_tel.llm_calls_this_request, 1)
                self.assertTrue(last_tel.cloud_attempted)
                self.assertEqual(last_tel.provenance, "MODEL")

    # 7. Telemetry never contains API keys
    def test_07_telemetry_never_contains_api_keys(self):
        secret_key = "gsk_live_secret_groq_key_value_998877"
        tel = RequestTelemetry(
            request="Test request",
            cloud_failure_reason=f"Auth error with {secret_key}"
        )
        d = tel.to_dict()
        for k, v in d.items():
            if isinstance(v, str):
                self.assertNotIn("gsk_", v)
                self.assertNotIn("998877", v)

    # 8. Search-only -> 0 LLM
    def test_08_search_only_zero_llm(self):
        with patch("brain.default_router.route", return_value={"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "Marvel"}}):
            with patch("brain.perform_web_search", return_value="Marvel Studios news and movies"):
                ans = run_planner_task("search Marvel")
                last_tel = default_telemetry.get_last()
                self.assertIsNotNone(last_tel)
                self.assertEqual(last_tel.llm_calls_this_request, 0)
                self.assertEqual(last_tel.provenance, "WEB")

    # 9. Search + synthesis -> model path
    def test_09_search_and_synthesis_model_path(self):
        with patch("core.cognition.research_topic", return_value={
            "success": True,
            "findings": ["Marvel Studios announces Phase 6", "Deadpool & Wolverine breaks records"],
            "sources": ["https://marvel.com"]
        }):
            with patch("models.gateway.default_gateway.generate", return_value=ModelResponse(
                text="Marvel announced Phase 6 updates and recent box office records.",
                model="llama-3.3-70b-versatile",
                provider="groq",
                duration_ms=310.0,
                success=True,
                cloud_attempted=True
            )):
                with patch.object(default_cognition.gateway.providers["groq"], "is_available", return_value=True):
                    ans = run_planner_task("search Marvel and summarize what you find")
                    last_tel = default_telemetry.get_last()
                    self.assertIsNotNone(last_tel)
                    self.assertEqual(last_tel.llm_calls_this_request, 1)
                    self.assertEqual(last_tel.provenance, "WEB + MODEL")

    # 10. Current-information query -> web retrieval first
    def test_10_current_information_web_retrieval_first(self):
        engine = CognitiveEngine()
        intent = engine.understand_intent("what is the latest Python release today?")
        self.assertEqual(intent.get("intent"), "RESEARCH")

    # 11. Reasoning query -> reasoning_required=True
    def test_11_reasoning_query_reasoning_required(self):
        engine = CognitiveEngine()
        req_eval = engine.evaluate_reasoning_necessity("explain why Python is popular")
        self.assertTrue(req_eval.required)
        self.assertFalse(req_eval.deterministic_solution_available)

    # 12. No infinite provider loop
    def test_12_no_infinite_provider_loop(self):
        os.environ["GROQ_API_KEY"] = "groq_key"
        os.environ["GEMINI_API_KEY"] = "gemini_key"
        gateway = ModelGateway()
        call_counts = {"groq": 0, "gemini": 0}

        def mock_groq_gen(*args, **kwargs):
            call_counts["groq"] += 1
            return ModelResponse("", "llama-3.3", "groq", success=False, error="timeout")

        def mock_gemini_gen(*args, **kwargs):
            call_counts["gemini"] += 1
            return ModelResponse("", "gemini-2.5", "gemini", success=False, error="timeout")

        with patch.object(gateway.providers["groq"], "generate", side_effect=mock_groq_gen), \
             patch.object(gateway.providers["gemini"], "generate", side_effect=mock_gemini_gen):

            resp = gateway.generate("Explain recursion", tier="CLOUD")
            self.assertEqual(call_counts["groq"], 1)
            self.assertEqual(call_counts["gemini"], 1)
            self.assertFalse(resp.success)
            self.assertEqual(resp.provider, "gemini")

    # 13. Existing safety paths remain deterministic
    def test_13_existing_safety_remains_deterministic(self):
        ans = run_planner_task("rm -rf /")
        self.assertTrue("blocked" in ans.lower() or "prohibited" in ans.lower() or "safety" in ans.lower())
        last_tel = default_telemetry.get_last()
        self.assertIsNotNone(last_tel)
        self.assertEqual(last_tel.llm_calls_this_request, 0)
        self.assertFalse(last_tel.reasoning_required)

    # 14. Existing memory and world-state paths remain deterministic
    def test_14_memory_and_world_state_paths_remain_deterministic(self):
        from core.memory import default_memory
        default_memory.add_memory("FACT", "user", "name", "Jai")
        ans = run_planner_task("what is my name?")
        self.assertIn("Jai", ans)
        last_tel = default_telemetry.get_last()
        self.assertIsNotNone(last_tel)
        self.assertEqual(last_tel.llm_calls_this_request, 0)
        self.assertEqual(last_tel.provenance, "MEMORY")

    # 15. Safe diagnostic status reporting
    def test_15_brain_cloud_status_diagnostic(self):
        ans = run_planner_task("Brain cloud status")
        self.assertIn("Cloud Intelligence", ans)
        self.assertIn("Groq:", ans)
        self.assertIn("Gemini:", ans)
        self.assertNotIn("Local Qwen:", ans)
        last_tel = default_telemetry.get_last()
        self.assertIsNotNone(last_tel)
        self.assertEqual(last_tel.llm_calls_this_request, 0)


if __name__ == "__main__":
    unittest.main()
