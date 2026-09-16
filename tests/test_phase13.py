import os
import unittest
from unittest.mock import patch, MagicMock

from tools.router import FastRouter, default_router
from tools.registry import ToolRegistry, default_registry, Tool
from core.recovery import AdaptiveRecoveryManager, default_recovery_manager
from core.identity import default_identity
from core.world_state import default_world_state
from tools.apps import default_app_tracker
from models.gateway import ModelGateway, ModelResponse


class TestPhase13FastIntelligenceAndToolOrchestration(unittest.TestCase):
    """
    Unit and integration tests for Phase 13:
    1. Deterministic FastRouter for conversation, identity, and system state
    2. Authoritative ToolRegistry validation and INVALID_TOOL recovery
    3. Compound browser workflows with screen perception integration
    4. ModelGateway routing policy and truthful fallback
    """

    def setUp(self):
        default_app_tracker.clear()
        default_world_state.sync_from_system()

    # --------------------------------------------------------------------------
    # 1. FAST ROUTER: CONVERSATION & GREETINGS
    # --------------------------------------------------------------------------
    def test_01_fast_router_greetings_variations(self):
        """Typo variations and common greetings respond instantly without LLM."""
        for greeting in ["hello", "hi", "hey", "ello", "hiya", "good morning", "good evening"]:
            route = default_router.route(greeting)
            self.assertIsNotNone(route, f"Greeting '{greeting}' should be routed fast.")
            self.assertEqual(route["type"], "final")
            self.assertIn("Hello", route["answer"])

    def test_02_fast_router_gratitudes_and_farewells(self):
        """Gratitudes and farewells are handled deterministically."""
        res_thanks = default_router.route("thanks")
        self.assertIsNotNone(res_thanks)
        self.assertEqual(res_thanks["type"], "final")
        self.assertIn("welcome", res_thanks["answer"].lower())

        res_bye = default_router.route("bye")
        self.assertIsNotNone(res_bye)
        self.assertEqual(res_bye["type"], "final")
        self.assertIn("goodbye", res_bye["answer"].lower())

    # --------------------------------------------------------------------------
    # 2. FAST ROUTER: IDENTITY & CAPABILITIES (NO LLM, NO WEB SEARCH)
    # --------------------------------------------------------------------------
    def test_03_fast_router_identity_no_search(self):
        """Identity queries are answered from core/identity.py, NOT web search."""
        for q in ["who are you", "what are you", "what is your name", "who made you"]:
            route = default_router.route(q)
            self.assertIsNotNone(route, f"Query '{q}' should be routed deterministically.")
            self.assertEqual(route["type"], "final")
            self.assertIn(default_identity.name, route["answer"])
            self.assertIn(default_identity.persona, route["answer"])

    def test_04_fast_router_capabilities(self):
        """Capability inquiries report structured capabilities directly."""
        for q in ["what can you do", "what are your capabilities", "help"]:
            route = default_router.route(q)
            self.assertIsNotNone(route, f"Query '{q}' should be routed deterministically.")
            self.assertEqual(route["type"], "final")
            self.assertIn("Here is what I can do", route["answer"])
            self.assertIn("Application lifecycle", route["answer"])

    # --------------------------------------------------------------------------
    # 3. FAST ROUTER: DETERMINISTIC SYSTEM & ENVIRONMENT QUERIES
    # --------------------------------------------------------------------------
    def test_05_fast_router_system_info(self):
        """Operating system and desktop environment queries resolve deterministically."""
        for q in ["what operating system am i using", "what os am i using", "what os is this"]:
            route = default_router.route(q)
            self.assertIsNotNone(route)
            self.assertEqual(route["type"], "final")
            self.assertIn("Linux Mint", route["answer"])

        res_desktop = default_router.route("what desktop am i using")
        self.assertIsNotNone(res_desktop)
        self.assertIn("XFCE", res_desktop["answer"])

    def test_06_fast_router_running_apps(self):
        """Running applications query uses AppTracker and WorldState directly."""
        route = default_router.route("what applications are running")
        self.assertIsNotNone(route)
        self.assertEqual(route["type"], "final")

        # Mock an app launch
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.poll.return_value = None
        default_app_tracker.record_launch("brave", "brave-browser", mock_proc)

        route2 = default_router.route("what apps are running")
        self.assertIn("Brave Browser", route2["answer"])

    def test_07_fast_router_preferred_browser(self):
        """Configured browser resolves from identity preferences."""
        route = default_router.route("what browser am i using")
        self.assertIsNotNone(route)
        self.assertIn("Brave", route["answer"])

    # --------------------------------------------------------------------------
    # 4. FAST ROUTER: NATURAL APP LAUNCHES & SEMANTIC EXCLUSION
    # --------------------------------------------------------------------------
    def test_08_natural_app_launch_intent(self):
        """Natural app launch variations route to OPEN_APP deterministically."""
        queries = [
            ("can you open brave", "brave"),
            ("please open brave", "brave"),
            ("open browser", "brave"),
            ("launch terminal", "terminal"),
            ("open file manager", "file_manager"),
            ("open calculator", "calculator"),
            ("can you close brave", "brave"),
        ]
        for q, expected_app in queries:
            route = default_router.route(q)
            self.assertIsNotNone(route, f"Failed to route natural app intent '{q}'")
            expected_tool = "CLOSE_APP" if "close" in q else "OPEN_APP"
            self.assertEqual(route["tool"], expected_tool)
            self.assertEqual(route["arguments"]["app_name"], expected_app)

    def test_09_semantic_diagnostic_bypasses_fast_router(self):
        """Diagnostic and reasoning questions must bypass FastRouter to reach cognitive engine."""
        diagnostic_queries = [
            "Why does my browser keep crashing?",
            "Why did Brave crash yesterday?",
            "How can I optimize Linux performance?",
            "What is the best way to structure Python projects?",
            "Summarize the latest Python 3.12 release notes"
        ]
        for q in diagnostic_queries:
            route = default_router.route(q)
            self.assertIsNone(route, f"Diagnostic query '{q}' should NOT be routed fast; it must reach reasoning.")

    # --------------------------------------------------------------------------
    # 5. TOOL REGISTRY: AUTHORITATIVE VALIDATION & INVALID_TOOL RECOVERY
    # --------------------------------------------------------------------------
    def test_10_tool_registry_authoritative_has_tool(self):
        """ToolRegistry correctly reports presence of registered tools and aliases."""
        self.assertTrue(default_registry.has_tool("OPEN_APP"))
        self.assertTrue(default_registry.has_tool("BROWSER_SEARCH"))
        self.assertTrue(default_registry.has_tool("BROWSER_SEARCH_FOREGROUND"))
        self.assertTrue(default_registry.has_tool("ANALYZE_SCREEN"))
        self.assertFalse(default_registry.has_tool("NON_EXISTENT_TOOL"))
        self.assertFalse(default_registry.has_tool(""))

    def test_11_invalid_tool_recovery_no_attempt_burn(self):
        """Unregistered tool is diagnosed as INVALID_TOOL and REPLANs without burning attempts."""
        res = {"success": False, "error": "Tool 'BROWSER_SEARCH_XYZ' is not registered."}
        reason, expl = default_recovery_manager.diagnose_failure("BROWSER_SEARCH_XYZ", {}, res)
        self.assertEqual(reason, "INVALID_TOOL")
        self.assertIn("does not exist", expl)

        strat = default_recovery_manager.determine_recovery_strategy("BROWSER_SEARCH_XYZ", {}, reason, attempt=0)
        self.assertEqual(strat["action"], "REPLAN")
        self.assertIn("Available tools:", strat["message"])

    # --------------------------------------------------------------------------
    # 6. COMPOUND BROWSER WORKFLOWS & PERCEPTION INTEGRATION
    # --------------------------------------------------------------------------
    def test_12_compound_browser_search_and_see(self):
        """Compound request generates plan coupling browser navigation and screen perception."""
        res = default_router.route("open brave, search marvel, and tell me what you see")
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "plan")
        plan = res["plan"]
        step_names = [s.tool_name for s in plan.steps]
        self.assertIn("OPEN_APP", step_names)
        self.assertIn("FOCUS_APP", step_names)
        self.assertIn("BROWSER_SEARCH_FOREGROUND", step_names)
        self.assertIn("ANALYZE_SCREEN", step_names)

    def test_13_find_element_on_screen(self):
        """Element search request invokes perception without clicking."""
        mock_elem = {
            "id": "btn_settings_100_200",
            "type": "button",
            "text": "Settings",
            "center_x": 100,
            "center_y": 200,
            "confidence": 0.98,
            "ambiguous": False
        }
        with patch("tools.vision.default_vision.find_element", return_value=mock_elem):
            route = default_router.route("find the Settings button on my screen")
            self.assertIsNotNone(route)
            self.assertEqual(route["type"], "final")
            self.assertIn("Found 'Settings'", route["answer"])
            self.assertIn("(100, 200)", route["answer"])

    def test_14_continue_reobserve_screen(self):
        """'continue' command triggers fresh screen observation."""
        with patch("tools.screen.analyze_captured_screen") as mock_analyze:
            mock_analyze.return_value = {
                "status": "OK",
                "elements": [{"id": "elem1", "text": "Home"}],
                "perception": {"screen_state": "NORMAL"}
            }
            route = default_router.route("continue")
            self.assertIsNotNone(route)
            self.assertEqual(route["type"], "final")
            self.assertIn("Screen observation refreshed", route["answer"])

    # --------------------------------------------------------------------------
    # 7. MODEL GATEWAY ROUTING POLICY & TRUTHFUL FALLBACK
    # --------------------------------------------------------------------------
    def test_15_model_gateway_cloud_failure_policy(self):
        """Cloud failure on visual request does not fall back to local Qwen, while text falls back honestly."""
        gateway = ModelGateway()
        # Visual request without cloud provider
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            resp = gateway.generate("Describe this chart", image_path="/tmp/nonexistent.png")
            self.assertFalse(resp.success)
            self.assertIn("Vision model unavailable offline", resp.error)
            self.assertFalse(resp.fallback_used)

        # Honest fallback metadata for text request when cloud fails
        with patch.object(gateway.providers["groq"], "is_available", return_value=False), \
             patch.object(gateway.providers["gemini"], "is_available", return_value=False), \
             patch.object(gateway.providers["ollama"], "generate") as mock_ollama:
            from models.gateway import ModelResponse
            mock_ollama.return_value = ModelResponse(
                text="Ollama answer",
                model="qwen2.5:3b",
                provider="ollama",
                success=True
            )
            resp = gateway.generate("Research quantum computing", tier="CLOUD")
            self.assertTrue(resp.success)
            self.assertEqual(resp.provider, "ollama")
            self.assertTrue(resp.fallback_used)
            self.assertEqual(resp.fallback_reason, "Cloud models unavailable")


if __name__ == "__main__":
    unittest.main()
