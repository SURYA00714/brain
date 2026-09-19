"""
Targeted Unit Tests for Stage 8 — General Browser + GUI Task Agent Architecture.
Mocks all Playwright, mouse, keyboard, vision, download, and external actions.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from models.needle_router import Needle2Router, ToolRouter
from tools.browser import PlaywrightBrowserProvider, BrowserCapability, browser_download
from tools.vision import VisionProvider, RemoteGUIVisionProvider, UnavailableVisionProvider
from core.recovery import AdaptiveRecoveryManager
from tools.registry import ToolRegistry, Tool


class TestNeedleRouter(unittest.TestCase):
    def setUp(self):
        self.needle_patch = patch.dict('sys.modules', {'needle': None})
        self.needle_patch.start()
        
    def tearDown(self):
        self.needle_patch.stop()
    def test_needle_router_registration_and_structured_output(self):
        mock_gateway = MagicMock()
        mock_gateway.generate.return_value = MagicMock(
            success=True,
            text='{"tool": "OPEN_APP", "arguments": {"app_name": "brave"}, "confidence": 0.95}'
        )
        router = Needle2Router(gateway=mock_gateway)
        res = router.route_tool("Open Brave browser", [{"name": "OPEN_APP", "description": "Open app", "parameters": {}}])
        self.assertTrue(res["success"])
        self.assertEqual(res["tool"], "OPEN_APP")
        self.assertEqual(res["arguments"], {"app_name": "brave"})
        self.assertGreaterEqual(res["confidence"], 0.9)

    def test_malformed_needle_output_handling(self):
        mock_gateway = MagicMock()
        mock_gateway.generate.return_value = MagicMock(success=True, text='NOT_VALID_JSON')
        router = Needle2Router(gateway=mock_gateway)
        res = router.route_tool("Open Brave", [{"name": "OPEN_APP", "description": "Open app", "parameters": {}}])
        self.assertFalse(res["success"])
        self.assertIn("error", res)

    def test_low_confidence_needle_fallback(self):
        mock_gateway = MagicMock()
        mock_gateway.generate.return_value = MagicMock(
            success=True,
            text='{"tool": "OPEN_APP", "arguments": {"app_name": "brave"}, "confidence": 0.3}'
        )
        needle = Needle2Router(gateway=mock_gateway, min_confidence=0.6)
        router = ToolRouter(needle_router=needle)
        res = router.route_tool("Open Brave", [{"name": "OPEN_APP", "description": "Open app", "parameters": {}}])
        self.assertTrue(res["success"])
        self.assertEqual(res["provider"], "structured_fallback_heuristic")


class TestBrowserAndDownloadEngine(unittest.TestCase):
    def test_browser_download_mock(self):
        with patch("tools.browser.os.path.exists", return_value=True), \
             patch("tools.browser.os.path.getsize", return_value=1024):
            provider = PlaywrightBrowserProvider()
            mock_pw = MagicMock()
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_download = MagicMock()
            mock_download.value.suggested_filename = "test_trailer.mp4"
            mock_page.expect_download.return_value.__enter__.return_value = mock_download
            mock_browser.new_page.return_value = mock_page
            mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser

            with patch("tools.browser.sync_playwright", mock_pw):
                res = provider.download("https://example.com/trailer.mp4")
                self.assertTrue(res["success"])
                self.assertEqual(res["filename"], "test_trailer.mp4")
                self.assertTrue(res["verified"])


class TestGUIVisionProvider(unittest.TestCase):
    def test_vision_provider_fallback(self):
        provider = VisionProvider(active_provider=UnavailableVisionProvider())
        obs = provider.analyze_screen()
        self.assertTrue(obs["success"])
        self.assertEqual(obs["status"], "VISION_NOT_AVAILABLE")
        self.assertEqual(obs["elements"], [])

    def test_remote_gui_vision_provider_unconfigured(self):
        mock_gw = MagicMock()
        mock_gw.generate.return_value = MagicMock(success=False, text="", error="API Key missing")
        remote_prov = RemoteGUIVisionProvider(gateway=mock_gw)
        with patch("pathlib.Path.exists", return_value=True):
            obs = remote_prov.analyze_screen("/tmp/fake.png")
            self.assertTrue(obs["success"])
            self.assertEqual(obs["status"], "VISION_NOT_AVAILABLE")


class TestRecoveryEngine(unittest.TestCase):
    def test_recovery_engine_method_diversity(self):
        rec_mgr = AdaptiveRecoveryManager(max_recovery_attempts=5)
        goal_id = "test_goal_1"
        rec_mgr.record_attempted_method(goal_id, "CLICK_FIRST_RESULT")
        
        strat = rec_mgr.suggest_alternative_method("CLICK_FIRST_RESULT", goal_id=goal_id)
        self.assertEqual(strat["action"], "SWITCH_METHOD")
        self.assertEqual(strat["recommended_tool"], "BROWSER_NAVIGATE")

    def test_recovery_retry_budget_exhaustion(self):
        rec_mgr = AdaptiveRecoveryManager(max_recovery_attempts=2)
        res = rec_mgr.determine_recovery_strategy("CLICK", {}, "ACTION_FAILED", attempt=2)
        self.assertEqual(res["action"], "HALT")
        self.assertIn("maximum recovery attempts", res["message"])


if __name__ == "__main__":
    unittest.main()
