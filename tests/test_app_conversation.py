"""
Unit and integration tests for Brain Terminal App Backend:
- Multi-turn conversation context tracking
- Device control fast routing (Bluetooth, WiFi, Volume)
- Pronoun / context reference resolution
- Conversation clearing
"""

import unittest
from unittest.mock import MagicMock, patch

from core.app_backend import BrainAppCore
from core.context import default_short_term_memory
from tools.router import default_router


class TestAppConversation(unittest.TestCase):

    def setUp(self):
        default_short_term_memory.clear()
        self.core = BrainAppCore(default_model="qwen3.5-brain:v2")

    def tearDown(self):
        default_short_term_memory.clear()

    def test_device_control_fast_routing(self):
        """Verify device control queries with varied phrasing route to correct tools."""
        queries = [
            ("turn off bluetooth on this device", "BLUETOOTH_OFF"),
            ("disable bluetooth", "BLUETOOTH_OFF"),
            ("turn on bluetooth", "BLUETOOTH_ON"),
            ("check bluetooth status", "BLUETOOTH_STATUS"),
            ("turn off wifi", "WIFI_OFF"),
            ("turn on wifi", "WIFI_ON"),
            ("check wifi status", "WIFI_STATUS"),
            ("mute volume", "VOLUME_MUTE"),
            ("turn up volume", "VOLUME_UP"),
            ("turn down volume", "VOLUME_DOWN"),
        ]
        for query, expected_tool in queries:
            routed = default_router.route(query)
            self.assertIsNotNone(routed, f"Expected route for '{query}'")
            self.assertEqual(routed.get("tool"), expected_tool, f"Mismatch for '{query}'")

    @patch("core.app_backend.run_planner_task")
    def test_execute_task_routes_device_control(self, mock_planner):
        """Verify execute_task runs device controls via autonomous tool path."""
        mock_planner.return_value = "Bluetooth blocked via rfkill."
        res = self.core.execute_task("turn off bluetooth on this device")
        
        self.assertEqual(res["execution_path"], "AUTONOMOUS_TOOL_EXECUTION")
        self.assertEqual(res["strategy"], "TOOL_ASSISTED_EXECUTION")
        self.assertEqual(res["text"], "Bluetooth blocked via rfkill.")
        mock_planner.assert_called_once()

    def test_multi_turn_context_stored(self):
        """Verify conversation turns are stored in short term memory."""
        self.assertEqual(len(default_short_term_memory.turns), 0)

        with patch.object(self.core.orchestrator, "solve") as mock_solve:
            mock_res = MagicMock()
            mock_res.text = "IPL is the Indian Premier League."
            mock_res.strategy = "DIRECT_RESPONSE"
            mock_res.mode = "DIRECT"
            mock_res.execution_path = "LLM_DIRECT"
            mock_res.model_id = "qwen3.5-brain:v2"
            mock_res.verified = True
            mock_res.confidence = 0.9
            mock_res.tokens_per_sec = 25.0
            mock_res.metadata = {}
            mock_solve.return_value = mock_res

            self.core.execute_task("do you know ipl")
            self.assertEqual(len(default_short_term_memory.turns), 1)
            self.assertEqual(default_short_term_memory.turns[0].user_text, "do you know ipl")

            # Second turn should receive context snippet
            mock_res2 = MagicMock()
            mock_res2.text = "There are 10 teams in the IPL."
            mock_res2.strategy = "DIRECT_RESPONSE"
            mock_res2.mode = "DIRECT"
            mock_res2.execution_path = "LLM_DIRECT"
            mock_res2.model_id = "qwen3.5-brain:v2"
            mock_res2.verified = True
            mock_res2.confidence = 0.9
            mock_res2.tokens_per_sec = 25.0
            mock_res2.metadata = {}
            mock_solve.return_value = mock_res2

            self.core.execute_task("how many teams are there")
            self.assertEqual(len(default_short_term_memory.turns), 2)
            
            # Verify context was passed to second solve() call
            call_args = mock_solve.call_args[1]
            self.assertIn("context", call_args)
            self.assertIn("IPL", call_args["context"])

    def test_clear_conversation(self):
        """Verify clear_conversation resets dialogue context."""
        default_short_term_memory.add_turn("hello", "hi there")
        self.assertEqual(len(default_short_term_memory.turns), 1)
        self.core.clear_conversation()
        self.assertEqual(len(default_short_term_memory.turns), 0)

    @patch("core.cognition.CognitiveEngine.execute_web_research")
    def test_real_time_web_research_routing(self, mock_web):
        """Verify queries asking for current real-time world facts trigger web research."""
        mock_web.return_value = {
            "text": "President Donald J. Trump is the current president of the United States.",
            "sources": ["whitehouse.gov"]
        }
        res = self.core.execute_task("who is president of usa")
        self.assertEqual(res["execution_path"], "LIVE_WEB_RESEARCH")
        self.assertEqual(res["strategy"], "GROUNDED_WEB_RESEARCH")
        self.assertIn("Donald J. Trump", res["text"])
        mock_web.assert_called_once()

    def test_system_context_passed_to_orchestrator(self):
        """Verify system context containing Brain identity is injected into solve()."""
        with patch.object(self.core.orchestrator, "solve") as mock_solve:
            mock_res = MagicMock()
            mock_res.text = "I am Brain."
            mock_res.strategy = "DIRECT_RESPONSE"
            mock_res.mode = "DIRECT"
            mock_res.execution_path = "LLM_DIRECT"
            mock_res.model_id = "qwen3.5-brain:v2"
            mock_res.verified = True
            mock_res.confidence = 0.9
            mock_res.tokens_per_sec = 25.0
            mock_res.metadata = {}
            mock_solve.return_value = mock_res

            self.core.execute_task("explain photosynthesis")
            call_kwargs = mock_solve.call_args[1]
            self.assertIn("system_prompt", call_kwargs)
            self.assertIn("Brain", call_kwargs["system_prompt"])
            self.assertIn("Linux Mint", call_kwargs["system_prompt"])

    def test_compound_browser_and_website_routing(self):
        """Verify compound browser actions route directly to multi-step navigation plan."""
        routed = default_router.route("open brave and open wikipedia")
        self.assertIsNotNone(routed)
        self.assertEqual(routed.get("type"), "plan")
        tools = [s.tool_name for s in routed["plan"].steps if s.tool_name]
        self.assertEqual(tools, ["OPEN_APP", "FOCUS_APP", "BROWSER_NAVIGATE"])
        nav_step = [s for s in routed["plan"].steps if s.tool_name == "BROWSER_NAVIGATE"][0]
        self.assertIn("wikipedia.org", nav_step.arguments.get("url", ""))

    def test_universal_compound_goal_decomposition(self):
        """Verify universal action decomposer handles multi-action compound goals."""
        from core.cognition import default_cognition
        plan = default_cognition.plan_autonomous_goal("turn off wifi and turn off bluetooth")
        self.assertIsNotNone(plan)
        tools = [s.tool_name for s in plan.steps if s.tool_name]
        self.assertIn("WIFI_OFF", tools)
        self.assertIn("BLUETOOTH_OFF", tools)


if __name__ == "__main__":
    unittest.main()
