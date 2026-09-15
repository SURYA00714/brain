import unittest
from tools.search import perform_web_search_structured, perform_web_search
from tools.browser import default_browser_capability, PlaywrightBrowserProvider, StructuredBrowserProvider
from tools.apps import AppTracker, open_app, close_app
from tools.vision import default_vision
from brain import BrainController, default_registry


class TestPhase94Consolidation(unittest.TestCase):
    def setUp(self):
        self.app_tracker = AppTracker()

    def test_structured_web_search_contract(self):
        res = perform_web_search_structured("Python programming language", max_results=2)
        self.assertIsInstance(res, dict)
        self.assertIn("success", res)
        self.assertIn("query", res)
        self.assertIn("results", res)
        self.assertIn("provider", res)
        self.assertIn("status", res)
        if res["success"]:
            self.assertGreaterEqual(len(res["results"]), 1)
            first = res["results"][0]
            self.assertIn("title", first)
            self.assertIn("url", first)
            self.assertIn("snippet", first)

    def test_perform_web_search_string_format(self):
        res = perform_web_search("Python 3.12 features", max_results=2)
        self.assertIsInstance(res, str)
        self.assertFalse(res.startswith("Error:"))

    def test_browser_capability_structured_search(self):
        res = default_browser_capability.search("Python programming language")
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("success"))
        self.assertIn("results", res)

    def test_app_lifecycle_ownership(self):
        # Register a fake user-owned app
        self.app_tracker.register_app("Brave", pid=9999, brain_owned=False)
        self.assertFalse(self.app_tracker.is_brain_owned("Brave"))
        # Attempting to close non-Brain-owned app returns explicit notice
        res = self.app_tracker.close_app("Brave")
        self.assertTrue(res.get("success"))
        self.assertIn("Notice", res.get("message", ""))

    def test_terminal_safety_gating(self):
        from brain import run_planner_task
        res = run_planner_task("Open terminal and type rm -rf /", quiet=True)
        self.assertIn("Safety Block", str(res))

    def test_observation_provenance_keys(self):
        obs = default_vision.get_current_observation()
        if not obs:
            from tools.screen import analyze_captured_screen
            obs = analyze_captured_screen(force_refresh=True)
        self.assertIsInstance(obs, dict)
        self.assertIn("focused_application", obs)
        self.assertIn("source_application", obs)


if __name__ == "__main__":
    unittest.main()
