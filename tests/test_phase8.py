from models.gateway import ModelResponse
import unittest
from unittest.mock import MagicMock, patch

from brain import TaskState, run_planner_task, MAX_RECOVERY_ATTEMPTS
from tools.registry import ToolRegistry, Tool
from tools.vision import default_vision, UnavailableVisionProvider


class TestPhase8StateAndRecovery(unittest.TestCase):

    def setUp(self):
        default_vision.clear_observation()
        self.test_registry = ToolRegistry()
        self.test_registry.register(Tool("WEB_SEARCH", "Web search", {"query": "str"}, "LOW", lambda query: f"Results for {query}"))
        self.test_registry.register(Tool("LIST_FILES", "List files", {"target_path": "str"}, "LOW", lambda target_path="Brain": "File list"))

    def test_01_task_state_initialization_and_transitions(self):
        state = TaskState("Open Brave")
        self.assertEqual(state.task_status, "PLANNING")
        self.assertEqual(state.verification_status, "UNVERIFIED")

        state.update_action({"type": "tool", "tool": "OPEN_APP", "arguments": {"app_name": "brave"}})
        self.assertEqual(state.task_status, "ACTING")
        self.assertEqual(state.step_count, 1)

        state.update_result({"success": True, "data": "Opened"}, verification_status="VERIFIED")
        self.assertEqual(state.task_status, "VERIFYING")
        self.assertEqual(state.verification_status, "VERIFIED")
        self.assertEqual(len(state.completed_steps), 1)

    def test_02_task_state_failure_and_recovery_counter(self):
        state = TaskState("Failing task")
        state.update_action({"type": "tool", "tool": "CLICK_ELEMENT", "arguments": {"element_id": "missing"}})
        state.update_result({"success": False, "error": "Element missing"}, verification_status="UNVERIFIED")

        self.assertEqual(state.task_status, "RECOVERING")
        self.assertEqual(state.recovery_attempts, 1)

    def test_03_bounded_recovery_attempts_exceeded(self):
        reg = ToolRegistry()
        attempt_counter = [0]
        def mock_tool_func(attempt=0):
            return {"success": False, "error": f"Error on attempt {attempt}"}

        reg.register(Tool("FAIL_TOOL", "Failing tool", {"attempt": "int"}, "LOW", mock_tool_func))

        def mock_post_impl(*args, **kwargs):
            attempt_counter[0] += 1
            return ModelResponse(model="mock", provider="mock", success=True, text=f'{{"type": "tool", "tool": "FAIL_TOOL", "arguments": {{"attempt": {attempt_counter[0]}}}}}')

        with patch("brain.default_gateway.generate", side_effect=mock_post_impl):
            ans = run_planner_task("Run failing tool", registry=reg, quiet=True)
            self.assertIn("failed after 3 recovery attempts", ans)

    def test_04_progress_loop_detection_halts_execution(self):
        reg = ToolRegistry()
        reg.register(Tool("NO_OP_FAIL", "No op tool", {}, "LOW", lambda: {"success": False, "error": "Failed"}))

        with patch("brain.default_gateway.generate") as mock_post:
            mock_post.side_effect = [
                ModelResponse(model="mock", provider="mock", success=True, text='{"type": "tool", "tool": "NO_OP_FAIL", "arguments": {}}'),
                ModelResponse(model="mock", provider="mock", success=True, text='{"type": "tool", "tool": "NO_OP_FAIL", "arguments": {}}'),
                ModelResponse(model="mock", provider="mock", success=True, text='{"type": "tool", "tool": "NO_OP_FAIL", "arguments": {}}'),
            ]
            ans = run_planner_task("Perform goal", registry=reg, max_steps=5, quiet=True)
            self.assertIn("Brain Error", ans)


if __name__ == "__main__":
    unittest.main()
