import os
import unittest
from tools.input import (
    move_mouse, click_mouse, double_click, scroll, type_text,
    press_key, hotkey, right_click, get_screen_size, get_active_window,
    validate_coordinates, validate_gui_action_safety, screen_prompt_safety
)
from tools.screen import capture_screen, analyze_captured_screen, ocr_screen, capture_screen_region
from tools.router import FastRouter
from tools.registry import default_registry

class TestInputAndScreen(unittest.TestCase):
    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def test_input_validation(self):
        # Coordinates validation
        cx, cy, err = validate_coordinates(500, 500)
        self.assertIsNone(err)
        self.assertEqual(cx, 500)

        cx_bad, cy_bad, err_bad = validate_coordinates(-10, 500)
        self.assertIsNotNone(err_bad)

        # Key validation
        pk = press_key("enter")
        self.assertIsInstance(pk, dict)

        pk_bad = press_key("invalid_key_name_foo")
        self.assertTrue(isinstance(pk_bad, str) and pk_bad.startswith("Error:"))

        # Hotkey validation
        hk = hotkey(["ctrl", "c"])
        self.assertIsInstance(hk, dict)

        # Max text length check
        long_txt = "a" * 2500
        tt_bad = type_text(long_txt)
        self.assertTrue(isinstance(tt_bad, str) and tt_bad.startswith("Error:"))

    def test_screen_control_and_observation(self):
        sc_size = get_screen_size()
        self.assertTrue(sc_size["success"])
        self.assertEqual(sc_size["tool"], "SCREEN_SIZE")

        act_win = get_active_window()
        self.assertTrue(act_win["success"])
        self.assertEqual(act_win["tool"], "ACTIVE_WINDOW")

        ocr_res = ocr_screen()
        self.assertTrue(ocr_res["success"])
        self.assertEqual(ocr_res["tool"], "OCR_SCREEN")

        region_res = capture_screen_region(0, 0, 400, 300)
        self.assertTrue(region_res["success"])

    def test_gui_action_safety(self):
        # Autonomous typing of rm -rf / must be blocked
        is_safe, err = validate_gui_action_safety("TYPE_TEXT", {"text": "rm -rf /"})
        self.assertFalse(is_safe)
        self.assertIn("Safety Block", err)

        # Prompt safety for destructive user requests
        is_safe_p, err_p = screen_prompt_safety("delete all my files and format drive")
        self.assertFalse(is_safe_p)
        self.assertIn("Safety Block", err_p)

    def test_registry_integration(self):
        registered_tools = [t["name"] for t in default_registry.list_tools()]
        expected = [
            "MOVE_MOUSE", "CLICK", "RIGHT_CLICK", "DOUBLE_CLICK", "SCROLL",
            "TYPE_TEXT", "PRESS_KEY", "HOTKEY", "SCREENSHOT", "SCREEN_SIZE",
            "ACTIVE_WINDOW", "OCR_SCREEN", "SCREEN_REGION"
        ]
        for t in expected:
            self.assertIn(t, registered_tools, f"Tool {t} not found in ToolRegistry.")

    def test_fast_router_zero_llm(self):
        router = FastRouter()
        queries = [
            ("screen size", "SCREEN_SIZE"),
            ("ocr screen", "OCR_SCREEN"),
            ("active window", "ACTIVE_WINDOW"),
            ("screenshot", "SCREENSHOT")
        ]
        for text, expected_tool in queries:
            res = router.route(text)
            self.assertIsNotNone(res, f"Failed to route: {text}")
            self.assertEqual(res.get("type"), "tool")
            self.assertEqual(res.get("tool"), expected_tool)

if __name__ == "__main__":
    unittest.main()
