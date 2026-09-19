import unittest
from unittest.mock import MagicMock, patch

from brain import determine_execution_mode, run_planner_task
from tools.router import FastRouter
from tools.apps import AppTracker, open_app, close_app, focus_app, default_app_tracker


class TestPhase91RoutingAndAppOwnership(unittest.TestCase):

    def setUp(self):
        default_app_tracker.clear()
        self.router = FastRouter()

    def test_01_fast_router_eligible_deterministic_commands(self):
        """Commands that MUST be eligible for FastRouter dispatch (<2ms)."""
        self.assertIsNotNone(self.router.route("hello"))
        self.assertIsNotNone(self.router.route("hi"))
        self.assertEqual(self.router.route("open brave")["tool"], "OPEN_APP")
        self.assertEqual(self.router.route("close brave")["tool"], "CLOSE_APP")
        self.assertEqual(self.router.route("focus brave")["tool"], "FOCUS_APP")
        self.assertEqual(self.router.route("open file manager")["tool"], "OPEN_APP")
        self.assertEqual(self.router.route("list files in brain")["tool"], "LIST_FILES")
        self.assertEqual(self.router.route("take a screenshot")["tool"], "SCREENSHOT")

    def test_02_fast_router_semantic_boundary_rejections(self):
        """Queries requiring semantic reasoning, decision-making, or open-ended synthesis MUST NOT bypass the LLM."""
        open_ended_queries = [
            "Can you open the browser and find something useful about Python?",
            "Research Python 3.12 and tell me whether I should upgrade.",
            "Find the best way to learn Python.",
            "Look into my project and tell me what needs improvement.",
            "Search for Python and summarize the important results.",
            "Do whatever is necessary to solve this problem."
        ]
        for query in open_ended_queries:
            routed = self.router.route(query)
            self.assertIsNone(routed, f"Query '{query}' incorrectly bypassed the LLM!")

    def test_03_app_tracker_scenario_a_brain_launches_and_closes(self):
        """Scenario A: Brain launches process -> Brain closes only that process handle."""
        mock_proc = MagicMock()
        mock_proc.pid = 1001
        mock_proc.poll.return_value = None

        default_app_tracker.record_launch("brave", "brave-browser", mock_proc)
        self.assertTrue(default_app_tracker.is_running("brave"))

        res = close_app("brave")
        self.assertIn("closed successfully", res)
        mock_proc.terminate.assert_called_once()
        self.assertFalse(default_app_tracker.is_running("brave"))

    def test_04_app_tracker_scenario_b_user_launched_untracked_app(self):
        """Scenario B: User launches app independently -> Brain does not claim ownership or kill it."""
        # AppTracker has zero recorded processes
        res = close_app("brave")
        self.assertIn("No active Brain-owned instance", res)

    def test_05_app_tracker_scenario_c_crashed_stale_process(self):
        """Scenario C: Brain launches process -> process exits/crashes -> tracker cleans stale state."""
        mock_proc = MagicMock()
        mock_proc.pid = 1002
        mock_proc.poll.return_value = 1  # Already exited/crashed

        default_app_tracker.record_launch("brave", "brave-browser", mock_proc)
        self.assertFalse(default_app_tracker.is_running("brave"))

        res = close_app("brave")
        self.assertIn("already closed or not running", res)

    def test_06_app_tracker_scenario_d_multiple_brain_processes(self):
        """Scenario D: Multiple Brain-launched processes exist -> close terminates each deterministically."""
        proc1 = MagicMock(pid=1003)
        proc1.poll.return_value = None
        proc2 = MagicMock(pid=1004)
        proc2.poll.return_value = None

        default_app_tracker.record_launch("brave", "brave-browser", proc1)
        default_app_tracker.record_launch("brave", "brave-browser", proc2)
        self.assertEqual(len(default_app_tracker.list_tracked()), 1)

        res = close_app("brave")
        self.assertIn("2 Brain-owned process instance(s) terminated", res)
        proc1.terminate.assert_called_once()
        proc2.terminate.assert_called_once()

    def test_07_execution_modes(self):
        """Verify AUTO / FOREGROUND / BACKGROUND mode determination."""
        self.assertEqual(determine_execution_mode("Search the web for Python 3.12."), "BACKGROUND")
        self.assertEqual(determine_execution_mode("Open Brave and search for Python 3.12."), "FOREGROUND")
        self.assertEqual(determine_execution_mode("In Brave look up docs"), "FOREGROUND")
        self.assertEqual(determine_execution_mode("Search for Python 3.12 without opening the browser."), "BACKGROUND")
        self.assertEqual(determine_execution_mode("What is the capital of France?"), "AUTO")


if __name__ == "__main__":
    unittest.main()
