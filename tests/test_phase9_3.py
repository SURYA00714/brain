import json
import unittest
from unittest.mock import MagicMock, patch

from brain import run_planner_task, parse_model_action
from tools.apps import default_app_tracker, open_app, close_app, focus_app
from tools.plan import ExecutionPlan, ExecutionStep
from tools.router import FastRouter, default_router
from tools.vision import default_vision
from tools.screen import analyze_captured_screen
from tools.input import validate_gui_action_safety, default_chain_tracker


class TestPhase93MultiStepAndAppLifecycle(unittest.TestCase):
    def setUp(self):
        default_app_tracker.clear()
        default_vision.clear_observation()
        default_chain_tracker.clear()

    def test_01_execution_plan_data_structures(self):
        plan = ExecutionPlan(goal="Test multi-step execution")
        plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "brave"}))
        plan.add_step(ExecutionStep(action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "brave"}))
        plan.add_step(ExecutionStep(action_type="final", answer="Brave opened and focused."))

        self.assertEqual(len(plan.steps), 3)
        self.assertEqual(plan.get_current_step().tool_name, "OPEN_APP")
        
        d = plan.to_dict()
        self.assertEqual(d["total_steps"], 3)
        self.assertEqual(d["goal"], "Test multi-step execution")

        reconstructed = ExecutionPlan.from_dict(d)
        self.assertIsNotNone(reconstructed)
        self.assertEqual(len(reconstructed.steps), 3)
        self.assertEqual(reconstructed.steps[0].tool_name, "OPEN_APP")

    def test_02_fast_router_compound_queries(self):
        router = FastRouter()

        # 1. Open Brave & Search
        match1 = router.route("Open Brave and search for Python programming language")
        self.assertIsNotNone(match1)
        self.assertEqual(match1.get("type"), "plan")
        plan1 = match1.get("plan")
        self.assertIsInstance(plan1, ExecutionPlan)
        self.assertTrue(any(s.tool_name == "BROWSER_SEARCH_FOREGROUND" for s in plan1.steps))

        # 2. Open Brave & Observe
        match2 = router.route("Open Brave and tell me what is on the screen")
        self.assertIsNotNone(match2)
        self.assertEqual(match2.get("type"), "plan")
        plan2 = match2.get("plan")
        self.assertEqual(plan2.steps[0].tool_name, "OPEN_APP")
        self.assertEqual(plan2.steps[1].tool_name, "FOCUS_APP")
        self.assertEqual(plan2.steps[2].tool_name, "ANALYZE_SCREEN")

        # 3. Open File Manager & open Brain folder
        match3 = router.route("Open File Manager and open my Brain folder")
        self.assertIsNotNone(match3)
        self.assertEqual(match3.get("type"), "plan")
        plan3 = match3.get("plan")
        self.assertEqual(plan3.steps[0].tool_name, "OPEN_APP")
        self.assertEqual(plan3.steps[2].tool_name, "LIST_FILES")

    def test_03_close_app_brain_owned_vs_user_owned(self):
        # Scenario A: Brain-owned process instance
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.poll.return_value = None
        default_app_tracker.record_launch("brave", "brave-browser", mock_proc)

        res_brain = close_app("brave")
        self.assertIn("closed successfully", res_brain)
        mock_proc.terminate.assert_called_once()

        # Scenario B: User-owned process (untracked by Brain, but window open)
        with patch("tools.apps.is_window_open", return_value=True):
            res_user = close_app("brave")
            self.assertIn("won't close it automatically", res_user)
            self.assertIn("was not launched by Brain", res_user)

    def test_04_observation_provenance_tracking(self):
        with patch("tools.apps.get_active_window_app_name", return_value="brave"):
            obs = analyze_captured_screen(force_refresh=True)
            self.assertIn("focused_application", obs)
            self.assertIn("source_application", obs)
            self.assertEqual(obs["focused_application"], "brave")
            self.assertEqual(obs["source_application"], "brave")

    @patch("tools.apps.open_app", return_value="Terminal is open.")
    def test_05_terminal_safety_gating(self, mock_open):
        default_chain_tracker.active_app_context = "terminal"

        # Dangerous command typing in terminal must be blocked
        is_safe, err = validate_gui_action_safety("TYPE_TEXT", {"text": "rm -rf /"})
        self.assertFalse(is_safe)
        self.assertIn("Safety Block", err)

        # Plan execution must halt cleanly without shortcut guessing
        plan = ExecutionPlan(goal="Dangerous test")
        plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "terminal"}))
        plan.add_step(ExecutionStep(action_type="tool", tool_name="TYPE_TEXT", arguments={"text": "rm -rf /"}))

        from brain import execute_plan
        from tools.profiler import PerformanceProfiler
        from tools.registry import default_registry
        res = execute_plan(plan, default_registry, PerformanceProfiler(), "Open terminal and type rm -rf /", quiet=True)
        self.assertIn("Safety Block", res)

    @patch("brain.requests.post")
    def test_06_single_pass_qwen_plan_parsing(self, mock_post):
        # Qwen returns a single multi-step plan JSON
        mock_plan_json = json.dumps({
            "type": "plan",
            "goal": "Research Python 3.12 features",
            "steps": [
                {"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "Python 3.12 features"}},
                {"type": "final", "answer": "Python 3.12 introduces improved error messages and per-interpreter GIL."}
            ]
        })
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": mock_plan_json}

        from tools.registry import ToolRegistry, Tool
        test_reg = ToolRegistry()
        test_reg.register(Tool("WEB_SEARCH", "Search", {}, "LOW", lambda query="": {"success": True, "data": "Python 3.12 details"}))

        res = run_planner_task("Research Python 3.12 features and tell me if I should upgrade", registry=test_reg, quiet=True)
        self.assertIn("Python 3.12", res)
        # Verify Qwen model was called ONLY ONCE for initial plan generation
        self.assertEqual(mock_post.call_count, 1)

    def test_07_bounded_recovery_state_based(self):
        plan = ExecutionPlan(goal="Test recovery")
        plan.add_step(ExecutionStep(action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "brave"}))
        
        self.assertEqual(plan.recovery_count, 0)
        self.assertEqual(plan.max_recovery_attempts, 2)


if __name__ == "__main__":
    unittest.main()
