import unittest
import os
from unittest.mock import patch
import time
from tools.time_tool import get_current_time
from tools.router import FastRouter, default_router
from tools.registry import default_registry
from tools.screen import capture_screen, analyze_captured_screen
from tools.vision import default_vision, UnavailableVisionProvider
from tools.apps import AppTracker, open_app, close_app
from brain import run_planner_task


class TestPhase92RuntimeFixes(unittest.TestCase):

    def setUp(self):
        default_vision.clear_observation()

    def test_01_time_capability_format(self):
        res = get_current_time()
        self.assertTrue(res.startswith("It is "))
        self.assertTrue(" AM" in res or " PM" in res)

    def test_02_fast_router_time_queries(self):
        router = FastRouter()
        queries = [
            "tell me the time",
            "what time is it", "what time is it?",
            "what's the current time",
            "current time",
            "time please"
        ]
        for q in queries:
            match = router.route(q)
            self.assertIsNotNone(match, f"Query '{q}' should be matched by FastRouter.")
            self.assertEqual(match.get("type"), "tool")
            self.assertEqual(match.get("tool"), "TIME")

    def test_03_time_tool_execution(self):
        resp = run_planner_task("Tell me the time.", quiet=True)
        self.assertTrue(resp.startswith("It is "))

    def test_04_screenshot_no_ocr(self):
        res = capture_screen()
        self.assertTrue(isinstance(res, (dict, str)))
        if isinstance(res, dict):
            self.assertIn("image_path", res)
            self.assertNotIn("elements", res)

    def test_05_analyze_screen_returns_elements(self):
        res = analyze_captured_screen(force_refresh=True)
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("tool"), "ANALYZE_SCREEN")
        self.assertIn("elements", res)
        self.assertIn("status", res)

    def test_06_observation_caching_and_reuse(self):
        obs1 = analyze_captured_screen(force_refresh=True)
        t1 = obs1.get("timestamp")
        
        # Second call without force_refresh should return cached observation (same timestamp)
        obs2 = analyze_captured_screen(force_refresh=False)
        self.assertEqual(obs2.get("timestamp"), t1)

    def test_07_fast_router_app_response_formatting(self):
        with patch.dict(os.environ, {"BRAIN_MOCK_GUI": "1"}):
            resp_open = run_planner_task("Open Brave", quiet=True)
            self.assertIn("Brave is open", resp_open)

            resp_close = run_planner_task("Close Brave", quiet=True)
            self.assertIn("Brave has been closed", resp_close)

    def test_08_semantic_queries_still_bypass_fast_router(self):
        router = FastRouter()
        q = "Research Python 3.12 and tell me whether I should upgrade."
        self.assertIsNone(router.route(q))

        q2 = "Find the best way to learn Python."
        self.assertIsNone(router.route(q2))


if __name__ == "__main__":
    unittest.main()
