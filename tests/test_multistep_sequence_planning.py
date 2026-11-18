"""
Unit tests for Phase 2 Intelligence Upgrade: Multi-Step Sequence Planning & Verification.
Tests:
1. Sequential execution of compound requests without skipping steps.
2. Targeted in-site searches vs general browser searches ('open youtube and search gemini').
3. Multi-app launch sequencing ('open terminal and open text editor').
4. Hardware monitoring sequencing ('open the terminal and check system CPU usage').
"""

import os
import unittest
from unittest.mock import patch

os.environ["BRAIN_MOCK_GUI"] = "1"

from brain import run_planner_task
from tools.router import default_router


class TestMultiStepSequencePlanning(unittest.TestCase):

    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def test_open_terminal_and_check_cpu_usage(self):
        query = "open the terminal and check system CPU usage"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        self.assertEqual(tool_names, ["OPEN_APP", "CPU_STATUS"])

        ans = run_planner_task(query)
        self.assertIn("Opened terminal and checked system CPU usage", ans)

    def test_open_terminal_and_check_memory(self):
        query = "open terminal and check memory"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        self.assertEqual(tool_names, ["OPEN_APP", "MEMORY_STATUS"])

        ans = run_planner_task(query)
        self.assertIn("Opened terminal and checked system memory usage", ans)

    def test_open_two_apps_in_sequence(self):
        query = "open terminal and open text editor"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        self.assertEqual(tool_names, ["OPEN_APP", "OPEN_APP"])

        ans = run_planner_task(query)
        self.assertIn("Opened Terminal and Text_editor", ans)

    def test_open_youtube_and_search_gemini_targeted(self):
        query = "open youtube and search gemini"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        nav_steps = [s for s in plan.steps if s.tool_name == "BROWSER_NAVIGATE"]
        self.assertEqual(len(nav_steps), 1)
        self.assertEqual(nav_steps[0].arguments.get("url"), "https://www.youtube.com/results?search_query=gemini")

        ans = run_planner_task(query)
        self.assertIn("Opened Youtube and searched for 'gemini'", ans)


    def test_open_one_piece_in_reanime_routes_to_browser_search(self):
        query = "open one piece in reanime"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "tool")
        self.assertEqual(route_res.get("tool"), "BROWSER_SEARCH")
        self.assertEqual(route_res.get("arguments", {}).get("query"), "one piece reanime")


if __name__ == "__main__":
    unittest.main()
