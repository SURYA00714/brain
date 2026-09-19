import unittest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path

from tools.input import (
    validate_coordinates,
    validate_gui_action_safety,
    move_mouse,
    click_mouse,
    double_click,
    scroll,
    type_text,
    press_key,
    hotkey,
    VALID_KEYS,
    MAX_TEXT_LENGTH
)
from tools.screen import capture_screen, VisionProvider
from tools.registry import ToolRegistry, Tool, default_registry
from brain import parse_model_action, run_planner_task


def make_mock_response(text):
    from models.gateway import ModelResponse
    return ModelResponse(text=text, model="mock", provider="mock", success=True)


class TestComputerInteraction(unittest.TestCase):

    def setUp(self):
        # Reset default_vision state for test environment
        from tools.vision import default_vision, UnavailableVisionProvider
        default_vision.set_provider(UnavailableVisionProvider())
        default_vision.clear_observation()

        # Create an isolated test registry with mock execution functions for planner tests
        self.test_registry = ToolRegistry()
        self.mock_screen = MagicMock(return_value={"image_path": "/tmp/screen.png", "width": 1920, "height": 1080})
        self.mock_type = MagicMock(return_value={"typed_chars": 15})
        self.mock_press = MagicMock(return_value={"key": "enter"})
        self.mock_app = MagicMock(return_value="Brave opened successfully.")

        self.test_registry.register(Tool("SCREENSHOT", "Capture screen", {}, "LOW", self.mock_screen))
        self.test_registry.register(Tool("TYPE_TEXT", "Type text", {}, "MEDIUM", self.mock_type))
        self.test_registry.register(Tool("PRESS_KEY", "Press key", {}, "MEDIUM", self.mock_press))
        self.test_registry.register(Tool("OPEN_APP", "Open app", {}, "MEDIUM", self.mock_app))

    # 1. SCREENSHOT registration test
    def test_screenshot_registered(self):
        tool = default_registry.get("SCREENSHOT")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.risk_level, "LOW")

    # 2. SCREENSHOT failure handling test
    @patch("tools.screen.HAS_MSS", False)
    @patch("tools.screen.HAS_PYAUTOGUI", False)
    def test_screenshot_failure_handling(self):
        with patch.dict("os.environ", {"BRAIN_MOCK_GUI": "0"}):
            res = capture_screen()
            is_err_str = isinstance(res, str) and res.startswith("Error:")
            is_err_dict = isinstance(res, dict) and not res.get("success") and "error" in res
            self.assertTrue(is_err_str or is_err_dict)

    # 3. Coordinate validation tests
    def test_coordinate_validation_valid(self):
        x, y, err = validate_coordinates(500, 300)
        self.assertIsNone(err)
        self.assertEqual(x, 500)
        self.assertEqual(y, 300)

    # 4. Invalid out-of-bounds coordinates rejected test
    def test_coordinate_validation_out_of_bounds(self):
        x, y, err = validate_coordinates(-50, 300)
        self.assertIsNone(x)
        self.assertIn("outside screen bounds", err)

        x, y, err = validate_coordinates(99999, 99999)
        self.assertIsNone(x)
        self.assertIn("outside screen bounds", err)

    # 5. CLICK parameter validation test
    @patch("tools.input.HAS_PYAUTOGUI", True)
    @patch("tools.input.pyautogui", create=True)
    def test_click_parameter_validation(self, mock_pyautogui):
        res = click_mouse(100, 200, button="left")
        self.assertIsInstance(res, dict)
        self.assertEqual(res["x"], 100)
        mock_pyautogui.click.assert_called_once_with(100, 200, button="left")

        err = click_mouse(100, 200, button="invalid_button")
        self.assertTrue(isinstance(err, str) and err.startswith("Error:"))

    # 6. DOUBLE_CLICK validation test
    @patch("tools.input.HAS_PYAUTOGUI", True)
    @patch("tools.input.pyautogui", create=True)
    def test_double_click_validation(self, mock_pyautogui):
        res = double_click(100, 200)
        self.assertIsInstance(res, dict)
        mock_pyautogui.doubleClick.assert_called_once_with(100, 200)

    # 7. SCROLL bounds validation test
    @patch("tools.input.HAS_PYAUTOGUI", True)
    @patch("tools.input.pyautogui", create=True)
    def test_scroll_bounds(self, mock_pyautogui):
        res = scroll(500)
        self.assertEqual(res["amount"], 500)
        mock_pyautogui.scroll.assert_called_once_with(500)

        # Test capping scroll amount at MAX_SCROLL_AMOUNT (1000)
        res_large = scroll(5000)
        self.assertEqual(res_large["amount"], 1000)

    # 8. TYPE_TEXT length limit test (>2000 chars rejected)
    def test_type_text_length_limit(self):
        oversized = "a" * (MAX_TEXT_LENGTH + 10)
        res = type_text(oversized)
        self.assertIn("exceeds maximum limit", res)

    # 9. Invalid key rejected test
    def test_invalid_key_rejected(self):
        res = press_key("invalid_key_123")
        self.assertIn("not in the validated key allowlist", res)

    # 10. Invalid hotkey rejected test
    def test_invalid_hotkey_rejected(self):
        res = hotkey(["ctrl", "invalid_key"])
        self.assertIn("not in the validated key allowlist", res)

    # 11. Unknown GUI tool rejected test
    def test_unknown_gui_tool_rejected(self):
        res = default_registry.execute("UNKNOWN_GUI_TOOL", {})
        self.assertFalse(res["success"])
        self.assertIn("not registered", res["error"])

    # 12. Planner can request SCREENSHOT test
    @patch("brain.default_gateway.generate")
    def test_planner_screenshot_request(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "SCREENSHOT", "arguments": {}}'),
            make_mock_response('{"type": "final", "answer": "Screenshot captured."}')
        ]

        res = run_planner_task("take a screenshot", registry=self.test_registry, quiet=True)
        self.assertTrue(res == "Screenshot captured." or res.startswith("Screenshot captured") or res.startswith("Screen captured"))
        self.mock_screen.assert_called_once()

    # 13. Planner can request TYPE_TEXT test
    @patch("brain.default_gateway.generate")
    def test_planner_type_text_request(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "TYPE_TEXT", "arguments": {"text": "Python tutorials"}}'),
            make_mock_response('{"type": "final", "answer": "Typed text."}')
        ]

        res = run_planner_task("type Python tutorials", registry=self.test_registry, quiet=True)
        self.assertEqual(res, "Typed text.")

    # 14. Planner can request PRESS_KEY test
    @patch("brain.default_gateway.generate")
    def test_planner_press_key_request(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "PRESS_KEY", "arguments": {"key": "enter"}}'),
            make_mock_response('{"type": "final", "answer": "Pressed enter."}')
        ]

        res = run_planner_task("press enter", registry=self.test_registry, quiet=True)
        self.assertEqual(res, "Pressed enter.")

    # 15. Multi-step sequence test (OPEN_APP -> SCREENSHOT -> TYPE_TEXT -> PRESS_KEY -> SCREENSHOT -> final)
    @patch("brain.default_gateway.generate")
    def test_planner_multistep_sequence(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "OPEN_APP", "arguments": {"app_name": "brave"}}'),
            make_mock_response('{"type": "tool", "tool": "SCREENSHOT", "arguments": {}}'),
            make_mock_response('{"type": "tool", "tool": "TYPE_TEXT", "arguments": {"text": "Python tutorials"}}'),
            make_mock_response('{"type": "tool", "tool": "PRESS_KEY", "arguments": {"key": "enter"}}'),
            make_mock_response('{"type": "tool", "tool": "SCREENSHOT", "arguments": {}}'),
            make_mock_response('{"type": "final", "answer": "Sequence complete."}')
        ]

        res = run_planner_task("open brave and search python tutorials", registry=self.test_registry, quiet=True)
        self.assertEqual(res, "Sequence complete.")
        self.mock_app.assert_called_once_with("brave")
        self.assertEqual(self.mock_screen.call_count, 2)
        self.mock_type.assert_called_once_with("Python tutorials")
        self.mock_press.assert_called_once_with("enter")

    # 25. Dangerous terminal workflow blocked / confirmation-gated test
    def test_dangerous_terminal_typing_blocked(self):
        safe, err = validate_gui_action_safety("TYPE_TEXT", {"text": "sudo rm -rf /"})
        self.assertFalse(safe)
        self.assertIn("Safety Block", err)

        res = type_text("sudo rm -rf /")
        self.assertIn("Safety Block", res)


if __name__ == "__main__":
    unittest.main()
