import os
import unittest
from tools.window_manager import (
    list_windows, focus_window, minimize_window, maximize_window,
    restore_window, close_window, move_window, resize_window
)
from tools.router import FastRouter
from tools.registry import default_registry

class TestWindowManager(unittest.TestCase):
    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def test_list_windows(self):
        res = list_windows()
        self.assertTrue(res["success"])
        self.assertEqual(res["tool"], "LIST_WINDOWS")
        self.assertGreater(res["count"], 0)
        self.assertIn("data", res)

    def test_window_focus_minimize_maximize_restore(self):
        f = focus_window("Brave")
        self.assertTrue(f["success"])
        self.assertEqual(f["tool"], "FOCUS_WINDOW")

        m = minimize_window("Terminal")
        self.assertTrue(m["success"])
        self.assertEqual(m["tool"], "MINIMIZE_WINDOW")

        mx = maximize_window("Calculator")
        self.assertTrue(mx["success"])
        self.assertEqual(mx["tool"], "MAXIMIZE_WINDOW")

        r = restore_window("Calculator")
        self.assertTrue(r["success"])
        self.assertEqual(r["tool"], "RESTORE_WINDOW")

    def test_move_and_resize_window(self):
        mv = move_window("Brave", 100, 200)
        self.assertTrue(mv["success"])

        # Test invalid coordinates
        mv_bad = move_window("Brave", -10, 200)
        self.assertFalse(mv_bad["success"])

        rs = resize_window("Brave", 1024, 768)
        self.assertTrue(rs["success"])

        # Test invalid dimensions
        rs_bad = resize_window("Brave", 10, 50)
        self.assertFalse(rs_bad["success"])

    def test_close_window_confirmation(self):
        # Confirmed
        cl = close_window("Calculator", confirmed=True)
        self.assertTrue(cl["success"])

    def test_registry_integration(self):
        registered_tools = [t["name"] for t in default_registry.list_tools()]
        expected = [
            "LIST_WINDOWS", "FOCUS_WINDOW", "MINIMIZE_WINDOW",
            "MAXIMIZE_WINDOW", "RESTORE_WINDOW", "CLOSE_WINDOW",
            "MOVE_WINDOW", "RESIZE_WINDOW"
        ]
        for t in expected:
            self.assertIn(t, registered_tools, f"Tool {t} not found in ToolRegistry.")

    def test_fast_router_zero_llm(self):
        router = FastRouter()
        queries = [
            ("list windows", "LIST_WINDOWS"),
            ("maximize Brave", "MAXIMIZE_WINDOW"),
            ("minimize Terminal", "MINIMIZE_WINDOW"),
            ("restore Calculator", "RESTORE_WINDOW")
        ]
        for text, expected_tool in queries:
            res = router.route(text)
            self.assertIsNotNone(res, f"Failed to route: {text}")
            self.assertEqual(res.get("type"), "tool")
            self.assertEqual(res.get("tool"), expected_tool)

if __name__ == "__main__":
    unittest.main()
