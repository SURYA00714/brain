from models.gateway import ModelResponse
import unittest
import time
from unittest.mock import MagicMock, patch

from brain import determine_execution_mode, run_planner_task
from tools.profiler import PerformanceProfiler
from tools.router import FastRouter, default_router
from tools.apps import AppTracker, open_app, close_app, focus_app, APPROVED_APPS
from tools.browser import BrowserCapability, StructuredBrowserProvider, GUIFallbackBrowserProvider
from tools.registry import default_registry


class TestPhase9AdaptiveRuntimeAndLatency(unittest.TestCase):

    def setUp(self):
        AppTracker.get_instance().clear()

    def test_01_determine_execution_mode(self):
        self.assertEqual(determine_execution_mode("Open Brave and search Python"), "FOREGROUND")
        self.assertEqual(determine_execution_mode("In Brave look up news"), "FOREGROUND")
        self.assertEqual(determine_execution_mode("List files in my project"), "BACKGROUND")
        self.assertEqual(determine_execution_mode("Search web for Python 3.12"), "BACKGROUND")
        self.assertEqual(determine_execution_mode("What is quantum computing?"), "AUTO")

    def test_02_performance_profiler_telemetry(self):
        profiler = PerformanceProfiler()
        profiler.start()
        time.sleep(0.01)
        profiler.record_route("FAST_ROUTER", "OPEN_APP")
        profiler.record_llm(0.05)
        profiler.record_tool("OPEN_APP", 0.02)
        profiler.record_total()

        summary = profiler.log_summary("Open Brave", mode="AUTO", status="SUCCESS")
        self.assertEqual(summary["intent_route"], "FAST_ROUTER:Open Brave")
        self.assertGreaterEqual(summary["total_latency_ms"], 10.0)
        self.assertEqual(summary["llm_latency_ms"], 50.0)
        self.assertEqual(summary["tool_latency_ms"], 20.0)
        self.assertEqual(summary["mode"], "AUTO")
        self.assertEqual(summary["status"], "SUCCESS")

    def test_03_fast_router_intents(self):
        router = FastRouter()
        self.assertEqual(router.route("hello")["type"], "final")
        self.assertEqual(router.route("hi")["type"], "final")
        self.assertEqual(router.route("open brave")["tool"], "OPEN_APP")
        self.assertEqual(router.route("close brave")["tool"], "CLOSE_APP")
        self.assertEqual(router.route("list files")["tool"], "LIST_FILES")
        self.assertEqual(router.route("take a screenshot")["tool"], "SCREENSHOT")
        self.assertIsNone(router.route("Write a complex python script to parse CSV files"))

    def test_04_app_tracker_and_close_app(self):
        tracker = AppTracker.get_instance()
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.poll.return_value = None
        tracker.record_launch("brave", "brave-browser", mock_proc)

        self.assertTrue(tracker.is_running("brave"))
        self.assertEqual(len(tracker.list_tracked()), 1)

        # Test close_app on tracked process
        res = close_app("brave")
        self.assertIn("closed successfully", res)
        self.assertTrue(mock_proc.terminate.called or mock_proc.kill.called)
        self.assertFalse(tracker.is_running("brave"))

        # Test close_app on unapproved app
        res_unapproved = close_app("malware")
        self.assertIn("is not in the approved safety allowlist", res_unapproved)

        # Test close_app on approved app that is not running
        res_not_running = close_app("text_editor")
        self.assertIn("No active Brain-owned instance", res_not_running)

    def test_05_focus_app(self):
        res = focus_app("brave")
        self.assertIn("focus", res.lower())

        res_unapproved = focus_app("unapproved_app")
        self.assertIn("is not in the approved safety allowlist", res_unapproved)

    def test_06_browser_capability(self):
        # GUI fallback provider test
        gui_provider = GUIFallbackBrowserProvider()
        cap_gui = BrowserCapability(provider=gui_provider)
        res_search = cap_gui.search("Python 3.12")
        self.assertTrue(res_search["success"])
        self.assertEqual(res_search["provider"], "gui_fallback")

        res_nav = cap_gui.navigate("https://python.org")
        self.assertTrue(res_nav["success"])

        # Structured browser provider test
        struct_provider = StructuredBrowserProvider()
        cap_struct = BrowserCapability(provider=struct_provider)
        res_struct = cap_struct.search("Python 3.12")
        self.assertTrue(res_struct["success"])
        self.assertEqual(res_struct["provider"], "structured")

    def test_07_fast_route_execution_bypasses_llm(self):
        # Ensure requests.post is NOT called when FastRouter matches
        with patch("brain.default_gateway.generate") as mock_post:
            mock_post.side_effect = AssertionError("LLM API should NOT be called for fast-routed intent!")
            
            # Fast-routed hello
            ans_hello = run_planner_task("hello", quiet=True)
            self.assertIn("assist you today", ans_hello)

            # Fast-routed list files
            ans_list = run_planner_task("list files", quiet=True)
            self.assertIn("file results", ans_list)

    def test_08_registry_new_phase9_tools(self):
        self.assertIsNotNone(default_registry.get("CLOSE_APP"))
        self.assertIsNotNone(default_registry.get("FOCUS_APP"))
        self.assertIsNotNone(default_registry.get("BROWSER_SEARCH"))
        self.assertIsNotNone(default_registry.get("BROWSER_NAVIGATE"))

        # Test parameter alias mapping ('key' -> 'keys')
        res_alias = default_registry.execute("PRESS_KEY", {"key": "enter"})
        self.assertEqual(res_alias["tool"], "PRESS_KEY")


if __name__ == "__main__":
    unittest.main()
